from lib.utils import eprint
from lib.runtimes.aws.base import Base
import re

SERVICE_CALL_PATTERN_TEMPLATE = r"\.\s*{}\((.*)\)" # .VALUE(OUTPUT)

class NodejsRuntime(Base):
    SERVICE_CALL_PATTERNS = dict(
            (name, re.compile(SERVICE_CALL_PATTERN_TEMPLATE.format(client_name), re.MULTILINE | re.DOTALL))
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
    def _get_services(self, filename, file):
        """
        >>> from io import StringIO
        >>> from pprint import pprint
        >>> from test.utils import normalize_dict
        >>> from test.mock import Mock
        >>> mock = Mock(__name__)
        >>> runtime = NodejsRuntime('path/to/function', config={}, session=None, default_region='default_region', default_account='default_account', environment={})

        >>> runtime._get_services("filename.txt", StringIO(".S3()"))
        >>> pprint(normalize_dict(runtime._permissions))
        {}

        >>> runtime._get_services("filename.js", StringIO(".S3()"))
        >>> pprint(normalize_dict(runtime._permissions))
        {'s3': {'default_region': {'default_account': {}}}}
        >>> runtime._permissions.clear()

        >>> runtime._get_services("filename.js", StringIO(".S3({ region: 'us-east-1' })"))
        >>> pprint(normalize_dict(runtime._permissions))
        {'s3': {'us-east-1': {'default_account': {}}}}

        >>> runtime._permissions.clear()
        >>> runtime._get_services("filename.js", StringIO('''
        ... aws.
        ...     S3({
        ...         region: 'us-east-1'
        ...     })
        ... '''))
        >>> pprint(normalize_dict(runtime._permissions))
        {'s3': {'us-east-1': {'default_account': {}}}}

        >>> mock.mock(None, 'eprint')

        >>> runtime._permissions.clear()
        >>> runtime._get_services("filename.js", StringIO('''
        ... aws.
        ...     S3({
        ...         region: getRegion()
        ...     })
        ... '''))
        >>> pprint(normalize_dict(runtime._permissions))
        {'s3': {'*': {'default_account': {}}}}
        >>> mock.calls_for('eprint')
        'warn: incomprehensive region: {\\n        region: getRegion()\\n    } (in filename.js)'

        >>> runtime._permissions.clear()
        >>> runtime._get_services("filename.js", StringIO('''
        ... aws.
        ...     S3({
        ...         region: 'us-' + region
        ...     })
        ... '''))
        >>> pprint(normalize_dict(runtime._permissions))
        {'s3': {'*': {'default_account': {}}}}
        >>> mock.calls_for('eprint')
        "warn: incomprehensive region: {\\n        region: 'us-' + region\\n    } (in filename.js)"

        >>> runtime._permissions.clear()
        >>> runtime._get_services("filename.js", StringIO('''
        ... aws.
        ...     S3({
        ...         accessKeyId: "some key"
        ...     })
        ... '''))
        >>> pprint(normalize_dict(runtime._permissions))
        {'s3': {'default_region': {'*': {}}}}
        >>> mock.calls_for('eprint')
        'warn: unknown account: {\\n        accessKeyId: "some key"\\n    } (in filename.js)'
        """

        if not NodejsRuntime.FILENAME_PATTERN.search(filename):
            return

        content = file.read()
        for service, pattern in NodejsRuntime.SERVICE_CALL_PATTERNS.items():
            for service_match in pattern.finditer(content):
                arguments = service_match.group(1)
                if arguments:
                    # region
                    region = self._get_variable_from_arguments(arguments, NodejsRuntime.REGION_PATTERN)
                    if region is None:
                        region = self.default_region
                    elif not region:
                        eprint("warn: incomprehensive region: {} (in {})".format(arguments, filename))
                        region = '*'
                    elif not any(pattern.match(region) for pattern in NodejsRuntime.REGION_PATTERNS.values()):
                        eprint("warn: incomprehensive region: {} (in {})".format(arguments, filename))
                        region = '*'
                    # account
                    if NodejsRuntime.AUTH_PATTERN.search(arguments):
                        eprint("warn: unknown account: {} (in {})".format(arguments, filename))
                        account = '*'
                    else:
                        account = self.default_account
                else:
                    region = self.default_region
                    account = self.default_account

                self._permissions[service][region][account] # accessing to initialize defaultdict

    def _get_regions(filename, file, regions, service, account):
        processor_name = NodejsRuntime.REGIONS_PROCESSOR.get(service)
        if processor_name:
            getattr(self, processor_name)(filename, file, regions, account=account)
        else:
            super()._get_regions(filename, file, regions, service=service, account=account)

    REGIONS_PROCESSOR = {
            # service: function(filename, file, regions, account)
            }

    def _get_resources(self, filename, file, resources, client, service):
        processor_name = NodejsRuntime.SERVICE_RESOURCES_PROCESSOR.get(service)
        if not processor_name:
            resources.add('*')
            return
        getattr(self, processor_name)(filename, file, resources, client=client)

    SERVICE_RESOURCES_PROCESSOR = {
            # service: function(filename, file, resources, client)
            'dynamodb': '_get_dynamodb_resources',
            }

    STRING_PATTERN = re.compile(r"['\"]([\w-]+)['\"]") # 'VALUE' or "VALUE"
    ENV_PATTERN = re.compile(r"process\.env(?:\.|\[['\"])(\w+)(?:['\"]\])?") # process.env.VALUE or process.env['VALUE'] or process.env["VALUE"]

    def _get_variable_from_arguments(self, arguments, pattern):
        """ Gets value of an argument within the code

        Returns:
            1. str value if found
            2. None if argument doesn't exist
            3. '' if can't process argument value

        >>> runtime = NodejsRuntime('path/to/function', config={}, session=None, default_region='default_region', default_account='default_account', environment={'var': "us-west-2"})

        >>> runtime._get_variable_from_arguments('''{
        ...     region: bla(),
        ... }''', NodejsRuntime.REGION_PATTERN)
        ''

        >>> runtime._get_variable_from_arguments('''{
        ...     region: 'us-east-1'
        ... }''', NodejsRuntime.REGION_PATTERN)
        'us-east-1'

        >>> runtime._get_variable_from_arguments('''{
        ...     region: 'us-east-1',
        ... }''', NodejsRuntime.REGION_PATTERN)
        'us-east-1'

        >>> runtime._get_variable_from_arguments('''{
        ...     region: process.env.var
        ... }''', NodejsRuntime.REGION_PATTERN)
        'us-west-2'

        >>> runtime._get_variable_from_arguments('''{
        ...     region: process.env.var,
        ... }''', NodejsRuntime.REGION_PATTERN)
        'us-west-2'

        >>> runtime._get_variable_from_arguments('''{
        ...     region: process.env['var']
        ... }''', NodejsRuntime.REGION_PATTERN)
        'us-west-2'

        >>> runtime._get_variable_from_arguments('''{
        ...     region: process.env['var'],
        ... }''', NodejsRuntime.REGION_PATTERN)
        'us-west-2'

        >>> runtime._get_variable_from_arguments('''{
        ...     region: process.env["var"]
        ... }''', NodejsRuntime.REGION_PATTERN)
        'us-west-2'

        >>> runtime._get_variable_from_arguments('''{
        ...     region: process.env["var2"]
        ... }''', NodejsRuntime.REGION_PATTERN)
        ''
        """
        match = pattern.search(arguments)
        if not match:
            return None

        value = match.group(1)
        match = NodejsRuntime.STRING_PATTERN.match(value)
        if match:
            return match.group(1)

        match = NodejsRuntime.ENV_PATTERN.match(value)
        if match:
            return self.environment.get(match.group(1), '')

        return ''

Runtime = NodejsRuntime

