# Get help

For a reproducible problem with this notebook or documentation, open an issue
in the public [GitHub issue tracker](https://github.com/standardmodelbio/smb-sagemaker-instructions/issues/new).
Include the step that failed and the exact error message.

For private product questions, sign in to [AWS Marketplace subscriptions](https://console.aws.amazon.com/marketplace/home#/subscriptions),
open your subscribed product, and use the seller support contact shown in its
product details. Use that channel for diagnostics that should not be public.
AWS directs software questions to the seller in its
[buyer support guide](https://docs.aws.amazon.com/marketplace/latest/buyerguide/getting-support.html).

For an AWS account, billing, service quota, or platform problem, use
[AWS Support Center](https://console.aws.amazon.com/support/home). For an IAM
permission error, first give the denied action and resource ARN to your
account administrator together with [the permission setup guide](AWS_SETUP.md).

## Include enough information to reproduce the problem

Provide these details through the appropriate support channel:

- The notebook step, complete error, and whether you used public or own data.
- The AWS region and model package ARN.
- The transform job name and its status or `FailureReason`, if a job was created.
- The request UUID and task from `request-index.json`, plus the response error.
- Relevant CloudWatch log lines from `/aws/sagemaker/TransformJobs`.
- Your Python version and the output of `python -m pip freeze`.
- For public-data mismatches, the named source file and expected and actual checksum.

Do not post patient data, credentials, or private account details to a public
issue. Use a minimal synthetic reproduction when possible. Keep your local
run folder until the problem is resolved. If a job might still be running,
follow [cleanup and recovery](PUBLIC_DATA_WALKTHROUGH.md#10-clean-up-the-tutorial-resources)
before retrying.
