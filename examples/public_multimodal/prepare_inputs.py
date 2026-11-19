"""Prepare eight public CPTAC requests. This script does not call AWS."""

from __future__ import annotations

import argparse
import csv
import hashlib
import io
import json
import re
import shutil
import tarfile
import uuid
import zipfile
from pathlib import Path
from typing import Any
from urllib.parse import urlencode
from urllib.request import urlopen

import openslide
import polars as pl
import pydicom

NBIA = "https://services.cancerimagingarchive.net/nbia-api/services/v1/"
VARIANTS = {
    "ehr": (),
    "ehr-wsi": ("wsi",),
    "ehr-ct": ("ct",),
    "ehr-wsi-ct": ("wsi", "ct"),
}
DATE_SOURCE = "gdc.samples.days_to_sample_procurement; index_date=Diagnosis"


def require(condition: bool, message: str) -> None:
    if not condition:
        raise ValueError(message)


def digest(path: Path) -> str:
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def save_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2) + "\n")


def download(url: str, path: Path, sha256: str | None = None) -> Path:
    """Cache completed downloads; never reuse a partial file."""
    path.parent.mkdir(parents=True, exist_ok=True)
    if not path.exists():
        print("Downloading", path.name, flush=True)
        partial = path.with_suffix(path.suffix + ".part")
        with urlopen(url, timeout=180) as response, partial.open("wb") as stream:
            shutil.copyfileobj(response, stream, length=1024 * 1024)
        partial.replace(path)
    if sha256 is not None:
        require(
            digest(path) == sha256,
            f"Checksum mismatch: {path}. Remove this cached file and retry.",
        )
    return path


def fetch_json(url: str, evidence_path: Path) -> dict[str, Any]:
    """Refresh small metadata records and save the source response for review."""
    with urlopen(url, timeout=60) as response:
        value = json.load(response)
    save_json(evidence_path, value)
    return value


def load_gdc_case(patient: dict[str, Any], evidence_path: Path) -> dict[str, Any]:
    """Use the recorded public response so this fixed cohort survives API outages."""
    metadata = Path(__file__).with_name("metadata")
    sources = json.loads((metadata / "sources.json").read_text())
    source = sources[patient["patient_id"]]
    path = metadata / source["filename"]
    require(digest(path) == source["sha256"], "GDC metadata snapshot checksum mismatch")
    evidence_path.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(path, evidence_path)
    return json.loads(path.read_text())["data"]


def match_sources(
    patient: dict[str, Any],
    row: dict[str, str],
    case: dict[str, Any],
    node: dict[str, Any],
) -> None:
    """Join case -> specimen -> slide using identifiers, never row position."""
    pid = patient["patient_id"]
    for field, expected in {
        "Case_ID": pid,
        "Specimen_ID": patient["specimen_id"],
        "Slide_ID": patient["slide_id"],
        "Pathology": str(patient["pathdb_node_id"]),
        "Tumor": "LUAD",
        "Specimen_Type": "tumor_tissue",
        "Radiology": pid,
        "GDC_Link": "https://portal.gdc.cancer.gov/cases/" + patient["gdc_case_id"],
    }.items():
        require(row[field] == expected, f"{pid}: PathDB {field} mismatch")
    require(
        case["submitter_id"] == pid and case["case_id"] == patient["gdc_case_id"],
        f"{pid}: GDC case mismatch",
    )
    require(
        case["index_date"] == "Diagnosis", f"{pid}: unsupported clinical time origin"
    )
    samples = [
        s for s in case["samples"] if s["submitter_id"] == patient["specimen_id"]
    ]
    require(len(samples) == 1, f"{pid}: specimen must match exactly once")
    sample = samples[0]
    require(
        sample["sample_type"] == "Primary Tumor", f"{pid}: expected a tumor specimen"
    )
    day = sample.get("days_to_sample_procurement")
    require(
        type(day) is int and day == patient["slide_day"],
        f"{pid}: missing or changed specimen date",
    )
    slide_ids = [
        s["submitter_id"]
        for portion in sample.get("portions", [])
        for s in portion.get("slides", [])
    ]
    require(
        slide_ids.count(patient["slide_id"]) == 1,
        f"{pid}: GDC slide-to-specimen link mismatch",
    )
    require(
        node["clinicaltrialsubjectid"][0]["value"] == pid,
        f"{pid}: slide patient mismatch",
    )
    require(
        node["imageid"][0]["value"] == patient["slide_id"], f"{pid}: slide ID mismatch"
    )
    # PathDB advertises HTTP. Fetch the identical path over HTTPS.
    url = node["field_wsiimage"][0]["url"].replace("http://", "https://", 1)
    require(url == patient["slide"]["url"], f"{pid}: slide download URL changed")
    require(
        max(0, day, patient["ct"]["day"]) <= patient["cutoff_day"],
        f"{pid}: asset after cutoff",
    )


