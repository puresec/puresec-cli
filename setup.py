#!/usr/bin/env python3

from setuptools import setup, find_packages
import distutils.cmd
import setuptools.command.bdist_egg
import setuptools.command.sdist
import setuptools.command.test

import re
import subprocess

def find_version():
    with open('puresec_cli/__init__.py') as f:
        version_match = re.search(r"^__version__ = ['\"]([^'\"]*)['\"]",
                                  f.read(), re.M)
    if version_match:
        return version_match.group(1)
    raise RuntimeError("Unable to find version string.")

def run_test(self):
    # nosetests raises SystemExit(False) which stops the setup process
    try:
        self.run_command('nosetests')
    except SystemExit as e:
        if e.code: raise

class InstallNonPythonDepsCommand(distutils.cmd.Command):
    def initialize_options(self):
        pass

    def finalize_options(self):
        pass

    def run(self):
        self.announce("Running command: rm -rf puresec_cli/resources/node_modules", level=distutils.log.INFO)
        subprocess.check_call(['rm', '-rf', 'puresec_cli/resources/node_modules'])
        self.announce("Running command: npm install", level=distutils.log.INFO)
        subprocess.check_call(['npm', 'install', 'dependency-tree@^5.9.1', '--prefix', 'puresec_cli/resources'])

class BdistEggCommand(setuptools.command.bdist_egg.bdist_egg):
    def run(self):
        self.run_command('install_non_python_deps')
        run_test(self)
        super().run()

class SdistCommand(setuptools.command.sdist.sdist):
    def run(self):
        self.run_command('install_non_python_deps')
        run_test(self)
        super().run()

setup(
    name='puresec-cli',
    version=find_version(),
    description="PureSec CLI tools for improving the security of your serverless applications.",
    long_description=open('README.rst').read(),
    author='PureSec',
    author_email='support@puresec.io',
    url='https://github.com/puresec/puresec-cli',
    cmdclass={
        'install_non_python_deps': InstallNonPythonDepsCommand,
        'bdist_egg': BdistEggCommand,
        'sdist': SdistCommand,
    },
    packages=find_packages(exclude=['tests*']),
    include_package_data=True,
    entry_points={
        'console_scripts': [
            'puresec=puresec_cli.cli:main',
        ],
    },
    install_requires=[
        'PyYAML',
        'ruamel.yaml',
        'termcolor',
        'analytics-python',
        # AWS
        'boto3',
        'aws-parsecf',
    ],
    setup_requires=['nose', 'coverage'],
)

