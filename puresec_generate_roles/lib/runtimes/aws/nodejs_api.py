from itertools import chain
import re

CALL_PATTERN_TEMPLATE = r"\.\s*{0}(\(.{{0,1024}})" # .VALUE(OUTPUT) including opening parantheses and 1000 characters after

SERVICE_CALL_PATTERNS = [
        (name, re.compile(CALL_PATTERN_TEMPLATE.format(client_name), re.MULTILINE | re.DOTALL))
        for name, client_name in (
            ('dynamodb', r"DynamoDB(?:\.DocumentClient)?"),
            ('kinesis', r"Kinesis"),
            ('kms', r"KMS"),
            ('s3', r"S3"),
            ('ses', r"SES"),
            ('sns', r"SNS"),
        )
    ]

S3_SIGNED_URL_PATTERN = r"(?:(?:{0})|(?:\.\s*getSignedUrl\(\s*['\"]{{0}}['\"](.*?)\)))".format(CALL_PATTERN_TEMPLATE) # .VALUE(OUTPUT) or .getSignedUrl('VALUE'OUTPUT)

# { service: { action: pattern } }
ACTION_CALL_PATTERNS = {
        'dynamodb': tuple(
            chain((
                (
                    # "batchGetItem" -> "dynamodb:BatchGetItem"
                    "dynamodb:{}{}".format(method[0].capitalize(), method[1:]),
                    re.compile(CALL_PATTERN_TEMPLATE.format(method), re.MULTILINE | re.DOTALL)
                )
                for method in (
                    'batchGetItem', 'batchWriteItem', 'createTable', 'deleteItem', 'deleteTable',
                    'describeLimits', 'describeTable', 'describeTimeToLive', 'getItem', 'listTables',
                    'listTagsOfResource', 'putItem', 'query', 'scan', 'tagResource',
                    'untagResource', 'updateItem', 'updateTable', 'updateTimeToLive',
                    )
                ), (
                    # DocumentClient
                    ("dynamodb:{}".format(action), re.compile(CALL_PATTERN_TEMPLATE.format(method), re.MULTILINE | re.DOTALL))
                    for action, method in (
                        ('BatchGetItem', 'batchGet'),
                        ('BatchWriteItem', 'batchWrite'),
                        ('DeleteItem', 'delete'),
                        ('GetItem', 'get'),
                        ('PutItem', 'put'),
                        ('Query', 'query'),
                        ('Scan', 'scan'),
                        ('UpdateItem', 'update'),
                    )
                ),
            )
        ),
        'kinesis': tuple(
            (
                # "batchGetItem" -> "kinesis:BatchGetItem"
                "kinesis:{}{}".format(method[0].capitalize(), method[1:]),
                re.compile(CALL_PATTERN_TEMPLATE.format(method), re.MULTILINE | re.DOTALL)
            )
            for method in (
                'addTagsToStream', 'createStream', 'decreaseStreamRetentionPeriod', 'deleteStream', 'describeLimits',
                'describeStream', 'disableEnhancedMonitoring', 'enableEnhancedMonitoring', 'getRecords', 'getShardIterator',
                'increaseStreamRetentionPeriod', 'listStreams', 'listTagsForStream', 'mergeShards', 'putRecord',
                'putRecords', 'removeTagsFromStream', 'splitShard', 'updateShardCount',
                )
        ),
        's3': tuple(
            chain((
                (
                    # "batchGetItem" -> "dynamodb:BatchGetItem"
                    "s3:{}{}".format(method[0].capitalize(), method[1:]),
                    re.compile(S3_SIGNED_URL_PATTERN.format(method, method), re.MULTILINE | re.DOTALL)
                )
                for method in (
                    'abortMultipartUpload', 'createBucket', 'deleteBucket', 'deleteBucketPolicy', 'deleteBucketWebsite',
                    'deleteObject', 'deleteObjectTagging', 'getBucketAcl', 'getBucketLocation', 'getBucketLogging',
                    'getBucketNotification', 'getBucketPolicy', 'getBucketRequestPayment', 'getBucketTagging', 'getBucketVersioning',
                    'getBucketWebsite', 'getObject', 'getObjectAcl', 'getObjectTagging', 'getObjectTorrent',
                    'putBucketAcl', 'putBucketLogging', 'putBucketNotification', 'putBucketPolicy', 'putBucketRequestPayment',
                    'putBucketTagging', 'putBucketVersioning', 'putBucketWebsite', 'putObject', 'putObjectAcl',
                    'putObjectTagging', 'restoreObject',
                    )
                ), (
                    ("s3:{}".format(action), re.compile(CALL_PATTERN_TEMPLATE.format(method), re.MULTILINE | re.DOTALL))
                    for action, method in (
                        ('DeleteObject', 'deleteObjects'),
                        ('DeleteReplicationConfiguration', 'deleteBucketReplication'),
                        ('GetAccelerateConfiguration', 'getBucketAccelerateConfiguration'),
                        ('GetAnalyticsConfiguration', 'getBucketAnalyticsConfiguration'),
                        ('GetAnalyticsConfiguration', 'listBucketAnalyticsConfigurations'),
                        ('GetBucketCORS', 'getBucketCors'),
                        ('GetBucketNotification', 'getBucketNotificationConfiguration'),
                        ('GetInventoryConfiguration', 'getBucketInventoryConfiguration'),
                        ('GetInventoryConfiguration', 'listBucketInventoryConfigurations'),
                        ('GetLifecycleConfiguration', 'getBucketLifecycle'),
                        ('GetLifecycleConfiguration', 'getBucketLifecycleConfiguration'),
                        ('GetMetricsConfiguration', 'getBucketMetricsConfiguration'),
                        ('GetMetricsConfiguration', 'listBucketMetricsConfigurations'),
                        ('GetObject', 'getSignedUrl'),
                        ('GetObject', 'headObject'),
                        ('GetReplicationConfiguration', 'getBucketReplication'),
                        ('ListBucket', 'headBucket'),
                        ('ListBucket', 'listBuckets'),
                        ('ListBucket', 'listObjects'),
                        ('ListBucket', 'listObjectsV2'),
                        ('ListBucketMultipartUploads', 'listMultipartUploads'),
                        ('ListBucketVersions', 'listObjectVersions'),
                        ('ListMultipartUploadParts', 'listParts'),
                        ('PutAccelerateConfiguration', 'putBucketAccelerateConfiguration'),
                        ('PutAnalyticsConfiguration', 'deleteBucketAnalyticsConfiguration'),
                        ('PutAnalyticsConfiguration', 'putBucketAnalyticsConfiguration'),
                        ('PutBucketCORS', 'deleteBucketCors'),
                        ('PutBucketNotification', 'putBucketNotificationConfiguration'),
                        ('PutBucketTagging', 'deleteBucketTagging'),
                        ('PutInventoryConfiguration', 'deleteBucketInventoryConfiguration'),
                        ('PutInventoryConfiguration', 'putBucketInventoryConfiguration'),
                        ('PutLifecycleConfiguration', 'deleteBucketLifecycle'),
                        ('PutLifecycleConfiguration', 'putBucketLifecycle'),
                        ('PutLifecycleConfiguration', 'putBucketLifecycleConfiguration'),
                        ('PutMetricsConfiguration', 'deleteBucketMetricsConfiguration'),
                        ('PutMetricsConfiguration', 'putBucketMetricsConfiguration'),
                        ('PutObject', 'completeMultipartUpload'),
                        ('PutObject', 'copyObject'),
                        ('PutObject', 'createMultipartUpload'),
                        ('PutObject', 'createPresignedPost'),
                        ('PutObject', 'getSignedUrl'),
                        ('PutObject', 'upload'),
                        ('PutObject', 'uploadPart'),
                        ('PutObject', 'uploadPartCopy'),
                        ('PutReplicationConfiguration', 'putBucketReplication'),
                        ('putBucketCORS', 'putBucketCors'),
                    )
                ),
            )
        ),
    }

