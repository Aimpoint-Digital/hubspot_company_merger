import requests
import os
import csv
import json
import dotenv
from datetime import datetime
import logging
from validate_csv import ValidateCSV

class HubspotAPI():
    def __init__(self, base_path="", test=False, api_key=None, input_file_path="../input_data.csv"):
        self.base_path = base_path
        self.input_data_file = input_file_path
        self.test = test
        if api_key:
            self.access_token = api_key
        else:
            if self.test:
                env_file = "env_test.env"
            else:
                env_file = "env_prod.env"
            dotenv.load_dotenv(env_file)
            self.access_token = os.getenv("HUBSPOT_ACCESS_TOKEN")
        self.headers = {
            "Authorization": f"Bearer {self.access_token}",
            "Content-Type": "application/json"
        }
        self.associations_code_map = {
            "parent_to_child": 13,
            "child_to_parent": 14
        }

    def load_and_group_data(self):
        with open(self.input_data_file, mode='r', encoding='utf-8') as file:
            csv_reader = csv.DictReader(file)
            data = list(csv_reader)
        try:
            ValidateCSV(data)
        except ValueError as e:
            error_message = f"Validation error: {e}"
            logging.error(error_message)
            raise Exception(error_message)
            
        grouped_data = {}
        for row in data:
            key = row['key']
            if key not in grouped_data:
                grouped_data[key] = []
            grouped_data[key].append(row)

        return grouped_data
    
    def write_to_json(self, data, output_path):
        with open(output_path, 'w', encoding='utf-8') as file:
            json.dump(data, file, indent=2)

        
    def check_company_exists(self, company_id):
        url = f"https://api.hubapi.com/crm/v3/objects/companies/{company_id}"
        response = requests.get(url, headers=self.headers)
        if response.status_code == 200 and company_id == response.json()["id"]:
            return True
        else:
            error_message = f"Error fetching company with id {company_id}. Status code: {response.status_code}"
            logging.error(error_message)
            return False

    def get_child_parent_companies(self, company_id, child_or_parent):
        url = f"https://api.hubapi.com/crm-associations/v1/associations/{company_id}/HUBSPOT_DEFINED/{self.associations_code_map[child_or_parent]}"
        response = requests.get(url, headers=self.headers)
        if response.status_code != 200:
            error_message = f"Error fetching {child_or_parent} companies: {response.status_code}"
            logging.error(error_message)
            raise Exception(error_message)
        return response.json()

    def enrich_companies(self, current_key_data):
        self.companies_with_child_parent = []
        for company in current_key_data:
            company_id = company["id"]
            company_enriched = {
                "id": company_id,
                "company_name": company["company_name"],
                "key": company["key"],
                "action": company["action"],
                "child_companies": self.get_child_parent_companies(company_id, "parent_to_child").get("results", []),
                "parent_companies": self.get_child_parent_companies(company_id, "child_to_parent").get("results", [])
            }
            self.companies_with_child_parent.append(company_enriched)
        return self.companies_with_child_parent

    def remove_association(self, from_id, to_id, definition_id):
        url = "https://api.hubapi.com/crm-associations/v1/associations/delete"
        payload = {
            "fromObjectId": from_id,
            "toObjectId": to_id,
            "category": "HUBSPOT_DEFINED",
            "definitionId": definition_id
        }
        response = requests.put(url, headers=self.headers, json=payload)
        if response.status_code != 204:
            error_message = f"Error removing association: {response.status_code} - {response.text}"
            logging.error(error_message)
            raise Exception(error_message)

    def remove_child_parent_associations(self, companies_with_child_parent):
        for company in companies_with_child_parent:
            company_id = company["id"]
            for child_id in company["child_companies"]:
                logging.info(f"Removing association between child {child_id} and parent {company_id}")
                self.remove_association(child_id, company_id, self.associations_code_map["child_to_parent"])
            
            for parent_id in company["parent_companies"]:
                logging.info(f"Removing association between parent {company_id} and child {parent_id}")
                self.remove_association(company_id, parent_id, self.associations_code_map["child_to_parent"])

    def merge_companies(self, companies):
        self.merged_companies = []
        self.merge_results = []
    
        # Identify the target company
        for company in companies:
            if company["action"] == "keep":
                target_company = company
                original_parent = company.get("parent_companies", [])
                break

        # Process and merge companies
        for company in companies:
            if company["action"] != "keep":
                logging.info(f"Attempting to merge {company['id']} into {target_company['id']}")
                self.merge_company(company["id"], target_company["id"])
                target_company["child_companies"].extend(company.get("child_companies", []))
                if "parent_companies" in company and company["parent_companies"] and not original_parent:
                    target_company["parent_companies"] = company["parent_companies"]
                if original_parent:
                    target_company["parent_companies"] = original_parent

        target_company["original_parent"] = original_parent
        self.merged_companies.append(target_company)
        return self.merged_companies

    def merge_company(self, source_company_id, target_company_id):
        url = "https://api.hubapi.com/crm/v3/objects/companies/merge"
        payload = {
            "primaryObjectId": target_company_id,
            "objectIdToMerge": source_company_id
        }
        response = requests.post(url, headers=self.headers, json=payload)
        if response.status_code != 200:
            error_message = f"Error merging company {source_company_id} into {target_company_id}: {response.status_code} - {response.text}"
            logging.error(error_message)
            raise Exception(error_message)
        else:
            logging.info(f"Merged company {source_company_id} into {target_company_id}")
            self.merge_results.append({
                "merged_company_id": source_company_id,
                "into_company_id": target_company_id
            })

    def reassociate_companies(self, merged_companies):
        for company in merged_companies:
            company_id = company.get("id")
            if not company_id or company.get("action") == "merge":
                continue

            logging.info(f"Reassociating for company ID: {company_id}")
            for child_id in company.get("child_companies", []):
                logging.info(f"Creating child association: {company_id} -> {child_id}")
                self.create_association(child_id, company_id, self.associations_code_map["child_to_parent"])

            if company.get("parent_companies") or company.get("original_parent"):
                logging.info(f"Creating parent association: {company.get('parent_companies')} -> {company_id}")
                self.create_association(company_id, self.get_parent_value(company), self.associations_code_map["child_to_parent"])

    def create_association(self, from_id, to_id, definition_id):
        url = "https://api.hubapi.com/crm-associations/v1/associations"
        payload = {
            "fromObjectId": from_id,
            "toObjectId": to_id,
            "category": "HUBSPOT_DEFINED",
            "definitionId": definition_id
        }
        response = requests.put(url, headers=self.headers, json=payload)
        if response.status_code != 204:
            error_message = f"Error creating association: {response.status_code} - {response.text}"
            logging.error(error_message)
            raise Exception(error_message)
        else:
            logging.info(f"Association created between {from_id} and {to_id}")

    def get_parent_value(self, data):
        # Check if 'original_parent' key exists and its list is not empty
        if 'original_parent' in data and data['original_parent']:
            return data['original_parent'][0]
        # Fallback to 'parent_companies' if 'original_parent' is not available or is empty
        elif 'parent_companies' in data and data['parent_companies']:
            return data['parent_companies'][0]
        else:
            return None 
        
    def run_merge(self, grouped_data):
        self.intermediate = []
        self.results = []
        self.missing = []
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        processed_companies = set()

        for key, companies in grouped_data.items():
            logging.info(f"Processing key: {key}")

            # Check that companies exist and have not been processed
            company_missing = False
            for company in companies:
                if company["id"] in processed_companies or not self.check_company_exists(company["id"]):
                    company_missing = True
                    missing_dict = {
                        "key": key,
                        "company_id": company["id"],
                        "error": "Company not found"
                    }
                    self.missing.append(missing_dict)
                    break

            if company_missing:
                logging.info(f"Skipping key {key}: One or more companies not found or already merged.")
                continue

            companies_with_child_parent = self.enrich_companies(companies)

            self.remove_child_parent_associations(companies_with_child_parent)
            merged_companies = self.merge_companies(companies_with_child_parent)
            self.reassociate_companies(merged_companies)

            # Outputs
            self.intermediate.append(companies_with_child_parent)
            self.results.append(merged_companies)

        self.write_to_json(self.missing, f"./data/errors/missing_companies_{timestamp}.json")
        self.write_to_json(companies_with_child_parent, f"./data/intermediate/companies_with_child_parent_{timestamp}.json")
        self.write_to_json(self.results, f"./data/outputs/merged_companies_{timestamp}.json")
        return self.results



