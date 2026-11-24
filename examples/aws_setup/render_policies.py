"""Write account-specific IAM policies for the batch walkthrough. No AWS calls."""

import argparse
import json
import re
from pathlib import Path


def statement(actions, resources, **extra):
    return {"Effect": "Allow", "Action": actions, "Resource": resources, **extra}


def policies(account, region, bucket, package, role_name):
    if not re.fullmatch(r"\d{12}", account):
        raise ValueError("Use your 12-digit AWS account ID.")
    if not re.fullmatch(r"[a-z]{2}(?:-[a-z]+)+-\d", region):
        raise ValueError("Use an AWS region such as us-east-1.")
    if not re.fullmatch(r"[a-z0-9][a-z0-9.-]{1,61}[a-z0-9]", bucket):
        raise ValueError("Use a bucket name, without s3:// or a path.")
    if not re.fullmatch(r"[\w+=,.@-]{1,64}", role_name):
        raise ValueError("Use a role name without a path.")
    if not re.fullmatch(
        rf"arn:aws:sagemaker:{region}:\d{{12}}:model-package/[\w./-]+", package
    ):
        raise ValueError("Use the subscribed package ARN in the selected region.")
    bucket_arn = f"arn:aws:s3:::{bucket}"
    sm = f"arn:aws:sagemaker:{region}:{account}"
    role = f"arn:aws:iam::{account}:role/{role_name}"
    logs = f"arn:aws:logs:{region}:{account}:log-group:/aws/sagemaker/TransformJobs"
    bucket_access = [
        statement(["s3:GetBucketLocation"], bucket_arn),
        statement(
            ["s3:ListBucket"],
            bucket_arn,
            Condition={"StringLike": {"s3:prefix": ["smb-public-demo/*"]}},
        ),
    ]
    execution = bucket_access + [
        statement(["s3:GetObject"], bucket_arn + "/smb-public-demo/*/input/*"),
        statement(
            ["s3:PutObject", "s3:AbortMultipartUpload"],
            bucket_arn + "/smb-public-demo/*/output/*",
        ),
        statement(
            [
                "ecr:GetAuthorizationToken",
                "ecr:BatchCheckLayerAvailability",
                "ecr:GetDownloadUrlForLayer",
                "ecr:BatchGetImage",
            ],
            "*",
        ),
        statement(
            [
                "logs:CreateLogGroup",
                "logs:CreateLogStream",
                "logs:PutLogEvents",
                "logs:DescribeLogStreams",
            ],
            logs + ":*",
        ),
        statement(["cloudwatch:PutMetricData"], "*"),
    ]
    caller = bucket_access + [
        statement(
            [
                "s3:GetObject",
                "s3:PutObject",
                "s3:DeleteObject",
                "s3:AbortMultipartUpload",
            ],
            bucket_arn + "/smb-public-demo/*",
        ),
        statement(
            [
                "sagemaker:CreateModel",
                "sagemaker:DescribeModel",
                "sagemaker:DeleteModel",
            ],
            sm + ":model/smb-public-*",
        ),
        statement(
            [
                "sagemaker:CreateTransformJob",
                "sagemaker:DescribeTransformJob",
                "sagemaker:StopTransformJob",
            ],
            sm + ":transform-job/smb-public-*",
        ),
        statement(["sagemaker:DescribeModelPackage"], package),
        statement(
            ["iam:PassRole"],
            role,
            Condition={
                "StringEquals": {"iam:PassedToService": "sagemaker.amazonaws.com"}
            },
        ),
        statement(["aws-marketplace:ViewSubscriptions"], "*"),
        statement(
            ["logs:DescribeLogStreams", "logs:GetLogEvents", "logs:FilterLogEvents"],
            logs + ":*",
        ),
    ]
    trust = [
        {
            "Effect": "Allow",
            "Principal": {"Service": "sagemaker.amazonaws.com"},
            "Action": "sts:AssumeRole",
            "Condition": {
                "StringEquals": {"aws:SourceAccount": account},
                "ArnLike": {"aws:SourceArn": sm + ":*"},
            },
        }
    ]
    return {
        name: {"Version": "2012-10-17", "Statement": statements}
        for name, statements in [
            ("trust", trust),
            ("execution", execution),
            ("caller", caller),
        ]
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("account", "region", "bucket", "package", "role-name", "output"):
        parser.add_argument("--" + name, required=True)
    args = parser.parse_args()
    rendered = policies(
        args.account, args.region, args.bucket, args.package, args.role_name
    )
    output = Path(args.output)
    output.mkdir(parents=True, exist_ok=True)
    for name, policy in rendered.items():
        path = output / (name + ".json")
        path.write_text(json.dumps(policy, indent=2) + "\n")
        print(path)
