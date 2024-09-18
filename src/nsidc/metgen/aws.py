import boto3


def post_to_kinesis(kinesis_stream_arn, cnm_message):
    client = boto3.client("kinesis", region_name="us-west-2")
    try:
        result = client.put_record(StreamARN=kinesis_stream_arn, Data=cnm_message, PartitionKey="duck")
        print(f'Published CNM message {cnm_message} to stream ARN: {kinesis_stream_arn}')
        return True
    except Exception as e:
        print(e)
        raise e
    return False
