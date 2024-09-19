import json
import os

import boto3
from moto import mock_aws
import pytest

from nsidc.metgen import aws


@pytest.fixture(scope="function")
def aws_credentials():
    """Mocked AWS Credentials for moto."""
    os.environ["AWS_ACCESS_KEY_ID"] = "testing"
    os.environ["AWS_SECRET_ACCESS_KEY"] = "testing"
    os.environ["AWS_SECURITY_TOKEN"] = "testing"
    os.environ["AWS_SESSION_TOKEN"] = "testing"
    os.environ["AWS_DEFAULT_REGION"] = "us-west-2"

@pytest.fixture(scope="function")
def kinesis(aws_credentials):
    """A mocked Kinesis client."""
    with mock_aws():
        yield boto3.client("kinesis", region_name="us-west-2")

@pytest.fixture
def kinesis_stream_arn(kinesis):
    """Create a Kinesis stream and return its ARN."""
    kinesis.create_stream(StreamName="duck-test-stream", ShardCount=1)
    summary = kinesis.describe_stream_summary(StreamName="duck-test-stream")
    return summary['StreamDescriptionSummary']['StreamARN']

@pytest.fixture
def test_message():
    return json.dumps({
        'foo': 333,
        'bar': 'xyzzy'
    })

def test_post_to_kinesis(kinesis_stream_arn, test_message):
    success = aws.post_to_kinesis(kinesis_stream_arn, test_message)
    assert type(success) is str

def test_post_to_kinesis_returns_foo(kinesis_stream_arn, test_message):
    result = aws.post_to_kinesis(kinesis_stream_arn, test_message)
    assert "shardId" in result

def test_post_to_kinesis_with_invalid_stream_arn(kinesis_stream_arn, test_message):
    invalid_stream_arn = "abcd-1234-wxyz-0987"
    with pytest.raises(Exception):
        aws.post_to_kinesis(invalid_stream_arn, test_message)

def test_post_to_kinesis_with_empty_message(kinesis_stream_arn):
    with pytest.raises(Exception):
        aws.post_to_kinesis(kinesis_stream_arn, None)
