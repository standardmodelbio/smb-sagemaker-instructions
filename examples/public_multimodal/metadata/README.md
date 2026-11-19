# Recorded public GDC metadata

These two JSON responses were saved from the public GDC cases API during the
successful November 19, 2026 inference run. They contain the case, sample,
portion, and slide records used to verify this tutorial's patient matching
and specimen procurement dates. The JSON content is unchanged from the saved
responses. [sources.json](sources.json) records the request URLs, retrieval
times, and hashes of the stored files.

The preparation helper verifies these hashes and performs the same identity
and date checks on every run. It copies the records and their source manifest
into the run's `sources/` directory. This fixed example uses recorded metadata
because the live GDC hostname failed to resolve during notebook testing.
It does not claim to refresh these GDC records on every run.

The clinical CSV, PathDB slide records, and image files still come from their
public TCIA endpoints. No clinical outcome from these metadata files is added
to the model inputs.
