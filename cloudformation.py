import traceback
import json
import utils

class CloudFormation():
    def __init__(self, cf_path):
        self.cf_path = cf_path
        self.lambda_resources = []

    def parse(self):
        """ Parses the current CloudFormation json file
        """
        self._load_cf_file()

        self._get_lambda_resources()

    def get_functions(self):
        """ Returnes all function Resources
        """
        return self.lambda_resources

    def _load_cf_file(self):
        """ Loads current CloudFormation json file into an object
        """
        _handle = open(self.cf_path, "r")
        cf_file_contents = _handle.read()
        _handle.close()

        try:
            self.cf_file_json = json.loads(cf_file_contents)
        except:
            print traceback.format_exc()

    def _get_lambda_resources(self):

        for cf_nested_list in utils.dict_iterator(self.cf_file_json):
            for value in cf_nested_list:
                if value == "AWS::Lambda::Function":
                    self.lambda_resources.append(self.cf_file_json['Resources'][cf_nested_list[0]])
