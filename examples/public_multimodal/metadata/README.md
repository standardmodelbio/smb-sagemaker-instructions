# Public GDC metadata

These public GDC case records link each selected patient to the tissue specimen
and pathology slide. They also give the specimen procurement day relative to
diagnosis. [sources.json](sources.json) records the source URLs and retrieval
times, with SHA-256 hashes of the stored responses.

The preparation helper checks these hashes and verifies the patient, specimen,
slide, and date relationships. It copies the records into each run's `sources/`
directory. Using these fixed snapshots keeps this example reproducible without
a live GDC API request.

The clinical CSV, PathDB slide records, and image files are downloaded from
their public providers. Clinical outcomes from the GDC records are excluded
from the model inputs.
