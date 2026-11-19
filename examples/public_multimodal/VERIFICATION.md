# Public multimodal input verification

The source matching and local preprocessing checks were completed on
November 17, 2026. On November 19, we refreshed the GDC and PathDB metadata,
rechecked the cached public assets, and ran the walkthrough in AWS.
All eight inference responses passed validation. The selected assets are in
[cohort.json](cohort.json), and the measured outputs are in
[reference-run/](reference-run/README.md). No dataset credentials were needed.
Later that day, a separate test executed the ready notebook through JupyterLab
from a fresh environment and empty download cache. All 13 code cells completed,
including eight matching AWS predictions and cleanup. See
[notebook-run/](notebook-run/README.md) for the executed notebook and evidence.

## Patient and specimen matching

| Check | C3L-00263 | C3L-00422 |
|---|---|---|
| GDC case UUID | `3a7449d1-7761-4c8e-afc0-9968b1f33305` | `67c1aa6e-0bc7-40e2-9742-8f73be3ed450` |
| GDC and PathDB specimen ID | `C3L-00263-04` | `C3L-00422-02` |
| Slide ID in both sources | `C3L-00263-24` | `C3L-00422-22` |
| PathDB slide node | `215986` | `216003` |
| Slide dimensions | 33,863 by 21,032 pixels. | 21,911 by 15,312 pixels. |
| GDC case `index_date` | `Diagnosis` | `Diagnosis` |
| Specimen `days_to_sample_procurement` | 0 | 0 |
| CT `ClinicalTrialTimePointID` | -1 on all 71 instances. | -109 on all 69 instances. |

The exact specimen is a `Primary Tumor` in GDC. Its nested portion/slide
relationship contains the selected slide ID. The PathDB row independently
links the same case, specimen, and slide. The slide node's
`clinicaltrialsubjectid` matches the case. Every downloaded CT instance has
the same patient ID and the study and series UIDs recorded in the manifest.

Sources:

