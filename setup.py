#!/usr/bin/env python

from setuptools import setup, find_packages

def find_version():
    with open('puresec_cli/__init__.py') as f:
        version_match = re.search(r"^__version__ = ['\"]([^'\"]*)['\"]",
                                  f.read(), re.M)
    if version_match:
        return version_match.group(1)
    raise RuntimeError("Unable to find version string.")

setup(
    name='puresec-cli',
    version='1.0.0',
    description="Set of wonderful tools to improve your serverless security (and social life).",
    long_description=open('README.rst').read(),
    author='PureSec <support@puresec.io>',
    url='https://github.com/puresec/puresec-cli',
    packages=find_packages(exclude=['tests*']),
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
    ]
)

