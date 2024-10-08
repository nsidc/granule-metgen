import boto3


KINESIS_PARTITION_KEY = "metgenc-duck"

def kinesis_stream_arn(stream_name):
    client = boto3.client("kinesis", region_name="us-west-2")
    try:
        summary = client.describe_stream_summary(StreamName=stream_name)
        return summary['StreamDescriptionSummary']['StreamARN']
    except Exception as e:
        return None

def kinesis_stream_exists(kinesis_stream_arn):
    client = boto3.client("kinesis", region_name="us-west-2")
    try:
        summary = client.describe_stream_summary(StreamARN=kinesis_stream_arn)
        return True
    except Exception as e:
        return False

def post_to_kinesis(kinesis_stream_arn, cnm_message):
    """Posts a message to a Kinesis stream."""
    client = boto3.client("kinesis", region_name="us-west-2")
    try:
        result = client.put_record(
            StreamARN=kinesis_stream_arn,
            Data=cnm_message,
            PartitionKey=KINESIS_PARTITION_KEY
        )
        print(f'Published CNM message {cnm_message} to stream ARN: {kinesis_stream_arn}')
        return result['ShardId']
    except Exception as e:
        print(e)
        raise e
