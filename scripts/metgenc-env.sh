#!/bin/bash

if (( $# != 1 )); then
    echo "Usage: source metgenc-env.sh aws_profile_name"
    echo "       where aws_profile_name is an AWS CLI named profile"
    echo "       https://docs.aws.amazon.com/cli/latest/userguide/cli-configure-profiles.html"
    exit 1
else
    export AWS_PROFILE=$1

    AWS_ACCESS_KEY_ID=$(aws configure get aws_access_key_id --profile "$AWS_PROFILE")
    AWS_SECRET_ACCESS_KEY=$(aws configure get aws_secret_access_key --profile "$AWS_PROFILE")
    AWS_REGION=$(aws configure get region --profile "$AWS_PROFILE" || echo "$AWS_DEFAULT_REGION")
    AWS_ACCOUNT_ID=$(aws sts get-caller-identity --query "Account" --output text)

    export AWS_ACCESS_KEY_ID
    export AWS_SECRET_ACCESS_KEY
    export AWS_REGION
    export AWS_ACCOUNT_ID

    echo "AWS environment:"
    echo "  AWS_PROFILE:          $AWS_PROFILE"
    echo "  AWS_REGION:           $AWS_REGION"
    echo "  AWS_ACCOUNT_ID:       $AWS_ACCOUNT_ID"
fi
