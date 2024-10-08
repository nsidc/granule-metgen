import json
import os

import boto3
from moto import mock_aws
import pytest

from nsidc.metgen import aws


# Unit tests for the 'aws' module functions.
#
# The test boundary is the aws module's interface with the AWS library's boto3
# module, so in addition to testing the aws module's behavior, the tests should
# mock that module's functions and assert that aws functions call them with the
# correct parameters, correctly handle their return values, and handle any
# exceptions they may throw.

@pytest.fixture(scope="module")
def aws_credentials():
    """Mocked AWS Credentials for moto."""
    os.environ["AWS_ACCESS_KEY_ID"] = "testing"
    os.environ["AWS_SECRET_ACCESS_KEY"] = "testing"
    os.environ["AWS_SECURITY_TOKEN"] = "testing"
    os.environ["AWS_SESSION_TOKEN"] = "testing"
    os.environ["AWS_DEFAULT_REGION"] = "us-west-2"

@pytest.fixture
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
    """Returns a JSON string for testing."""
    return json.dumps({
        'foo': 333,
        'bar': 'xyzzy'
    })

def test_kinesis_stream_arn_for_valid_name(kinesis_stream_arn):
    stream_name = "duck-test-stream"
    assert aws.kinesis_stream_arn(stream_name) == kinesis_stream_arn

def test_kinesis_stream_arn_for_invalid_name(kinesis_stream_arn):
    stream_name = "xyzzy"
    assert aws.kinesis_stream_arn(stream_name) is None

# Do these become OBE then?
# TODO: test_kinesis_stream_exists_for_valid_name

# TODO: test_kinesis_stream_exists_for_invalid_name

def test_post_to_kinesis(kinesis_stream_arn, test_message):
    """Given a Kinesis stream ARN and a message, it should post successfully."""
    success = aws.post_to_kinesis(kinesis_stream_arn, test_message)
    assert type(success) is str

def test_post_to_kinesis_returns_foo(kinesis_stream_arn, test_message):
    """Given a Kinesis stream ARN and a test message, the response should include the shard id."""
    result = aws.post_to_kinesis(kinesis_stream_arn, test_message)
    assert "shardId" in result

def test_post_to_kinesis_with_invalid_stream_arn(kinesis_stream_arn, test_message):
    """Given an invalid Kinesis stream ARN and a message, it should raise an exception."""
    invalid_stream_arn = "abcd-1234-wxyz-0987"
    with pytest.raises(Exception):
        aws.post_to_kinesis(invalid_stream_arn, test_message)

def test_post_to_kinesis_with_empty_message(kinesis_stream_arn):
    """Given a Kinesis stream ARN, it should raise an exception when posting an empty message."""
    with pytest.raises(Exception):
        aws.post_to_kinesis(kinesis_stream_arn, None)
