"""Verify that a polling timeout stops compute and cleanup stays within its run."""

import json
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace

import boto3
from botocore.exceptions import ClientError
from botocore.stub import Stubber

ROOT = Path(__file__).resolve().parents[2]
CELLS = [
    "".join(c["source"])
    for c in json.loads((ROOT / "public_multimodal_walkthrough.ipynb").read_text())[
        "cells"
    ]
    if c["cell_type"] == "code"
]
POLL = next(c for c in CELLS if c.startswith("deadline ="))
CLEANUP = next(c for c in CELLS if c.startswith("def is_missing_resource"))


def job(status):
    return {
        "TransformJobName": "smb-public-test",
        "TransformJobArn": "arn:aws:sagemaker:us-east-1:123456789012:transform-job/smb-public-test",
        "TransformJobStatus": status,
        "ModelName": "smb-public-test",
        "TransformInput": {
            "DataSource": {
                "S3DataSource": {
                    "S3DataType": "S3Prefix",
                    "S3Uri": "s3://test-bucket/input/",
                }
            }
        },
        "TransformOutput": {"S3OutputPath": "s3://test-bucket/output/"},
        "TransformResources": {"InstanceType": "ml.g5.2xlarge", "InstanceCount": 1},
        "CreationTime": datetime.now(timezone.utc),
    }


class RecoveryTests(unittest.TestCase):
    def setUp(self):
        session = boto3.Session(
            aws_access_key_id="test",
            aws_secret_access_key="test",
            region_name="us-east-1",
        )
        self.sm, self.s3 = session.client("sagemaker"), session.client("s3")
        self.state = {"job_name": "smb-public-test", "model_name": "smb-public-test"}

    def test_poll_timeout_requests_stop_before_raising(self):
        ticks = iter([0, 5401])
        clock = SimpleNamespace(
            monotonic=lambda: next(ticks), strftime=lambda _: "test"
        )
        with Stubber(self.sm) as stub:
            stub.add_response(
                "describe_transform_job",
                job("InProgress"),
                {"TransformJobName": "smb-public-test"},
            )
            stub.add_response(
                "stop_transform_job", {}, {"TransformJobName": "smb-public-test"}
            )
            with self.assertRaisesRegex(TimeoutError, "Stop requested"):
                exec(POLL, {"time": clock, "sm": self.sm, "state": self.state})
            stub.assert_no_pending_responses()

    def test_cleanup_waits_for_stop_and_deletes_only_indexed_keys_in_chunks(self):
        prefix = "smb-public-demo/smb-public-test/"
        index = [{"filename": f"patient-{i}.tar"} for i in range(501)]
        keys = [
            entry
            for item in index
            for entry in (
                {"Key": prefix + "input/" + item["filename"]},
                {"Key": prefix + "output/" + item["filename"] + ".out"},
            )
        ]
        with tempfile.TemporaryDirectory() as temp, Stubber(
            self.sm
        ) as sm_stub, Stubber(self.s3) as s3_stub:
            sm_stub.add_response(
                "describe_transform_job",
                job("InProgress"),
                {"TransformJobName": "smb-public-test"},
            )
            sm_stub.add_response(
                "stop_transform_job", {}, {"TransformJobName": "smb-public-test"}
            )
            sm_stub.add_response(
                "describe_transform_job",
                job("Stopping"),
                {"TransformJobName": "smb-public-test"},
            )
            sm_stub.add_response(
                "describe_transform_job",
                job("Stopped"),
                {"TransformJobName": "smb-public-test"},
            )
            sm_stub.add_response("delete_model", {}, {"ModelName": "smb-public-test"})
            sm_stub.add_client_error(
                "describe_model",
                service_error_code="ValidationException",
                service_message="Could not find model",
                expected_params={"ModelName": "smb-public-test"},
            )
            for chunk in (keys[:1000], keys[1000:]):
                s3_stub.add_response(
                    "delete_objects",
                    {},
                    {"Bucket": "test-bucket", "Delete": {"Objects": chunk}},
                )
            s3_stub.add_response(
                "list_objects_v2",
                {"IsTruncated": False},
                {"Bucket": "test-bucket", "Prefix": prefix},
            )
            exec(
                CLEANUP,
                {
                    "sm": self.sm,
                    "s3": self.s3,
                    "state": self.state,
                    "index": index,
                    "prefix": prefix,
                    "BUCKET": "test-bucket",
                    "work": Path(temp),
                    "json": json,
                    "ClientError": ClientError,
                    "time": SimpleNamespace(sleep=lambda _: None),
                },
            )
            self.assertEqual(
                json.loads((Path(temp) / "cleanup.json").read_text())["job_status"],
                "Stopped",
            )
            sm_stub.assert_no_pending_responses()
            s3_stub.assert_no_pending_responses()


if __name__ == "__main__":
    unittest.main()
