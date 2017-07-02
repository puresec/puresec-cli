""" Methods for Python API. """

from functools import partial
from itertools import chain
from puresec_cli.utils import snakecase
import re

CALL_PATTERN_TEMPLATE = r"\.[\s\\]*{0}(\(.{{0,512}})" # .VALUE(OUTPUT... including opening parantheses and 512 characters after
SERVICE_INIT_PATTERN = r"\.[\s\\]*(?:client|resource)(\([\s\\]*['\"]{0}['\"].{{0,512}})" # .client('VALUE'OUTPUT... or .resource("VALUE"OUTPUT...
# .VALUE(OUTPUT) or .generate_presigned_url('VALUE'OUTPUT) including opening paranthesis and 512 characters after
SIGNED_URL_PATTERN_TEMPLATE = r"{0}|\.[\s\\]*generate_presigned_url(\([\s\\]*['\"]{{0}}['\"].{{{{0,512}}}})".format(CALL_PATTERN_TEMPLATE)

class PythonApi:
    SERVICE_CALL_PATTERNS = [
        (name, re.compile(SERVICE_INIT_PATTERN.format(client_name), re.MULTILINE | re.DOTALL))
        for name, client_name in (
                ('dynamodb', r"dynamodb"),
                ('kinesis', r"kinesis"),
                ('kms', r"kms"),
                ('lambda', r"lambda"),
                ('s3', r"s3"),
                ('ses', r"ses"),
                ('sns', r"sns"),
                ('states', r"stepfunctions"),
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
        'dynamodb': tuple(
            (
                "dynamodb:{}".format(action),
                re.compile(SIGNED_URL_PATTERN_TEMPLATE.format(snakecase(action)), re.MULTILINE | re.DOTALL)
            )
            for action in (
                    'BatchGetItem', 'BatchWriteItem', 'CreateTable', 'DeleteItem', 'DeleteTable',
                    'DescribeLimits', 'DescribeTable', 'DescribeTimeToLive', 'GetItem', 'ListTables',
                    'ListTagsOfResource', 'PutItem', 'Query', 'Scan', 'TagResource',
                    'UntagResource', 'UpdateItem', 'UpdateTable', 'UpdateTimeToLive',
            )
        ),
        'kinesis': tuple(
            (
                "kinesis:{}".format(action),
                re.compile(SIGNED_URL_PATTERN_TEMPLATE.format(snakecase(action)), re.MULTILINE | re.DOTALL)
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
                    re.compile(SIGNED_URL_PATTERN_TEMPLATE.format(snakecase(action)), re.MULTILINE | re.DOTALL)
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
                ("kms:{}".format(action), re.compile(SIGNED_URL_PATTERN_TEMPLATE.format(method), re.MULTILINE | re.DOTALL))
                for action, method in (
                        ('ReEncryptFrom', 're_encrypt'),
                        ('ReEncryptTo', 're_encrypt'),
                )
            ),
        )),
        'lambda': tuple(chain(
            (
                (
                    "lambda:{}".format(action),
                    re.compile(SIGNED_URL_PATTERN_TEMPLATE.format(snakecase(action)), re.MULTILINE | re.DOTALL)
                )
                for action in (
                        'AddPermission', 'CreateAlias', 'CreateEventSourceMapping', 'CreateFunction', 'DeleteAlias',
                        'DeleteEventSourceMapping', 'DeleteFunction', 'GetAccountSettings', 'GetAlias', 'GetEventSourceMapping',
                        'GetFunction', 'GetFunctionConfiguration', 'GetPolicy', 'InvokeAsync', 'ListAliases',
                        'ListEventSourceMappings', 'ListFunctions', 'ListVersionsByFunction', 'PublishVersion', 'RemovePermission',
                        'UpdateAlias', 'UpdateEventSourceMapping', 'UpdateFunctionCode', 'UpdateFunctionConfiguration',
                )
            ), (
                ("lambda:{}".format(action), re.compile(SIGNED_URL_PATTERN_TEMPLATE.format(method), re.MULTILINE | re.DOTALL))
                for action, method in (
                        ('InvokeFunction', 'invoke'),
                )
            ),
        )),
        's3': tuple(chain(
            (
                (
                    "s3:{}".format(action),
                    re.compile(SIGNED_URL_PATTERN_TEMPLATE.format(snakecase(action)), re.MULTILINE | re.DOTALL)
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
                ("s3:{}".format(action), re.compile(SIGNED_URL_PATTERN_TEMPLATE.format(method), re.MULTILINE | re.DOTALL))
                for action, method in (
                        ('DeleteObject', 'delete_objects'),
                        ('DeleteReplicationConfiguration', 'delete_bucket_replication'),
                        ('GetAccelerateConfiguration', 'get_bucket_accelerate_configuration'),
                        ('GetAnalyticsConfiguration', 'get_bucket_analytics_configuration'),
                        ('GetAnalyticsConfiguration', 'list_bucket_analytics_configurations'),
                        ('GetBucketCORS', 'get_bucket_cors'),
                        ('GetBucketNotification', 'get_bucket_notification_configuration'),
                        ('GetInventoryConfiguration', 'get_bucket_inventory_configuration'),
                        ('GetInventoryConfiguration', 'list_bucket_inventory_configurations'),
                        ('GetLifecycleConfiguration', 'get_bucket_lifecycle'),
                        ('GetLifecycleConfiguration', 'get_bucket_lifecycle_configuration'),
                        ('GetMetricsConfiguration', 'get_bucket_metrics_configuration'),
                        ('GetMetricsConfiguration', 'list_bucket_metrics_configurations'),
                        ('GetObject', 'download_file'),
                        ('GetObject', 'download_fileobj'),
                        ('GetObject', 'head_object'),
                        ('GetReplicationConfiguration', 'get_bucket_replication'),
                        ('ListAllMyBuckets', 'list_buckets'),
                        ('ListBucket', 'head_bucket'),
                        ('ListBucket', 'list_objects'),
                        ('ListBucket', 'list_objects_v2'),
                        ('ListBucketMultipartUploads', 'list_multipart_uploads'),
                        ('ListBucketVersions', 'list_object_versions'),
                        ('ListMultipartUploadParts', 'list_parts'),
                        ('PutAccelerateConfiguration', 'put_bucket_accelerate_configuration'),
                        ('PutAnalyticsConfiguration', 'delete_bucket_analytics_configuration'),
                        ('PutAnalyticsConfiguration', 'put_bucket_analytics_configuration'),
                        ('PutBucketCORS', 'delete_bucket_cors'),
                        ('PutBucketCORS', 'put_bucket_cors'),
                        ('PutBucketNotification', 'put_bucket_notification_configuration'),
                        ('PutBucketTagging', 'delete_bucket_tagging'),
                        ('PutInventoryConfiguration', 'delete_bucket_inventory_configuration'),
                        ('PutInventoryConfiguration', 'put_bucket_inventory_configuration'),
                        ('PutLifecycleConfiguration', 'delete_bucket_lifecycle'),
                        ('PutLifecycleConfiguration', 'put_bucket_lifecycle'),
                        ('PutLifecycleConfiguration', 'put_bucket_lifecycle_configuration'),
                        ('PutMetricsConfiguration', 'delete_bucket_metrics_configuration'),
                        ('PutMetricsConfiguration', 'put_bucket_metrics_configuration'),
                        ('PutObject', 'complete_multipart_upload'),
                        ('PutObject', 'copy'),
                        ('PutObject', 'copy_object'),
                        ('PutObject', 'create_multipart_upload'),
                        ('PutObject', 'generate_presigned_post'),
                        ('PutObject', 'upload_file'),
                        ('PutObject', 'upload_fileobj'),
                        ('PutObject', 'upload_part'),
                        ('PutObject', 'upload_part_copy'),
                        ('PutReplicationConfiguration', 'put_bucket_replication'),
                )
        ),
        )),
        'ses': tuple(chain(
            (
                (
                    "ses:{}".format(action),
                    re.compile(SIGNED_URL_PATTERN_TEMPLATE.format(snakecase(action)), re.MULTILINE | re.DOTALL)
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
                ("ses:{}".format(action), re.compile(SIGNED_URL_PATTERN_TEMPLATE.format(method), re.MULTILINE | re.DOTALL))
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
                re.compile(SIGNED_URL_PATTERN_TEMPLATE.format(snakecase(action)), re.MULTILINE | re.DOTALL)
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
                re.compile(SIGNED_URL_PATTERN_TEMPLATE.format(snakecase(action)), re.MULTILINE | re.DOTALL)
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
        >>> from io import StringIO
        >>> runtime = PythonApi()

        >>> actions = set()
        >>> runtime._get_generic_actions("path/to/file.py", "code .put_item() code", actions, service='dynamodb')
        >>> sorted(actions)
        ['dynamodb:PutItem']

        >>> actions = set()
        >>> runtime._get_generic_actions("path/to/file.py", "code .put_object(params) .generate_presigned_url('get_object', params) code", actions, service='s3')
        >>> sorted(actions)
        ['s3:GetObject', 's3:PutObject']
        """
        if patterns is None:
            patterns = PythonApi.ACTION_CALL_PATTERNS[service]
        for action, pattern in patterns:
            if pattern.search(contents):
                actions.add(action)

