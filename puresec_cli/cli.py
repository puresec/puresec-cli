#!/usr/bin/env python3

import sys

if sys.version_info.major != 3:
    print("Sorry, requires Python 3.x")
    sys.exit(1)

from argparse import ArgumentParser
from importlib import import_module
from urllib import request
import urllib.error
import json

from puresec_cli import actions
from puresec_cli.utils import eprint
from puresec_cli.stats import Stats
import puresec_cli

def check_version():
    try:
        response = request.urlopen("http://cli.puresec.io/verify/version/{}".format(puresec_cli.__version__))
    except urllib.error.URLError:
        return

    try:
        response = json.loads(response.read().decode())
    except ValueError:
        return

    if not isinstance(response, dict):
        return

    try:
        is_uptodate, last_version = response['is_uptodate'], response['last_version']
    except KeyError:
        return

    if not is_uptodate:
        eprint("warn: you are using an outdated version of PureSec CLI (installed={}, latest={})".format(puresec_cli.__version__, last_version))

def main(argv=None):
    check_version()

    parser = ArgumentParser(
        description="PureSec CLI tools for improving the security of your serverless applications."
    )

    parser.add_argument('--stats', choices=['enable', 'disable'],
                        help="Enable/disable sending anonymous statistics (on by default)")


    subparsers = parser.add_subparsers(title="Available commands")

    for action_name in actions.__all__:
        action = import_module("puresec_cli.actions.{}.action".format(action_name)).Action

        subparser = subparsers.add_parser(action.command(), **action.argument_parser_options())
        action.add_arguments(subparser)
        subparser.set_defaults(action=action)

    args = parser.parse_args()

    stats = Stats()
    stats.args = args

    ran = False

    if args.stats:
        ran = True
        stats.toggle(args.stats)

    if hasattr(args, 'action'):
        ran = True
        try:
            action = args.action(args, stats)
            action.run()
        except SystemExit:
            stats.result(action, 'Expected error')
            raise
        except Exception:
            stats.result(action, 'Unexpected error')
            raise
        else:
            stats.result(action, 'Successful run')

    if not ran:
        parser.print_usage()

if __name__ == '__main__':
    main()

