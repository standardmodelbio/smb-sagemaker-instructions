"""Package prepared patient folders into a batch. Does not download data or call AWS."""

import argparse
import io
import json
import math
import re
import shutil
import sys
import tarfile
import uuid
from pathlib import Path

import openslide
import polars as pl
import pydicom

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "public_multimodal"))
from prepare_inputs import digest, patient_input_fingerprint, require, save_json

TASKS = {"os": "time_to_death", "ttnt": "time_to_next_treatment_or_death"}
REQUIRED = {
    "diagnosis": ["INITIAL_DX_INTERVAL"],
    "labs": ["TEST_INTERVAL"],
    "icd10": ["CD_INTERVAL"],
    "encounter": ["START_INTERVAL"],
    "procedure": ["START_INTERVAL"],
    "staging_events": ["EVENT_INTERVAL"],
    "comorbidity_events": ["ONSET_INTERVAL"],
    "metastatic_disease": ["METS_INTERVAL"],
    "biomarker": ["TEST_RESULT_INTERVAL"],
    "surgery": ["SURGERY_INTERVAL"],
    "radiation": ["RADIATION_START_INTERVAL"],
    "treatment": ["LOT", "ANTINEOPLASTIC_START_INTERVAL"],
    "performance": ["ECOG_DT_INTERVAL", "KPS_DT_INTERVAL"],
    "medications": ["START_INTERVAL"],
    "vitals": ["ENCOUNTER_ID"],
    "notes": ["NOTE_INTERVAL"],
    "imaging": ["RESULT_INTERVAL", "DEID_ACCESSION_NUMBER"],
    "reports": ["RESULT_INTERVAL", "DEID_ACCESSION_NUMBER"],
    "patient_characteristics": ["PTID"],
    "wsi_list": [
        "DEID_ACCESSION_NUMBER",
        "PATHOLOGY_IMG_FILENAME",
        "SLIDE_INTERVAL",
        "DATE_SOURCE",
    ],
    "dicom_inventory_file": ["FULL_FILE_NAME", "IMG_INTERVAL"],
}


def finite_day(value, cutoff):
    return (
        isinstance(value, (int, float))
        and not isinstance(value, bool)
        and math.isfinite(value)
        and value <= cutoff
    )


def input_files(root, patient_id, modalities, cutoff):
    require(root.is_dir(), f"Missing patient directory: {root}")
    # Reject symlinks before traversing or adding any patient files.
    require(not any(p.is_symlink() for p in root.rglob("*")), f"Symlink in {root}")
    files = []
    tables = {}
    excluded = set()
    if "wsi" not in modalities:
        excluded.add("wsi_list")
    if "radiology" not in modalities:
        excluded.add("dicom_inventory_file")
    for path in sorted((root / "ehr").glob("*.parquet")):
        name = path.stem
        if name in excluded:
            continue
        require(
            name in REQUIRED,
            f"Unsupported table: {path.name}; see README clinical schema",
        )
        frame = pl.read_parquet(path)
        require(not frame.is_empty(), f"Empty table: {path}; omit unused tables")
        require(
            set(REQUIRED[name]) <= set(frame.columns),
            f"{path.name} requires {REQUIRED[name]}",
        )
        for column in frame.columns:
            if column.endswith("_INTERVAL"):
                require(
                    all(finite_day(day, cutoff) for day in frame[column].drop_nulls()),
                    f"{path.name}.{column}: use numeric days at or before the cutoff",
                )
        if "PTID" in frame.columns:
            require(
                frame["PTID"].to_list() == [patient_id] * frame.height,
                f"{path.name}: PTID does not match {patient_id}",
            )
        tables[name] = frame
        files.append(path)
    require(
        "patient_characteristics" in tables, "Missing patient_characteristics.parquet"
    )
    require(
        tables["patient_characteristics"].height == 1,
        "Use one patient_characteristics row",
    )
    has_event = any(
        any(finite_day(day, cutoff) for day in frame[column].drop_nulls())
        for name, frame in tables.items()
        if name != "patient_characteristics"
        for column in REQUIRED[name]
        if column.endswith("_INTERVAL")
    )
    require(
        has_event, "Include a dated clinical or image event at or before the cutoff"
    )
    if "vitals" in tables:
        require(
            "encounter" in tables and "ENCOUNTER_ID" in tables["encounter"].columns,
            "Vitals require encounter.parquet with ENCOUNTER_ID and START_INTERVAL",
        )
        encounters = tables["encounter"]
        require(
            encounters["ENCOUNTER_ID"].n_unique() == encounters.height,
            "Encounter IDs must be unambiguous",
        )
        require(
            set(tables["vitals"]["ENCOUNTER_ID"]) <= set(encounters["ENCOUNTER_ID"]),
            "Vital row has no matching encounter",
        )
    if "wsi" in modalities:
        require("wsi_list" in tables, "WSI requires wsi_list.parquet")
        names = set()
        for row in tables["wsi_list"].to_dicts():
            name = row["PATHOLOGY_IMG_FILENAME"]
            require(
                isinstance(name, str) and name == Path(name).name and name not in names,
                "Slide filenames must be unique basenames",
            )
            names.add(name)
            require(
                bool(row["DEID_ACCESSION_NUMBER"]) and bool(row["DATE_SOURCE"]),
                "Each slide needs an accession and date source",
            )
            require(
                finite_day(row["SLIDE_INTERVAL"], cutoff),
                "Missing or future slide date",
            )
            path = root / "pathology" / name
            require(path.is_file(), f"Missing slide: {path}")
            with openslide.OpenSlide(str(path)) as slide:
                slide.get_thumbnail((64, 64)).load()
            files.append(path)
    if "radiology" in modalities:
        require(
            "dicom_inventory_file" in tables, "CT requires dicom_inventory_file.parquet"
        )
        studies = set()
        for row in tables["dicom_inventory_file"].to_dicts():
            parts = str(row["FULL_FILE_NAME"]).split("/")
            require(
                len(parts) == 2
                and parts[0] == patient_id
                and re.fullmatch(r"[0-9.]+", parts[1]),
                "Use FULL_FILE_NAME = patient_id/StudyInstanceUID",
            )
            study = parts[1]
            require(study not in studies, "Duplicate CT study")
            studies.add(study)
            require(
                finite_day(row["IMG_INTERVAL"], cutoff), "Missing or future CT date"
            )
            paths = sorted((root / "radiology" / study).glob("*/*.dcm"))
            require(bool(paths), f"No CT slices for study {study}")
            sops = set()
            for path in paths:
                ds = pydicom.dcmread(path)
                require(
                    str(ds.get("PatientID", "")) == patient_id,
                    f"CT patient mismatch: {path}",
                )
                require(
                    str(ds.get("StudyInstanceUID", "")) == study,
                    f"CT study mismatch: {path}",
                )
                require(
                    str(ds.get("SeriesInstanceUID", "")) == path.parent.name,
                    f"CT series mismatch: {path}",
                )
                require(ds.get("Modality") == "CT", f"Expected CT: {path}")
                require(
                    "LOCALIZER" not in ds.get("ImageType", []),
                    f"Exclude CT scouts: {path}",
                )
                sop = str(ds.get("SOPInstanceUID", ""))
                require(
                    bool(sop) and sop not in sops,
                    f"Missing or duplicate CT instance: {path}",
                )
                sops.add(sop)
                require(ds.pixel_array.size > 0, f"Empty CT pixels: {path}")
            files.extend(paths)
    return files


