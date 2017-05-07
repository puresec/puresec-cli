import re

"""
Modules here need to implement 3 functions:

# permissions = { service: { region: { account: { resource } } } }
def get_services(filename, content, permissions, default_region, default_account, environment):

# regions = set()
def get_regions(filename, content, regions, client, service, environment):

# resources = set()
def get_resources(filename, content, resources, client, service, environment)
"""

# { type(client): region }
SERVICE_REGIONS_CACHE = {}
def get_regions(filename, content, regions, client, environment):
    service_regions = SERVICE_REGIONS_CACHE.get(type(client))
    if service_regions is None:
        service_regions = SERVICE_REGIONS_CACHE[type(client)] = [
                region['RegionName'] for region in client.describe_regions()['Regions']
                ]

    # From content
    regions.update(
            region for region in service_regions
            if region in content
            )
    # From environment
    regions.update(
            region for region in service_regions
            if any(region in value for value in environment.values())
            )

# { client: { table: table_pattern } }
DYNAMODB_TABLES_CACHE = {}
def get_dynamodb_tables(client):
    tables = DYNAMODB_TABLES_CACHE.get(client)
    if tables is None:
        tables = DYNAMODB_TABLES_CACHE[client] = dict(
                (table, re.compile(re.escape(table), re.IGNORECASE))
                for table in client.list_tables()['TableNames']
                )
        if not tables:
            eprint("WARNING: DynamoDB has no tables")

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

