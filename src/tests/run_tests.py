import sys
import json
import csv
import requests

root_dir = '../' 
sys.path.append(root_dir)
from main import HubspotAPI, run_hubspot_merge

class HubspotTestRunner:
    def __init__(self):
        self.hubspot_client = HubspotAPI(test=True)

    def create_company(self, name):
        url = "https://api.hubapi.com/crm/v3/objects/companies"
        payload = {
            "properties": {
                "name": name,
                "domain": "aimpointtest.com"
            }
        }
        r = requests.post(url, headers=self.hubspot_client.headers, json=payload)
        if r.status_code == 200 or r.status_code == 201:
            response_data = r.json()
            company_id = response_data.get("id")
            company_name = response_data.get("name")
            return company_id, company_name
        else:
            print(f"Failed to create company. Status Code: {r.status_code}")
            print(f"Response: {r.text}")
            return None

    def setup_test_scenario(self, scenario):
        company_ids = {}
        for company_name in scenario["companies"]:
            company_id, _ = self.create_company(company_name)
            if company_id:
                company_ids[company_name] = company_id
                if company_name != "test_merge":
                    self.companies_to_clean.add(company_id)
        return company_ids

    def update_associations_and_expected_results(self, scenario, company_ids):
        updated_associations = []
        updated_expected_results = []

        for association in scenario["associations"]:
            from_id = company_ids.get(association["fromObjectId"])
            to_id = company_ids.get(association["toObjectId"])
            if from_id and to_id:
                updated_associations.append({
                    "fromObjectId": int(from_id),
                    "toObjectId": int(to_id),
                    "category": association["category"],
                    "definitionId": association["definitionId"]
                })

        for expected in scenario["expected_result"]:
            from_id = company_ids.get(expected["fromObjectId"])
            to_id = company_ids.get(expected["toObjectId"])
            if from_id and to_id:
                updated_expected_results.append({
                    "fromObjectId": int(from_id),
                    "toObjectId": int(to_id),
                    "category": expected["category"],
                    "definitionId": expected["definitionId"]
                })

        return updated_associations, updated_expected_results

    def associate_companies(self, association):
        url = "https://api.hubapi.com/crm-associations/v1/associations"
        response = requests.put(url, headers=self.hubspot_client.headers, json=association)
        if response.status_code != 204:
            raise Exception(f"Error creating association: {response.status_code} - {response.text}")

    def get_associations(self, company_id, definition_id):
        url = f"https://api.hubapi.com/crm-associations/v1/associations/{company_id}/HUBSPOT_DEFINED/{definition_id}"
        response = requests.get(url, headers=self.hubspot_client.headers)
        if response.status_code != 200:
            raise Exception(f"Error getting associations: {response.status_code} - {response.text}")
        else:
            return response.json()['results']

    def get_company_name_by_id(self, company_id):
        url = f"https://api.hubapi.com/companies/v2/companies/{company_id}"
        response = requests.get(url, headers=self.hubspot_client.headers)
        if response.status_code != 200:
            raise Exception(f"Error getting company name: {response.status_code} - {response.text}")
        else:
            return response.json()["properties"]["name"]["value"]

    def assert_is_expected(self, test_scenario, merge_results):
        associations = []
        for company in merge_results:
            child_companies = self.get_associations(company["id"], 13)
            if child_companies:
                for child in child_companies:
                    associations.append({
                        "fromObjectId": self.get_company_name_by_id(company["id"]), 
                        "toObjectId": self.get_company_name_by_id(child), 
                        "category": "HUBSPOT_DEFINED", 
                        "definitionId": 13
                    })
        parent_companies = self.get_associations(company["id"], 14)
        if parent_companies:
            for parent in parent_companies:
                associations.append({
                    "fromObjectId":  self.get_company_name_by_id(parent), 
                    "toObjectId": self.get_company_name_by_id(company["id"]),
                    "category": "HUBSPOT_DEFINED", 
                    "definitionId": 13
                })

        expected_result = test_scenario["expected_result"]
        if self.is_list1_in_list2(expected_result, associations):
            print("Test passed")
        else:
            print(associations)
            print(expected_result)
            raise Exception("Test scenario failed")
        

    def is_list1_in_list2(self, list1, list2):
        def dict_to_tuple(d):
            return tuple(sorted(d.items()))

        set1 = {dict_to_tuple(d) for d in list1}
        set2 = {dict_to_tuple(d) for d in list2}

        return set1.issubset(set2)

    def delete_company(self, company_id):
        url = f"https://api.hubapi.com/companies/v2/companies/{company_id}"
        response = requests.delete(url, headers=self.hubspot_client.headers)
        if response.status_code != 200:
            raise Exception(f"Error removing company: {response.status_code} - {response.text}")

    def run_all_tests(self, test_scenarios):
        self.companies_to_clean = set()
        input_data = []

        for i, scenario in enumerate(test_scenarios):
            print(f"Setting up Test Scenario {i+1}")

            # Create companies for the scenario
            company_ids = self.setup_test_scenario(scenario)
            self.companies_to_clean.update(company_ids)

            # Prepare data for input file
            input_data.append([company_ids["test_merge"], "test_merge", i + 1, 'merge'])
            input_data.append([company_ids["test_keep"], "test_keep", i + 1, 'keep'])

            # Update and associate companies
            updated_associations, _ = self.update_associations_and_expected_results(scenario, company_ids)
            for assoc in updated_associations:
                self.associate_companies(assoc)

        # Generate a single input data file
        self.generate_input_data("input_data.csv", input_data)

        # Run Merge for all scenarios together
        merge_results = run_hubspot_merge(test=True)

        for i, scenario in enumerate(test_scenarios):
            self.assert_is_expected(scenario, merge_results[i])

        # Cleanup
        self.clean_up(self.companies_to_clean)

    def generate_input_data(self, csv_file_path, input_data):
        with open(csv_file_path, mode='w', newline='', encoding='utf-8') as file:
            writer = csv.writer(file)
            writer.writerow(['id', 'company_name', 'key', 'action'])
            for row in input_data:
                writer.writerow(row)
        print(f"CSV file created at {csv_file_path}")

    def clean_up(self, company_ids):
        for company_id in company_ids:
            try:
                if isinstance(company_id, int) or company_id.isdigit():
                    print(f"Deleting company: {company_id}")
                    self.delete_company(company_id)
            except Exception as e:
                print(f"Failed to delete company {company_id}: {e}")


       
if __name__ == "__main__":
    with open('test_scenarios.json') as f:
        test_scenarios = json.load(f)

    tester = HubspotTestRunner()
    tester.run_all_tests(test_scenarios)
    print(f"All test scenarios completed!\n")