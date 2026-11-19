"""Checks for patient/date matching and isolation between input combinations."""

import copy
import hashlib
import io
import json
import tarfile
import tempfile
import unittest
import uuid
import zipfile
from pathlib import Path

import pydicom
from pydicom.dataset import FileDataset, FileMetaDataset
from pydicom.uid import CTImageStorage, ExplicitVRLittleEndian

from prepare_inputs import (
    VARIANTS,
    match_sources,
    package_request,
    verify_ct,
    write_tables,
)


class PreparationTests(unittest.TestCase):
    def setUp(self):
        self.patients = json.loads(Path(__file__).with_name("cohort.json").read_text())[
            "patients"
        ]
        self.patient = self.patients[0]
        p = self.patient
        self.row = {
            "Case_ID": p["patient_id"],
            "Specimen_ID": p["specimen_id"],
            "Slide_ID": p["slide_id"],
            "Pathology": str(p["pathdb_node_id"]),
            "Tumor": "LUAD",
            "Specimen_Type": "tumor_tissue",
            "Radiology": p["patient_id"],
            "GDC_Link": "https://portal.gdc.cancer.gov/cases/" + p["gdc_case_id"],
            "Age": "80",
            "Gender": "Male",
            "Race": "Unknown",
            "Ethnicity": "Unknown",
            "Topographic_Site": "Lung",
            "Tumor_Histological_Type": "Adenocarcinoma",
        }
        self.case = {
            "submitter_id": p["patient_id"],
            "case_id": p["gdc_case_id"],
            "index_date": "Diagnosis",
            "samples": [
                {
                    "submitter_id": p["specimen_id"],
                    "sample_type": "Primary Tumor",
                    "days_to_sample_procurement": 0,
                    "portions": [{"slides": [{"submitter_id": p["slide_id"]}]}],
                }
            ],
        }
        self.node = {
            "clinicaltrialsubjectid": [{"value": p["patient_id"]}],
            "imageid": [{"value": p["slide_id"]}],
            "field_wsiimage": [{"url": p["slide"]["url"]}],
        }

    def test_exact_matching_and_missing_or_wrong_dates(self):
        match_sources(self.patient, self.row, self.case, self.node)
        for day in (None, True, "0", 1):
            with self.subTest(day=day):
                case = copy.deepcopy(self.case)
                case["samples"][0]["days_to_sample_procurement"] = day
                with self.assertRaisesRegex(ValueError, "specimen date"):
                    match_sources(self.patient, self.row, case, self.node)
        case = copy.deepcopy(self.case)
        case["index_date"] = "Study Enrollment"
        with self.assertRaisesRegex(ValueError, "time origin"):
            match_sources(self.patient, self.row, case, self.node)

    def test_cross_patient_or_cross_specimen_slide_is_rejected(self):
        node = copy.deepcopy(self.node)
        node["clinicaltrialsubjectid"][0]["value"] = self.patients[1]["patient_id"]
        with self.assertRaisesRegex(ValueError, "slide patient"):
            match_sources(self.patient, self.row, self.case, node)
        case = copy.deepcopy(self.case)
        case["samples"][0]["portions"][0]["slides"][0]["submitter_id"] = "another-slide"
        with self.assertRaisesRegex(ValueError, "slide-to-specimen"):
            match_sources(self.patient, self.row, case, self.node)

    def test_all_eight_archives_keep_only_the_requested_modalities(self):
        with tempfile.TemporaryDirectory() as temp:
            work = Path(temp)
            (work / "requests").mkdir()
            uuids = set()
            for patient in self.patients:
                root = work / "patients" / patient["patient_id"]
                (root / "pathology").mkdir(parents=True)
                (root / "pathology" / patient["slide"]["filename"]).write_bytes(
                    b"test-slide"
                )
                ct = (
                    root
                    / "radiology"
                    / patient["ct"]["study_uid"]
                    / patient["ct"]["series_uid"]
                )
                ct.mkdir(parents=True)
                (ct / "1.2.3.dcm").write_bytes(b"test-ct")
                write_tables(root, patient, self.row)
                baseline = None
                for variant in VARIANTS:
                    item = package_request(work, patient, variant, "os")
                    uuids.add(uuid.UUID(item["request"]["request_uuid"]))
                    with tarfile.open(
                        work / "requests" / item["filename"], "r:"
                    ) as archive:
                        names = archive.getnames()
                        self.assertTrue(all(m.isfile() for m in archive.getmembers()))
                        self.assertEqual(
                            "input/ehr/wsi_list.parquet" in names, "wsi" in variant
                        )
                        self.assertEqual(
                            "input/ehr/dicom_inventory_file.parquet" in names,
                            "ct" in variant,
                        )
                        self.assertEqual(
                            any(n.startswith("input/pathology/") for n in names),
                            "wsi" in variant,
                        )
                        self.assertEqual(
                            any(n.startswith("input/radiology/") for n in names),
                            "ct" in variant,
                        )
                        common = [
                            archive.extractfile("input/ehr/" + name).read()
                            for name in (
                                "patient_characteristics.parquet",
                                "diagnosis.parquet",
                            )
                        ]
                        if baseline is None:
                            baseline = common
                        self.assertEqual(common, baseline)
            self.assertEqual(len(uuids), 8)
            self.assertTrue(all(value.version == 4 for value in uuids))

    def test_ct_checks_each_slice_identity_date_and_checksum(self):
        patient = copy.deepcopy(self.patient)
        ct = patient["ct"]
        sop = "1.2.826.0.1.3680043.10.543.1"
        meta = FileMetaDataset()
        meta.TransferSyntaxUID = ExplicitVRLittleEndian
        meta.MediaStorageSOPClassUID = CTImageStorage
        meta.MediaStorageSOPInstanceUID = sop
        ds = FileDataset(None, {}, file_meta=meta, preamble=b"\0" * 128)
        for name, value in {
            "SOPClassUID": CTImageStorage,
            "SOPInstanceUID": sop,
            "PatientID": patient["patient_id"],
            "StudyInstanceUID": ct["study_uid"],
            "SeriesInstanceUID": ct["series_uid"],
            "Modality": "CT",
            "ClinicalTrialTimePointID": str(ct["day"]),
            "ImageType": ["ORIGINAL", "PRIMARY", "AXIAL"],
            "Rows": 512,
            "Columns": 512,
            "SamplesPerPixel": 1,
            "PhotometricInterpretation": "MONOCHROME2",
            "BitsAllocated": 16,
            "BitsStored": 16,
            "HighBit": 15,
            "PixelRepresentation": 1,
            "PixelData": b"\0" * (512 * 512 * 2),
        }.items():
            setattr(ds, name, value)
        stream = io.BytesIO()
        pydicom.dcmwrite(stream, ds, enforce_file_format=True)
        raw = stream.getvalue()
        sha = hashlib.sha256(raw).hexdigest()
        ct.update(
            instances=1,
            uncompressed_bytes=len(raw),
            instances_sha256=hashlib.sha256(f"{sop} {sha}\n".encode()).hexdigest(),
        )
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            archive = root / "series.zip"
            with zipfile.ZipFile(archive, "w") as out:
                out.writestr("../../untrusted-name.dcm", raw)
            records = verify_ct(archive, root / "good", patient)
            self.assertEqual(records[0]["sop_uid"], sop)
            self.assertFalse((root.parent / "untrusted-name.dcm").exists())
            for keyword, value, message in (
                ("day", -99, "ClinicalTrialTimePointID"),
                ("series_uid", "1.2.3.4", "SeriesInstanceUID"),
                ("instances", 2, "missing or extra"),
                ("instances_sha256", "0" * 64, "checksums"),
            ):
                changed = copy.deepcopy(patient)
                changed["ct"][keyword] = value
                with (
                    self.subTest(keyword=keyword),
                    self.assertRaisesRegex(ValueError, message),
                ):
                    verify_ct(archive, root / keyword, changed)


if __name__ == "__main__":
    unittest.main()
