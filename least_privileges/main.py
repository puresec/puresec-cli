from contextlib import contextmanager
from importlib import import_module
from lib import arguments, providers
from lib.utils import eprint
import os
import yaml

@contextmanager
def generate_config(path, args):
    config_path = os.path.join(path, "least-privileges.yml")
    if os.path.isfile(config_path):
        with open(config_path, 'r', errors='replace') as config_file:
            config = yaml.load(config_file)
    else:
        config = {}

    yield config

    with open(config_path, 'w', errors='replace') as config_file:
        yaml.dump(config, config_file, default_flow_style=False)

@contextmanager
def generate_framework(path, args, config):
    if not args.framework:
        yield None
    else:
        with import_module("lib.frameworks.{}".format(args.framework)).Framework(path, executable=args.framework_path, config=config) as framework:
            yield framework

@contextmanager
def generate_provider(path, args, framework, config):
    if framework:
        provider = framework.get_provider_name()
        if provider:
            if args.provider:
                # args.provider always in providers.__all__, no need to check
                if args.provider != provider:
                    eprint("error: conflict between --provider ('{}') option and framework ('{}')".format(args.provider, provider))
                    raise SystemExit(2)
            elif provider not in providers.__all__:
                eprint("error: unsupported provider received from framework: '{}', sorry :(".format(provider))
                raise SystemExit(2)
        else:
            if not args.provider:
                eprint("error: could not determine provider from framework, please specify with --provider")
                raise SystemExit(2)
            provider = args.provider
    else:
        if not args.provider:
            eprint("error: must specify either --provider or --framework")
            raise SystemExit(2)
        provider = args.provider

    with import_module("lib.providers.{}".format(provider)).Provider(path, resource_template=args.resource_template, framework=framework, config=config) as provider:
        yield provider

def main(argv=None):
    args = arguments.parser.parse_args(argv)

    for path in args.path:
        if len(args.path) > 1:
            print("{}:".format(path))
        with generate_config(path, args) as config:
            with generate_framework(path, args, config) as framework:
                with generate_provider(path, args, framework, config) as provider:
                    provider.process()
                    # TODO: output
                    from pprint import pprint
                    pprint(provider.permissions)
                    print()

if __name__ == '__main__':
    main()
