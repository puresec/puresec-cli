from ...utils import eprint
import base
import re

SERVICE_CLIENT_NAMES = {
        'sqs': "SQS",
        's3': "S3",
        'dynamodb': "DynamoDB",
        'sns': "SNS",
        'kinesis': "Kinesis",
        'ses': "SES"
        }

SERVICE_PATTERNS = dict(
        (name, re.compile(r"\.\s*{}\(((?:.|\n)*)\)".format(client_name), re.MULTILINE))
        for name, client_name in SERVICE_CLIENT_NAMES.items()
        )

# Argument patterns
ARGUMENT_PATTERN_TEMPLATE = r"['\"]?\b{}['\"]?\s*:\s*([^\s].*)\s*,?"
REGION_PATTERN = re.compile(ARGUMENT_PATTERN_TEMPLATE.format('region'))
AUTH_PATTERN = re.compile(r"accessKeyId|secretAccessKey|sessionToken|credentials")

FILENAME_PATTERN = re.compile(r"\.js$", re.IGNORECASE)

def get_services(filename, content, permissions, default_region, default_account, environment):
    if not FILENAME_PATTERN.match(filename):
        return

    for service, pattern in SERVICE_PATTERNS.items():
        for service_match in pattern.finditer(content):
            arguments = service_match.group(1)
            if arguments:
                # region
                region = _get_variable_from_arguments(arguments, REGION_PATTERN, environment)
                if region is None:
                    region = default_region
                elif not region:
                    eprint("WARNING: Incomprehensive region: {} (in {})".format(arguments, filename))
                    region = '*'
                # account
                if AUTH_PATTERN.match(arguments):
                    eprint("WARNING: Unknown account: {} (in {})".format(arguments, filename))
                    account = '*'
                else:
                    account = default_account
            else:
                region = default_region
                account = default_account

            permissions[service][region][account] # accessing to initialize defaultdict

    return permissions

def get_regions(filename, content, regions, client, service, environment):
    processor = SERVICE_RESOURCES_PROCESSOR.get(service) or base.get_regions
    processor(filename, content, regions, client=client, environment=environment)

REGION_PROCESSOR = {
        # service: function(filename, content, regions, client, environment)
        }

def get_resources(filename, content, resources, client, service, environment):
    processor = SERVICE_RESOURCES_PROCESSOR.get(service)
    if not processor:
        resources.add('*')
        return
    processor(filename, content, resources, client=client, environment=environment)

SERVICE_RESOURCES_PROCESSOR = {
        # service: function(filename, content, resources, client, environment)
        'dynamodb': base.get_dynamodb_resources,
        }

STRING_PATTERN = re.compile(r"['\"]([\w-]+)['\"]") # 'VALUE' or "VALUE"
ENV_PATTERN = re.compile(r"process\.env(?:\.|\[['\"])(\w+)(?:['\"]\])") # process.env.VALUE or process.env['VALUE'] or process.env["VALUE"]

def _get_variable_from_arguments(arguments, pattern, environment):
    """ Gets value of an argument within the code

    Returns:
        1. str value if found
        2. None if argument doesn't exist
        3. '' if can't process argument value
    """
    match = pattern.match(arguments)
    if not match:
        return None

    value = match.group(1)
    match = STRING_PATTERN.match(value)
    if match:
        return match.group(1)

    match = ENV_PATTERN.match(value)
    if match:
        return environment.get(match.group(1))

    return ''

