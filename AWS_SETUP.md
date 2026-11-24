# Set up permissions for the batch walkthrough

Use this page if your account does not already have a suitable execution role
and notebook permissions. Complete the product subscription first. An account
administrator performs the IAM setup once. The buyer then runs the notebook
with the caller permissions below.

The notebook identity uploads inputs and submits the job. SageMaker assumes a
separate execution role to read those inputs and write results. Giving one
identity access does not give the other identity access.

## 1. Choose a bucket and sign in

Follow the [local login steps](PUBLIC_DATA_WALKTHROUGH.md#2-set-up-the-notebook)
through `aws sts get-caller-identity`. If you administer IAM through a different
profile, use that profile for the setup commands on this page.

In the S3 console, create a private general purpose bucket in your chosen
region. Keep **Block all public access** enabled and use **SSE-S3** encryption
for this tutorial. A new bucket with versioning disabled makes tutorial object
cleanup complete. You can also use an existing bucket with these settings.

These policies cover the notebook's `smb-public-demo/` prefix. They do not
create buckets, purchase subscriptions, configure a VPC, or grant KMS access.
If your organization requires a customer managed KMS key, its administrator
must also grant the caller and execution role `kms:Decrypt` and
`kms:GenerateDataKey` on that key, with a key policy that permits them. Account
policies and permission boundaries can still restrict the permissions below.

## 2. Generate the three policies

Run this from the repository root with Python 3.12. Replace the example values
with the account shown by `get-caller-identity` and your subscribed package.
The script writes JSON locally and makes no AWS calls.

```bash
python3.12 examples/aws_setup/render_policies.py \
  --account 123456789012 \
  --region us-east-1 \
  --bucket YOUR_BUCKET \
  --package YOUR_MODEL_PACKAGE_ARN \
  --role-name smb-batch-execution \
  --output public-data-demo/iam
```

Open the generated JSON files and check the account, region, bucket, and
package. The files have these purposes:

| File | Attach it to |
|---|---|
| `trust.json` | The execution role's trust policy. Only SageMaker resources in your account and region may assume it. |
| `execution.json` | The execution role. It reads tutorial inputs, writes outputs, pulls the model image, and writes logs and metrics. |
| `caller.json` | Your notebook identity. It manages tutorial models and jobs, accesses tutorial S3 objects, and passes this execution role. |

Image-pull permissions cover ECR repositories because Marketplace supplies the
seller's image. This policy does not grant image-push permission. Job and model
permissions are limited to names beginning with `smb-public-`. Keep that naming
and the S3 prefix when using these policies with your own data.

## 3. Create the execution role

These commands create a new role. Choose a different name in both step 2 and
these commands if `smb-batch-execution` already exists.

```bash
aws iam create-role \
  --role-name smb-batch-execution \
  --assume-role-policy-document file://public-data-demo/iam/trust.json
aws iam put-role-policy \
  --role-name smb-batch-execution \
  --policy-name smb-batch-execution \
  --policy-document file://public-data-demo/iam/execution.json
aws iam get-role --role-name smb-batch-execution --query Role.Arn --output text
```

Copy the returned ARN into `EXECUTION_ROLE_ARN` in the notebook.

## 4. Grant the caller permissions

For an IAM role used by a notebook or an assumed-role profile, an administrator
can attach the caller policy with this command. `YOUR_CALLER_ROLE_NAME` is the
role running Python, which is separate from `smb-batch-execution`.

```bash
aws iam put-role-policy \
  --role-name YOUR_CALLER_ROLE_NAME \
  --policy-name smb-batch-caller \
  --policy-document file://public-data-demo/iam/caller.json
```

For IAM Identity Center, open **Permission sets**, select the permission set
assigned to your account, and add the JSON from `caller.json` to its inline
policy. Preserve any existing statements. Provision the updated permission
set to the account, then log in again with `aws sso login --profile YOUR_PROFILE`.
Do not edit an IAM Identity Center managed role directly.

For an IAM user, use `aws iam put-user-policy` with `--user-name` instead of
`put-role-policy` with `--role-name`.

The policy covers the API calls made by the notebook. Browsing all resources
in the AWS console or creating SageMaker Studio compute requires additional
permissions. Your administrator may already provide those separately.

## 5. Run and clean up

Return to the walkthrough. Its configuration cell verifies the AWS account,
bucket region, and package before downloading the public data. IAM changes
can take time to propagate. If a new role is rejected immediately, wait briefly
and retry after checking the error.

Notebook cleanup removes the temporary model and the run's current S3 objects.
The bucket and IAM roles remain reusable. If you created them only for this
exercise, remove the caller policy from its identity after cleanup, then run:

```bash
aws iam delete-role-policy --role-name smb-batch-execution --policy-name smb-batch-execution
aws iam delete-role --role-name smb-batch-execution
aws s3api delete-bucket --bucket YOUR_BUCKET --region YOUR_REGION
```

Delete the bucket only if you created it for the exercise and it is empty.

The policies follow AWS's [execution-role permissions](https://docs.aws.amazon.com/sagemaker/latest/dg/sagemaker-roles.html)
and [API permission reference](https://docs.aws.amazon.com/sagemaker/latest/dg/api-permissions-reference.html).
