import boto3
import botocore
import re

"""
Modules here need to implement 3 functions:

# permissions = { service: { region: { account: { resource } } } }
def get_services(filename, content, permissions, default_region, default_account, environment):

# regions = set()
def get_regions(filename, content, regions, service, environment):

# resources = set()
def get_resources(filename, content, resources, client, service, environment)
"""

try:
    ALL_REGIONS = boto3.Session().get_available_regions('ec2')
except botocore.exceptions.BotoCoreError as e:
    eprint("error: failed to create aws session:\n{}".format(e))
    raise SystemExit(-1)

def get_regions(filename, content, regions, environment):
    # From content
    regions.update(
            region for region in ALL_REGIONS
            if region in content
            )
    # From environment
    regions.update(
            region for region in ALL_REGIONS
            if any(region in value for value in environment.values())
            )

# { client: { table: table_pattern } }
DYNAMODB_TABLES_CACHE = {}
def get_dynamodb_tables(client):
    tables = DYNAMODB_TABLES_CACHE.get(client)

    if tables is None:
        try:
            tables = client.list_tables()['TableNames']
        except botocore.exceptions.BotoCoreError as e:
            eprint("error: failed to list table names on DynamoDB:\n{}".format(e))
            raise SystemExit(-1)
        tables = DYNAMODB_TABLES_CACHE[client] = dict(
                (table, re.compile(re.escape(table), re.IGNORECASE))
                for table in tables
                )
        if not tables:
            eprint("warn: no tables on DynamoDB on region '{}'".format(client.meta.region_name))

    return tables

DYNAMODB_TABLE_RESOURCE_FORMAT = "Table/{}"
def get_dynamodb_resources(filename, content, resources, client, environment):
    """ Simply greps tables inside the given content """
    tables = get_dynamodb_tables(client)
    # From content
    resources.update(
            DYNAMODB_TABLE_RESOURCE_FORMAT.format(table)
            for table, pattern in tables.items()
            if pattern.match(content)
            )
    # From environment (TODO: once enough for entire lambda)
    resources.update(
            DYNAMODB_TABLE_RESOURCE_FORMAT.format(table)
            for table, pattern in tables.items()
            if any(pattern.match(value) for value in environment.values())
            )

