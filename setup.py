#!/usr/bin/env python

from setuptools import setup, find_packages

setup(
    name='puresec-generate-roles',
    version='1.0.0',
    description="A CLI tool for creating cloud roles with least privilege permissions using static code analysis.",
    long_description=open('README.rst').read(),
    author='Oded Niv',
    url='https://github.com/puresec/puresec-generate-roles',
    packages=find_packages(exclude=['tests*']),
    entry_points={
        'console_scripts': [
            'puresec-gen-roles=puresec_generate_roles.main:main',
        ],
    },
    install_requires=[
        'PyYAML',
        'boto3',
        'aws-parsecf==1.0.0',
        'termcolor',
    ],
    dependency_links=[
        'git+https://github.com/puresec/aws-parsecf.git#egg=aws-parsecf-1.0.0',
    ],
)

