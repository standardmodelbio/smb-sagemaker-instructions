# Run a batch with your own patients

The public tutorial uses eight requests to demonstrate four input combinations.
Your batch can contain any number of requests. You can use all modalities once
per patient, or compare combinations. Each request still contains one patient.

Use the same [notebook](public_multimodal_walkthrough.ipynb) and
[AWS permissions](AWS_SETUP.md). Change `OWN_DATA_MANIFEST` in its configuration
cell to select your prepared patients. Leave it empty to run the public example.
The notebook uses the request index to count and verify your responses.

## 1. Prepare each patient's clinical tables

Create a separate directory for each patient. Map source fields to the
[clinical schema](README.md#ehr). Use one patient ID consistently in the
clinical tables, DICOM headers, and manifest. Keep the mapping from this ID to
your source records in your own system.

For example, if your CSV already has the columns shown below, this code writes
the clinical inputs. Run it in a separate notebook or Python script after
installing `examples/public_multimodal/requirements.txt`.

```text
patient_id,age,sex,diagnosis_day,histology
patient-001,62,Female,0,Adenocarcinoma
patient-002,55,Male,0,Adenocarcinoma
patient-003,70,Female,0,Adenocarcinoma
```

Save that synthetic example as `clinical.csv` to try the conversion. For your
own records, compute `diagnosis_day` from the patient's chosen time origin.
Zero here means diagnosis is the origin; do not assign zero to unknown dates.

```python
from pathlib import Path
import json
import polars as pl

rows = pl.read_csv("clinical.csv").to_dicts()
assert len({row["patient_id"] for row in rows}) == len(rows)
manifest = []
for row in rows:
    patient_id = row["patient_id"]
    ehr = Path("my-patients") / patient_id / "ehr"
    ehr.mkdir(parents=True, exist_ok=True)
    pl.DataFrame({"PTID": [patient_id], "AGE": [row["age"]], "SEX": [row["sex"]]}).write_parquet(
        ehr / "patient_characteristics.parquet")
    pl.DataFrame({"INITIAL_DX_INTERVAL": [row["diagnosis_day"]], "HISTOLOGY": [row["histology"]]}).write_parquet(
        ehr / "diagnosis.parquet")
    manifest.append({"patient_id": patient_id, "directory": "my-patients/" + patient_id,
                     "cutoff_day": 0, "task": "os", "modalities": ["ehr"]})
Path("my-batch.json").write_text(json.dumps(manifest, indent=2))
```

You now have a complete three-patient EHR batch definition. Optional clinical
tables such as labs and notes go in each patient's `ehr/` directory. Preserve
units and missing values. Exclude future follow-up and records unavailable at
the prediction time. The preparation helper requires already filtered inputs
and rejects nonnumeric or future dates. The separate synthetic quickstart
includes a future lab specifically to demonstrate the service's cutoff
filtering. Omit such rows when using this helper.

## 2. Add matched slides and CT files

For a full multimodal patient, extend its directory as follows:

```text
my-patients/patient-001/
  ehr/
    patient_characteristics.parquet
    diagnosis.parquet
    wsi_list.parquet
    dicom_inventory_file.parquet
  pathology/
    slide-001.svs
  radiology/
    STUDY_UID/
      SERIES_UID/
        INSTANCE_UID.dcm
        ...
```

Use your pathology system's patient-to-specimen-to-slide link to confirm that
`slide-001.svs` belongs to this patient. Record the source of the slide date.
For CT, check every slice's `PatientID`, `StudyInstanceUID`, and
`SeriesInstanceUID`. Preserve complete diagnostic series. Record where the
scan date came from and how it was converted to the patient's time axis.

The following example writes the two metadata tables. Replace its filenames,
identifiers, and day offsets with values verified against your source records.
The example days mean the slide event occurred at the cutoff and the CT was
one day earlier. They are not defaults for missing dates.

```python
from pathlib import Path
import polars as pl

ehr = Path("my-patients/patient-001/ehr")
pl.DataFrame({
    "DEID_ACCESSION_NUMBER": ["specimen-001"],
    "PATHOLOGY_IMG_FILENAME": ["slide-001.svs"],
    "SLIDE_INTERVAL": [0],
    "DATE_SOURCE": ["Verified specimen procurement date relative to diagnosis"],
}).write_parquet(ehr / "wsi_list.parquet")
pl.DataFrame({
    "FULL_FILE_NAME": ["patient-001/REPLACE_WITH_STUDY_UID"],
    "IMG_INTERVAL": [-1],
}).write_parquet(ehr / "dicom_inventory_file.parquet")
```

Repeat for each patient with images. If the prediction time is prospective,
also verify that the images and results were available by then. Acquisition
and procurement dates alone do not prove availability. Do not combine shifted
DICOM calendar dates with unshifted clinical dates.

For each full multimodal request, change its manifest entry to
`"modalities": ["ehr", "wsi", "radiology"]`. Use `radiology` in the manifest;
the generated index labels that combination `ehr-wsi-ct` for readability.
Patients without a particular image can have a different modality list.

To compare combinations for one patient, add another manifest entry with the
same directory, cutoff, and task but a different modality list. The helper
omits the unused image metadata as well as the unused images. Use one cutoff
per patient, task, and combination in a batch; run a separate batch for another
cutoff.

## 3. Check and package locally

Paths in `directory` are relative to the manifest file, or can be absolute.
The source directory contains `ehr/`, `pathology/`, and `radiology/`; it does
not need `request.json` or an enclosing `input/` directory.

```bash
python examples/own_data/prepare_batch.py \
  --manifest my-batch.json \
  --output public-data-demo/own-data-check
```

For the three-patient EHR example, expect:

```text
PASS: packaged 3 requests for 3 patients.
```

The helper checks required columns and dates. It checks patient IDs and image
paths, opens each slide, and decodes every CT slice. It packages one TAR per
manifest entry and writes `request-index.json` with generated UUIDs and input
checksums. Only files for the selected modalities are included. Use a new
output directory when retrying after a failure.

The helper cannot verify your clinical field meanings or infer a slide's
patient identity from its pixels. It does not know your date origin, source
series' expected slice count, or whether a result was available at the cutoff.
Verify those against your source system before running inference. It also
does not guarantee that the model will select every supplied image. The
[imaging schema](README.md#pathology-whole-slide-images) explains preprocessing
and supported formats. This helper expects self-contained slide files and
CT directories organized exactly as above.

## 4. Run the same notebook

In the configuration cell, set:

```python
OWN_DATA_MANIFEST = "my-batch.json"
```

Keep the four AWS settings filled in and run the notebook from the repository
root. The preparation cell now calls `prepare_batch.py` instead of downloading
the public cohort. It creates a new run directory and new request UUIDs. The
public-patient descriptions and score table apply only to the public example.

The AWS upload, submission, response verification, and cleanup cells work
without edits. Every expected output must match its request UUID and task.
Your results contain one row per manifest entry. Public reference scores are
not expected for your patients, so that numerical comparison is skipped.

Keep the request index with `predictions.csv`. The index connects each UUID to
your patient and modality combination. A positive, structurally valid score
checks that inference returned a result. Assessing accuracy on your population
requires a separate evaluation with appropriate outcomes.

If a cell fails, follow [cleanup and recovery](PUBLIC_DATA_WALKTHROUGH.md#10-clean-up-the-tutorial-resources)
before starting another job. Your source patient folders are never removed.
