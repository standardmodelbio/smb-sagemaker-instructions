# SMB v2.0 on Amazon SageMaker

This repository documents the inputs and outputs of the SMB v2.0
Marketplace model. OS refers to overall survival; TTNT refers to time to next
treatment or death. The repository contains documentation, synthetic examples,
and a notebook for using a subscribed model package. The public multimodal
walkthrough includes a selection manifest and a preparation helper that download
deidentified clinical data and images from their public providers. This repository
contains no private patient data.
The walkthrough includes eight recorded AWS inference responses and code to
compare your results with that run.

These instructions cover the product release with streaming Batch Transform
input. Use the corresponding Marketplace version. Older versions can have
smaller input limits.

- [Request format and options](#requestjson-schema)
- [Multimodal batch inference with two public patients](PUBLIC_DATA_WALKTHROUGH.md)
- [Run the public multimodal notebook](public_multimodal_walkthrough.ipynb)
- [Patient data formats](#patient-data-formats)
- [Real-time inference](#real-time-inference)
- [Batch Transform](#batch-transform)
- [Output format](#output-format)
- [Notebook](sagemaker_quickstart.ipynb)
- [Marketplace form text](MARKETPLACE.md)

## What to send

Send one **uncompressed TAR archive per patient and task** with
`Content-Type: application/x-tar` and `Accept: application/json`.
The archive must contain `request.json` at its root and the referenced patient
files under `input/`.

```text
request.json
input/ehr/patient_characteristics.parquet
input/ehr/labs.parquet
```

`request.json` describes the task, observation cutoff, and files. Sending that
JSON alone is not a valid invocation. ZIP, gzip, and JSONL are not supported
outer request formats. Do not put multiple patients or multiple manifests in
one archive.

For real-time inference, send the TAR bytes as the request body. For Batch
Transform, upload each TAR as a separate S3 object. SageMaker reads S3 using
your execution role and delivers the bytes to the container. The isolated
container does not fetch S3 URLs or HTTPS URLs from the manifest.

## request.json schema

All seven fields below are required. Unknown fields are rejected at both the
request level and within each `data_objects` entry. JSON keys must be unique.

| Field | JSON type | Accepted value and meaning |
|---|---|---|
| `schema_version` | string | Exactly `"1.0"`. |
| `request_uuid` | string | A valid UUID version 4. Generate a new UUID for each patient/task request. This value is returned in the response; it is not a patient lookup key. |
| `task_id` | string | `"time_to_death"` for OS or `"time_to_next_treatment_or_death"` for TTNT. No other task is served by this product. |
| `task_version` | string | Exactly `"1.0"` for either task. |
| `task_inputs` | object | Exactly `{}` for both tasks. This field is required even though it is empty. Additional keys are rejected. |
| `observation_cutoff_day_offset` | integer | The last included day on the same time axis as the patient tables' interval columns. Dated events after this day are excluded. A JSON string, decimal, boolean, or null is not accepted. Negative integers are accepted by the request schema. |
| `data_objects` | array of objects | A nonempty list of files or directories in this request. Include EHR Parquet data that can form a usable timeline. Imaging assets are optional and require their corresponding metadata. |

The cutoff is not a prediction horizon, a count of future days, or an ISO date.
Use consistent day offsets throughout a patient's files. Events dated exactly
at the cutoff are eligible. Undated context is handled separately, so supply
only context that was known at the observation cutoff.

There are no request options for temperature, maximum tokens, model weights,
thresholds or S3 credentials. Select the task using `task_id`.
To evaluate both OS and TTNT, send two archives with different request UUIDs
and task IDs. Both can contain the same patient files and cutoff.

### data_objects entries

Each entry has exactly these three required fields.

| Field | JSON type | Accepted value and meaning |
|---|---|---|
| `modality` | string | Use `"ehr"`, `"wsi"`, or `"radiology"` as described below. Separate `"genomics"` objects do not contribute to predictions in this version. |
| `artifact_kind` | string | `"file"` for one regular file or `"archive"` for a directory already expanded inside the outer TAR. |
| `local_path` | string | The logical absolute path under `/input/` to an existing file or directory. For example, `/input/ehr/labs.parquet` maps to TAR member `input/ehr/labs.parquet`. |

For `artifact_kind: "archive"`, the target is a directory, not a nested TAR,
ZIP, or gzip file. Include its files in the outer TAR. Paths must stay inside
`/input/`. Use forward slashes and ordinary path components without `..`.
Do not use filesystem links or host-machine paths such as `/Users/...`.

### Complete OS request

This is [examples/os.request.json](examples/os.request.json), also contained in
[examples/os.tar](examples/os.tar).

```json
{
  "schema_version": "1.0",
  "request_uuid": "eb4baeba-23e6-46b5-8cdf-acb1eb02e0a3",
  "task_id": "time_to_death",
  "task_version": "1.0",
  "task_inputs": {},
  "observation_cutoff_day_offset": 100,
  "data_objects": [
    {
      "modality": "ehr",
      "artifact_kind": "archive",
      "local_path": "/input/ehr"
    }
  ]
}
```

The [TTNT request](examples/ttnt.request.json) has
`task_id: "time_to_next_treatment_or_death"` and request UUID
`eb1e910d-2744-4c2d-98b0-eae991759ea3`. Its other fields are the same.
Use [examples/ttnt.tar](examples/ttnt.tar) to send that request.

### Referencing individual files

Instead of one directory entry, the same EHR inputs can be described as:

```json
[
  {
    "modality": "ehr",
    "artifact_kind": "file",
    "local_path": "/input/ehr/patient_characteristics.parquet"
  },
  {
    "modality": "ehr",
    "artifact_kind": "file",
    "local_path": "/input/ehr/labs.parquet"
  }
]
```

This array replaces `data_objects`; it is not a complete request by itself.

## Patient data formats

### EHR

Use Parquet tables with the supported table names and columns. An arbitrary
Parquet file, CSV export, PDF, or free-text note does not satisfy this interface.
Each archive represents one patient's data. The model does not split a table
containing multiple patients into separate requests.

At least one usable EHR Parquet table is required, including when sending WSI
or radiology assets. Table names are significant. Distinct EHR files with the
same basename are rejected because they would map to the same table.

The bundled examples contain these entirely synthetic tables:

`patient_characteristics.parquet`:

| PTID | VITAL_STATUS | LAST_ALIVE_INTERVAL | DEATH_INTERVAL |
|---|---|---|---|
| synthetic-patient | Alive | 300 | null |

`labs.parquet`:

| TEST_INTERVAL | CD_DESC | CD | TEST_RESULT_VALUE | TEST_RESULT_UOM |
|---|---|---|---|---|
| 10 | hemoglobin | x | 12.0 | g/dL |
| 200 | future | y | 99.0 | g/dL |

The day-200 lab is beyond the day-100 cutoff. These files are a small working
input example, not a complete schema for every supported EHR table. Preserve
the product's required table names and columns when supplying additional tables.

### Pathology whole-slide images

Use `modality: "wsi"` for a slide file or a directory of slide files. The service
recognizes `.bif`, `.ndpi`, `.mrxs`, `.scn`, `.svs`, `.tif`, and `.tiff` filenames.
The file contents must also be readable by the packaged slide reader;
a recognized suffix alone does not establish compatibility.

Include `wsi_list.parquet` in an EHR object. Its required columns are:

| Column | Meaning |
|---|---|
| `DEID_ACCESSION_NUMBER` | The slide's deidentified accession identifier. |
| `PATHOLOGY_IMG_FILENAME` | The image filename. Its basename must match a supplied slide. |
| `SLIDE_INTERVAL` | The slide day on the same time axis as the observation cutoff. |
| `DATE_SOURCE` | The source of the slide date. |

Slides with missing dates or missing image files can be omitted during
preprocessing. Slides dated after the observation cutoff are excluded.
Distinct slide files with the same basename are rejected.

### CT and other radiology data

Use `modality: "radiology"` with `artifact_kind: "archive"` for a directory
containing study/series folders and DICOM files. Use `.dcm` filenames for this
product version. A directory containing a single study is also accepted.
The service needs study directories, so an individual DICOM file entry is not
a substitute for the study directory.

Include `dicom_inventory_file.parquet` in an EHR object with columns
`FULL_FILE_NAME` and `IMG_INTERVAL`. `FULL_FILE_NAME` identifies a study path,
such as `patient-id/1.2.826.0.1.3680043.10.543.1`. The service removes the first
path segment and resolves the remaining study path inside the supplied
radiology directory. Preserve the study/series layout and valid DICOM headers.
`IMG_INTERVAL` uses the same day axis as the cutoff.

Missing, undated, or unresolved studies can be omitted. The preprocessing
also selects diagnostic series from the available DICOM files. A successful
prediction does not prove that every supplied image was used.

A manifest containing both imaging modalities could use this `data_objects`
array, with the corresponding files and metadata included in the TAR:

```json
[
  {"modality": "ehr", "artifact_kind": "archive", "local_path": "/input/ehr"},
  {"modality": "wsi", "artifact_kind": "file", "local_path": "/input/pathology/slide.svs"},
  {"modality": "radiology", "artifact_kind": "archive", "local_path": "/input/radiology"}
]
```

The bundled working examples use EHR only. They do not contain WSI or CT data.

## Package your own request

Prepare a directory containing `request.json` and `input/`. The following
standard-library example writes an uncompressed TAR with regular files only.
Change the two paths to your prepared directory and desired output file.
Put the output outside the input directory.

```python
from pathlib import Path
import tarfile

source = Path("patient-request").resolve()
output = Path("patient.tar").resolve()
assert (source / "request.json").is_file()
assert (source / "input").is_dir()
assert not output.is_relative_to(source)
paths = [source / "request.json"]
for path in sorted((source / "input").rglob("*")):
    if path.is_symlink() or not (path.is_file() or path.is_dir()):
        raise ValueError(f"Not a regular file or directory: {path}")
    if path.is_file():
        paths.append(path)
with tarfile.open(output, "w", format=tarfile.PAX_FORMAT) as archive:
    for path in paths:
        archive.add(path, arcname=path.relative_to(source).as_posix(), recursive=False)
```

The resulting member names must start with `input/`, or be exactly
`request.json`. Do not add a parent directory around them or use `./` prefixes.

## Real-time inference

Create an endpoint from your subscribed model package with network isolation.
The [notebook](sagemaker_quickstart.ipynb) demonstrates model and endpoint
creation, requests for both tasks, and cleanup. Then invoke the endpoint with
the TAR bytes. This command uses your default AWS credentials:

```bash
aws --region us-east-1 sagemaker-runtime invoke-endpoint \
  --endpoint-name YOUR_ENDPOINT_NAME \
  --content-type application/x-tar \
  --accept application/json \
  --body fileb://examples/os.tar \
  os-result.json
```

Use small archives for real-time inference. AWS documents a 25 MB request limit
and a 60-second processing limit for ordinary endpoint responses. Large WSI/CT
requests should use Batch Transform. The service returns one JSON response,
not a streamed prediction response. [AWS endpoint limits](https://docs.aws.amazon.com/marketplace/latest/userguide/ml-service-restrictions-and-limits.html)

## Batch Transform

Upload each TAR to a dedicated S3 input prefix. Include only invocation TARs
in that prefix, not standalone manifests or Parquet files. Both example TARs
can be used in the same job, because each manifest selects its own task.

Create the model from the subscribed package with `EnableNetworkIsolation=True`.
Use an execution role that can read your input prefix and write your output
prefix. The [notebook](sagemaker_quickstart.ipynb) includes a complete small
synthetic example. Configure the transform job as follows:

| Setting | Value |
|---|---|
| `BatchStrategy` | `SingleRecord` |
| `MaxConcurrentTransforms` | `1` |
| `MaxPayloadInMB` | `0` |
| `TransformInput.ContentType` | `application/x-tar` |
| `TransformInput.CompressionType` | `None` |
| `TransformInput.SplitType` | `None` |
| `TransformOutput.Accept` | `application/json` |
| `TransformOutput.AssembleWith` | `None` |
| `TransformResources.InstanceType` | `ml.g5.2xlarge`, if supported by your subscribed package |
| `TransformResources.InstanceCount` | `1` |
| `ModelClientConfig.InvocationsTimeoutInSeconds` | Up to `3600` for large requests |

`MaxPayloadInMB=0` enables HTTP chunked input for this product. It does not
split a patient into separate inference calls. Each S3 object remains one
invocation. [AWS chunked-input setting](https://docs.aws.amazon.com/sagemaker/latest/APIReference/API_CreateTransformJob.html#sagemaker-CreateTransformJob-request-MaxPayloadInMB)

The input limits are 64 GiB for the complete TAR, including TAR overhead,
64 GiB for its extracted contents, 1 MiB for `request.json`, and 2,048 archive
members including the manifest and any directory entries. Links, duplicate
paths, sparse files, and special files are rejected. These are application
bounds, not a guarantee that every input within them fits GPU memory or the
job timeout. Keep enough scratch space for extraction and preprocessing.

The archive is extracted as it arrives. Inference begins after the full request
has been received and validated. No second full copy of the TAR is retained
on the container's scratch disk. Batch Transform does not require an endpoint.

## Output format

Successful real-time calls return one JSON object with
`Content-Type: application/json`. Batch Transform writes that same JSON
format to S3, normally in a corresponding `.tar.out` object.

| Field | JSON type | Meaning |
|---|---|---|
| `schema_version` | string | `"1.0"`. |
| `request_uuid` | string | The UUID from the input manifest. |
| `task_id` | string | The selected task. |
| `task_version` | string | `"1.0"`. |
| `prediction` | number | A finite positive risk-ranking score for the selected task. |
| `score_type` | string | `"rank_preserving_pseudo_days"`. |

The score preserves risk ordering on a positive scale. Within the same task
and model version, a smaller score corresponds to higher model risk. It is
**not an estimated number of days until an event, a survival probability, or a
confidence interval**. Do not compare OS and TTNT scores as though they were
one shared time scale. The response contains no clinical narrative or image
interpretation.

OS example:

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

See [OS output](examples/os.output.json) and
[TTNT output](examples/ttnt.output.json). These are recorded outputs from the
November 12, 2026 validation of the same synthetic fixture. They demonstrate
the response contract; they are not results of a new deployment from this
repository.

## Errors

The container returns error objects such as `{"error":"invalid_patient_input"}`
instead of a prediction when a request fails. AWS can expose container errors
through its endpoint error response or Batch Transform failure details.

| Container status | Error | Meaning |
|---|---|---|
| 400 | `invalid_archive` | Invalid TAR layout, unsafe paths, or malformed manifest JSON. |
| 413 | `payload_too_large` | An archive, extracted-size, manifest, or member limit was exceeded. |
| 415 | `unsupported_content_type` | The request did not use `application/x-tar`. |
| 422 | `invalid_patient_input` | The manifest or patient data could not be processed. |
| 503 | `model_not_ready` / `model_busy` | Wait for readiness or reduce concurrent invocations. |
| 503 | `model_failed` | The inference process encountered an unrecoverable failure. |
| 500 | `inference_failed` | Inference failed for another reason. |

## Notebook setup

Open [sagemaker_quickstart.ipynb](sagemaker_quickstart.ipynb). It uses only
`boto3`, `polars`, and the Python standard library and constructs synthetic
patient data in memory. Set the subscribed model-package ARN, your SageMaker
execution role, your S3 bucket, and the AWS region. Follow the cleanup cell
to remove the endpoint and demo resources.

The notebook exercises small EHR requests. Use the settings above for your
existing large imaging archives and validate those cases separately.
