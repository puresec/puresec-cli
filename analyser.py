import traceback
import utils
import os
import re
import yaml
import ConfigParser
import pdb
from project_conf import *

class Analyser():

    def __init__(self, cf, code_dir, framework):
        self.cf = cf
        self.code_dir = code_dir
        self.framework = framework
        self.framework_file_data = None
        self.account_number = None
        self.aws_resources = [
            "SQS",
            "S3",
            "DynamoDB",
            "SNS",
            "Kinesis",
            "SES"
        ]
        self.object_regex = {
            "python": {
                "DynamoDB": {
                    "Obj": "",
                },
                "S3": {
                    "Obj": ""
                }
            },
            "nodejs": {
                "DynamoDB": {
                    "Obj": "TableName\:.*(\'|\")Demo-AccountMoneyTable(\'|\")"
                },
                "S3": {
                    "Obj": ""
                }
            }
        }

        # Check for config file
        self._get_from_config_file()

        if self.framework:
            self._parse_framework_file()

    def _parse_framework_file(self):
        """ Parses framework file
        """
        if self.framework == "serverless":
            with open(os.path.join(self.code_dir, "serverless.yml"), 'r') as data:
                try:
                    self.framework_file_data = yaml.load(data)
                except yaml.YAMLError as e:
                    utils.log_error(e)

    def _get_from_config_file(self):
        """ Checks for existing config file
        """
        config_file_path = os.path.join(self.code_dir, '.puresec.conf')
        if os.path.exists(config_file_path):
            Config = ConfigParser.ConfigParser()
            Config.read(config_file_path)
            try:
                self.account_number = Config.get('Account', 'Number')
            except ConfigParser.NoSectionError:
                self.account_number = None
            except ConfigParser.NoOptionError:
                self.account_number = None

    def _add_to_config_file(self, data_type, value):
        """ Adds relevant data type to config
        """
        config_file_path = os.path.join(self.code_dir, '.puresec.conf')
        Config = ConfigParser.ConfigParser()
        config_file = open(config_file_path, 'a')
        if data_type == 'account_number':
            Config.add_section('Account')
            Config.set('Account', 'Number', value)
        Config.write(config_file)
        config_file.close()

    def get_minimal_roles_from_code(self):
        """ Gets minimal roles from code
        """
        self._scan_functions_code()

    def _scan_functions_code(self):
        """ Scans functions code and creates minimal role
        """
        for lambda_function in self.cf.get_functions():
            self._analyse_function(lambda_function)

    def _analyse_function(self, lambda_function):
        """ Analyses functions code for minimal permissions needed
        """
        function_files, runtime = self._get_function_files(lambda_function)
        permissions = self._create_minimal_role(function_files, runtime)
        utils.log_msg("Lambda Function: %s, requires the following permissions:" % lambda_function['Properties']['FunctionName'])
        utils.log_msg(permissions)

    def _get_function_files(self, lambda_function):
        """ Gets relevant function files including libraries
        """
        handler = lambda_function['Properties']['Handler']

        # Serverless Framework
        if self.framework == "serverless":
            sls_lambda_name = lambda_function['Properties']['FunctionName'].split("-")[-1]
            if "/" in self.framework_file_data['functions'][sls_lambda_name]['handler']:
                function_files_path = os.path.join(self.code_dir,
                r"/".join(self.framework_file_data['functions'][sls_lambda_name]['handler'].split(r"/")[:-1]))
            else:
                function_files_path = self.code_dir
        else:
            # CloudFormation: Ask for path
            pass

        function_files = []
        handler_name = handler.split(".")[0]
        handler_file = None

        for file_name in os.listdir(function_files_path):
            if os.path.isfile(os.path.join(function_files_path, file_name)):
                file_part = ".".join(file_name.split(".")[:-1])
                if handler_name == file_part:
                    relevant_extension = file_name.split(".")[-1]
                    handler_file = file_name

                    if relevant_extension == "py":
                        runtime = "python"
                    elif relevant_extension == "js":
                        runtime = "nodejs"

        if not handler_file:
            utils.log_error("Couldn't find handler file for function: %s" %
            lambda_function['Properties']['FunctionName'])

        #TODO: Include excluded + included files
        try:
            for subdir, dirs, files in os.walk(function_files_path):
                for file_name in files:
                    file_path = os.path.join(subdir, file_name)

                    if file_path.endswith(relevant_extension):
                        function_files.append(file_path)
        except:
            print traceback.format_exc()

        return function_files, runtime

    def _create_minimal_role(self, function_files, runtime):
        """ Scans function code and creates minimal roles
        """
        permissions = []

        # Service Level
        services_used = self._scan_code_for_used_services(function_files, runtime)
        utils.log_msg("Services used:")
        utils.log_msg(services_used)

        # Account Level
        account_used = self._get_account_number(function_files, runtime)
        utils.log_msg("Account used:")
        utils.log_msg(account_used)

        for service in services_used:

            # Region Level
            regions_used = self._scan_for_service_region(function_files, runtime, service)
            utils.log_msg("Regions used:")
            utils.log_msg(regions_used)

            # Table / Bucket / Stream Level
            objects_used = self._scan_for_service_objects(function_files, runtime, service)
            utils.log_msg("Objects used:")
            utils.log_msg(objects_used)

            for region in regions_used:
                for obj in objects_used:
                    if service == "DynamoDB":
                        permissions.append("arn::aws::dynamodb::%s::%s::%s" %
                        (region, account_used, obj))

        return permissions

    def _scan_code_for_used_services(self, function_files, runtime):
        """ Scans function code for used services
        """
        if runtime == "python":
            return self._scan_code_for_used_services_python(function_files)
        elif runtime == "nodejs":
            return self._scan_code_for_used_services_nodejs(function_files)

    def _scan_code_for_used_services_python(self, function_files):
        """ Scans function code for used services (Python)
        """
        services = []

        for file_path in function_files:
            file_code = open(file_path, "r").read()
            lines = file_code.splitlines()

            for line in lines:
                for resource in self.aws_resources:
                    if '.client(' in line.lower() and \
                    resource.lower() in line.lower():
                        services.append(resource)
                    if '.resource(' in line.lower() and \
                    resource.lower() in line.lower():
                        services.append(resource)

        return services

    def _scan_code_for_used_services_nodejs(self, function_files):
        """ Scans function code for used services (NodeJS)
        """
        services = []

        for file_path in function_files:
            file_code = open(file_path, "r").read()
            lines = file_code.splitlines()

            for line in lines:
                for resource in self.aws_resources:
                    str_to_check = "aws." + resource.lower()
                    if str_to_check in line.lower():
                        services.append(resource)

        return services

    def _scan_for_service_region(self, function_files, runtime, service):
        """ Scans for relevant region for the used services.
        """
        return ["*"]

    def _try_to_extract_from_cf(self, data_type):
        """ Attempts to extract relevant data types (account_number / region)
        from CloudFormation
        """
        return None

    def _get_account_number(self, function_files, runtime):
        """ Scans for relevant account number.
        """
        if not self.account_number:
            extracted_account_number = self._try_to_extract_from_cf('account_number')
            if not extracted_account_number:
                self.account_number = raw_input("Please enter relevant AWS account number: ")
            else:
                answer = raw_input("Is you account number: %s? If YES - just press enter, if NOT - enter your account number." % extracted_account_number)
                if len(answer) > 3:
                    #TODO: Test if the input is valid account number
                    self.account_number = answer
            self._add_to_config_file('account_number', self.account_number)
        return self.account_number

    def _get_object_from_regex(self, regex_res, objects, service):
        """ Extracts relevant new objects names from regex result
        """
        if "'" in regex_res:
            obj = regex_res.split("'")[1]
            if obj not in objects:
                objects.append(obj)
        elif '"' in regex_res:
            obj = regex_res.split("'")[1]

            if service == "DynamoDB":
                including_service_obj = 'table/' + obj
            #TODO: Add other services

            if including_service_obj not in objects:
                objects.append(including_service_obj)

        return objects

    def _scan_for_service_objects(self, function_files, runtime, service):
        """ Scans for specific objects used by the services
        """
        objects = []

        for file_path in function_files:
            file_code = open(file_path, "r").read()
            lines = file_code.splitlines()

            for line in lines:
                if runtime in self.object_regex.keys():
                    if service in self.object_regex[runtime].keys():
                        is_matched = re.search(self.object_regex[runtime][service]['Obj'], line)
                        if is_matched:
                            regex_res = is_matched.group()
                            objects = self._get_object_from_regex(regex_res, objects, service)

        return objects
