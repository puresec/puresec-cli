"""
Use puresec_cli.stats, not puresec_cli.stats.Stats.
"""

from collections import defaultdict
from uuid import uuid4
import analytics
import os
import sys
import traceback
import re

import puresec_cli

analytics.write_key = ''

ANONYMIZED_VALUE = "<ANONYMIZED>"

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
        self.disabled = os.path.exists(Stats.DISABLED_PATH)
        self.anonymous_user_id = None

        def defaultdict_defaultdict():
            return defaultdict(defaultdict_defaultdict)
        self.payload = defaultdict_defaultdict()

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
    EXCEPTION_FILE_PATTERN = re.compile(r'  File "/.*?/([^\/]*)", line')
    EXCEPTION_FILE_REPLACEMENT = r'File "/{}/\1", line'.format(ANONYMIZED_VALUE)

    def result(self, message):
        """
        >>> from tests.mock import Mock
        >>> mock = Mock(__name__)

        >>> Stats.instance = None
        >>> stats = Stats()
        >>> mock.mock(stats, '_send')

        >>> stats.disabled = True
        >>> stats.result("Some result")
        >>> mock.calls_for('Stats._send')

        >>> stats.disabled = False
        >>> stats.anonymous_user_id = 'uuid'
        >>> stats.payload = {'some': 'payload'}

        >>> stats.result("Successful run")
        >>> mock.calls_for('Stats._send')
        'Successful run', {'some': 'payload'}

        >>> from puresec_cli.utils import eprint
        >>> try:
        ...     raise FileNotFoundError("some/file")
        ... except:
        ...     stats.result("Unexpected error")
        >>> # NOTE: this will fail if utils.py changes, don't worry just update the line number
        >>> mock.calls_for('Stats._send')
        'Unexpected error',
        {'exception': 'Traceback (most recent call last):\\n'
            ...
                      'FileNotFoundError: some/file\\n',
         'some': 'payload'}
        """

        if self.disabled:
            return

        self.generate_anonymous_user_id()
        if sys.exc_info()[0]:
            self.payload['exception'] = Stats.EXCEPTION_FILE_PATTERN.sub(Stats.EXCEPTION_FILE_REPLACEMENT, traceback.format_exc())
        self._send(message, self.payload)

    def _send(self, message, payload):
        payload['execution'] = {
            'version': puresec_cli.__version__,
            'python_version': sys.version,
        }
        analytics.track(self.anonymous_user_id, message, payload)

stats = Stats()

