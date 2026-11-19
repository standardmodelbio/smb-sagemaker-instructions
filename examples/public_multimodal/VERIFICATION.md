# Patient matching and date alignment

Use this reference to check which public files belong together and how their
dates map to the observation cutoff. The [cohort manifest](cohort.json) contains
the asset identifiers and checksums used by the preparation helper.

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

## Expected image inputs

| Combination | Pathology slides per patient | CT series per patient |
|---|---:|---:|
| `ehr` | 0 | 0 |
| `ehr-wsi` | 1 | 0 |
| `ehr-ct` | 0 | 1 |
| `ehr-wsi-ct` | 1 | 1 |

Each CT series contains one diagnostic acquisition. The service samples it
to 64 slices. Its event day stays at -1 or -109. Each slide event stays at zero.
The selected slide inputs produce 128 patches and one thumbnail per slide.
The [expected results](reference-run/README.md) contain all eight AWS responses.

The service response has no per-image usage report. Check identities and dates
before submission. A successful prediction alone does not establish which
images contributed or whether the prediction is clinically accurate.
