import boto3


KINESIS_PARTITION_KEY = "metgenc-duck"

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
