import boto3


KINESIS_PARTITION_KEY = "metgenc-duck"

def kinesis_stream_exists(stream_name):
    client = boto3.client("kinesis", region_name="us-west-2")
    try:
        summary = client.describe_stream_summary(StreamName=stream_name)
        return True
    except Exception as e:
        return False

def post_to_kinesis(stream_name, cnm_message):
    """Posts a message to a Kinesis stream."""
    client = boto3.client("kinesis", region_name="us-west-2")
    try:
        result = client.put_record(
            StreamName=stream_name,
            Data=cnm_message,
            PartitionKey=KINESIS_PARTITION_KEY
        )
        print(f'Published CNM message {cnm_message} to stream: {stream_name}')
        return result['ShardId']
    except Exception as e:
        print(e)
        raise e
