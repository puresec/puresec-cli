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
        with open(config_path, 'rb') as config_file:
            config = yaml.load(config_file)
    else:
        config = {}

    yield config

    with open(config_path, 'wb') as config_file:
        yaml.dump(config_file)

@contextmanager
def generate_framework(args, config):
    if not args.framework:
        yield None
    else:
        with import_module(args.framework, 'lib.frameworks').Handler(args.path, config=config) as framework:
            yield framework

@contextmanager
def generate_provider(args, framework, config):
    with import_module(args.provider, 'lib.providers').Handler(args.path, resource_template=args.resource_template, framework=framework, config=config) as provider:
        yield provider

def main():
    args = arguments.parser.parse_args()

    with generate_config(args) as config:
        with generate_framework(args, config) as framework:
            with generate_provider(args, framework, config) as provider:
                provider.process()
                # TODO: output

if __name__ == '__main__':
    main()
