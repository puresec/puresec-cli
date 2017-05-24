import re

CALL_PATTERN_TEMPLATE = r"\.\s*{}\((.*?)\)" # .VALUE(OUTPUT)

SERVICE_CALL_PATTERNS = dict(
        (name, re.compile(CALL_PATTERN_TEMPLATE.format(client_name), re.MULTILINE | re.DOTALL))
        for name, client_name in
        (
            ('s3', r"S3"),
            ('dynamodb', r"DynamoDB(?:\.DocumentClient)?"),
            ('sns', r"SNS"),
            ('kinesis', r"Kinesis"),
            ('ses', r"SES"),
            ('kms', r"KMS"),
        ))

DYNAMODB_ACTION_CALL_PATTERNS = dict(
        # "batchGetItem" -> "dynamodb:BatchGetItem"
        ("dynamodb:{}{}".format(method[0].capitalize(), method[1:]), re.compile(CALL_PATTERN_TEMPLATE.format(method), re.MULTILINE | re.DOTALL))
        for method in
        (
            'batchGetItem', 'batchWriteItem', 'createTable', 'deleteItem', 'deleteTable',
            'describeLimits', 'describeTable', 'describeTimeToLive', 'getItem', 'listTables',
            'listTagsOfResource', 'putItem', 'query', 'scan', 'tagResource',
            'untagResource', 'updateItem', 'updateTable', 'updateTimeToLive',
        ))