def verify_slide(path: Path, patient: dict[str, Any]) -> None:
    expected = patient["slide"]
    require(path.stat().st_size == expected["bytes"], f"{path.name}: size mismatch")
    require(digest(path) == expected["sha256"], f"{path.name}: checksum mismatch")
    with openslide.OpenSlide(str(path)) as slide:
        require(
            list(slide.dimensions) == expected["dimensions"],
            f"{path.name}: dimensions mismatch",
        )
        slide.get_thumbnail((512, 512)).load()
        width, height = slide.dimensions
        slide.read_region((width // 2, height // 2), 0, (224, 224)).load()


def verify_ct(
    zip_path: Path, destination: Path, patient: dict[str, Any]
) -> list[dict[str, Any]]:
    """Check every slice and write a clean study/series directory."""
    ct = patient["ct"]
    output = destination / ct["study_uid"] / ct["series_uid"]
    require(
        not output.exists(), f"Output already exists: {output}. Use a fresh run folder."
    )
    output.mkdir(parents=True)
    records = []
    seen = set()
    with zipfile.ZipFile(zip_path) as archive:
        members = [
            m
            for m in archive.infolist()
            if not m.is_dir() and m.filename.endswith(".dcm")
        ]
        require(
            len(members) == ct["instances"],
            f"{patient['patient_id']}: missing or extra CT slices",
        )
        require(
            sum(m.file_size for m in members) == ct["uncompressed_bytes"],
            "CT byte count changed",
        )
        for member in members:
            raw = archive.read(member)
            ds = pydicom.dcmread(io.BytesIO(raw))
            for keyword, expected in {
                "PatientID": patient["patient_id"],
                "StudyInstanceUID": ct["study_uid"],
                "SeriesInstanceUID": ct["series_uid"],
                "Modality": "CT",
                "ClinicalTrialTimePointID": str(ct["day"]),
            }.items():
                require(
                    str(getattr(ds, keyword, "")) == expected,
                    f"{member.filename}: {keyword} mismatch",
                )
            require(
                list(ds.ImageType) == ["ORIGINAL", "PRIMARY", "AXIAL"],
                "Expected original axial CT",
            )
            require(ds.Rows == 512 and ds.Columns == 512, "CT dimensions changed")
            require(
                ds.pixel_array.shape == (512, 512), "CT pixels could not be decoded"
            )
            sop = str(ds.SOPInstanceUID)
            require(
                bool(re.fullmatch(r"[0-9]+(?:\.[0-9]+)+", sop)) and sop not in seen,
                "Invalid or repeated CT instance ID",
            )
            seen.add(sop)
            sha256 = hashlib.sha256(raw).hexdigest()
            records.append({"sop_uid": sop, "sha256": sha256, "bytes": len(raw)})
            # Do not extract ZIP paths. Use the verified DICOM identifiers instead.
            (output / (sop + ".dcm")).write_bytes(raw)
    fingerprint = hashlib.sha256(
        "".join(
            f"{r['sop_uid']} {r['sha256']}\n"
            for r in sorted(records, key=lambda r: r["sop_uid"])
        ).encode()
    ).hexdigest()
    require(
        fingerprint == ct["instances_sha256"],
        "CT instance checksums differ from the verified series",
    )
    return records


def known(value: str) -> str | None:
    return (
        None
        if value.strip().lower() in {"", "unknown", "not reported", "n/a"}
        else value
    )


def write_tables(
    patient_root: Path, patient: dict[str, Any], row: dict[str, str]
) -> None:
    ehr = patient_root / "ehr"
    ehr.mkdir()
    pl.DataFrame(
        {
            "PTID": [patient["patient_id"]],
            "AGE": [int(row["Age"])],
            "SEX": [known(row["Gender"])],
            "RACE": [known(row["Race"])],
            "ETHNICITY": [known(row["Ethnicity"])],
        },
        schema={
            "PTID": pl.String,
            "AGE": pl.Int64,
            "SEX": pl.String,
            "RACE": pl.String,
            "ETHNICITY": pl.String,
        },
    ).write_parquet(ehr / "patient_characteristics.parquet")
    pl.DataFrame(
        {
            "INITIAL_DX_INTERVAL": [0],
            "ANATOMIC_SITE": [row["Topographic_Site"]],
            "HISTOLOGY": [row["Tumor_Histological_Type"]],
        },
        schema={
            "INITIAL_DX_INTERVAL": pl.Int64,
            "ANATOMIC_SITE": pl.String,
            "HISTOLOGY": pl.String,
        },
    ).write_parquet(ehr / "diagnosis.parquet")
    pl.DataFrame(
        {
            "DEID_ACCESSION_NUMBER": [patient["specimen_id"]],
            "PATHOLOGY_IMG_FILENAME": [patient["slide"]["filename"]],
            "SLIDE_INTERVAL": [patient["slide_day"]],
            "DATE_SOURCE": [DATE_SOURCE],
        }
    ).write_parquet(ehr / "wsi_list.parquet")
    pl.DataFrame(
        {
            "FULL_FILE_NAME": [
                patient["patient_id"] + "/" + patient["ct"]["study_uid"]
            ],
            "IMG_INTERVAL": [patient["ct"]["day"]],
        }
    ).write_parquet(ehr / "dicom_inventory_file.parquet")


def package_request(
    work: Path, patient: dict[str, Any], variant: str, task: str
) -> dict[str, Any]:
    modalities = VARIANTS[variant]
    root = work / "patients" / patient["patient_id"]
    tables = ["patient_characteristics.parquet", "diagnosis.parquet"]
    objects = [
        {"modality": "ehr", "artifact_kind": "archive", "local_path": "/input/ehr"}
    ]
    paths = []
    if "wsi" in modalities:
        tables.append("wsi_list.parquet")
        paths.append(root / "pathology" / patient["slide"]["filename"])
        objects.append(
            {
                "modality": "wsi",
                "artifact_kind": "archive",
                "local_path": "/input/pathology",
            }
        )
    if "ct" in modalities:
        tables.append("dicom_inventory_file.parquet")
        paths.extend(sorted((root / "radiology").rglob("*.dcm")))
        objects.append(
            {
                "modality": "radiology",
                "artifact_kind": "archive",
                "local_path": "/input/radiology",
            }
        )
    paths = [root / "ehr" / name for name in tables] + paths
    request = {
        "schema_version": "1.0",
        "request_uuid": str(uuid.uuid4()),
        "task_id": {"os": "time_to_death", "ttnt": "time_to_next_treatment_or_death"}[
            task
        ],
        "task_version": "1.0",
        "task_inputs": {},
        "observation_cutoff_day_offset": patient["cutoff_day"],
        "data_objects": objects,
    }
    filename = f"{patient['patient_id']}-{variant}-{task}.tar"
    output = work / "requests" / filename
    with tarfile.open(output, "w", format=tarfile.PAX_FORMAT) as archive:
        raw = json.dumps(request, indent=2).encode()
        member = tarfile.TarInfo("request.json")
        member.size = len(raw)
        archive.addfile(member, io.BytesIO(raw))
        for path in paths:
            require(
                path.is_file() and not path.is_symlink(),
                f"Expected a regular file: {path}",
            )
            archive.add(
                path,
                arcname="input/" + path.relative_to(root).as_posix(),
                recursive=False,
            )
    return {
        "patient_id": patient["patient_id"],
        "ablation": variant,
        "task_label": task,
        "filename": filename,
        "bytes": output.stat().st_size,
        "sha256": digest(output),
        "archive_members": len(paths) + 1,
        "request": request,
    }


def prepare(work: Path, cache: Path, task: str = "os") -> None:
    cohort = json.loads(Path(__file__).with_name("cohort.json").read_text())
    require(task in {"os", "ttnt"}, "Task must be os or ttnt")
    work.mkdir(parents=True, exist_ok=True)
    require(
        not (work / "patients").exists() and not (work / "request-index.json").exists(),
        "Use a fresh run folder; retain the cache to avoid downloading again.",
    )
    for name in ("sources", "requests", "results"):
        (work / name).mkdir(exist_ok=True)
    csv_path = download(
        cohort["pathdb_csv_url"],
        cache / "cptac_metadata_07-09-2024.csv",
        cohort["pathdb_csv_sha256"],
    )
    shutil.copyfile(csv_path, work / "sources" / csv_path.name)
    shutil.copyfile(
        Path(__file__).with_name("metadata") / "sources.json",
        work / "sources" / "gdc-sources.json",
    )
    with csv_path.open(newline="") as stream:
        rows = list(csv.DictReader(stream))
    evidence = []
    for patient in cohort["patients"]:
        pid = patient["patient_id"]
        print("Preparing", pid, flush=True)
        matches = [r for r in rows if r["Slide_ID"] == patient["slide_id"]]
        require(len(matches) == 1, f"{pid}: PathDB slide must match exactly once")
        row = matches[0]
        gdc_url = (
            "https://api.gdc.cancer.gov/cases/"
            + patient["gdc_case_id"]
            + "?"
            + urlencode({"expand": "samples,samples.portions,samples.portions.slides"})
        )
        node_url = f"https://pathdb.cancerimagingarchive.net/node/{patient['pathdb_node_id']}?_format=json"
        case = load_gdc_case(patient, work / "sources" / (pid + "-gdc.json"))
        node = fetch_json(node_url, work / "sources" / (pid + "-slide-node.json"))
        match_sources(patient, row, case, node)
        root = work / "patients" / pid
        (root / "pathology").mkdir(parents=True)
        slide = download(
            patient["slide"]["url"],
            cache / patient["slide"]["filename"],
            patient["slide"]["sha256"],
        )
        verify_slide(slide, patient)
        shutil.copyfile(slide, root / "pathology" / slide.name)
        ct_url = (
            NBIA
            + "getImage?"
            + urlencode({"SeriesInstanceUID": patient["ct"]["series_uid"]})
        )
        ct_zip = download(ct_url, cache / (pid + "-ct.zip"))
        ct_records = verify_ct(ct_zip, root / "radiology", patient)
        write_tables(root, patient, row)
        evidence.append(
            {
                "patient_id": pid,
                "gdc_case_id": patient["gdc_case_id"],
                "specimen_id": patient["specimen_id"],
                "slide_id": patient["slide_id"],
                "index_date": case["index_date"],
                "slide_day": patient["slide_day"],
                "slide_date_source": DATE_SOURCE,
                "ct_day": patient["ct"]["day"],
                "ct_date_source": "DICOM ClinicalTrialTimePointID (0012,0050)",
                "cutoff_day": patient["cutoff_day"],
                "ct_instances": ct_records,
                "slide_sha256": digest(slide),
                "gdc_url": gdc_url,
                "gdc_metadata_source": "repository snapshot; see metadata/sources.json",
                "pathdb_node_url": node_url,
            }
        )
    index = [
        package_request(work, patient, variant, task)
        for patient in cohort["patients"]
        for variant in VARIANTS
    ]
    save_json(work / "cohort.json", cohort)
    save_json(work / "verification.json", evidence)
    save_json(work / "request-index.json", index)
    print(
        f"PASS: matched 2 patients; verified 2 slides and 140 CT slices; wrote {len(index)} requests."
    )
    print(f"TAR bytes to upload: {sum(item['bytes'] for item in index):,}")
    print("Request index:", (work / "request-index.json").resolve())


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--cache", type=Path, default=Path("public-data-demo/cache"))
    parser.add_argument("--task", choices=("os", "ttnt"), default="os")
    args = parser.parse_args()
    prepare(args.output, args.cache, args.task)
