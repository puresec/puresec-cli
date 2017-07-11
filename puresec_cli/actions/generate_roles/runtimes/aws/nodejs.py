import pkg_resources
import os
import re
import subprocess

from puresec_cli.utils import eprint, get_inner_parentheses
from puresec_cli.actions.generate_roles.runtimes.aws.base import Base
from puresec_cli.actions.generate_roles.runtimes.aws.nodejs_api import NodejsApi

class NodejsRuntime(Base, NodejsApi):
    JAVASCRIPT_FILENAME_PATTERN = re.compile(r"\.js$", re.IGNORECASE)

    def _walk(self, processor, *args, **kwargs):
        """
        >>> from collections import namedtuple
        >>> from tests.mock import Mock
        >>> mock = Mock(__name__)

        >>> mock.mock(pkg_resources, 'resource_filename', "/path/to/node_modules")

        >>> processed = []
        >>> def processor(filename, contents, custom_positional, custom_keyword):
        ...     processed.append((filename, contents, custom_positional, custom_keyword))

        >>> def stat(self, filename):
        ...     return namedtuple('Stat', ('st_size',))(5*1024*1024 if filename == "/path/to/function/large-file" else 512)
        >>> mock.mock(NodejsRuntime, '_stat', stat)

        >>> mock.filesystem = {'': {'path': {'to': {'function': {
        ...     'large-file': True,
        ...     'config': True,
        ...     'unreferenced': True,
        ... }}}}}
        >>> with mock.open("/path/to/function/config", 'w') as f:
        ...     f.write("some config") and None
        >>> with mock.open("/path/to/function/src/index.js", 'w') as f:
        ...     f.write("some code config large-file more code") and None

        >>> mock.mock(subprocess, 'check_output', b"/path/to/function/src/index.js\\n")
        >>> NodejsRuntime('/path/to/function', resource_properties={'Handler': "src/index.handler"}, provider=object()) \\
        ...     ._walk(processor, 'positional', custom_keyword='keyword')
        >>> mock.calls_for('subprocess.check_output')
        ['node', '/path/to/node_modules/dependency-tree/bin/cli.js', '/path/to/function/src/index.js', '--directory', '/path/to/function', '--list-form'], stderr=-2
        >>> processed
        [('/path/to/function/src/index.js', 'some code config large-file more code', 'positional', 'keyword'),
         ('/path/to/function/config', 'some config', 'positional', 'keyword')]
        """

        if hasattr(self, '_dependencies'):
            # cached
            for filename in self._dependencies:
                with open(filename, 'r', errors='replace') as file:
                    processor(filename, file.read(), *args, **kwargs)
            return

        # getting main JavaScript file (from Handler)
        handler = self.resource_properties.get('Handler')
        if not handler:
            # dummy CloudFormation? walking everything
            super()._walk(processor, *args, **kwargs)
            return
        module = '.'.join(handler.split('.')[0:-1]) # all except the last part which is the method
        filename = os.path.abspath(os.path.join(self.root, "{}.js".format(module)))
        if not os.path.exists(filename):
            return

        # acquiring dependencies using NPM's dependency-tree
        dependency_tree_cli_path = os.path.abspath(os.path.join(pkg_resources.resource_filename('puresec_cli', 'resources/node_modules'), 'dependency-tree/bin/cli.js'))
        try:
            dependencies = subprocess.check_output(['node', dependency_tree_cli_path, filename, '--directory', self.root, '--list-form'], stderr=subprocess.STDOUT)
        except FileNotFoundError:
            eprint("error: function runtime (nodejs) must be installed")
            raise SystemExit(-1)
        except subprocess.CalledProcessError as e:
            eprint("error: failed to get dependency tree:\n{}", e.output.decode())
            raise SystemExit(-1)

        dependencies = [
            dependency for dependency in dependencies.decode().split('\n')
            # skipping last blank line and aws-sdk
            if dependency and '/node_modules/aws-sdk/' not in dependency
        ]
        self._dependencies = dependencies[:] # cache

        # getting all non-dependency files
        resources = [] # (abspath, filename)
        for path, dirs, filenames in os.walk(self.root):
            if path.endswith('node_modules'):
                # skipping aws-sdk
                try:
                    dirs.remove('aws-sdk')
                except ValueError:
                    pass

            paths_generator = (
                (os.path.abspath(os.path.join(path, filename)), filename)
                for filename in filenames
                if not NodejsRuntime.JAVASCRIPT_FILENAME_PATTERN.search(filename)
            )
            resources.extend(
                paths_tuple for paths_tuple in paths_generator
                if self._stat(paths_tuple[0]).st_size < NodejsRuntime.MAX_FILE_SIZE
            )

        while dependencies:
            filename = dependencies.pop(0)
            with open(filename, 'r', errors='replace') as file:
                # adding resources referenced by current file
                used_resources_indexes = []
                contents = file.read()
                for index, (resource_abspath, resource_filename) in enumerate(resources):
                    if resource_filename in contents:
                        dependencies.append(resource_abspath)
                        self._dependencies.append(resource_abspath)
                        used_resources_indexes.append(index)
                for index in reversed(used_resources_indexes):
                    resources.pop(index)
                # processing current file
                processor(filename, contents, *args, **kwargs)

    # Processors

    SERVICE_REGIONS_PROCESSOR = {
        # service: lambda self: function(self, filename, contents, regions, account)
    }

    # Argument patterns
    ARGUMENT_PATTERN_TEMPLATE = r"['\"]?\b{}['\"]?\s*:\s*([^\s].*?)\s*(?:[,}}]|\Z)" # "VALUE": OUTPUT, or 'VALUE': OUTPUT} or VALUE: OUTPUT
    REGION_PATTERN = re.compile(ARGUMENT_PATTERN_TEMPLATE.format('region'), re.MULTILINE)
    AUTH_PATTERN = re.compile(r"accessKeyId|secretAccessKey|sessionToken|credentials")
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

        >>> runtime = NodejsRuntime('path/to/function', resource_properties={}, provider=provider)

        >>> runtime._get_services("filename.txt", ".S3()")
        >>> pprint(normalize_dict(runtime._permissions))
        {}

        >>> runtime._get_services("filename.js", ".S3()")
        >>> pprint(normalize_dict(runtime._permissions))
        {'s3': {'default_region': {'default_account': {}}}}
        >>> runtime._permissions.clear()

        >>> runtime._get_services("filename.js", ".S3({ region: 'us-east-1' })")
        >>> pprint(normalize_dict(runtime._permissions))
        {'s3': {'us-east-1': {'default_account': {}}}}

        >>> runtime._permissions.clear()
        >>> runtime._get_services("filename.js", '''
        ... aws.
        ...     S3({
        ...         region: 'us-east-1'
        ...     })
        ... ''')
        >>> pprint(normalize_dict(runtime._permissions))
        {'s3': {'us-east-1': {'default_account': {}}}}

        >>> runtime._permissions.clear()
        >>> runtime._get_services("filename.js", '''
        ... aws.
        ...     S3({
        ...         region: 'us-east-1', something: 'else'
        ...     })
        ... ''')
        >>> pprint(normalize_dict(runtime._permissions))
        {'s3': {'us-east-1': {'default_account': {}}}}

        >>> mock.mock(None, 'eprint')

        >>> runtime._permissions.clear()
        >>> runtime._get_services("filename.js", '''
        ... aws.
        ...     S3({
        ...         region: getRegion()
        ...     })
        ... ''')
        >>> pprint(normalize_dict(runtime._permissions))
        {'s3': {'*': {'default_account': {}}}}
        >>> mock.calls_for('eprint')
        "warn: incomprehensive region: {} (in {}), falling back to '*'", '{\\n        region: getRegion()\\n    }', 'filename.js'

        >>> runtime._permissions.clear()
        >>> runtime._get_services("filename.js", '''
        ... aws.
        ...     S3({
        ...         region: 'us-' + region
        ...     })
        ... ''')
        >>> pprint(normalize_dict(runtime._permissions))
        {'s3': {'*': {'default_account': {}}}}
        >>> mock.calls_for('eprint')
        "warn: incomprehensive region: {} (in {}), falling back to '*'", "{\\n        region: 'us-' + region\\n    }", 'filename.js'

        >>> runtime._permissions.clear()
        >>> runtime._get_services("filename.js", '''
        ... aws.
        ...     S3({
        ...         accessKeyId: "some key"
        ...     })
        ... ''')
        >>> pprint(normalize_dict(runtime._permissions))
        {'s3': {'default_region': {'*': {}}}}
        >>> mock.calls_for('eprint')
        "warn: unknown account: {} (in {}), falling back to '*'", '{\\n        accessKeyId: "some key"\\n    }', 'filename.js'
        """

        if not NodejsRuntime.JAVASCRIPT_FILENAME_PATTERN.search(filename):
            return

        for service, pattern in NodejsApi.SERVICE_CALL_PATTERNS:
            for service_match in pattern.finditer(contents):
                arguments = get_inner_parentheses(service_match.group(1))
                if arguments:
                    # region
                    region = self._get_variable_from_arguments(arguments, NodejsRuntime.REGION_PATTERN)
                    if region is None:
                        region = self.provider.default_region
                    elif not region:
                        eprint("warn: incomprehensive region: {} (in {}), falling back to '*'", arguments, filename)
                        region = '*'
                    elif not any(pattern.match(region) for pattern in NodejsRuntime.REGION_PATTERNS.values()):
                        eprint("warn: incomprehensive region: {} (in {}), falling back to '*'", arguments, filename)
                        region = '*'
                    # account
                    if NodejsRuntime.AUTH_PATTERN.search(arguments):
                        eprint("warn: unknown account: {} (in {}), falling back to '*'", arguments, filename)
                        account = '*'
                    else:
                        account = self.provider.default_account
                else:
                    region = self.provider.default_region
                    account = self.provider.default_account

                self._permissions[service][region][account] # accessing to initialize defaultdict

    def _get_regions(filename, contents, regions, service, account):
        processor = NodejsRuntime.SERVICE_REGIONS_PROCESSOR.get(service)
        if processor:
            processor(self)(filename, contents, regions, account=account)
        else:
            super()._get_regions(filename, contents, regions, service=service, account=account)

    def _get_resources(self, filename, contents, resources, region, account, service):
        processor = NodejsRuntime.SERVICE_RESOURCES_PROCESSOR.get(service)
        if not processor:
            resources['*'] # accessing to initialize defaultdict
            return
        processor(self)(filename, contents, resources, region=region, account=account)

    def _get_actions(self, filename, contents, actions, service):
        if not NodejsRuntime.JAVASCRIPT_FILENAME_PATTERN.search(filename):
            return

        processor = NodejsApi.SERVICE_ACTIONS_PROCESSOR.get(service)
        if not processor:
            actions.add('*')
            return
        processor(self)(filename, contents, actions)

    # Helpers

    STRING_PATTERN = re.compile(r"['\"]([\w-]+)['\"]") # 'VALUE' or "VALUE"
    ENV_PATTERN = re.compile(r"process\.env(?:\.|\[['\"])(\w+)(?:['\"]\])?") # process.env.VALUE or process.env['VALUE'] or process.env["VALUE"]
    def _get_variable_from_arguments(self, arguments, pattern):
        """ Gets value of an argument within the code

        Returns:
            1. str value if found
            2. None if argument doesn't exist
            3. '' if can't process argument value

        >>> runtime = NodejsRuntime('path/to/function', resource_properties={'Environment': {'Variables': {'var': "us-west-2"}}}, provider=object())

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
            return self.environment_variables.get(match.group(1), '')

        return ''

Runtime = NodejsRuntime

