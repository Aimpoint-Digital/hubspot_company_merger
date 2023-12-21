import logging

class ValidateCSV():
    def __init__(self, input_data):
        self.input_data = input_data
        self.validate_csv()

    def validate_csv(self):
        self.validate_csv__no_duplicate_records(self.input_data)
        self.validate_csv__no_keep_merge_id_overlap(self.input_data)
        self.validate_csv__merge_mapped_to_single_keep(self.input_data)
        self.validate_csv__each_key_has_two_records(self.input_data)
        self.validate_csv__keys_have_merge_and_keep(self.input_data)
        self.validate_csv__action_has_correct_values(self.input_data)
        logging.info('Input data has been validated')

    def validate_csv__no_duplicate_records(self, data):
        seen = set()
        for record in data:
            record_tuple = tuple(record.items())
            if record_tuple in seen:
                error_message = f"Duplicate record found: {record}"
                logging.error(error_message) 
                raise ValueError(error_message)
            seen.add(record_tuple)

    def validate_csv__no_keep_merge_id_overlap(self, data):
        keep_ids = set()
        merge_ids = set()

        for record in data:
            action = record['action']
            company_id = record['id']

            if action == 'keep':
                if company_id in merge_ids:
                    error_message = f"ID {company_id} is used as 'merge' in another key."
                    logging.error(error_message) 
                    raise ValueError(error_message)
                keep_ids.add(company_id)
            elif action == 'merge':
                if company_id in keep_ids:
                    error_message = f"ID {company_id} is used as 'keep' in another key."
                    logging.error(error_message) 
                    raise ValueError(error_message)
                merge_ids.add(company_id)

    def validate_csv__merge_mapped_to_single_keep(self, data):
        key_action_count = {}

        for record in data:
            key = record['key']
            action = record['action']

            if key not in key_action_count:
                key_action_count[key] = {'keep': 0, 'merge': 0}
            key_action_count[key][action] += 1

        for key, actions in key_action_count.items():
            if actions['merge'] != 1 or actions['keep'] != 1:
                error_message = f"Key {key} does not map one 'merge' to exactly one 'keep' (found {actions['merge']} merge and {actions['keep']} keep)."
                logging.error(error_message) 
                raise ValueError(error_message)

    def validate_csv__each_key_has_two_records(self, data):
        key_counts = {}

        for record in data:
            key = record['key']
            key_counts[key] = key_counts.get(key, 0) + 1

        for key, count in key_counts.items():
            if count != 2:
                error_message = f"Key {key} does not have exactly two records (found {count})."
                logging.error(error_message) 
                raise ValueError(error_message)


    def validate_csv__keys_have_merge_and_keep(self, data):
        key_actions = {}
        for record in data:
            key = record['key']
            action = record['action']
            if key not in key_actions:
                key_actions[key] = set()
            key_actions[key].add(action)

        for key, actions in key_actions.items():
            if actions != {"merge", "keep"}:
                error_message = f"Key {key} does not have both 'merge' and 'keep' actions."
                logging.error(error_message) 
                raise ValueError(error_message)

    def validate_csv__action_has_correct_values(self, data):
        valid_actions = {"merge", "keep"}
        for record in data:
            action = record['action']
            if action not in valid_actions:
                error_message = f"Invalid action '{action}' in record: {record}"
                logging.error(error_message) 
                raise ValueError(error_message)