def prepare(manifest, output):
    manifest = Path(manifest).resolve()
    output = Path(output).resolve()
    rows = json.loads(manifest.read_text())
    require(
        isinstance(rows, list) and bool(rows), "Manifest must be a nonempty JSON list"
    )
    require(
        not (output / "request-index.json").exists()
        and not (output / "requests").exists(),
        "Use a fresh output folder",
    )
    checked = []
    combinations = set()
    patient_roots = {}
    for row in rows:
        patient = row["patient_id"]
        require(
            isinstance(patient, str)
            and re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_-]{0,99}", patient),
            "Use a patient ID containing letters, numbers, underscores, or hyphens",
        )
        root = (manifest.parent / row["directory"]).resolve()
        require(
            not output.is_relative_to(root), "Keep output outside patient directories"
        )
        require(
            patient not in patient_roots or patient_roots[patient] == root,
            "Use one source directory per patient",
        )
        patient_roots[patient] = root
        modalities = row["modalities"]
        require(
            isinstance(modalities, list)
            and "ehr" in modalities
            and set(modalities) <= {"ehr", "wsi", "radiology"}
            and len(modalities) == len(set(modalities)),
            "Choose ehr, wsi, and/or radiology; ehr is required",
        )
        cutoff, task = row["cutoff_day"], row.get("task", "os")
        require(finite_day(cutoff, float("inf")), "Cutoff must be a finite numeric day")
        require(task in TASKS, "Task must be os or ttnt")
        variant = (
            "ehr"
            + ("-wsi" if "wsi" in modalities else "")
            + ("-ct" if "radiology" in modalities else "")
        )
        key = (patient, variant, task)
        require(
            key not in combinations,
            "Use one cutoff per patient/task/combination in a batch",
        )
        combinations.add(key)
        checked.append(
            (row, root, variant, input_files(root, patient, modalities, cutoff))
        )
    for name in ("requests", "results"):
        (output / name).mkdir(parents=True, exist_ok=True)
    index = []
    for row, root, variant, paths in checked:
        task = row.get("task", "os")
        request = {
            "schema_version": "1.0",
            "request_uuid": str(uuid.uuid4()),
            "task_id": TASKS[task],
            "task_version": "1.0",
            "task_inputs": {},
            "observation_cutoff_day_offset": row["cutoff_day"],
            "data_objects": [
                {
                    "modality": m,
                    "artifact_kind": "archive",
                    "local_path": "/input/" + folder,
                }
                for m, folder in [
                    ("ehr", "ehr"),
                    ("wsi", "pathology"),
                    ("radiology", "radiology"),
                ]
                if m in row["modalities"]
            ],
        }
        filename = f"{row['patient_id']}-{variant}-{task}.tar"
        target = output / "requests" / filename
        with tarfile.open(target, "w", format=tarfile.PAX_FORMAT) as archive:
            raw = json.dumps(request, indent=2).encode()
            member = tarfile.TarInfo("request.json")
            member.size = len(raw)
            archive.addfile(member, io.BytesIO(raw))
            for path in paths:
                require(
                    path.is_file() and not path.is_symlink(),
                    f"Not a regular file: {path}",
                )
                archive.add(
                    path,
                    arcname="input/" + path.relative_to(root).as_posix(),
                    recursive=False,
                )
        index.append(
            {
                "patient_id": row["patient_id"],
                "ablation": variant,
                "task_label": task,
                "filename": filename,
                "bytes": target.stat().st_size,
                "sha256": digest(target),
                "patient_input_sha256": patient_input_fingerprint(target),
                "archive_members": len(paths) + 1,
                "request": request,
            }
        )
    shutil.copyfile(manifest, output / "own-data-manifest.json")
    save_json(output / "request-index.json", index)
    print(f"PASS: packaged {len(index)} requests for {len(patient_roots)} patients.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    prepare(args.manifest, args.output)
