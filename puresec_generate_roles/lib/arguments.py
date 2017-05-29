from argparse import ArgumentParser
from lib import frameworks, providers
import os

parser = ArgumentParser(
        usage="bin/gen-roles",
        description="PureSec Role Generator"
        )
parser.add_argument('path', nargs='*', default=[os.getcwd()],
                    help="Path to the root directory of your project")

parser.add_argument('--provider', '-p', choices=providers.__all__,
                    help="Name of the cloud provider (required)")

parser.add_argument('--resource-template', '-t',
                    help="Provider-specific resource template (e.g CloudFormation JSON for AWS)")

parser.add_argument('--framework', '-f', choices=frameworks.__all__,
                    help="Framework used for deploying (optional)")

parser.add_argument('--framework-path', '-e',
                    help="Path to the framework's executable, usually not needed.")

parser.add_argument('--format', choices=['json', 'yaml'],
                    help="Wanted output format, defaults to framework/provider guesswork")

