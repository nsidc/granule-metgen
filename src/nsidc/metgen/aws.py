import boto3


KINESIS_PARTITION_KEY = "metgenc-duck"

def kinesis_stream_exists(stream_name):
    """
    Predicate which determines if a Kinesis stream with the given name exists
    in the configured AWS environment.
    """
    client = boto3.client("kinesis")
    try:
        summary = client.describe_stream_summary(StreamName=stream_name)
        return True
    except Exception as e:
        return False

def post_to_kinesis(stream_name, cnm_message):
    """
    Posts a message to a Kinesis stream.
    """
    client = boto3.client("kinesis")
    result = client.put_record(
        StreamName=stream_name,
        Data=cnm_message,
        PartitionKey=KINESIS_PARTITION_KEY
    )

    return result['ShardId']

def staging_bucket_exists(bucket_name):
    """
    Predicate which determines if an s3 bucket with the given name exists
    in the configured AWS environment.
    """
    client = boto3.client("s3")
    try:
        client.head_bucket(Bucket=bucket_name)
        return True
    except Exception as e:
        return False

def stage_file(s3_bucket_name, object_name, *, data=None, file=None):
    """
    Stages data into an s3 bucket at a given path.
    """
    client = boto3.client("s3")
    if not object_name:
        raise Exception("Missing object name for s3 target")

    if data:
        client.put_object(
            Body=data,
            Bucket=s3_bucket_name,
            Key=object_name,
        )
    elif file:
        client.upload_fileobj(file, s3_bucket_name, object_name)
    else:
        raise Exception("No data or file to stage to s3")
