"""Exercise arbitrary batches and reject patient/date mistakes before upload."""

import json
import tempfile
import unittest
from pathlib import Path

import polars as pl
from prepare_batch import prepare


class BatchTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.rows = []
        for number in range(3):
            patient = f"patient-{number}"
            ehr = self.root / patient / "ehr"
            ehr.mkdir(parents=True)
            pl.DataFrame({"PTID": [patient]}).write_parquet(
                ehr / "patient_characteristics.parquet"
            )
            pl.DataFrame(
                {"INITIAL_DX_INTERVAL": [0], "HISTOLOGY": ["Adenocarcinoma"]}
            ).write_parquet(ehr / "diagnosis.parquet")
            self.rows.append(
                {
                    "patient_id": patient,
                    "directory": patient,
                    "cutoff_day": 0,
                    "task": "os",
                    "modalities": ["ehr"],
                }
            )
        self.manifest = self.root / "batch.json"
        self.output = self.root / "output"

    def run_prepare(self):
        self.manifest.write_text(json.dumps(self.rows))
        prepare(self.manifest, self.output)

    def test_three_patients_have_unique_requests_and_matching_index(self):
        self.run_prepare()
        index = json.loads((self.output / "request-index.json").read_text())
        self.assertEqual(len(index), 3)
        self.assertEqual(len({item["request"]["request_uuid"] for item in index}), 3)
        self.assertEqual(
            {item["patient_id"] for item in index},
            {row["patient_id"] for row in self.rows},
        )
        self.assertEqual(len(list((self.output / "requests").glob("*.tar"))), 3)

    def test_wrong_patient_and_future_followup_are_rejected(self):
        path = self.root / "patient-0/ehr/patient_characteristics.parquet"
        pl.DataFrame({"PTID": ["another-patient"]}).write_parquet(path)
        with self.assertRaisesRegex(ValueError, "PTID"):
            self.run_prepare()
        pl.DataFrame(
            {"PTID": ["patient-0"], "LAST_ALIVE_INTERVAL": [300]}
        ).write_parquet(path)
        with self.assertRaisesRegex(ValueError, "cutoff"):
            self.run_prepare()
        self.assertFalse((self.output / "requests").exists())

    def test_duplicate_request_and_missing_image_are_rejected(self):
        self.rows.append(self.rows[0].copy())
        with self.assertRaisesRegex(ValueError, "one cutoff"):
            self.run_prepare()
        self.rows.pop()
        self.rows[0]["modalities"].append("wsi")
        with self.assertRaisesRegex(ValueError, "wsi_list"):
            self.run_prepare()

    def test_unused_image_metadata_is_excluded(self):
        pl.DataFrame({"wrong_column": [1]}).write_parquet(
            self.root / "patient-0/ehr/wsi_list.parquet"
        )
        self.run_prepare()
        import tarfile

        with tarfile.open(self.output / "requests/patient-0-ehr-os.tar") as archive:
            self.assertNotIn("input/ehr/wsi_list.parquet", archive.getnames())


if __name__ == "__main__":
    unittest.main()
