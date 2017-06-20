#!/usr/bin/env python

from setuptools import setup, find_packages

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
        'termcolor',
        # AWS
        'boto3',
        'aws-parsecf',
    ]
)

