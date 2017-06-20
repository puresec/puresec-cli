from collections import defaultdict
from puresec_cli.utils import eprinted
from uuid import uuid4
import analytics
import os
import puresec_cli
import sys
import traceback

analytics.write_key = 'CnRP4aqeHLvdTdS9nOAzdEtnQz5c2w74'

class Stats:
    """ Singleton object in charge of sending anonymous statistics.

    Only known-values are sent, no paths or names. More specifically:
    * Providers, frameworks, runtimes, and formats (which can only be from a list of accepted values)
    * Whether or not arguments were set and how many (and not their actual values)
    * Exceptions with traceback
    * Warnings without dynamic variables (only the message format)
    * Package version and Python version

    Sent events are:
    * Enabling/disabling anonymous statistics
    * Upon run completion (once per run)

    All events are sent with an anonymous unique identifier saved under `~/.puresec`.

    Thank you for your help!
    """

    CONFIG_DIRECTORY = os.path.expanduser('~/.puresec')
    ENABLED_PATH = os.path.join(CONFIG_DIRECTORY, 'stats-enabled')
    DISABLED_PATH = os.path.join(CONFIG_DIRECTORY, 'stats-disabled')

    instance = None
    def __new__(cls):
        if not Stats.instance:
            Stats.instance = super().__new__(cls)
        return Stats.instance

    def __init__(self):
        self.args = None
        self.providers = []
        self.frameworks = []
        self.disabled = os.path.exists(Stats.DISABLED_PATH)
        self.anonymous_user_id = None

    def generate_anonymous_user_id(self):
        """
        >>> from tests.mock import Mock
        >>> mock = Mock(__name__)
        >>> mock.mock(os, 'makedirs')
        >>> mock.mock(None, 'uuid4', 'generated-uuid')

        >>> Stats.CONFIG_DIRECTORY = "/path/to/config"

        >>> Stats.instance = None
        >>> stats = Stats()
        >>> stats.anonymous_user_id = "exists"
        >>> stats.generate_anonymous_user_id()
        >>> stats.anonymous_user_id
        'exists'
        >>> mock.calls_for('os.makedirs')

        >>> Stats.instance = None
        >>> stats = Stats()
        >>> stats.disabled = False
        >>> stats.generate_anonymous_user_id()
        >>> stats.anonymous_user_id
        'generated-uuid'
        >>> mock.calls_for('os.makedirs')
        '/path/to/config', exist_ok=True
        >>> with mock.open(Stats.ENABLED_PATH, 'r') as f:
        ...     f.read()
        'generated-uuid'
        >>> mock.exists(Stats.DISABLED_PATH)
        False

        >>> Stats.instance = None
        >>> stats = Stats()
        >>> stats.generate_anonymous_user_id()
        >>> stats.anonymous_user_id
        'generated-uuid'
        >>> mock.calls_for('os.makedirs')
        >>> with mock.open(Stats.ENABLED_PATH, 'r') as f:
        ...     f.read()
        'generated-uuid'
        >>> mock.exists(Stats.DISABLED_PATH)
        False

        >>> mock.clear_filesystem()
        >>> Stats.instance = None
        >>> stats = Stats()
        >>> stats.disabled = True
        >>> with mock.open(Stats.DISABLED_PATH, 'w') as f:
        ...     f.write('disabled-uuid') and None
        >>> stats.generate_anonymous_user_id()
        >>> stats.anonymous_user_id
        'disabled-uuid'
        >>> mock.calls_for('os.makedirs')
        >>> with mock.open(Stats.DISABLED_PATH, 'r') as f:
        ...     f.read()
        'disabled-uuid'
        >>> mock.exists(Stats.ENABLED_PATH)
        False
        """

        if self.anonymous_user_id is not None:
            return

        if not self.disabled:
            if not os.path.exists(Stats.ENABLED_PATH):
                self.anonymous_user_id = str(uuid4()) # uuid1 compromises privacy
                os.makedirs(Stats.CONFIG_DIRECTORY, exist_ok=True)
                with open(Stats.ENABLED_PATH, 'w') as f:
                    f.write(self.anonymous_user_id)
            else:
                with open(Stats.ENABLED_PATH, 'r') as f:
                    self.anonymous_user_id = f.read()
        else:
            with open(Stats.DISABLED_PATH, 'r') as f:
                self.anonymous_user_id = f.read() # just in case you decide to enable

    def enable(self):
        """
        >>> from tests.mock import Mock
        >>> mock = Mock(__name__)
        >>> mock.mock(os, 'rename')

        >>> Stats.ENABLED_PATH = '/path/to/enabled'
        >>> Stats.DISABLED_PATH = '/path/to/disabled'

        >>> Stats.instance = None
        >>> stats = Stats()
        >>> mock.mock(stats, '_send')
        >>> stats.anonymous_user_id = 'uuid'

        >>> stats.disabled = False
        >>> stats.enable()
        >>> stats.disabled
        False
        >>> mock.calls_for('os.rename')
        >>> mock.calls_for('Stats._send')
        'Enable stats', {'was_disabled': False}

        >>> stats.disabled = True
        >>> stats.enable()
        >>> stats.disabled
        False
        >>> mock.calls_for('os.rename')
        '/path/to/disabled', '/path/to/enabled'
        >>> mock.calls_for('Stats._send')
        'Enable stats', {'was_disabled': True}
        """

        self.generate_anonymous_user_id()

        if self.disabled:
            os.rename(Stats.DISABLED_PATH, Stats.ENABLED_PATH)

        # thank you for your help
        self._send('Enable stats', {'was_disabled': self.disabled})

        self.disabled = False

    def disable(self):
        """
        >>> from tests.mock import Mock
        >>> mock = Mock(__name__)
        >>> mock.mock(os, 'rename')

        >>> Stats.ENABLED_PATH = '/path/to/enabled'
        >>> Stats.DISABLED_PATH = '/path/to/disabled'

        >>> Stats.instance = None
        >>> stats = Stats()
        >>> mock.mock(stats, '_send')
        >>> stats.anonymous_user_id = 'uuid'

        >>> stats.disabled = True
        >>> stats.disable()
        >>> stats.disabled
        True
        >>> mock.calls_for('os.rename')
        >>> mock.calls_for('Stats._send')
        'Disable stats', {'was_disabled': True}

        >>> stats.disabled = False
        >>> stats.disable()
        >>> stats.disabled
        True
        >>> mock.calls_for('os.rename')
        '/path/to/enabled', '/path/to/disabled'
        >>> mock.calls_for('Stats._send')
        'Disable stats', {'was_disabled': False}
        """

        self.generate_anonymous_user_id()

        if not self.disabled:
            os.rename(Stats.ENABLED_PATH, Stats.DISABLED_PATH)

        # one last time!
        self._send('Disable stats', {'was_disabled': self.disabled})

        self.disabled = True

    ACTIONS = {
        'enable': enable,
        'disable': disable,
    }

    def toggle(self, value):
        Stats.ACTIONS[value](self)

    KNOWN_RUNTIMES = {'python', 'java', 'nodejs', 'javascript', 'ruby', 'c#', 'f#', 'php', 'bash', 'batch', 'powershell', 'go'}

    def result(self, action, message):
        """
        >>> from tests.mock import Mock
        >>> mock = Mock(__name__)

        >>> Stats.instance = None
        >>> stats = Stats()
        >>> mock.mock(stats, '_send')

        >>> class Action:
        ...     def command(self):
        ...         return "some-command"
        >>> action = Action()

        >>> stats.disabled = True
        >>> stats.result(action, "Some result")
        >>> mock.calls_for('Stats._send')

        >>> stats.disabled = False
        >>> stats.anonymous_user_id = 'uuid'

        >>> class Args: pass
        >>> stats.args = Args()
        >>> stats.args.__dict__ = {
        ...     'path': ['one/path', 'two/path'],
        ...     'provider': 'aws',
        ...     'resource_template': "path/to/cloudformation.json",
        ...     'runtime': 'nodejs',
        ...     'framework': 'serverless',
        ...     'framework_path': "path/to/sls",
        ...     'function': 'someFunction',
        ...     'format': 'json',
        ... }
        >>> class SomeProvider:
        ...     def __init__(self, runtimes):
        ...         self.runtimes = runtimes
        >>> stats.providers.append(SomeProvider(runtimes={'nodejs': 2, 'python': 3, 'unknown': 10}))
        >>> stats.providers.append(SomeProvider(runtimes={'python': 1, 'java': 6}))
        >>> class SomeFramework: pass
        >>> stats.frameworks.append(SomeFramework())
        >>> stats.frameworks.append(SomeFramework())
        >>> mock.mock(None, 'eprinted', ['warning1', 'warning2'])

        >>> stats.result(action, "Successful run")
        >>> mock.calls_for('Stats._send')
        'Successful run', {'arguments': {'command': 'some-command',
                       'format': 'json',
                       'framework': 'serverless',
                       'framework_path': True,
                       'function': True,
                       'path': 2,
                       'provider': 'aws',
                       'resource_template': True,
                       'runtime': 'nodejs'},
         'environment': {'framework': 'SomeFramework',
                         'provider': 'SomeProvider',
                         'runtimes': {'java': 6, 'nodejs': 2, 'python': 4}},
         'eprinted': ['warning1', 'warning2'],
         'exception': None}

        >>> try:
        ...     raise FileNotFoundError("some/file")
        ... except:
        ...     stats.result(action, "Unexpected error")
        >>> mock.calls_for('Stats._send')
        'Unexpected error', {'arguments': {'command': 'some-command',
                       'format': 'json',
                       'framework': 'serverless',
                       'framework_path': True,
                       'function': True,
                       'path': 2,
                       'provider': 'aws',
                       'resource_template': True,
                       'runtime': 'nodejs'},
         'environment': {'framework': 'SomeFramework',
                         'provider': 'SomeProvider',
                         'runtimes': {'java': 6, 'nodejs': 2, 'python': 4}},
         'eprinted': ['warning1', 'warning2'],
         'exception': 'Traceback (most recent call last):\\n'
            ...
                      'FileNotFoundError: some/file\\n'}
        """

        if self.disabled:
            return

        self.generate_anonymous_user_id()

        runtimes = defaultdict(int)
        for provider in self.providers:
            for runtime, count in provider.runtimes.items():
                if runtime in Stats.KNOWN_RUNTIMES:
                    runtimes[runtime] += count

        self._send(message, {
            'arguments': {
                'command': action.command(),
                # TODO: action-specific
                'path': len(self.args.path),
                'provider': self.args.provider,
                'resource_template': bool(self.args.resource_template),
                'runtime': self.args.runtime,
                'framework': self.args.framework,
                'framework_path': bool(self.args.framework_path),
                'function': bool(self.args.function),
                'yes': self.args.yes,
            },
            'environment': {
                'provider': type(self.providers[0]).__name__ if self.providers else None,
                'runtimes': dict(runtimes),
                'framework': type(self.frameworks[0]).__name__ if self.frameworks else None,
            },
            'exception': traceback.format_exc() if sys.exc_info()[0] else None,
            'eprinted': eprinted,
        })

    def _send(self, message, payload):
        payload['execution'] = {
            'version': puresec_cli.__version__,
            'python_version': sys.version,
        }
        analytics.track(self.anonymous_user_id, message, payload)

