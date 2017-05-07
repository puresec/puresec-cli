from base import Base
from subprocess import call
from ..utils import eprint
from zipfile import ZipFile
import os
import shutil
import tempfile
import yaml

class Handler(Base):
    def __init__(self, config, code_path, config):
        super().__init__(config, code_path, config)

        with open(os.path.join(code_path, "serverless.yml"), 'rb') as serverless_config:
            self.serverless_config = yaml.load(serverless_config)

    def get_resource_template(self):
        if not hasattr(self, 'sls_package_path'):
            self.sls_package_path = tempfile.mkdtemp(prefix="puresec-least-privilege-")
            result = call(['sls', 'package', '--package', self.sls_package_path], cwd=self.code_path)
            if result != 0:
                eprint("ERROR: Serverless package failed.")
                raise SystemExit(result)
        return os.path.join(self.sls_package_path, "cloudformation-template-update-stack.json")

    def get_default_profile(self):
        return self.serverless_config['provider'].get('profile')

    def get_default_region(self):
        return self.serverless_config['provider'].get('region')

    def get_function_root(self, name):
        function_root = os.path.join(self.sls_package_path, name)
        with ZipFile(os.path.join(self.sls_package_path, "{}.zip".format(name)), 'r') as zipfile:
            zipfile.extractall(function_root)
        return function_root

    def __exit__(self, type, value, traceback):
        super().__exit__(type, value, traceback)
        if hasattr(self, 'sls_package_path') and self.sls_package_path:
            shutil.rmtree(self.sls_package_path)