def run_hubspot_merge(test=False):
    # Create directories
    os.makedirs('logs', exist_ok=True)
    os.makedirs('data', exist_ok=True)
    os.makedirs('data/intermediate', exist_ok=True)
    os.makedirs('data/outputs', exist_ok=True)
    os.makedirs('data/errors', exist_ok=True)
    
    # Logging
    logging.basicConfig(filename='./logs/merge_operations.log',
                    level=logging.INFO,
                    format='%(asctime)s - %(levelname)s - %(message)s',
                    datefmt='%Y-%m-%d %H:%M:%S')
    
    # Create and configure a StreamHandler for console output
    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.INFO)  # Set the logging level for console
    console_formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s', '%Y-%m-%d %H:%M:%S')
    console_handler.setFormatter(console_formatter)

    # Add the console handler to the root logger
    logging.getLogger().addHandler(console_handler)
    
    try:
        api_key = None
        if not test:
            # API key provision
            api_key = input("Please provide your Hubspot API key and press Enter: ")
            if not api_key:
                logging.info("Merge operation aborted.")
                return
        
        # Start client, load & validate data
        hubspot_client = HubspotAPI(test=test, api_key=api_key, input_file_path="input_data.csv")
        grouped_data = hubspot_client.load_and_group_data()

        # User confirmation
        if not test:
            user_input = input("The data input file has been successfully validated. Do you want to continue with the merge? (y/n) ")
            if user_input.lower() != 'y':
                logging.info("Merge operation aborted.")
                return
        
        # Run merge
        logging.info('Merge operation started')
        merge_results = hubspot_client.run_merge(grouped_data)
        return merge_results

    except Exception as e:
        logging.error(f"An error occurred: {e}")

if __name__ == '__main__':
    # Run program
    run_hubspot_merge()

    # Finish
    logging.info('Merge operation finished')



def csv_to_dict(csv_file_path):
    data = []
    with open(csv_file_path, mode="r", encoding="utf-8") as file:
        csv_reader = csv.DictReader(file)
        for row in csv_reader:
            data.append(row)
    return data

