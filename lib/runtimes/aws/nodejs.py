from ...utils import eprint
import base
import re

SERVICE_CALL_PATTERN_TEMPLATE = r"\.\s*{}\(((?:.|\n)*)\)" # .VALUE(OUTPUT)
SERVICE_CALL_PATTERNS = dict(
        (name, re.compile(SERVICE_CALL_PATTERN_TEMPLATE.format(client_name), re.MULTILINE))
        for name, client_name in
        (
            ('sqs', "SQS"),
            ('s3', "S3"),
            ('dynamodb', "DynamoDB"),
            ('sns', "SNS"),
            ('kinesis', "Kinesis"),
            ('ses', "SES"),
        ))

# Argument patterns
ARGUMENT_PATTERN_TEMPLATE = r"['\"]?\b{}['\"]?\s*:\s*([^\s].*)\s*,?"
REGION_PATTERN = re.compile(ARGUMENT_PATTERN_TEMPLATE.format('region'))
AUTH_PATTERN = re.compile(r"accessKeyId|secretAccessKey|sessionToken|credentials")

FILENAME_PATTERN = re.compile(r"\.js$", re.IGNORECASE)

def get_services(filename, content, permissions, default_region, default_account, environment):
    if not FILENAME_PATTERN.match(filename):
        return

    for service, pattern in SERVICE_CALL_PATTERNS.items():
        for service_match in pattern.finditer(content):
            arguments = service_match.group(1)
            if arguments:
                # region
                region = _get_variable_from_arguments(arguments, REGION_PATTERN, environment)
                if region is None:
                    region = default_region
                elif not region:
                    eprint("warn: incomprehensive region: {} (in {})".format(arguments, filename))
                    region = '*'
                # account
                if AUTH_PATTERN.match(arguments):
                    eprint("warn: unknown account: {} (in {})".format(arguments, filename))
                    account = '*'
                else:
                    account = default_account
            else:
                region = default_region
                account = default_account

            permissions[service][region][account] # accessing to initialize defaultdict

def get_regions(filename, content, regions, service, environment):
    processor = SERVICE_RESOURCES_PROCESSOR.get(service) or base.get_regions
    processor(filename, content, regions, environment=environment)

REGION_PROCESSOR = {
        # service: function(filename, content, regions, environment)
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

