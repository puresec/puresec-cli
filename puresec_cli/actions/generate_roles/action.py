from contextlib import contextmanager
from importlib import import_module
import os
import yaml

from puresec_cli.actions.base import Base
from puresec_cli.actions.generate_roles import providers, frameworks
from puresec_cli.actions.generate_roles.runtimes import aws
from puresec_cli.utils import eprint
from puresec_cli import stats

class GenerateRoles(Base):
    @staticmethod
    def command():
        return 'gen-roles'

    @classmethod
    def argument_parser_options(cls):
        options = super().argument_parser_options()
        options.update(
            description="PureSec role generator."
        )
        return options

    @classmethod
    def add_arguments(cls, parser):
        super().add_arguments(parser)

        parser.add_argument('path', nargs='*', default=[os.getcwd()],
                            help="Path to the root directory of your project")

        parser.add_argument('--provider', '-p', choices=providers.__all__,
                            help="Name of the cloud provider (required without --framework)")

        parser.add_argument('--resource-template', '-t',
                            help="Provider-specific resource template (e.g CloudFormation JSON for AWS) (optional)")

        parser.add_argument('--runtime', '-r', choices=aws.__all__,
                            help="Runtime language (optional)")

        parser.add_argument('--framework', '-f', choices=frameworks.__all__,
                            help="Framework used for deploying (optional)")

        parser.add_argument('--framework-path', '-e',
                            help="Path to the framework's executable, usually not needed.")

        parser.add_argument('--function',
                            help="Only generate roles for a specific function.")

        parser.add_argument('--overwrite', action='store_true',
                            help="Overwrite previously generated files if they exist (e.g puresec-roles.yml).")
        parser.add_argument('--no-overwrite', action='store_true',
                            help="Don't overwrite previously generated files if they exist (will do nothing).")

        parser.add_argument('--reference', action='store_true',
                            help="Reference functions to newly created roles.")
        parser.add_argument('--no-reference', action='store_true',
                            help="Don't reference functions to newly created roles.")

        parser.add_argument('--remove-obsolete', action='store_true',
                            help="Remove obsolete roles that are no longer needed.")
        parser.add_argument('--no-remove-obsolete', action='store_true',
                            help="Don't remove obsolete roles that are no longer needed.")

        parser.add_argument('--yes', '-y', action='store_true',
                            help="Yes for all - overwrite files, remove old roles, etc.")


    def __init__(self, args):
        super().__init__(args)

        stats.payload['arguments'].update(
            path=len(self.args.path),
            provider=self.args.provider,
            resource_template=bool(self.args.resource_template),
            runtime=self.args.runtime,
            framework=self.args.framework,
            framework_path=bool(self.args.framework_path),
            function=bool(self.args.function),

            overwrite=self.args.overwrite,
            no_overwrite=self.args.no_overwrite,
            reference=self.args.reference,
            no_reference=self.args.no_reference,
            remove_obsolete=self.args.remove_obsolete,
            no_remove_obsolete=self.args.no_remove_obsolete,
            yes=self.args.yes,
        )

    @contextmanager
    def generate_config(self, path):
        config_path = os.path.join(path, "puresec.yml")
        if os.path.isfile(config_path):
            with open(config_path, 'r', errors='replace') as config_file:
                config = yaml.load(config_file)
        else:
            config = {}

        yield config

        if config:
            with open(config_path, 'w', errors='replace') as config_file:
                yaml.dump(config, config_file, default_flow_style=False)

    @contextmanager
    def generate_framework(self, path, config):
        if not self.args.framework:
            yield None
        else:
            framework = import_module("puresec_cli.actions.generate_roles.frameworks.{}".format(self.args.framework)).Framework(
                path, config,
                executable=self.args.framework_path,
                function=self.args.function,
                args=self.args,
            )
            with framework:
                yield framework

    @contextmanager
    def generate_provider(self, path, framework, config):
        if framework:
            provider = framework.get_provider_name()
            if provider:
                if self.args.provider:
                    # self.args.provider always in providers.__all__, no need to check
                    if self.args.provider != provider:
                        eprint("error: conflict between --provider ('{}') option and framework ('{}')".format(self.args.provider, provider))
                        raise SystemExit(2)
                elif provider not in providers.__all__:
                    eprint("error: provider not yet supported: '{}'".format(provider))
                    raise SystemExit(2)
            else:
                if not self.args.provider:
                    eprint("error: could not determine provider from framework, please specify with --provider")
                    raise SystemExit(2)
                provider = self.args.provider
        else:
            if not self.args.provider:
                eprint("error: must specify either --provider or --framework")
                raise SystemExit(2)
            provider = self.args.provider

        provider = import_module("puresec_cli.actions.generate_roles.providers.{}".format(provider)).Provider(
            path, config,
            resource_template=self.args.resource_template,
            runtime=self.args.runtime,
            framework=framework,
            function=self.args.function,
            args=self.args,
        )
        with provider:
            yield provider

    def run(self):
        for path in self.args.path:
            if len(self.args.path) > 1:
                print("{}:".format(path))

            with self.generate_config(path) as config:

                with self.generate_framework(path, config) as framework:
                    with self.generate_provider(path, framework, config) as provider:
                        provider.process()
                        if framework:
                            framework.result(provider)
                        else:
                            provider.result()

Action = GenerateRoles

