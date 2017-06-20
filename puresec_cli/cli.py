#!/usr/bin/env python3

import sys

if sys.version_info.major != 3:
    print("Sorry, requires Python 3.x")
    sys.exit(1)

from argparse import ArgumentParser
from importlib import import_module
from puresec_cli import actions

def main(argv=None):
    parser = ArgumentParser(
        description="Set of wonderful tools to improve your serverless security (and social life)."
    )

    subparsers = parser.add_subparsers(title="Available commands")

    for action_name in actions.__all__:
        action = import_module("puresec_cli.actions.{}.action".format(action_name)).Action

        subparser = subparsers.add_parser(action.command(), **action.argument_parser_options())
        action.add_arguments(subparser)
        subparser.set_defaults(action=action)

    args = parser.parse_args()
    if hasattr(args, 'action'):
        action = args.action(args)
        action.run()
    else:
        parser.print_usage()

if __name__ == '__main__':
    main()

