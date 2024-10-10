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
def kinesis_stream_summary(kinesis):
    """Create a Kinesis stream and return its summary info."""
    kinesis.create_stream(StreamName="duck-test-stream", ShardCount=1)
    summary = kinesis.describe_stream_summary(StreamName="duck-test-stream")
    return summary['StreamDescriptionSummary']

@pytest.fixture
def test_message():
    """Returns a JSON string for testing."""
    return json.dumps({
        'foo': 333,
        'bar': 'xyzzy'
    })

@pytest.fixture
def s3(aws_credentials):
    """A mocked s3 client."""
    with mock_aws():
        yield boto3.client("s3")

@pytest.fixture
def s3_bucket(s3):
    """Create an S3 buket and return the bucket name."""
    bucket_name = "duck-test-bucket"
    response = s3.create_bucket(
            Bucket=bucket_name,
            CreateBucketConfiguration={
                'LocationConstraint': 'us-west-2'
            },
    )
    return bucket_name

@pytest.fixture
def science_data():
    return """
        xyzzy
        foo
        bar
        """

def test_kinesis_stream_exists_for_valid_name(kinesis_stream_summary):
    stream_name = "duck-test-stream"
    assert aws.kinesis_stream_exists(stream_name)

def test_kinesis_stream_exists_for_invalid_name(kinesis_stream_summary):
    stream_name = "xyzzy"
    assert not aws.kinesis_stream_exists(stream_name)

def test_post_to_kinesis(kinesis_stream_summary, test_message):
    """Given a Kinesis stream name and a message, it should post successfully."""
    stream_name = kinesis_stream_summary['StreamName']
    success = aws.post_to_kinesis(stream_name, test_message)
    assert type(success) is str

def test_post_to_kinesis_returns_shard_id(kinesis_stream_summary, test_message):
    """Given a Kinesis stream name and a test message, the response should include the shard id."""
    stream_name = kinesis_stream_summary['StreamName']
    result = aws.post_to_kinesis(stream_name, test_message)
    assert "shardId" in result

def test_post_to_kinesis_with_invalid_stream_name(kinesis_stream_summary, test_message):
    """Given an invalid Kinesis stream name and a message, it should raise an exception."""
    invalid_stream_name = "abcd-1234-wxyz-0987"
    with pytest.raises(Exception):
        aws.post_to_kinesis(invalid_stream_name, test_message)

def test_post_to_kinesis_with_empty_message(kinesis_stream_summary):
    """Given a Kinesis stream name, it should raise an exception when posting an empty message."""
    stream_name = kinesis_stream_summary['StreamName']
    with pytest.raises(Exception):
        aws.post_to_kinesis(stream_name, None)

def test_copy_to_s3(s3, s3_bucket, science_data):
    path = "/external/NSIDC-TEST666/3/abcd-1234-wxyz-0987"
    filename = "science-data.bin"
    aws.stage_file(s3_bucket, path, filename, science_data)

    s3_object = s3.get_object(
            Bucket=s3_bucket,
            Key=f'{path}/{filename}',
    )
    object_lines = [line.decode(encoding="utf-8") for line in s3_object['Body'].readlines()]
    object_data = "".join(object_lines)

    assert object_data == science_data

