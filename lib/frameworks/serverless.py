from base import Base
from subprocess import call
from ..utils import eprint
from zipfile import ZipFile, BadZipFile
import os
import shutil
import tempfile
import yaml

class Handler(Base):
    def __init__(self, config, path, config):
        super().__init__(config, path, config)

        try:
            serverless_config = open(os.path.join(path, "serverless.yml"), 'rb')
        except FileNotFoundError:
            eprint("error: 'serverless' framework specified, but serverless.yml was not found in path")
            raise SystemExit(2)

        with serverless_config:
            try:
                self.serverless_config = yaml.load(serverless_config)
            except yaml.YAMLError as e:
                eprint("error: invalid serverless.yml:\n{}".format(e))
                raise SystemExit(-1)

    def get_resource_template(self):
        if not hasattr(self, 'sls_package_path'):
            self.sls_package_path = tempfile.mkdtemp(prefix="puresec-least-privilege-")
            result = call(['sls', 'package', '--package', self.sls_package_path], cwd=self.path)
            if result != 0:
                eprint("error: sls package failed")
                raise SystemExit(result)

        return os.path.join(self.sls_package_path, "cloudformation-template-update-stack.json")

    def get_default_profile(self):
        return self.serverless_config.get('provider', {}).get('profile')

    def get_default_region(self):
        return self.serverless_config.get('provider', {}).get('region')

    def get_function_root(self, name):
        try:
            zipfile = ZipFile(os.path.join(self.sls_package_path, "{}.zip".format(name)), 'r')
        except FileNotFoundError:
            eprint("error: sls package did not create function zip for '{}'".format(name))
            raise SystemExit(2)
        except BadZipFile:
            eprint("error: sls package did not create a valid function zip for '{}'".format(name))
            raise SystemExit(2)

        function_root = os.path.join(self.sls_package_path, name)
        with zipfile:
            zipfile.extractall(function_root)
        return function_root

    def __exit__(self, type, value, traceback):
        super().__exit__(type, value, traceback)
        if hasattr(self, 'sls_package_path') and self.sls_package_path:
            shutil.rmtree(self.sls_package_path)

