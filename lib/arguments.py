from argparse import ArgumentParser
from lib import frameworks, providers
import os

parser = ArgumentParser(description="PureSec Least Privilege Role Creator")
parser.add_argument('path', nargs='?', default=os.getcwd(),
                    help="Path to the root directory of your project")
parser.add_argument('--framework', '-f', default='none', choices=['none'].extend(frameworks.__all__),
                    help="Framework used for deploying")
parser.add_argument('--provider', '-p', choices=providers.__all__, required=True,
                    help="Name of the cloud provider")
parser.add_argument('--resource-template', '-t',
                    help="Provider-specific resource template (e.g CloudFormation JSON for AWS)")
