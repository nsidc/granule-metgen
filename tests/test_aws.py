import json

import boto3
from moto import mock_aws
import pytest

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

    success = aws.post_to_kinesis(stream_arn, test_message)

    assert success == True

@mock_aws
def test_post_to_kinesis_with_invalid_stream_arn():
    client = boto3.client("kinesis", region_name="us-west-2")
    client.create_stream(StreamName="duck-test-stream", ShardCount=1)
    summary = client.describe_stream_summary(StreamName="duck-test-stream")
    stream_arn = summary['StreamDescriptionSummary']['StreamARN']
    test_message = json.dumps({
        'foo': 333,
        'bar': 'xyzzy'
    })
    invalid_stream_arn = "abcd-1234-wxyz-0987"

    with pytest.raises(Exception):
        aws.post_to_kinesis(invalid_stream_arn, test_message)

@mock_aws
def test_post_to_kinesis_with_empty_message():
    client = boto3.client("kinesis", region_name="us-west-2")
    client.create_stream(StreamName="duck-test-stream", ShardCount=1)
    summary = client.describe_stream_summary(StreamName="duck-test-stream")
    stream_arn = summary['StreamDescriptionSummary']['StreamARN']

    with pytest.raises(Exception):
        aws.post_to_kinesis(stream_arn, None)
