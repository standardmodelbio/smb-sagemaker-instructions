# Marketplace form text

The URLs below assume this repository is published as
`standardmodelbio/smb-sagemaker-instructions` on branch `main`. They will work
only after publication. Change the owner or branch if you choose different
values. The form can use the linked TAR files as binary input samples or the
sample text below as a readable description.

## Model input summary

SMB v2.0 accepts one patient and one prediction task per invocation. The input
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

SMB v2.0 returns one JSON object per patient/task request with Content-Type
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

## Usage instructions

1. Subscribe to SMB v2.0 and use the model-package ARN for your deployment
   region. Create the SageMaker model with network isolation enabled. Use a
   SageMaker execution role that can read your input S3 location and write
   to your output location. Keep the package, compute, and S3 bucket in the
   same AWS region. Start with the supplied synthetic examples and notebook
   before submitting your own patient data.

2. Prepare one uncompressed TAR per patient and task. Include request.json
   at the archive root and all referenced files under input/. Send the TAR
   bytes with Content-Type application/x-tar and Accept application/json.
   The manifest alone is not a complete request. Do not include S3 URLs,
   nested compressed archives, or filesystem links as patient inputs.

3. Follow the request.json schema in the repository README. Every field is
   required, and additional fields are rejected. Use a UUIDv4 request_uuid,
   schema_version "1.0", task_version "1.0", and task_inputs {}. Select OS
   with task_id "time_to_death" or TTNT with
   "time_to_next_treatment_or_death". To obtain both predictions, submit
   separate archives with distinct request UUIDs and the appropriate task IDs.

4. Set observation_cutoff_day_offset to an integer on the same time axis as
   the patient records. Supply only information available at that cutoff.
   Include usable EHR Parquet tables with the documented filenames and
   columns. For slides, match image filenames to wsi_list.parquet and provide
   slide dates. For CT/DICOM studies, preserve the study/series layout and
   matching dicom_inventory_file.parquet entries. Missing dates, missing
   assets, and dates after the cutoff can cause images to be omitted. A
   successful prediction does not confirm that every supplied image was used.

5. Use real-time endpoints for small requests that fit the endpoint's payload
   and processing-time limits. Use Batch Transform for large patient archives,
   including whole-slide images and CT studies. For Batch Transform, upload
   one TAR per S3 object to a dedicated input prefix containing only request
   TARs. Do not upload standalone JSON manifests or Parquet files to that
   prefix. Set BatchStrategy=SingleRecord, MaxPayloadInMB=0,
   MaxConcurrentTransforms=1, SplitType=None, CompressionType=None,
   ContentType=application/x-tar, Accept=application/json, and AssembleWith=None.
   Each archive remains one complete inference request.

6. Start with ml.g5.2xlarge if it is supported by your subscribed package.
   Keep one active inference request per instance. Measure processing time
   and resource use on representative inputs before running a large cohort.
   For long Batch Transform requests, configure
   ModelClientConfig.InvocationsTimeoutInSeconds up to 3600 as needed.
   Provide enough scratch space for extracted assets and preprocessing.

7. Keep each TAR, including its headers, within 64 GiB and its extracted
   contents within 64 GiB. Keep request.json within 1 MiB and the archive
   within 2,048 members, counting the manifest and any directory entries.
   These are input limits, not guarantees of memory fit or completion time.
   Avoid duplicate files and unnecessary assets. Do not split one patient's
   archive into separate invocations and assume their predictions will be
   combined; each invocation is evaluated independently.

8. If an error reports model_not_ready or model_busy, wait and retry with
   bounded backoff. Correct invalid_archive, invalid_patient_input,
   unsupported_content_type, or payload_too_large errors before retrying.
   For a failed Batch Transform job, inspect the failure reason and CloudWatch
   logs. Use request_uuid and task_id to match each successful response to its
   input. Batch outputs are JSON objects in corresponding .out files.

9. Interpret prediction as a positive risk-ranking score. Within the same
   task and model version, smaller values indicate higher model risk. Do not
   interpret the value as an estimated number of days or a survival
   probability, or compare OS and TTNT values as one shared time scale.

10. Delete real-time endpoints when they are no longer needed. Follow the
    notebook's cleanup steps to remove demo resources and synthetic S3 data.

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
