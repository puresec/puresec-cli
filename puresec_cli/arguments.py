from argparse import ArgumentParser
from puresec_cli import frameworks, providers
from puresec_cli.runtimes import aws
import os

parser = ArgumentParser(
    description="Set of wonderful tools to improve your serverless security (and social life)."
)

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

parser.add_argument('--format', choices=['json', 'yaml'],
                    help="Wanted output format, defaults to framework/provider guesswork")

