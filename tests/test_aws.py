import json

import pytest
import boto3
from moto import mock_aws

from nsidc.metgen import aws


@mock_aws
def test_post_to_kinesis():
    client = boto3.client("kinesis", region_name="us-west-2")
    client.create_stream(StreamName="duck-test-stream", ShardCount=1)
    summary = client.describe_stream_summary(StreamName="duck-test-stream")
    stream_arn = summary['StreamDescriptionSummary']['StreamARN']
    test_message = json.dumps({
        'foo': 333,
        'bar': 'xyzzy'
    })

    aws.post_to_kinesis(stream_arn, test_message)
