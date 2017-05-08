#!/usr/bin/env python3

from contextlib import contextmanager
from importlib import import_module
from lib import arguments
import os
import yaml

@contextmanager
def generate_config(args):
    config_path = os.path.join(args.path, "puresec-least-privilege.yml")
    if os.path.isfile(config_path):
        with open(config_path, 'r') as config_file:
            config = yaml.load(config_file)
    else:
        config = {}

    yield config

    with open(config_path, 'w') as config_file:
        yaml.dump(config, config_file, default_flow_style=False)

@contextmanager
def generate_framework(args, config):
    if not args.framework:
        yield None
    else:
        with import_module("lib.frameworks.{}".format(args.framework)).Handler(args.path, config=config) as framework:
            yield framework

@contextmanager
def generate_provider(args, framework, config):
    with import_module("lib.providers.{}".format(args.provider)).Handler(args.path, resource_template=args.resource_template, framework=framework, config=config) as provider:
        yield provider

def main(argv=None):
    args = arguments.parser.parse_args(argv)

    with generate_config(args) as config:
        with generate_framework(args, config) as framework:
            with generate_provider(args, framework, config) as provider:
                provider.process()
                # TODO: output

if __name__ == '__main__':
    main()
