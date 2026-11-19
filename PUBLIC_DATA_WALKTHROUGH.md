# Run multimodal inference on two public patients

This guide uses two patients from the public CPTAC lung adenocarcinoma
collection. For each patient, you will prepare clinical data, one pathology
whole-slide image, and one CT series. You will then submit both patients in
one SageMaker Batch Transform job and match the results back to each input.

The batch has eight requests. Each patient appears in four input combinations:

| Combination | Clinical data | Pathology slide | CT series |
|---|---|---|---|
| `ehr` | Yes | No | No |
| `ehr-wsi` | Yes | Yes | No |
| `ehr-ct` | Yes | No | Yes |
| `ehr-wsi-ct` | Yes | Yes | Yes |

An ablation is a comparison where you leave out part of the input. Here, the
clinical records, task, and cutoff stay the same for a patient. Only the
included imaging changes. We keep clinical data in every combination because
this product requires a usable EHR timeline.

The default task is overall survival, or OS. Each response contains a positive
risk-ranking score. Within the same task and model version, a smaller score
means higher model risk. The score is not a predicted number of days or a
survival probability. Eight responses demonstrate the workflow, not a clinical
performance benchmark.

You do not need a GPU locally. Allow about 3 GB of free disk space for the
download cache and prepared files. The selected source downloads total about
289 MB. The eight uncompressed TAR requests total about 649 MB because each
imaging asset is included in two combinations. These sizes use decimal MB.

