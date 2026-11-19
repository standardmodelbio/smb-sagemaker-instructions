# Recorded public multimodal inference

These are the measured outputs from the completed November 19, 2026 AWS run
of the [public walkthrough](../../../PUBLIC_DATA_WALKTHROUGH.md).
The cohort contains two public CPTAC-LUAD patients, each submitted with four
modality combinations. All requests use OS and observation cutoff zero.

- [Run configuration and validation](run.json).
- [Submitted requests and TAR checksums](request-index.json).
- [Full precision prediction table](predictions.csv).

The response files below contain the original bytes retrieved from S3.
Their SHA-256 hashes are in `run.json`.

- [C3L-00263, ehr](responses/C3L-00263-ehr-os.tar.out).
- [C3L-00263, ehr-wsi](responses/C3L-00263-ehr-wsi-os.tar.out).
- [C3L-00263, ehr-ct](responses/C3L-00263-ehr-ct-os.tar.out).
- [C3L-00263, ehr-wsi-ct](responses/C3L-00263-ehr-wsi-ct-os.tar.out).
- [C3L-00422, ehr](responses/C3L-00422-ehr-os.tar.out).
- [C3L-00422, ehr-wsi](responses/C3L-00422-ehr-wsi-os.tar.out).
- [C3L-00422, ehr-ct](responses/C3L-00422-ehr-ct-os.tar.out).
- [C3L-00422, ehr-wsi-ct](responses/C3L-00422-ehr-wsi-ct-os.tar.out).

The request UUIDs identify this particular run. Newly prepared requests get
new UUIDs, so compare scores by patient, combination, and task. Numerical
comparison also requires the same model image and input preparation.
The walkthrough includes code for that comparison.

Patient images and TAR files are excluded from Git. Recreate them using the
[cohort manifest](../cohort.json) and [preparation helper](../prepare_inputs.py).
The [verification record](../VERIFICATION.md) explains patient matching and
date alignment, including the distinction between specimen procurement and
digital-slide availability.

The temporary SageMaker model and this run's S3 objects were removed after
verification. The cleanup result is recorded in `run.json`.

Each request index entry also contains a `patient_input_sha256` fingerprint.
These were derived from the preserved input TARs after checking their recorded
archive hashes. The fingerprint hashes sorted lines of `path SHA256_OF_FILE`
with a newline after each line, excluding `request.json`. The notebook checks
request settings separately and ignores only the generated UUID. This permits
comparison after a fresh download or a change to metadata retrieval code.
