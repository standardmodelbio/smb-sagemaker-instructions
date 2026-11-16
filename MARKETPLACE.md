# Marketplace form text

The URLs below assume this repository is published as
`standardmodelbio/smb-sagemaker-instructions` on branch `main`. They will work
only after publication. Change the owner or branch if you choose different
values. The form can use the linked TAR files as binary input samples or the
sample text below as a readable description.

## Model input summary

The model accepts one patient and one prediction task per invocation. The input
is an uncompressed TAR archive sent with Content-Type application/x-tar. Each
archive contains request.json at its root and the referenced patient files
under input/.

The required request.json fields are schema_version, request_uuid, task_id,
task_version, task_inputs, observation_cutoff_day_offset, and data_objects.
Use schema_version "1.0", a UUIDv4 request_uuid, task_version "1.0", and an
empty task_inputs object. Select OS with task_id "time_to_death" or TTNT with
"time_to_next_treatment_or_death". The observation cutoff is an integer on the
same day-offset time axis as the patient records. Each data object declares
its modality, artifact_kind, and local_path under /input/.

Patient inputs include EHR Parquet tables with the required filenames and
columns. The README contains a working synthetic example. Optional whole-slide images use modality "wsi" and require slide metadata in
wsi_list.parquet. Optional CT/DICOM studies use modality "radiology" and
require study metadata in dicom_inventory_file.parquet. At least one usable
EHR table is required. Imaging files must match the metadata and observation
cutoff. The README documents the accepted fields, options, paths, and formats.

Real-time requests send the TAR bytes directly. Batch Transform reads one TAR
per S3 object. For large inputs, use Batch Transform with MaxPayloadInMB=0,
SplitType=None, CompressionType=None, and MaxConcurrentTransforms=1. The
service enforces a 64 GiB archive limit; actual input suitability also depends on available resources and processing time. S3 URLs in
request.json are not supported.

## Real-time input data sample

Sample file URL:

```text
https://raw.githubusercontent.com/standardmodelbio/smb-sagemaker-instructions/main/examples/os.tar
```

Text alternative:

```text
Send the bytes of examples/os.tar with Content-Type: application/x-tar.
The archive contains request.json and two synthetic EHR Parquet tables:

request.json
input/ehr/patient_characteristics.parquet
input/ehr/labs.parquet

request.json:
{
  "schema_version": "1.0",
  "request_uuid": "eb4baeba-23e6-46b5-8cdf-acb1eb02e0a3",
  "task_id": "time_to_death",
  "task_version": "1.0",
  "task_inputs": {},
  "observation_cutoff_day_offset": 100,
  "data_objects": [
    {"modality": "ehr", "artifact_kind": "archive", "local_path": "/input/ehr"}
  ]
}

This JSON is the manifest inside the TAR, not the complete HTTP body.
```

## Batch job input data sample

Sample file URL:

```text
https://raw.githubusercontent.com/standardmodelbio/smb-sagemaker-instructions/main/examples/ttnt.tar
```

Text alternative:

```text
Upload examples/ttnt.tar as one S3 input object. The TAR contains request.json
and the same synthetic EHR Parquet tables as the real-time example.

request.json:
{
  "schema_version": "1.0",
  "request_uuid": "eb1e910d-2744-4c2d-98b0-eae991759ea3",
  "task_id": "time_to_next_treatment_or_death",
  "task_version": "1.0",
  "task_inputs": {},
  "observation_cutoff_day_offset": 100,
  "data_objects": [
    {"modality": "ehr", "artifact_kind": "archive", "local_path": "/input/ehr"}
  ]
}

Use ContentType=application/x-tar, Accept=application/json,
BatchStrategy=SingleRecord, SplitType=None, CompressionType=None,
MaxPayloadInMB=0, MaxConcurrentTransforms=1, and AssembleWith=None.
Each TAR remains one complete patient/task request.
Either task can be used with either inference mode.
```

## Model output summary

The model returns one JSON object per patient/task request with Content-Type
application/json. The response contains schema_version, the input request_uuid,
task_id, task_version, a finite positive numeric prediction, and score_type
"rank_preserving_pseudo_days". Real-time inference returns this object in the
response body. Batch Transform writes the same JSON format to the configured
S3 output location, in a corresponding .out file.

The prediction is a positive risk-ranking score for the selected task.
Within a task and model version, smaller values indicate higher model risk.
It is not an estimated number of days until an event or a survival probability.
The output does not include a confidence interval, clinical narrative, or
image interpretation.

## Real-time output data sample

```json
{
  "schema_version": "1.0",
  "request_uuid": "eb4baeba-23e6-46b5-8cdf-acb1eb02e0a3",
  "task_id": "time_to_death",
  "task_version": "1.0",
  "prediction": 207.02597072139167,
  "score_type": "rank_preserving_pseudo_days"
}
```

Sample file URL:

```text
https://raw.githubusercontent.com/standardmodelbio/smb-sagemaker-instructions/main/examples/os.output.json
```

## Batch job output data sample

Example contents of `ttnt.tar.out`:

```json
{
  "schema_version": "1.0",
  "request_uuid": "eb1e910d-2744-4c2d-98b0-eae991759ea3",
  "task_id": "time_to_next_treatment_or_death",
  "task_version": "1.0",
  "prediction": 328.6650240123797,
  "score_type": "rank_preserving_pseudo_days"
}
```

Sample file URL:

```text
https://raw.githubusercontent.com/standardmodelbio/smb-sagemaker-instructions/main/examples/ttnt.output.json
```

Both output examples are recorded synthetic-fixture outputs from the
November 12, 2026 model validation. They show the response format and are not
newly measured results from the streaming release.

## Git repository

```text
https://github.com/standardmodelbio/smb-sagemaker-instructions
```

## Sample notebook

```text
https://github.com/standardmodelbio/smb-sagemaker-instructions/blob/main/sagemaker_quickstart.ipynb
```

The notebook constructs synthetic data and demonstrates endpoint inference,
Batch Transform, and cleanup. Its configuration cell requires the subscribed
model-package ARN, your SageMaker execution role, and a same-region S3 bucket.
