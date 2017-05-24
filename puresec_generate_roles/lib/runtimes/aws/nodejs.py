from lib.utils import eprint, get_inner_parentheses
from lib.runtimes.aws.base import Base
from lib.runtimes.aws.nodejs_api import SERVICE_CALL_PATTERNS, ACTION_CALL_PATTERNS
from functools import partial
import re

class NodejsRuntime(Base):
    FILENAME_PATTERN = re.compile(r"\.js$", re.IGNORECASE)

    # Processors

    # Argument patterns
    ARGUMENT_PATTERN_TEMPLATE = r"['\"]?\b{}['\"]?\s*:\s*([^\s].*?)\s*(?:[,}}]|\Z)" # "VALUE": OUTPUT, or 'VALUE': OUTPUT} or VALUE: OUTPUT
    REGION_PATTERN = re.compile(ARGUMENT_PATTERN_TEMPLATE.format('region'))
    AUTH_PATTERN = re.compile(r"accessKeyId|secretAccessKey|sessionToken|credentials")

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

        >>> runtime._permissions.clear()
        >>> runtime._get_services("filename.js", StringIO('''
        ... aws.
        ...     S3({
        ...         region: 'us-east-1', something: 'else'
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
        for service, pattern in SERVICE_CALL_PATTERNS:
            for service_match in pattern.finditer(content):
                arguments = get_inner_parentheses(service_match.group(1))
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
        processor = NodejsRuntime.REGIONS_PROCESSOR.get(service)
        if processor:
            processor(self)(filename, file, regions, account=account)
        else:
            super()._get_regions(filename, file, regions, service=service, account=account)

    REGIONS_PROCESSOR = {
            # service: lambda self: function(self, filename, file, regions, account)
            }

    def _get_resources(self, filename, file, resources, region, account, service):
        processor = NodejsRuntime.SERVICE_RESOURCES_PROCESSOR.get(service)
        if not processor:
            resources['*'] # accessing to initialize defaultdict
            return
        processor(self)(filename, file, resources, region=region, account=account)

    SERVICE_RESOURCES_PROCESSOR = {
            # service: function(self, filename, file, resources, region, account)
            'dynamodb': lambda self: self._get_dynamodb_resources,
            's3':       lambda self: self._get_s3_resources,
            }

    def _get_actions(self, filename, file, actions, region, account, resource, service):
        if not NodejsRuntime.FILENAME_PATTERN.search(filename):
            return

        processor = NodejsRuntime.SERVICE_ACTIONS_PROCESSOR.get(service)
        if not processor:
            actions.add('*')
            return
        processor(self)(filename, file, actions, region=region, account=account, resource=resource)

    SERVICE_ACTIONS_PROCESSOR = {
            # service: function(self, filename, file, actions, region, account, resource)
            'dynamodb': lambda self: partial(self._get_generic_actions, service='dynamodb'),
            's3':       lambda self: partial(self._get_generic_actions, service='s3'),
            }

    # Helpers

    def _get_generic_actions(self, filename, file, actions, region, account, resource, service):
        """
        >>> from io import StringIO
        >>> from test.utils import normalize_dict
        >>> runtime = NodejsRuntime('path/to/function', config={}, session=None, default_region='default_region', default_account='default_account', environment={})

        >>> runtime._permissions = {'dynamodb': {'us-east-1': {'some-account': {'Table/SomeTable': set()}}}}
        >>> actions = set()
        >>> runtime._get_generic_actions("path/to/file.js", StringIO("code .putItem() code"), actions, region='us-east-1', account='some-account', resource='Table/SomeTable', service='dynamodb')
        >>> runtime._permissions
        {'dynamodb': {'us-east-1': {'some-account': {'Table/SomeTable': {'dynamodb:PutItem'}}}}}

        >>> runtime._permissions = {'s3': {'us-east-1': {'some-account': {'SomeBucket': set()}}}}
        >>> actions = set()
        >>> runtime._get_generic_actions("path/to/file.js", StringIO("code .putObject(params) .getSignedUrl('getObject', params) code"), actions, region='us-east-1', account='some-account', resource='SomeBucket', service='s3')
        >>> normalize_dict(runtime._permissions)
        {'s3': {'us-east-1': {'some-account': {'SomeBucket': {'s3:GetObject', 's3:PutObject'}}}}}
        """
        content = file.read()
        for action, pattern in ACTION_CALL_PATTERNS[service]:
            if pattern.search(content):
                self._permissions[service][region][account][resource].add(action)

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

