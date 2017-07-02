import re

from puresec_cli.utils import eprint, get_inner_parentheses
from puresec_cli.actions.generate_roles.runtimes.aws.base import Base
from puresec_cli.actions.generate_roles.runtimes.aws.python_api import PythonApi

class PythonRuntime(Base, PythonApi):
    PYTHON_FILENAME_PATTERN = re.compile(r"\.py$", re.IGNORECASE)

    # Processors

    SERVICE_REGIONS_PROCESSOR = {
        # service: lambda self: function(self, filename, contents, regions, account)
    }

    # Argument patterns
    ARGUMENT_PATTERN_TEMPLATE = r"\b{}[\s\\]*=[\s\\]*([^\s].*?)[\s\\]*(?:,|\Z)" # VALUE=OUTPUT, or VALUE=OUTPUT) or VALUE=OUTPUT
    REGION_PATTERN = re.compile(ARGUMENT_PATTERN_TEMPLATE.format('region_name'), re.MULTILINE)
    AUTH_PATTERN = re.compile(r"aws_access_key_id|aws_secret_access_key|aws_session_token")
    def _get_services(self, filename, contents):
        """
        >>> from pprint import pprint
        >>> from tests.utils import normalize_dict
        >>> from tests.mock import Mock
        >>> mock = Mock(__name__)

        >>> class Provider:
        ...     pass
        >>> provider = Provider()
        >>> provider.default_region = 'default_region'
        >>> provider.default_account = 'default_account'

        >>> runtime = PythonRuntime('path/to/function', resource_properties={}, provider=provider)

        >>> runtime._get_services("filename.txt", ".client('s3')")
        >>> pprint(normalize_dict(runtime._permissions))
        {}

        >>> runtime._get_services("filename.py", ".client('s3')")
        >>> pprint(normalize_dict(runtime._permissions))
        {'s3': {'default_region': {'default_account': {}}}}
        >>> runtime._permissions.clear()

        >>> runtime._get_services("filename.py", ".client('s3', region_name='us-east-1')")
        >>> pprint(normalize_dict(runtime._permissions))
        {'s3': {'us-east-1': {'default_account': {}}}}

        >>> runtime._permissions.clear()
        >>> runtime._get_services("filename.py", '''
        ... boto3. \\
        ...     client('s3',
        ...         region_name='us-east-1'
        ...     )
        ... ''')
        >>> pprint(normalize_dict(runtime._permissions))
        {'s3': {'us-east-1': {'default_account': {}}}}

        >>> runtime._permissions.clear()
        >>> runtime._get_services("filename.py", '''
        ... boto3.
        ...     client('s3',
        ...         region_name='us-east-1', something='else'
        ...     )
        ... ''')
        >>> pprint(normalize_dict(runtime._permissions))
        {'s3': {'us-east-1': {'default_account': {}}}}

        >>> mock.mock(None, 'eprint')

        >>> runtime._permissions.clear()
        >>> runtime._get_services("filename.py", '''
        ... boto3.
        ...     client('s3',
        ...         region_name=getRegion()
        ...     )
        ... ''')
        >>> pprint(normalize_dict(runtime._permissions))
        {'s3': {'*': {'default_account': {}}}}
        >>> mock.calls_for('eprint')
        'warn: incomprehensive region: {} (in {})', "'s3',\\n        region_name=getRegion()\\n    ", 'filename.py'

        >>> runtime._permissions.clear()
        >>> runtime._get_services("filename.py", '''
        ... boto3.
        ...     client('s3',
        ...         region_name='us-' + region
        ...     )
        ... ''')
        >>> pprint(normalize_dict(runtime._permissions))
        {'s3': {'*': {'default_account': {}}}}
        >>> mock.calls_for('eprint')
        'warn: incomprehensive region: {} (in {})', "'s3',\\n        region_name='us-' + region\\n    ", 'filename.py'

        >>> runtime._permissions.clear()
        >>> runtime._get_services("filename.py", '''
        ... boto3.
        ...     client('s3',
        ...         aws_access_key_id='some key'
        ...     )
        ... ''')
        >>> pprint(normalize_dict(runtime._permissions))
        {'s3': {'default_region': {'*': {}}}}
        >>> mock.calls_for('eprint')
        'warn: unknown account: {} (in {})', "'s3',\\n        aws_access_key_id='some key'\\n    ", 'filename.py'
        """

        if not PythonRuntime.PYTHON_FILENAME_PATTERN.search(filename):
            return

        for service, pattern in PythonApi.SERVICE_CALL_PATTERNS:
            for service_match in pattern.finditer(contents):
                arguments = get_inner_parentheses(service_match.group(1))
                if arguments:
                    # region
                    region = self._get_variable_from_arguments(arguments, PythonRuntime.REGION_PATTERN)
                    if region is None:
                        region = self.provider.default_region
                    elif not region:
                        eprint("warn: incomprehensive region: {} (in {})", arguments, filename)
                        region = '*'
                    elif not any(pattern.match(region) for pattern in PythonRuntime.REGION_PATTERNS.values()):
                        eprint("warn: incomprehensive region: {} (in {})", arguments, filename)
                        region = '*'
                    # account
                    if PythonRuntime.AUTH_PATTERN.search(arguments):
                        eprint("warn: unknown account: {} (in {})", arguments, filename)
                        account = '*'
                    else:
                        account = self.provider.default_account
                else:
                    region = self.provider.default_region
                    account = self.provider.default_account

                self._permissions[service][region][account] # accessing to initialize defaultdict

    def _get_regions(filename, contents, regions, service, account):
        processor = PythonRuntime.SERVICE_REGIONS_PROCESSOR.get(service)
        if processor:
            processor(self)(filename, contents, regions, account=account)
        else:
            super()._get_regions(filename, contents, regions, service=service, account=account)

    def _get_resources(self, filename, contents, resources, region, account, service):
        processor = PythonRuntime.SERVICE_RESOURCES_PROCESSOR.get(service)
        if not processor:
            resources['*'] # accessing to initialize defaultdict
            return
        processor(self)(filename, contents, resources, region=region, account=account)

    def _get_actions(self, filename, contents, actions, service):
        if not PythonRuntime.PYTHON_FILENAME_PATTERN.search(filename):
            return

        processor = PythonApi.SERVICE_ACTIONS_PROCESSOR.get(service)
        if not processor:
            actions.add('*')
            return
        processor(self)(filename, contents, actions)

    # Helpers

    STRING_PATTERN = re.compile(r"['\"]([\w-]+)['\"]") # 'OUTPUT' or "OUTPUT"
    ENV_PATTERN = re.compile(
        r"os\.environ\[['\"](\w+)['\"]|" + # os.environ['OUTPUT']
        r"os\.environ\.get\(['\"](\w+)['\"]|" + # os.environ.get("OUTPUT") or os.environ.get("OUTPUT",
        r"os\.getenv\(['\"](\w+)['\"]" # os.getenv("OUTPUT") or os.getenv("OUTPUT",
    )
    def _get_variable_from_arguments(self, arguments, pattern):
        """ Gets value of an argument within the code

        Returns:
            1. str value if found
            2. None if argument doesn't exist
            3. '' if can't process argument value

        >>> runtime = PythonRuntime('path/to/function', resource_properties={'Environment': {'Variables': {'var': "us-west-2"}}}, provider=object())

        >>> runtime._get_variable_from_arguments('''
        ...     region_name=bla(),
        ... ''', PythonRuntime.REGION_PATTERN)
        ''

        >>> runtime._get_variable_from_arguments('''
        ...     region_name='us-east-1'
        ... ''', PythonRuntime.REGION_PATTERN)
        'us-east-1'

        >>> runtime._get_variable_from_arguments('''
        ...     region_name="us-east-1",
        ... ''', PythonRuntime.REGION_PATTERN)
        'us-east-1'

        >>> runtime._get_variable_from_arguments('''
        ...     region_name=os.environ['var']
        ... ''', PythonRuntime.REGION_PATTERN)
        'us-west-2'

        >>> runtime._get_variable_from_arguments('''
        ...     region_name=os.environ["var"],
        ... ''', PythonRuntime.REGION_PATTERN)
        'us-west-2'

        >>> runtime._get_variable_from_arguments('''
        ...     region_name=os.getenv('var')
        ... ''', PythonRuntime.REGION_PATTERN)
        'us-west-2'

        >>> runtime._get_variable_from_arguments('''
        ...     region_name=os.getenv("var"),
        ... ''', PythonRuntime.REGION_PATTERN)
        'us-west-2'

        >>> runtime._get_variable_from_arguments('''
        ...     region_name=os.getenv('var', 'default')
        ... ''', PythonRuntime.REGION_PATTERN)
        'us-west-2'

        >>> runtime._get_variable_from_arguments('''
        ...     region_name=os.environ.get('var', 'default')
        ... ''', PythonRuntime.REGION_PATTERN)
        'us-west-2'

        >>> runtime._get_variable_from_arguments('''
        ...     region_name=os.environ.get('var2', 'default')
        ... ''', PythonRuntime.REGION_PATTERN)
        ''
        """
        match = pattern.search(arguments)
        if not match:
            return None

        value = match.group(1)
        match = PythonRuntime.STRING_PATTERN.match(value)
        if match:
            return match.group(1)

        match = PythonRuntime.ENV_PATTERN.match(value)
        if match:
            return self.environment_variables.get(next(g for g in match.groups() if g), '')

        return ''

Runtime = PythonRuntime

