# Expected public-data results

These are the eight actual AWS responses for the two CPTAC-LUAD patients in
the [walkthrough](../../../PUBLIC_DATA_WALKTHROUGH.md). Each patient has four
input combinations. Every request uses OS with observation cutoff zero.

- [Full precision scores and request UUIDs](predictions.csv).
- [Request settings and input checksums](request-index.json).
- [Model identity and execution settings](run.json).
- [Patient matching and date alignment](../VERIFICATION.md).

## Expected scores

| Patient | `ehr` | `ehr-wsi` | `ehr-ct` | `ehr-wsi-ct` |
|---|---:|---:|---:|---:|
| `C3L-00263` | 291.09576153 | 271.37754702 | 296.24379776 | 260.38882875 |
| `C3L-00422` | 272.53007848 | 277.64935748 | 345.72121953 | 319.67090811 |

The table is rounded. Use the CSV for full precision. Your requests will have
new UUIDs. Compare each response with your own request, then compare scores
by patient, input combination, and task. The walkthrough checks numerical
agreement when the model image, patient files, and request settings match.

Each `patient_input_sha256` hashes sorted lines of `path SHA256_OF_FILE`, with
a newline after each line, for the patient files in the TAR. It excludes
`request.json`; request settings are compared separately. This keeps generated
UUIDs and TAR timestamps out of the patient-data comparison.

## Response files

These files contain the response values returned by AWS, saved as indented
JSON. Their checksums are in `run.json`.

- [C3L-00263, ehr](responses/C3L-00263-ehr-os.tar.out).
- [C3L-00263, ehr-wsi](responses/C3L-00263-ehr-wsi-os.tar.out).
- [C3L-00263, ehr-ct](responses/C3L-00263-ehr-ct-os.tar.out).
- [C3L-00263, ehr-wsi-ct](responses/C3L-00263-ehr-wsi-ct-os.tar.out).
- [C3L-00422, ehr](responses/C3L-00422-ehr-os.tar.out).
- [C3L-00422, ehr-wsi](responses/C3L-00422-ehr-wsi-os.tar.out).
- [C3L-00422, ehr-ct](responses/C3L-00422-ehr-ct-os.tar.out).
- [C3L-00422, ehr-wsi-ct](responses/C3L-00422-ehr-wsi-ct-os.tar.out).

The observed AWS job completed in 499.099 seconds on one `ml.g5.2xlarge` in
`us-east-1`. All eight responses passed the notebook's identity and score
checks. The temporary model and S3 objects were removed after completion.
