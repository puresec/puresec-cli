""" Methods for NodeJS API. """

from functools import partial
from itertools import chain
from puresec_cli.utils import lowerize
import re

# .VALUE(OUTPUT) including opening parantheses and 512 characters after
CALL_PATTERN_TEMPLATE = r"\.\s*{0}(\(.{{0,512}})"
# .VALUE(OUTPUT) or .getSignedUrl('VALUE'OUTPUT) including opening paranthesis and 512 characters after
SIGNED_URL_PATTERN_TEMPLATE = r"{0}|\.\s*getSignedUrl(\(\s*['\"]{{0}}['\"].{{{{0,512}}}})".format(CALL_PATTERN_TEMPLATE)

class NodejsApi:
    SERVICE_CALL_PATTERNS = [
        (name, re.compile(CALL_PATTERN_TEMPLATE.format(client_name), re.MULTILINE | re.DOTALL))
        for name, client_name in (
                ('dynamodb', r"DynamoDB"),
                ('dynamodb', r"DocumentClient"),
                ('dynamodb', r"DynamoDBStreams"),
                ('kinesis', r"Kinesis"),
                ('kms', r"KMS"),
                ('lambda', r"Lambda"),
                ('s3', r"S3"),
                ('ses', r"SES"),
                ('sns', r"SNS"),
                ('states', r"StepFunctions"),
        )
    ]

    SERVICE_ACTIONS_PROCESSOR = {
        # service: function(self, filename, contents, actions)
        'dynamodb': lambda self: partial(self._get_generic_actions, service='dynamodb'),
        'kinesis':  lambda self: partial(self._get_generic_actions, service='kinesis'),
        'kms':      lambda self: partial(self._get_generic_actions, service='kms'),
        'lambda':   lambda self: partial(self._get_generic_actions, service='lambda'),
        's3':       lambda self: partial(self._get_generic_actions, service='s3'),
        'ses':      lambda self: partial(self._get_generic_actions, service='ses'),
        'sns':      lambda self: partial(self._get_generic_actions, service='sns'),
        'states':   lambda self: partial(self._get_generic_actions, service='states'),
    }

    # { service: (action, pattern) }
    ACTION_CALL_PATTERNS = {
        'dynamodb': tuple(chain(
            (
                (
                    "dynamodb:{}".format(action),
                    re.compile(CALL_PATTERN_TEMPLATE.format(lowerize(action)), re.MULTILINE | re.DOTALL)
                )
                for action in (
                        'BatchGetItem', 'BatchWriteItem', 'CreateTable', 'DeleteItem', 'DeleteTable',
                        'DescribeLimits', 'DescribeStream', 'DescribeTable', 'DescribeTimeToLive', 'GetItem',
                        'GetRecords', 'GetShardIterator', 'ListStreams', 'ListTables', 'ListTagsOfResource',
                        'PutItem', 'Query', 'Scan', 'TagResource', 'UntagResource',
                        'UpdateItem', 'UpdateTable', 'UpdateTimeToLive',
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
                        ('UpdateItem', 'update'),
                )
            ),
        )),
        'kinesis': tuple(
            (
                "kinesis:{}".format(action),
                re.compile(CALL_PATTERN_TEMPLATE.format(lowerize(action)), re.MULTILINE | re.DOTALL)
            )
            for action in (
                    'AddTagsToStream', 'CreateStream', 'DecreaseStreamRetentionPeriod', 'DeleteStream', 'DescribeLimits',
                    'DescribeStream', 'DisableEnhancedMonitoring', 'EnableEnhancedMonitoring', 'GetRecords', 'GetShardIterator',
                    'IncreaseStreamRetentionPeriod', 'ListStreams', 'ListTagsForStream', 'MergeShards', 'PutRecord',
                    'PutRecords', 'RemoveTagsFromStream', 'SplitShard', 'UpdateShardCount',
            )
        ),
        'kms': tuple(chain(
            (
                (
                    "kms:{}".format(action),
                    re.compile(CALL_PATTERN_TEMPLATE.format(lowerize(action)), re.MULTILINE | re.DOTALL)
                )
                for action in (
                        'CancelKeyDeletion', 'CreateAlias', 'CreateGrant', 'CreateKey', 'Decrypt',
                        'DeleteAlias', 'DeleteImportedKeyMaterial', 'DescribeKey', 'DisableKey', 'DisableKeyRotation',
                        'EnableKey', 'EnableKeyRotation', 'Encrypt', 'GenerateDataKey', 'GenerateDataKeyWithoutPlaintext',
                        'GenerateRandom', 'GetKeyPolicy', 'GetKeyRotationStatus', 'GetParametersForImport', 'ImportKeyMaterial',
                        'ListAliases', 'ListGrants', 'ListKeyPolicies', 'ListKeys', 'ListRetirableGrants',
                        'PutKeyPolicy', 'RevokeGrant', 'ScheduleKeyDeletion', 'UpdateAlias', 'UpdateKeyDescription',
                )
            ), (
                ("kms:{}".format(action), re.compile(CALL_PATTERN_TEMPLATE.format(method), re.MULTILINE | re.DOTALL))
                for action, method in (
                        ('ReEncryptFrom', 'reEncrypt'),
                        ('ReEncryptTo', 'reEncrypt'),
                )
            ),
        )),
        'lambda': tuple(chain(
            (
                (
                    "lambda:{}".format(action),
                    re.compile(CALL_PATTERN_TEMPLATE.format(lowerize(action)), re.MULTILINE | re.DOTALL)
                )
                for action in (
                        'AddPermission', 'CreateAlias', 'CreateEventSourceMapping', 'CreateFunction', 'DeleteAlias',
                        'DeleteEventSourceMapping', 'DeleteFunction', 'GetAccountSettings', 'GetAlias', 'GetEventSourceMapping',
                        'GetFunction', 'GetFunctionConfiguration', 'GetPolicy', 'InvokeAsync', 'ListAliases',
                        'ListEventSourceMappings', 'ListFunctions', 'ListVersionsByFunction', 'PublishVersion', 'RemovePermission',
                        'UpdateAlias', 'UpdateEventSourceMapping', 'UpdateFunctionCode', 'UpdateFunctionConfiguration',
                )
            ), (
                ("lambda:{}".format(action), re.compile(CALL_PATTERN_TEMPLATE.format(method), re.MULTILINE | re.DOTALL))
                for action, method in (
                        ('InvokeFunction', 'invoke'),
                )
            ),
        )),
        's3': tuple(chain(
            (
                (
                    "s3:{}".format(action),
                    re.compile(SIGNED_URL_PATTERN_TEMPLATE.format(lowerize(action)), re.MULTILINE | re.DOTALL)
                )
                for action in (
                        'AbortMultipartUpload', 'CreateBucket', 'DeleteBucket', 'DeleteBucketPolicy', 'DeleteBucketWebsite',
                        'DeleteObject', 'DeleteObjectTagging', 'GetBucketAcl', 'GetBucketLocation', 'GetBucketLogging',
                        'GetBucketNotification', 'GetBucketPolicy', 'GetBucketRequestPayment', 'GetBucketTagging', 'GetBucketVersioning',
                        'GetBucketWebsite', 'GetObject', 'GetObjectAcl', 'GetObjectTagging', 'GetObjectTorrent',
                        'PutBucketAcl', 'PutBucketLogging', 'PutBucketNotification', 'PutBucketPolicy', 'PutBucketRequestPayment',
                        'PutBucketTagging', 'PutBucketVersioning', 'PutBucketWebsite', 'PutObject', 'PutObjectAcl',
                        'PutObjectTagging', 'RestoreObject',
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
                        ('GetObject', 'headObject'),
                        ('GetReplicationConfiguration', 'getBucketReplication'),
                        ('ListAllMyBuckets', 'listBuckets'),
                        ('ListBucket', 'headBucket'),
                        ('ListBucket', 'listObjects'),
                        ('ListBucket', 'listObjectsV2'),
                        ('ListBucketMultipartUploads', 'listMultipartUploads'),
                        ('ListBucketVersions', 'listObjectVersions'),
                        ('ListMultipartUploadParts', 'listParts'),
                        ('PutAccelerateConfiguration', 'putBucketAccelerateConfiguration'),
                        ('PutAnalyticsConfiguration', 'deleteBucketAnalyticsConfiguration'),
                        ('PutAnalyticsConfiguration', 'putBucketAnalyticsConfiguration'),
                        ('PutBucketCORS', 'deleteBucketCors'),
                        ('PutBucketCORS', 'putBucketCors'),
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
                        ('PutObject', 'upload'),
                        ('PutObject', 'uploadPart'),
                        ('PutObject', 'uploadPartCopy'),
                        ('PutReplicationConfiguration', 'putBucketReplication'),
                )
            ),
        )),
        'ses': tuple(chain(
            (
                (
                    "ses:{}".format(action),
                    re.compile(SIGNED_URL_PATTERN_TEMPLATE.format(lowerize(action)), re.MULTILINE | re.DOTALL)
                )
                for action in (
                        'CloneReceiptRuleSet', 'CreateReceiptFilter', 'CreateReceiptRule', 'CreateReceiptRuleSet', 'DeleteIdentity',
                        'DeleteIdentityPolicy', 'DeleteReceiptFilter', 'DeleteReceiptRule', 'DeleteReceiptRuleSet', 'DeleteVerifiedEmailAddress',
                        'DescribeActiveReceiptRuleSet', 'DescribeReceiptRule', 'DescribeReceiptRuleSet', 'GetIdentityDkimAttributes', 'GetIdentityNotificationAttributes',
                        'GetIdentityPolicies', 'GetIdentityVerificationAttributes', 'GetSendQuota', 'GetSendStatistics', 'ListIdentities',
                        'ListIdentityPolicies', 'ListReceiptFilters', 'ListReceiptRuleSets', 'ListVerifiedEmailAddresses', 'PutIdentityPolicy',
                        'ReorderReceiptRuleSet', 'SendBounce', 'SendEmail', 'SendRawEmail', 'SetActiveReceiptRuleSet',
                        'SetIdentityDkimEnabled', 'SetIdentityFeedbackForwardingEnabled', 'SetIdentityNotificationTopic', 'SetReceiptRulePosition', 'UpdateReceiptRule',
                        'VerifyDomainDkim', 'VerifyDomainIdentity', 'VerifyEmailAddress', 'VerifyEmailIdentity',
                )
            ), (
                ("ses:{}".format(action), re.compile(CALL_PATTERN_TEMPLATE.format(method), re.MULTILINE | re.DOTALL))
                for action, method in (
                        #('CreateConfigurationSet'),
                        #('CreateConfigurationSetEventDestination'),
                        #('DeleteConfigurationSet'),
                        #('DeleteConfigurationSetEventDestination'),
                        #('DescribeConfigurationSet'),
                        #('GetIdentityMailFromDomainAttributes'),
                        #('ListConfigurationSets'),
                        #('SetIdentityHeadersInNotificationsEnabled'),
                        #('SetIdentityMailFromDomain'),
                        #('UpdateConfigurationSetEventDestination'),
                )
            ),
        )),
        'sns': tuple(
            (
                "sns:{}".format(action),
                re.compile(CALL_PATTERN_TEMPLATE.format(lowerize(action)), re.MULTILINE | re.DOTALL)
            )
            for action in (
                    'AddPermission', 'CheckIfPhoneNumberIsOptedOut', 'ConfirmSubscription', 'CreatePlatformApplication', 'CreatePlatformEndpoint',
                    'CreateTopic', 'DeleteEndpoint', 'DeletePlatformApplication', 'DeleteTopic', 'GetEndpointAttributes',
                    'GetPlatformApplicationAttributes', 'GetSMSAttributes', 'GetSubscriptionAttributes', 'GetTopicAttributes', 'ListEndpointsByPlatformApplication',
                    'ListPhoneNumbersOptedOut', 'ListPlatformApplications', 'ListSubscriptions', 'ListSubscriptionsByTopic', 'ListTopics',
                    'OptInPhoneNumber', 'Publish', 'RemovePermission', 'SetEndpointAttributes', 'SetPlatformApplicationAttributes',
                    'SetSMSAttributes', 'SetSubscriptionAttributes', 'SetTopicAttributes', 'Subscribe', 'Unsubscribe',
            )
        ),
        'states': tuple(
            (
                "states:{}".format(action),
                re.compile(CALL_PATTERN_TEMPLATE.format(lowerize(action)), re.MULTILINE | re.DOTALL)
            )
            for action in (
                    'CreateActivity', 'CreateStateMachine', 'DeleteActivity', 'DeleteStateMachine', 'DescribeActivity',
                    'DescribeExecution', 'DescribeStateMachine', 'GetActivityTask', 'GetExecutionHistory', 'ListActivities',
                    'ListExecutions', 'ListStateMachines', 'SendTaskFailure', 'SendTaskHeartbeat', 'SendTaskSuccess',
                    'StartExecution', 'StopExecution',
            )
        ),
    }

    def _get_generic_actions(self, filename, contents, actions, service, patterns=None):
        """
        >>> runtime = NodejsApi()

        >>> actions = set()
        >>> runtime._get_generic_actions("path/to/file.js", "code .putItem() code", actions, service='dynamodb')
        >>> sorted(actions)
        ['dynamodb:PutItem']

        >>> actions = set()
        >>> runtime._get_generic_actions("path/to/file.js", "code .putObject(params) .getSignedUrl('getObject', params) code", actions, service='s3')
        >>> sorted(actions)
        ['s3:GetObject', 's3:PutObject']
        """
        if patterns is None:
            patterns = NodejsApi.ACTION_CALL_PATTERNS[service]
        for action, pattern in patterns:
            if pattern.search(contents):
                actions.add(action)

