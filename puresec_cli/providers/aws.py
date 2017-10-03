import abc
import aws_parsecf
import boto3
import botocore
import os

from puresec_cli.utils import eprint

class Aws:
    __metaclass__ = abc.ABCMeta

    def __init__(self, resource_template=None, framework=None):
        """
        >>> class Framework:
        ...     def get_resource_template(self):
        ...         return "path/to/resource_template"

        >>> Aws().resource_template

        >>> Aws(resource_template="path/to/resource_template").resource_template
        'path/to/resource_template'
        >>> Aws(framework=Framework()).resource_template
        'path/to/resource_template'
        >>> Aws(resource_template="path/to/custom_resource_template", framework=Framework()).resource_template
        'path/to/custom_resource_template'
        """

        self.resource_template = resource_template
        self.framework = framework

        if not self.resource_template and self.framework:
            self.resource_template = self.framework.get_resource_template()

    @property
    def session(self):
        """
        >>> from tests.mock import Mock
        >>> mock = Mock(__name__)
        >>> mock.mock(None, 'eprint')

        >>> class Framework:
        ...     def get_default_profile(self):
        ...         return "default_profile"

        >>> with mock.open("path/to/cloudformation.json", 'w') as f:
        ...     f.write('{"a": {"b": 1}}') and None

        >>> Aws(resource_template="path/to/cloudformation.json").session
        Session(...)

        >>> Aws(resource_template="path/to/cloudformation.json", framework=Framework()).session
        Traceback (most recent call last):
        SystemExit: -1
        >>> mock.calls_for('eprint')
        'error: failed to create aws session:\\n{}', ProfileNotFound('The config profile (default_profile) could not be found',)
        """

        if not hasattr(self, '_session'):
            if self.framework:
                profile = self.framework.get_default_profile()
            else:
                profile = None

            try:
                self._session = boto3.Session(profile_name=profile)
            except (botocore.exceptions.BotoCoreError, botocore.exceptions.ClientError) as e:
                eprint("error: failed to create aws session:\n{}", e)
                raise SystemExit(-1)
        return self._session

    @property
    def default_region(self):
        """
        >>> from tests.mock import Mock
        >>> mock = Mock(__name__)
        >>> mock.mock(None, 'eprint')

        >>> class Framework:
        ...     def __init__(self, has_default_region):
        ...         self.has_default_region = has_default_region
        ...     def get_default_region(self):
        ...         return "framework-region" if self.has_default_region else None

        >>> with mock.open("path/to/cloudformation.json", 'w') as f:
        ...     f.write('{}') and None

        >>> Aws(resource_template="path/to/cloudformation.json", framework=Framework(True)).default_region
        'framework-region'

        >>> mock.mock(Aws, 'session', boto3.Session(region_name='session-region'))

        >>> Aws(resource_template="path/to/cloudformation.json", framework=Framework(False)).default_region
        'session-region'
        >>> Aws(resource_template="path/to/cloudformation.json").default_region
        'session-region'

        >>> mock.mock(Aws, 'session', boto3.Session(region_name=''))
        >>> Aws(resource_template="path/to/cloudformation.json", framework=Framework(False)).default_region
        '*'
        >>> Aws(resource_template="path/to/cloudformation.json").default_region
        '*'
        """

        if not hasattr(self, '_default_region'):
            self._default_region = None
            # from framework
            if self.framework:
                self._default_region = self.framework.get_default_region()
            # from default config (or ENV)
            if not self._default_region:
                self._default_region = self.session.region_name

            if not self._default_region:
                self._default_region = '*'
        return self._default_region

    @property
    def default_account(self):
        if not hasattr(self, '_default_account'):
            try:
                self._default_account = self.session.client('sts').get_caller_identity()['Account']
            except (botocore.exceptions.BotoCoreError, botocore.exceptions.ClientError) as e:
                eprint("error: failed to get account from aws:\n{}", e)
                raise SystemExit(-1)
        return self._default_account

    TEMPLATE_LOADERS = {
        '.json': aws_parsecf.load_json,
        '.yaml': aws_parsecf.load_yaml,
        '.yml': aws_parsecf.load_yaml,
    }

    @property
    def cloudformation_template(self):
        """
        >>> from tests.mock import Mock
        >>> mock = Mock(__name__)
        >>> mock.mock(None, 'eprint')

        >>> Aws(resource_template="path/to/cloudformation.json").cloudformation_template
        Traceback (most recent call last):
        SystemExit: 2
        >>> mock.calls_for('eprint')
        'error: could not find CloudFormation template in: {}', 'path/to/cloudformation.json'

        >>> with mock.open("path/to/cloudformation.json", 'w') as f:
        ...     f.write("not a JSON") and None
        >>> Aws(resource_template="path/to/cloudformation.json").cloudformation_template
        Traceback (most recent call last):
        SystemExit: -1
        >>> mock.calls_for('eprint') # ValueError for <=3.4, JSONDecodeError for >=3.5
        'error: invalid CloudFormation template:\\n{}', ...Error('Expecting value: line 1 column 1 (char 0)',)

        >>> with mock.open("path/to/cloudformation.json", 'w') as f:
        ...     f.write('{ "a": { "b": 1 } }') and None
        >>> Aws(resource_template="path/to/cloudformation.json").cloudformation_template
        {'a': {'b': 1}}
        """

        if not hasattr(self, '_cloudformation_template'):
            if not self.resource_template:
                self._cloudformation_template = None
                self.cloudformation_filetype = None
                return

            _, self.cloudformation_filetype = os.path.splitext(self.resource_template)

            if self.cloudformation_filetype not in Aws.TEMPLATE_LOADERS:
                eprint("error: don't know how to load '{}' file", self.resource_template)
                raise SystemExit(2)

            try:
                resource_template = open(self.resource_template, 'r', errors='replace')
            except FileNotFoundError:
                eprint("error: could not find CloudFormation template in: {}", self.resource_template)
                raise SystemExit(2)

            with resource_template:
                try:
                    self._cloudformation_template = Aws.TEMPLATE_LOADERS[self.cloudformation_filetype](resource_template, default_region=self.default_region)
                except ValueError as e:
                    eprint("error: invalid CloudFormation template:\n{}", e)
                    raise SystemExit(-1)
        return self._cloudformation_template