- [PathDB metadata CSV](https://pathdb.cancerimagingarchive.net/system/files/collectionmetadata/202407/cptac_metadata_07-09-2024.csv).
- [GDC case C3L-00263 with specimens and slides](https://api.gdc.cancer.gov/cases/3a7449d1-7761-4c8e-afc0-9968b1f33305?expand=samples,samples.portions,samples.portions.slides).
- [GDC case C3L-00422 with specimens and slides](https://api.gdc.cancer.gov/cases/67c1aa6e-0bc7-40e2-9742-8f73be3ed450?expand=samples,samples.portions,samples.portions.slides).
- [PathDB slide C3L-00263-24](https://pathdb.cancerimagingarchive.net/node/215986?_format=json).
- [PathDB slide C3L-00422-22](https://pathdb.cancerimagingarchive.net/node/216003?_format=json).

## Date interpretation

TCIA documents `ClinicalTrialTimePointID` as the scan day relative to initial
pathologic diagnosis. GDC defines sample procurement relative to the case's
index date. Both selected cases use `Diagnosis`. These recorded offsets permit
a common axis without using shifted DICOM calendar dates.
[TCIA collection documentation](https://www.cancerimagingarchive.net/collection/cptac-luad/)
and [GDC sample definitions](https://api.gdc.cancer.gov/v0/submission/_dictionary/sample).

The pathology event is dated to specimen procurement, with that provenance
recorded in `DATE_SOURCE`. This establishes when the tissue was obtained. It
does not establish when the digital image or pathology result became available.
The example is retrospective, with cutoff zero. It does not claim prospective
availability of the digitized slides at that cutoff.

## Asset and preprocessing checks

The preparation helper verified the complete slide SHA-256 hashes and decoded
a thumbnail and a full-resolution region from each slide. It decoded all 140
CT pixel arrays and checked every instance's patient, study, series, and day.
The CT fingerprint in the manifest is SHA-256 over sorted lines of
`SOPInstanceUID SHA256_OF_ORIGINAL_DICOM_BYTES`, with one newline per line.
This avoids relying on ZIP timestamps or ZIP entry order.

All eight generated TARs passed the SageMaker wrapper's archive reader.
All eight passed timeline construction using the deployment's pinned source:

| Component | Revision |
|---|---|
| `clintic-v1` | `406415b0ab4d46269af76caecfb9e3eea3e67d0e` |
| `smb-data-pipeline` | `47562ac3929be7a0e71e6a8eebf7227c86c46364` |

The retained image inputs were:

| Combination | Retained pathology events | Retained CT inputs |
|---|---:|---|
| `ehr` | 0 | None. |
| `ehr-wsi` | 1 | None. |
| `ehr-ct` | 0 | One diagnostic series. |
| `ehr-wsi-ct` | 1 | One diagnostic series. |

These counts held for both patients. The pinned preprocessing sampled each
complete CT series to 64 slices. Neither series had excluded or unresolved
diagnostic inputs. Its event day stayed at -1 or -109. The slide event stayed
at zero. The pinned pathology reader produced 128 patches plus one thumbnail
from each slide. These local checks establish image readability and which
events the preprocessing retained. The hosted run below additionally exercised
GPU inference. Neither check establishes clinical prediction accuracy.

The guide's AWS request parameters passed the installed SDK's validation.
Local simulated responses exercised collection and identity checks, including
missing outputs and invalid scores. Recovery and cleanup were checked against
a simulated active job. The November 19 run then exercised the guide's input
preparation, submission, polling, and response validation cells with live AWS
clients. That first run executed Python blocks extracted from the Markdown
guide in a shared Python namespace. It did not open or execute a Jupyter
notebook. We supplied the account's existing role, bucket, and subscribed package.
We independently fetched and validated all eight S3 outputs a second time.

The eight TARs totaled 648,847,360 bytes in the validation run. The helper's
matching and packaging tests can be run from the repository root after
installing the walkthrough dependencies:

```bash
python -m unittest discover -s examples/public_multimodal -p 'test_*.py' -v
```

The tests reject mismatched identities and dates. They also check CT instance
integrity and confirm that omitted modalities and their metadata are absent
from the corresponding TARs. Source data and generated image archives are not
committed to this repository.

## Hosted inference on November 19, 2026

The job `smb-public-20261119-113451-7c9e9376` completed with all eight expected outputs.
Each response matched its request UUID, schema version, task ID, and task
version. Every prediction was finite and positive, with score type
`rank_preserving_pseudo_days`. The result set contained exactly one response
for each of the two patients and four input combinations. Input TAR hashes
still matched the submitted request index when outputs were collected.

| Patient | `ehr` | `ehr-wsi` | `ehr-ct` | `ehr-wsi-ct` |
|---|---:|---:|---:|---:|
| `C3L-00263` | 291.09576153 | 271.37754702 | 296.24379776 | 260.38882875 |
| `C3L-00422` | 272.53007848 | 277.64935748 | 345.72121953 | 319.67090811 |

The package image digest was
`sha256:5764e06af2cabf973208c067c88220b2825db17fef84f51d5af8df995e2c0303`.
It was the subscribed package for Marketplace release v3 of the SMB v2.0
product, with wrapper 0.1.4. The job used one `ml.g5.2xlarge` in `us-east-1`,
network isolation, and the guide's streaming Batch Transform configuration.
Creation to completion took 526.541 seconds.

See [run.json](reference-run/run.json) for the exact package, timestamps,
configuration, and checksums. See [request-index.json](reference-run/request-index.json)
for the submitted UUIDs and input archive hashes. The
[CSV](reference-run/predictions.csv) contains full precision scores, and
the [reference directory](reference-run/README.md) links the original S3 output
bytes. These are measured responses, not simulated examples. The separate
notebook run below reproduced all eight scores exactly at the returned
precision. Clinical accuracy was not evaluated.

The guide's recovery and cleanup cells also ran against the completed job.
A separate AWS check confirmed that its temporary model was absent and its
S3 prefix contained no objects. The bucket had versioning disabled, so no
older versions or delete markers remained. Local inputs and results were
retained, along with AWS job history and CloudWatch logs. The cleanup checks
and timestamp are recorded in [run.json](reference-run/run.json).

## Fresh JupyterLab test on November 19, 2026

The ready notebook was opened in JupyterLab 4.6.6 with a newly created Python
3.12.0 virtual environment on macOS arm64. The environment initially contained
JupyterLab and its kernel dependencies. Boto3, Polars, NumPy, pydicom, and
OpenSlide were absent. The notebook's installation cell installed them.
The public asset cache was absent before execution.

We supplied the four documented AWS settings as environment variables, selected
the documented kernel, and chose **Run > Run All Cells** once. The 13 code cells
executed consecutively with counts 1 through 13 and no errors. No cell source
was edited or extracted for execution. The recovery cell correctly did nothing
during this normal run. It was not a kernel restart recovery test.

An initial fresh attempt had stopped before creating AWS resources because the
GDC API hostname failed to resolve. The fixed tutorial now uses the two public
GDC metadata responses recorded during the earlier successful run, with hashes
and source URLs. We then started the successful test with another new
environment and empty cache. The clinical CSV,
both whole-slide images, both CT archives, and the PathDB slide records were
downloaded again. The GDC records were checked from the bundled snapshots.

The helper checked both patient and specimen matches, the slide day zero,
and CT days -1 and -109 across all 140 instances. All eight patient file
fingerprints and request settings matched the reference run, apart from the
new request UUIDs. The hosted job
`smb-public-20261119-142907-4061f891` completed in 482.871 seconds from creation.
It used the same subscribed image, instance type, and network isolation.
All eight response identities and scores passed the notebook checks. Every
returned score equaled the earlier run's score at full returned precision.

The notebook removed its temporary model and S3 objects. A separate AWS read
confirmed the completed job, absent model, and zero remaining objects, versions,
or delete markers under the run prefix. The bucket had versioning disabled.
The local Jupyter server and kernel were then stopped. Local results, AWS job
history, and CloudWatch logs were retained.

The [execution record](notebook-run/run.json) contains the code cell hashes,
execution counts, versions, timings, and cleanup checks. The
[executed notebook](notebook-run/executed.ipynb) preserves the tested file and
its outputs. Its explanatory text predates this added verification summary;
all executable cells still match the distributed notebook. This test used
existing AWS account prerequisites. It did not test a new Marketplace purchase
or creation of a new AWS account, role, bucket, or quota.