Batch Transform uses temporary compute in your AWS account. The inference job
is billable. Check the subscribed product and AWS instance pricing before
submission. S3 storage and notebook compute can have separate charges.
[AWS Batch Transform overview](https://docs.aws.amazon.com/sagemaker/latest/dg/batch-transform.html)

- [Prepare your account](#1-get-your-aws-account-ready).
- [Set up the notebook](#2-set-up-the-notebook).
- [Download and verify the matched assets](#3-download-and-verify-the-matched-assets).
- [Understand the patient files and dates](#4-understand-the-patient-files-and-dates).
- [Inspect the eight requests](#5-inspect-the-eight-requests).
- [Upload and run the batch](#6-check-aws-settings-and-upload-the-requests).
- [Verify the responses](#8-retrieve-and-verify-all-eight-responses).
- [Clean up](#10-clean-up-the-tutorial-resources).
- [Use your own data](#11-replace-the-public-data-with-your-own-data).

## 1. Get your AWS account ready

Use the AWS account where you bought the product. Gather these four values:

| Value | Where to get it |
|---|---|
| AWS region | Choose a region supported by your subscribed product. Use it throughout this guide. |
| Model package ARN | In AWS Marketplace, open your subscription, configure its version and region, and choose **View in Amazon SageMaker AI**. Copy the model package ARN for that version. |
| Execution role ARN | Use a SageMaker execution role in your account. This is the role SageMaker will assume to run the job. |
| S3 bucket name | Use a bucket in the same region. In the S3 console, choose **Create bucket** if you need one. Keep it private. |

An ARN is AWS's full identifier for a resource. The package ARN identifies
the product version. The role ARN identifies the permissions SageMaker will
use. They are different values. The package can belong to the seller's account.
The execution role must belong to yours.
[AWS Marketplace deployment instructions](https://docs.aws.amazon.com/marketplace/latest/buyerguide/deploying-ml-products.html)

Your notebook or local AWS identity needs permission to create, describe, stop,
and clean up this job and its model. It also needs permission to describe the
model package, pass the execution role with `iam:PassRole`, and read and write
the tutorial's S3 objects. Cleanup also needs permission to delete those objects.

The execution role must trust `sagemaker.amazonaws.com` and have the required
model image and logging permissions. It must be able to list the bucket, read
the input objects, and write the output objects. If your bucket uses a customer
managed KMS key, the relevant identities also need access to that key.

To create the role, follow AWS's
[SageMaker execution role instructions](https://docs.aws.amazon.com/sagemaker/latest/dg/sagemaker-roles.html).
The standard `AmazonSageMakerFullAccess` policy does not give access to every
arbitrarily named S3 bucket. Add access to your chosen bucket if needed.

This guide uses one `ml.g5.2xlarge` instance. Check that your subscribed version
supports it and that your account has a nonzero SageMaker quota for
`ml.g5.2xlarge` **transform job usage** in your region. An endpoint quota is a
different quota. In **Service Quotas**, select **Amazon SageMaker**, find the
transform quota, and request an increase if its value is zero.

## 2. Set up the notebook

Download this repository, including `examples/public_multimodal/`. Open the
included [public_multimodal_walkthrough.ipynb](public_multimodal_walkthrough.ipynb).
It already contains the explanations and executable cells below. You do not
need to create a notebook or copy code blocks. The notebook keeps each step
and its output together while you learn the workflow. The product accepts
SageMaker API requests; your production pipeline can make the same Boto3
calls from a Python program without Jupyter.

For a fresh local environment on macOS or Linux, install Python 3.12, then run
these commands from the repository root:

```bash
python3.12 -m venv .venv-public-demo
source .venv-public-demo/bin/activate
python -m pip install --no-cache-dir "jupyterlab>=4,<5" "ipykernel>=6,<8"
python -m ipykernel install --sys-prefix --name smb-public-demo --display-name "Python 3.12 (SMB public demo)"
jupyter lab public_multimodal_walkthrough.ipynb
```

Select the **Python 3.12 (SMB public demo)** kernel. In SageMaker Studio, open
the same notebook in the repository root and select a Python 3.12 kernel.
See the [JupyterLab installation instructions](https://jupyterlab.readthedocs.io/en/stable/getting_started/installation.html)
and [IPython kernel instructions](https://ipython.readthedocs.io/en/stable/install/kernel_install.html)
if you need to configure another environment.

Fill in the four AWS settings in the configuration cell. Then choose
**Run > Run All Cells** once, or run cells individually in order. Run All
installs the data packages, prepares inputs, runs the paid AWS job, verifies
the results, and removes its temporary model and current S3 objects. Your
downloaded data and results stay on disk. The recovery cell does nothing
during a normal run. Rerunning the whole notebook creates another job.

The notebook needs internet access for the public downloads. You do not need
a GDC or TCIA account for the selected files. Install the packages:

```python
%pip install --no-cache-dir -r examples/public_multimodal/requirements.txt
```

OpenSlide is used to check that the slide files can be read. The `openslide-bin`
package supplies its native library. See the
[OpenSlide installation instructions](https://openslide.org/api/python/#installing)
if your environment does not support that package.

SageMaker notebooks can use their attached role for AWS credentials. For a
local notebook using IAM Identity Center, run `aws configure sso` and then
`aws sso login --profile YOUR_PROFILE` in a terminal. Set
`AWS_PROFILE=YOUR_PROFILE` in the terminal where you start JupyterLab.
An existing default AWS credential profile also works.

You can instead supply the four settings through `SMB_REGION`,
`SMB_MODEL_PACKAGE_ARN`, `SMB_EXECUTION_ROLE_ARN`, and `SMB_BUCKET` environment
variables before starting JupyterLab. The configuration cell reads them by
default. These identify resources; use your AWS credential profile for login.

Fill in your four AWS settings. `BUCKET` is a bucket name without `s3://` or
a folder. Input preparation in steps 3 to 5 does not create any AWS resources.

```python
import csv
import hashlib
import json
import math
import os
import subprocess
import sys
import tarfile
import time
import uuid
from pathlib import Path

import boto3
import polars as pl
from botocore.exceptions import ClientError

REGION = os.environ.get("SMB_REGION", "us-east-1")
MODEL_PACKAGE_ARN = os.environ.get("SMB_MODEL_PACKAGE_ARN", "")  # Or paste your package ARN.
EXECUTION_ROLE_ARN = os.environ.get("SMB_EXECUTION_ROLE_ARN", "")  # Or paste your role ARN.
BUCKET = os.environ.get("SMB_BUCKET", "")  # Or paste your bucket name.
INSTANCE_TYPE = "ml.g5.2xlarge"

assert sys.version_info[:2] == (3, 12), "Select a Python 3.12 kernel."
assert MODEL_PACKAGE_ARN and EXECUTION_ROLE_ARN and BUCKET, "Fill in the four AWS settings."
print("Notebook kernel:", sys.executable)
helper = Path("examples/public_multimodal/prepare_inputs.py")
assert helper.is_file(), "Open the notebook in the repository root."
run_id = "smb-public-" + time.strftime("%Y%m%d-%H%M%S") + "-" + uuid.uuid4().hex[:8]
work = Path("public-data-demo") / run_id
work.mkdir(parents=True, exist_ok=False)
prefix = "smb-public-demo/" + run_id + "/"
print("Run folder:", work.resolve())
```

## 3. Download and verify the matched assets

We use CPTAC-LUAD because its CT files include a documented day offset from
pathologic diagnosis. This lets us place the scans on the same time axis as
the clinical records and tissue specimens.

These are the exact selected records:

| Patient | Tumor specimen | Slide | Specimen day | CT day | CT slices |
|---|---|---|---:|---:|---:|
| `C3L-00263` | `C3L-00263-04` | `C3L-00263-24.svs` | 0 | -1 | 71 |
| `C3L-00422` | `C3L-00422-02` | `C3L-00422-22.svs` | 0 | -109 | 69 |

Both CT series are complete original axial chest series with 512 by 512 pixels
per slice. We selected one small series per patient, rather than downloading
every series in each study. No slices or slide pixels are edited. The study
and series UIDs, file checksums, and source URLs are recorded in the
[cohort manifest](examples/public_multimodal/cohort.json).

The clinical records and slide-to-specimen links come from the
[CPTAC PathDB metadata](https://pathdb.cancerimagingarchive.net/system/files/collectionmetadata/202407/cptac_metadata_07-09-2024.csv).
The matching GDC cases are
[C3L-00263](https://portal.gdc.cancer.gov/cases/3a7449d1-7761-4c8e-afc0-9968b1f33305)
and [C3L-00422](https://portal.gdc.cancer.gov/cases/67c1aa6e-0bc7-40e2-9742-8f73be3ed450).
GDC provides each specimen's procurement day and its linked slide identifier.
The repository includes the two public GDC responses recorded on November 19,
2026, with their original URLs and SHA-256 hashes in the
[metadata source record](examples/public_multimodal/metadata/sources.json).
The helper verifies and uses these fixed metadata snapshots. It does not need
the live GDC API.
Clinical tables and both sets of images are downloaded from TCIA and PathDB.
The CT instances come from the public NBIA API linked by the
[CPTAC-LUAD collection](https://www.cancerimagingarchive.net/collection/cptac-luad/).

Run the included preparation helper. It downloads the selected assets, checks
their identities and dates, and writes the Parquet tables and TAR requests.
You can read every conversion in
[prepare_inputs.py](examples/public_multimodal/prepare_inputs.py).

```python
subprocess.run([
    sys.executable, str(helper),
    "--output", str(work),
    "--cache", "public-data-demo/cache",
], check=True)
index = json.loads((work / "request-index.json").read_text())
cohort = json.loads((work / "cohort.json").read_text())
verification = json.loads((work / "verification.json").read_text())
PATIENT_IDS = [patient["patient_id"] for patient in cohort["patients"]]
assert len(index) == 8
```

Expect this message:

```text
PASS: matched 2 patients; verified 2 slides and 140 CT slices; wrote 8 requests.
```

The helper checks the following before it writes the request index:

1. The clinical case, pathology portal subject, and every CT `PatientID` agree.
2. The exact slide belongs to the exact tumor specimen in both PathDB and GDC.
3. GDC uses `Diagnosis` as the case's time origin and provides the expected
   specimen procurement day. A missing date causes an error.
4. Every CT instance has the expected study UID and series UID. Its
   `ClinicalTrialTimePointID` contains the expected diagnosis-relative day.
5. Both slide checksums and every CT instance checksum match the verified
   assets. Both slides open in OpenSlide, and all 140 CT pixel arrays decode.

It saves the downloaded and bundled source metadata under `sources/` and its matching
evidence in `verification.json`. The large downloads are cached separately.
If a step fails, correct the reported problem and use a new run folder. Keep
the cache so you do not have to download successful files again. Never bypass
an identity, date, or checksum error to obtain a prediction.

## 4. Understand the patient files and dates

Each patient now has this layout. `STUDY_UID` and `SERIES_UID` stand for the
long identifiers saved in the manifest:

```text
patients/C3L-00263/
  ehr/
    patient_characteristics.parquet
    diagnosis.parquet
    wsi_list.parquet
    dicom_inventory_file.parquet
  pathology/
    C3L-00263-24.svs
  radiology/
    STUDY_UID/
      SERIES_UID/
        SOP_INSTANCE_UID.dcm
        ...
```

Parquet is the product's format for clinical tables and imaging metadata. The
slide stays an SVS file. The CT stays a directory of DICOM files. You do not
put the image pixels into Parquet.

| Table | Fields and source |
|---|---|
| `patient_characteristics.parquet` | PathDB `Case_ID` becomes `PTID`. `Age` becomes `AGE`, and `Gender` becomes `SEX`. Race and ethnicity retain their corresponding fields. Unknown values become null. |
| `diagnosis.parquet` | The initial diagnosis is day 0 on GDC's diagnosis axis. PathDB's `Topographic_Site` becomes `ANATOMIC_SITE`, and `Tumor_Histological_Type` becomes `HISTOLOGY`. |
| `wsi_list.parquet` | `DEID_ACCESSION_NUMBER` uses the public specimen ID as the grouping identifier. `PATHOLOGY_IMG_FILENAME` matches the SVS basename. `SLIDE_INTERVAL` uses that specimen's GDC `days_to_sample_procurement`. `DATE_SOURCE` records this choice explicitly. |
| `dicom_inventory_file.parquet` | `FULL_FILE_NAME` is `patient_id/STUDY_UID`. `IMG_INTERVAL` comes from the CT's `ClinicalTrialTimePointID`. The study directory must exist under `input/radiology/` in the request. |

Inspect the actual tables:

```python
for patient_id in PATIENT_IDS:
    print(patient_id)
    for path in sorted((work / "patients" / patient_id / "ehr").glob("*.parquet")):
        print(path.name)
        print(pl.read_parquet(path))
```

The two patients have ages 80 and 35 in the source table. The selected clinical
features contain demographics and diagnosis information. Later vital status,
survival outcomes, and follow-up are excluded from the model inputs.

### How the dates line up

Day zero is pathologic diagnosis for each patient. Both selected tumor
specimens were procured on day zero. The CT for C3L-00263 was acquired on day
-1. The CT for C3L-00422 was acquired on day -109. The cutoff is zero for every
combination, so these selected events are eligible in all eight requests.

For CT, use DICOM tag `(0012,0050)`, `ClinicalTrialTimePointID`. TCIA defines it
as the number of days from initial pathologic diagnosis to the scan. Do not
subtract the DICOM `StudyDate` from a clinical date. Those calendar dates were
shifted during deidentification.
[CPTAC date conventions](https://www.cancerimagingarchive.net/collection/cptac-luad/)

For the slide, we use the specimen procurement day. GDC defines
`days_to_sample_procurement` relative to the case's `index_date`. The case
records and sample-to-slide links establish that date for these exact slides.
Do not substitute `days_to_collection`, which describes receipt for processing.
[GDC sample field definitions](https://api.gdc.cancer.gov/v0/submission/_dictionary/sample)

This is a retrospective example aligned to the tissue specimen's date. It
does not establish that the digitized slide was available to a clinician on
day zero. The public slide records do not provide that diagnosis-relative
availability date. SVS scanner dates and portal upload timestamps are not used
to make one up. For a prospective evaluation on your own data, also establish
when each result or image became available and choose the cutoff accordingly.

## 5. Inspect the eight requests

Each TAR contains one patient, one task, and one input combination. Both
patients go in the same batch as separate objects. Sending one multi-patient
TAR would not perform batch inference correctly.

An `ehr-wsi-ct` request has this layout:

```text
request.json
input/ehr/patient_characteristics.parquet
input/ehr/diagnosis.parquet
input/ehr/wsi_list.parquet
input/ehr/dicom_inventory_file.parquet
input/pathology/C3L-00263-24.svs
input/radiology/STUDY_UID/SERIES_UID/SOP_INSTANCE_UID.dcm
...
```

The `ehr` request contains only the first two Parquet tables. The `ehr-wsi`
request adds the slide and its metadata. The `ehr-ct` request adds the CT and
its metadata. This also prevents an omitted image from appearing as an event
through a leftover metadata table.

```python
expected = {(patient_id, ablation) for patient_id in PATIENT_IDS
            for ablation in ("ehr", "ehr-wsi", "ehr-ct", "ehr-wsi-ct")}
assert {(item["patient_id"], item["ablation"]) for item in index} == expected
assert len({item["request"]["request_uuid"] for item in index}) == 8
for item in index:
    path = work / "requests" / item["filename"]
    with tarfile.open(path, "r:") as archive:
        members = archive.getmembers()
        assert len(members) == item["archive_members"]
        assert all(member.isfile() for member in members)
        assert members[0].name == "request.json"
        with archive.extractfile("request.json") as stream:
            assert json.load(stream) == item["request"]
    print(item["patient_id"], item["ablation"], round(item["bytes"] / 1e6, 1), "MB")
full = next(item for item in index if item["ablation"] == "ehr-wsi-ct")
print(json.dumps(full["request"], indent=2))
```

The manifest selects `time_to_death`, task version `1.0`, empty `task_inputs`,
and cutoff `0`. Its `data_objects` contains `ehr`, `wsi`, and `radiology` for
the full request. The logical paths `/input/ehr`, `/input/pathology`, and
`/input/radiology` refer to directories inside the TAR. They are not URLs.

`request-index.json` maps each unique request UUID back to its patient and
combination. The model does not return your patient ID or ablation name, so
keep this index with your results. Keep the existing TAR and UUID when retrying
the same request. Generate a new UUID when its contents or task change.

## 6. Check AWS settings and upload the requests

This cell checks your account, bucket region, and the package's supported
instance types before creating compute. If an assertion fails, correct the
setting named in the error before continuing.

```python
assert MODEL_PACKAGE_ARN and EXECUTION_ROLE_ARN and BUCKET, "Fill in the AWS settings."
assert MODEL_PACKAGE_ARN.split(":")[3] == REGION, "Package and job region differ."
session = boto3.Session(region_name=REGION)
sm = session.client("sagemaker")
s3 = session.client("s3")
account = session.client("sts").get_caller_identity()["Account"]
assert EXECUTION_ROLE_ARN.split(":")[4] == account, "Role must be in your account."
location = s3.get_bucket_location(Bucket=BUCKET).get("LocationConstraint")
bucket_region = {None: "us-east-1", "EU": "eu-west-1"}.get(location, location)
assert bucket_region == REGION, "Bucket and job region differ."
package = sm.describe_model_package(ModelPackageName=MODEL_PACKAGE_ARN)
spec = package["InferenceSpecification"]
assert INSTANCE_TYPE in spec.get("SupportedTransformInstanceTypes", []), spec
assert "application/x-tar" in spec.get("SupportedContentTypes", []), spec
assert "application/json" in spec.get("SupportedResponseMIMETypes", []), spec
assert any(container.get("ProductId") for container in spec["Containers"]), (
    "Use the subscribed Marketplace model package."
)

state = {
    "region": REGION,
    "account": account,
    "model_package_arn": MODEL_PACKAGE_ARN,
    "execution_role_arn": EXECUTION_ROLE_ARN,
    "instance_type": INSTANCE_TYPE,
    "bucket": BUCKET,
    "prefix": prefix,
    "model_name": run_id,
    "job_name": run_id,
    "cohort_sha256": hashlib.sha256((work / "cohort.json").read_bytes()).hexdigest(),
}
(work / "run.json").write_text(json.dumps(state, indent=2))
(work / "package-description.json").write_text(json.dumps(package, indent=2, default=str))

for item in index:
    with (work / "requests" / item["filename"]).open("rb") as stream:
        assert hashlib.file_digest(stream, "sha256").hexdigest() == item["sha256"]
    s3.upload_file(
        str(work / "requests" / item["filename"]), BUCKET,
        prefix + "input/" + item["filename"],
        ExtraArgs={"ContentType": "application/x-tar"},
    )
print("Uploaded 8 requests to", "s3://" + BUCKET + "/" + prefix + "input/")
print("Saved recovery settings to", (work / "run.json").resolve())
```

Only the eight TAR files belong under this S3 input prefix. Keep the source
metadata, request index, and any other files outside it. SageMaker will attempt to
process every object under the input prefix.

## 7. Submit the inference job and wait for completion

Run the submission cell once. It creates a SageMaker model resource from your
subscribed package and starts one job. It does not train or change the model.

The model runs with network isolation. SageMaker reads your S3 objects using
the execution role and delivers each TAR to the container. The container does
not fetch the public dataset or read URLs from `request.json`.

```python
sm.create_model(
    ModelName=state["model_name"],
    ExecutionRoleArn=EXECUTION_ROLE_ARN,
    PrimaryContainer={"ModelPackageName": MODEL_PACKAGE_ARN},
    EnableNetworkIsolation=True,
)
job_request = {
    "TransformJobName": state["job_name"],
    "ModelName": state["model_name"],
    "BatchStrategy": "SingleRecord",
    "MaxConcurrentTransforms": 1,
    "MaxPayloadInMB": 0,
    "ModelClientConfig": {"InvocationsTimeoutInSeconds": 3600, "InvocationsMaxRetries": 1},
    "TransformInput": {
        "DataSource": {"S3DataSource": {
            "S3DataType": "S3Prefix",
            "S3Uri": "s3://" + BUCKET + "/" + prefix + "input/",
        }},
        "ContentType": "application/x-tar",
        "CompressionType": "None",
        "SplitType": "None",
    },
    "TransformOutput": {
        "S3OutputPath": "s3://" + BUCKET + "/" + prefix + "output/",
        "Accept": "application/json",
        "AssembleWith": "None",
    },
    "TransformResources": {
        "InstanceType": INSTANCE_TYPE,
        "InstanceCount": 1,
        "TransformAmiVersion": "al2-ami-sagemaker-batch-gpu-535",
    },
}
(work / "job-request.json").write_text(json.dumps(job_request, indent=2))
sm.create_transform_job(**job_request)
print("Submitted:", state["job_name"])
```

`SplitType="None"` keeps each TAR intact. `MaxConcurrentTransforms=1` sends one
request at a time to the instance. `MaxPayloadInMB=0` enables chunked input for
this product; it does not mean an empty request. Keep these settings when
adapting the example to larger patient inputs.
[AWS transform job API](https://docs.aws.amazon.com/sagemaker/latest/APIReference/API_CreateTransformJob.html)

The submission call returns before inference finishes. Use the next cell to
check the status every 30 seconds. It allows up to 90 minutes of waiting and
prints the job name if you need to investigate. That limit applies to this
local wait, not to the AWS job's lifetime.

```python
deadline = time.monotonic() + 90 * 60
while True:
    description = sm.describe_transform_job(TransformJobName=state["job_name"])
    status = description["TransformJobStatus"]
    print(time.strftime("%H:%M:%S"), status, flush=True)
    if status in {"Completed", "Failed", "Stopped"}:
        break
    if time.monotonic() >= deadline:
        raise TimeoutError("Job may still be running. Inspect it or run step 10 cleanup.")
    time.sleep(30)
(work / "job-description.json").write_text(json.dumps(description, indent=2, default=str))
assert status == "Completed", description.get("FailureReason", status)
print("Inference completed. Retrieve the results in step 8.")
```

Expect `InProgress` while AWS provisions the instance, loads the model, and
processes the requests. A small dataset can still spend time in startup.
There is no guaranteed completion time in this guide.

If the notebook disconnects, the AWS job continues. Do not submit it again just
to check progress. Open the SageMaker console in your region and find the job
under **Inference**, then **Batch transform jobs**, using the saved job name.
Step 10 includes code for restoring the saved settings.

## 8. Retrieve and verify all eight responses

For `C3L-00263-ehr-wsi-ct-os.tar`, expect
`C3L-00263-ehr-wsi-ct-os.tar.out` under the output prefix. The output is one
JSON object. It is not a TAR, despite its name. AWS appends `.out` to the input
object name. [AWS output naming](https://docs.aws.amazon.com/sagemaker/latest/dg/batch-transform.html)

Check job completion, all eight output files, and the identity of every
response. Then save a table with one row per patient and combination:

```python
assert sm.describe_transform_job(TransformJobName=state["job_name"])["TransformJobStatus"] == "Completed"
expected_keys = {prefix + "output/" + item["filename"] + ".out" for item in index}
actual_keys = set()
for page in s3.get_paginator("list_objects_v2").paginate(Bucket=BUCKET, Prefix=prefix + "output/"):
    actual_keys.update(obj["Key"] for obj in page.get("Contents", []))
assert actual_keys == expected_keys, {
    "missing": sorted(expected_keys - actual_keys),
    "unexpected": sorted(actual_keys - expected_keys),
}

def verify_response(value, request):
    assert isinstance(value, dict) and "error" not in value, value
    for field in ("schema_version", "request_uuid", "task_id", "task_version"):
        assert value.get(field) == request[field], (field, value)
    assert value.get("score_type") == "rank_preserving_pseudo_days", value
    score = value.get("prediction")
    assert isinstance(score, (int, float)) and not isinstance(score, bool), value
    assert math.isfinite(score) and score > 0, value

responses = {}
summary = []
for item in index:
    key = prefix + "output/" + item["filename"] + ".out"
    with s3.get_object(Bucket=BUCKET, Key=key)["Body"] as stream:
        value = json.load(stream)
    verify_response(value, item["request"])
    responses[item["filename"]] = value
    (work / "results" / (item["filename"] + ".out")).write_text(json.dumps(value, indent=2))
    summary.append({
        "patient_id": item["patient_id"], "ablation": item["ablation"],
        "task": item["task_label"], "request_uuid": value["request_uuid"],
        "prediction": value["prediction"], "score_type": value["score_type"],
    })
assert len(summary) == 8
assert {(row["patient_id"], row["ablation"]) for row in summary} == {
    (patient_id, ablation) for patient_id in PATIENT_IDS
    for ablation in ("ehr", "ehr-wsi", "ehr-ct", "ehr-wsi-ct")
}
with (work / "predictions.csv").open("w", newline="") as stream:
    writer = csv.DictWriter(stream, fieldnames=list(summary[0]))
    writer.writeheader()
    writer.writerows(summary)
print("PASS: all 8 patient/combination responses are present and valid.")
print(pl.DataFrame(summary).pivot(on="ablation", index=["patient_id", "task"], values="prediction"))
print(json.dumps(responses[index[0]["filename"]], indent=2))
```

Expect two rows in the printed comparison, with four score columns. Your
`predictions.csv` contains the same eight scores in separate rows, along with
their request UUIDs. Read an individual response as follows:

| Field | Expected value |
|---|---|
| `schema_version` | `"1.0"`. |
| `request_uuid` | The UUID recorded for this exact TAR. |
| `task_id` | `"time_to_death"` for the default OS run. |
| `task_version` | `"1.0"`. |
| `prediction` | A finite number greater than zero. |
| `score_type` | `"rank_preserving_pseudo_days"`. |

### Recorded AWS outputs

The notebook ran these eight requests in AWS on November 19, 2026. The job completed on
one `ml.g5.2xlarge` in `us-east-1`, with network isolation enabled. All eight
responses passed the checks above. The measured OS scores were:

| Patient | `ehr` | `ehr-wsi` | `ehr-ct` | `ehr-wsi-ct` |
|---|---:|---:|---:|---:|
| `C3L-00263` | 291.09576153 | 271.37754702 | 296.24379776 | 260.38882875 |
| `C3L-00422` | 272.53007848 | 277.64935748 | 345.72121953 | 319.67090811 |

The table is rounded to eight decimal places. The
[recorded CSV](examples/public_multimodal/reference-run/predictions.csv)
contains the full values. For example, the actual response for C3L-00263 with
clinical data, its slide, and CT was:

```json
{
  "schema_version": "1.0",
  "request_uuid": "7d04b3eb-a8b8-4e0f-817b-2ae5f8ba5ff5",
  "task_id": "time_to_death",
  "task_version": "1.0",
  "prediction": 260.38882875210766,
  "score_type": "rank_preserving_pseudo_days"
}
```

Your new requests will have different UUIDs. Check each response against your
own request index. Compare numerical scores by patient, combination, and task.

The [expected-results record](examples/public_multimodal/reference-run/run.json)
identifies the model package and image used for these scores. Use the package
from your subscription. Scores can differ when the model or inputs differ.

The observed AWS job took 482.871 seconds, or about 8.0 minutes, including
provisioning and model startup. Allow for variation in startup and processing
time. The [expected-results directory](examples/public_multimodal/reference-run/README.md)
contains all eight responses and their request settings.

The following cell compares your OS scores with the expected results.
It applies only to the same model image, patient file contents, and request
settings. Patient file fingerprints exclude generated request UUIDs and TAR
timestamps, so a fresh download can be compared with the recorded run.
It checks numerical agreement using relative tolerance `1e-6` and absolute
tolerance `1e-8`. If scores differ, retain both runs and investigate the package,
inputs, and runtime before treating the difference as a model finding.

```python
reference_dir = Path("examples/public_multimodal/reference-run")
reference_run = json.loads((reference_dir / "run.json").read_text())
reference_index = json.loads((reference_dir / "request-index.json").read_text())
current_package = json.loads((work / "package-description.json").read_text())
current_digest = current_package["InferenceSpecification"]["Containers"][0].get("ImageDigest")

def comparison_inputs(items):
    return {
        (item["patient_id"], item["ablation"], item["task_label"]): {
            "patient_input_sha256": item["patient_input_sha256"],
            "request": {key: value for key, value in item["request"].items() if key != "request_uuid"},
        }
        for item in items
    }

same_setup = (
    current_digest == reference_run["image_digest"]
    and comparison_inputs(index) == comparison_inputs(reference_index)
    and {row["task"] for row in summary} == {"os"}
)
if same_setup:
    with (reference_dir / "predictions.csv").open(newline="") as stream:
        expected_scores = {(row["patient_id"], row["ablation"], row["task"]): float(row["prediction"])
                           for row in csv.DictReader(stream)}
    differences = []
    for row in summary:
        key = (row["patient_id"], row["ablation"], row["task"])
        expected_score = expected_scores[key]
        if not math.isclose(row["prediction"], expected_score, rel_tol=1e-6, abs_tol=1e-8):
            differences.append({"input": key, "expected": expected_score, "actual": row["prediction"]})
    assert not differences, differences
    print("PASS: all 8 OS scores match the recorded AWS run within tolerance.")
else:
    print("Numerical comparison skipped: this run uses a different image, patient input, or request setting.")
```

These scores verify the example's inference workflow. They do not establish
clinical accuracy or predict a number of survival days.

## 9. Interpret the comparison and retain the evidence

Compare the four combinations within each patient. There is no required
direction of change when you add imaging. More modalities need not produce a
larger or smaller score. Different combinations may return the same score.
Two patients are enough to learn the batch interface, but not enough to measure
whether a modality improves predictions.

The preparation helper verifies that the intended image files are present and
correctly linked. See the [patient and date checks](examples/public_multimodal/VERIFICATION.md)
for the source relationships and expected image inputs.

The service response contains no per-image usage report. A valid response, or
a changed score between combinations, does not by itself prove that every
image was used. When using your own inputs, inspect matching metadata and
cutoffs first. Missing or unresolved images can be omitted by preprocessing.

Keep these files together:

| File or directory | Purpose |
|---|---|
| `cohort.json`, `sources/`, `verification.json` | The asset identities and the evidence for their dates. |
| `request-index.json`, `requests/` | The exact input archives and the patient/combination mapping. |
| `run.json`, `package-description.json`, `job-request.json` | The AWS account, package, and job configuration. |
| `job-description.json`, `results/`, `predictions.csv` | Job status and the returned predictions. |

For a numerical reproducibility check, submit the same saved TARs using the
same package and instance configuration under a new job name and output prefix.
Join responses by UUID and compare scores with `math.isclose`, using relative
tolerance `1e-6` and absolute tolerance `1e-8`. Retain both runs if they disagree.
That tests repeatability, not predictive accuracy. Assess accuracy separately
using appropriate outcomes and follow-up, without including those outcomes in
the inference inputs.

## 10. Clean up the tutorial resources

Run cleanup after saving your results, including when an earlier step failed.
If the job is still running, this cell stops it and waits for a terminal state
before deleting the model resource. It leaves your local files intact.

Leave `RECOVER_RUN` empty for a normal run. If you restarted the kernel,
run the installation cell, set `RECOVER_RUN` to the folder printed in step 6,
and run this recovery cell. Then run the cleanup cell. To collect completed
outputs first, run step 8 after recovery. Do not rerun the configuration or
submission cells to recover an existing job.

```python
RECOVER_RUN = ""  # Recovery only, e.g. "public-data-demo/smb-public-YOUR_RUN".
if RECOVER_RUN:
    import csv
    import hashlib
    import json
    import math
    import time
    from pathlib import Path
    import boto3
    import polars as pl
    from botocore.exceptions import ClientError

    work = Path(RECOVER_RUN)
    state = json.loads((work / "run.json").read_text())
    index = json.loads((work / "request-index.json").read_text())
    REGION, BUCKET, prefix = state["region"], state["bucket"], state["prefix"]
    PATIENT_IDS = list(dict.fromkeys(item["patient_id"] for item in index))
    session = boto3.Session(region_name=REGION)
    sm, s3 = session.client("sagemaker"), session.client("s3")
    print("Restored:", state["job_name"])
```

Then run the cleanup cell. It deletes only the exact input and output keys for
this run. It does not delete the bucket or any unrelated S3 folder.

```python
def is_missing_resource(error):
    details = error.response["Error"]
    message = details.get("Message", "").lower()
    return details["Code"] in {"ResourceNotFound", "ResourceNotFoundException"} or (
        details["Code"] == "ValidationException"
        and any(text in message for text in ("could not find", "does not exist", "not found"))
    )

try:
    status = sm.describe_transform_job(TransformJobName=state["job_name"])["TransformJobStatus"]
except ClientError as error:
    if not is_missing_resource(error):
        raise
    status = "NotCreated"
if status == "InProgress":
    sm.stop_transform_job(TransformJobName=state["job_name"])
while status in {"InProgress", "Stopping"}:
    time.sleep(30)
    status = sm.describe_transform_job(TransformJobName=state["job_name"])["TransformJobStatus"]
assert status in {"Completed", "Failed", "Stopped", "NotCreated"}, status

try:
    sm.delete_model(ModelName=state["model_name"])
except ClientError as error:
    if not is_missing_resource(error):
        raise

keys = []
for item in index:
    keys.append({"Key": prefix + "input/" + item["filename"]})
    keys.append({"Key": prefix + "output/" + item["filename"] + ".out"})
deleted = s3.delete_objects(Bucket=BUCKET, Delete={"Objects": keys})
assert not deleted.get("Errors"), deleted.get("Errors")
try:
    sm.describe_model(ModelName=state["model_name"])
except ClientError as error:
    if not is_missing_resource(error):
        raise
else:
    raise AssertionError("The temporary model still exists.")
remaining = []
for page in s3.get_paginator("list_objects_v2").paginate(Bucket=BUCKET, Prefix=prefix):
    remaining.extend(obj["Key"] for obj in page.get("Contents", []))
assert not remaining, remaining
cleanup = {"job_status": status, "temporary_model_absent": True, "current_s3_objects_remaining": 0}
(work / "cleanup.json").write_text(json.dumps(cleanup, indent=2))
print("PASS: job is terminal; temporary model and current S3 objects are removed.")
print("Local inputs and results remain in", work.resolve())
```

Completed job history and CloudWatch logs remain. If S3 versioning is enabled,
deleting current objects can leave older versions and delete markers. Use your
bucket's retention rules or remove those versions separately if required.
Stop any notebook compute you started for the tutorial. This workflow created
no endpoint to delete.

## 11. Replace the public data with your own data

The batch mechanism stays the same. Your main new work is producing each
patient's clinical tables and correctly linking their images.

1. Choose your prediction time. Establish which records and images were
   available then. For slides, distinguish tissue procurement from digitization
   and report availability when your intended use requires it.
2. Select a common day origin for each patient. Convert every event to that
   axis and express the observation cutoff on the same axis. Do not mix
   diagnosis-relative offsets with shifted calendar dates. Keep the date source
   beside each conversion.
3. Map your clinical fields to the supported Parquet filenames and columns.
   Preserve recorded units and missing values. The example's demographics and
   diagnosis are a small clinical subset, not a complete longitudinal EHR.
4. Match each slide to its patient and specimen. Put its basename and day in
   `wsi_list.parquet`. Include the actual supported slide file. A thumbnail or
   slide URL is not a substitute for the image.
5. Match each CT study and series to its patient. Check the DICOM headers,
   preserve the study/series layout, and put the study path and acquisition day
   in `dicom_inventory_file.parquet`. Exclude scouts and unusable acquisitions.
6. Package one patient, task, cutoff, and modality combination per TAR. Keep
   the patient-to-request mapping outside `request.json`. If you use ablations,
   hold clinical data and cutoff fixed while changing the image inputs.
7. Start with a few patients in one new S3 prefix. Submit the same Batch
   Transform configuration and require one matching response per archive.
   Retain input checksums and the package version before scaling up.

Use the [clinical table reference](README.md#ehr) for filenames, column types,
and required fields. It covers the walkthrough's demographics and diagnosis
tables, plus optional clinical history such as labs, treatment, and notes.
Include `patient_characteristics.parquet` for each patient and dated clinical
or image events at or before the cutoff. The same README documents the
[slide metadata](README.md#pathology-whole-slide-images) and
[CT metadata](README.md#ct-and-other-radiology-data).

The default example runs OS only to keep the job small. To try time to next
treatment or death, create a new run folder and add `"--task", "ttnt"` to the
helper command in step 3. It will create the same eight combinations with
`task_id="time_to_next_treatment_or_death"` and new UUIDs. Use the new index for
the rest of the guide. Both tasks use `task_version="1.0"` and `task_inputs={}`.
Do not compare OS and TTNT scores as if they share a time scale.

Use streaming Batch Transform for these slides. Keep `SplitType="None"`,
`MaxPayloadInMB=0`, and `MaxConcurrentTransforms=1`. Check the
[input limits](README.md#batch-transform) before using larger inputs.
Prepare and upload archives as files rather than loading multi-gigabyte TARs
into memory.

## If something goes wrong

| What you see | What to do |
|---|---|
| `Open the notebook in the repository root` | Change the notebook's working directory to the folder containing this README and `examples/`. |
| OpenSlide cannot be imported | Install both `openslide-python` and its native library, as described in step 2. Restart the kernel after installation if needed. |
| A public download times out | Retry in a new run folder while keeping `public-data-demo/cache`. Partial downloads have `.part` filenames and are not treated as complete. |
| A checksum, patient, specimen, or date check fails | Read the named source record in `sources/`. Verify the manifest against the public source. Do not silently replace an asset or invent a date. |
| The CT checksum check fails for a cached ZIP | Remove only that patient's ZIP from the download cache, then retry in a new run folder. A second failure needs source investigation. |
| AWS reports missing credentials | Log in to your local AWS profile, or check the role attached to the SageMaker notebook. |
| `AccessDenied` or `iam:PassRole` | Check the caller's permissions separately from the execution role's permissions, including access to your S3 bucket and any KMS key. |
| A subscription or package error | Confirm the subscription in the selected AWS account and copy the package ARN for the selected region and version. |
| `ResourceLimitExceeded` | Check the regional `ml.g5.2xlarge` transform-job quota. Endpoint quotas are separate. |
| A model or job name already exists | Inspect that job before submitting again. Use a new job name for a deliberate retry after a terminal failure. |
| `invalid_archive` or `unsupported_content_type` | Use an uncompressed TAR with `request.json` at its root and `application/x-tar`. Do not upload the downloaded CT ZIP as the inference request. |
| `invalid_patient_input` | Check table names and columns, manifest paths, and cutoff. An image directory alone is not a complete request. |
| `payload_too_large` on these images | Check the archive size and member count against the input limits. Use the documented streaming Batch Transform settings. |
| The notebook disconnects or waiting times out | The AWS job may still be running. Restore `run.json` using step 10, then inspect the job, retrieve completed outputs, or stop it. |
| A job fails or outputs are missing | Read `FailureReason` and CloudWatch logs. Do not treat partial outputs as a complete batch. |

```python
description = sm.describe_transform_job(TransformJobName=state["job_name"])
print(description["TransformJobStatus"])
print(description.get("FailureReason", "No failure reason reported."))
print("CloudWatch log group: /aws/sagemaker/TransformJobs")
print("Find log streams beginning with:", state["job_name"] + "/")
```

AWS can retain outputs for successful inputs even when other inputs cause the
job to fail. Step 8 therefore requires both `Completed` and all eight outputs.
[AWS failure behavior](https://docs.aws.amazon.com/sagemaker/latest/dg/batch-transform-errors.html)
and [log locations](https://docs.aws.amazon.com/sagemaker/latest/dg/logging-cloudwatch.html).

## Public data attribution

Data used in this tutorial were generated by the National Cancer Institute
Clinical Proteomic Tumor Analysis Consortium (CPTAC). The collection citation
is [CPTAC-LUAD, DOI 10.7937/K9/TCIA.2018.PAT12TBS](https://doi.org/10.7937/K9/TCIA.2018.PAT12TBS).
The current collection page links its data license and citation requirements.
This repository includes download instructions and a selection manifest; the
slide images and CT pixels remain hosted by their public providers.
