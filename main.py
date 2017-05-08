#!/usr/bin/env python3

from contextlib import contextmanager
from importlib import import_module
import argparse
import os
import yaml

@contextmanager
def generate_config(args):
    config_path = os.path.join(args.code_path, "puresec-least-privilege.yml")
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
        with import_module(args.framework, 'frameworks').Handler(args.code_path, config=config) as framework:
            yield framework

@contextmanager
def generate_provider(args, framework, config):
    with import_module(args.provider, 'providers').Handler(args.code_path, resource_template=args.resource_template, framework=framework, config=config) as provider:
        yield provider

def main():
    parser = argparse.ArgumentParser(description="PureSec Least Privilege Role Creator")
    parser.add_argument('code_path', nargs='?', default=os.getcwd(),
                        help="Path to base directory for functions code")
    parser.add_argument('--framework', '-f', default='none', choices=['none', 'serverless'],
                        help="Framework used for deploying")
    parser.add_argument('--provider', '-p', choices=['aws'], required=True,
                        help="Name of the cloud provider")
    parser.add_argument('--resource-template', '-t',
                        help="Provider-specific resource template (e.g CloudFormation JSON for AWS)")

    args = parser.parse_args()

    with generate_config(args) as config:
        with generate_framework(args, config) as framework:
            with generate_provider(args, framework, config) as provider:
                provider.process()
                # TODO: output

if __name__ == "__main__":
    main()
