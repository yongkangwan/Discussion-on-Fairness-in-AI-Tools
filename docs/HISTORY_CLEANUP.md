# Release history and private archive

Verified on 2026-10-04 against main at
`771cf31a1d06a5bce165efce5d83807b7d2721e0`.

The release repository, `yongkangwan/Discussion-on-Fairness-in-AI-Tools`, has a
clean root commit, `28b2e52ce0aec395cb1a89e68e6ff07c50198797`. Its main history
contains code and documentation, with later additions of aggregate tables,
PMID-only cohorts and explicitly synthetic examples. The archived raw article
JSONL datasets are absent from this history. Remote inventory at verification
contained only main, with no tags or pull requests.

The original raw-data sources referenced by the provenance manifests belong to
the separate `Discussion-on-Fairness-in-AI-Tools-private-archive` repository.
Keep that archive private; making the release repository public does not require
publishing the archive or moving its commits into this repository.

An earlier version of this document incorrectly carried forward history-rewrite
instructions from the original working repository. Those instructions no longer
apply to the release repository. No further history rewrite is needed for the
archived raw-data paths checked here.

Future additions should follow the [data guide](../data/README.md): publish
identifiers, appropriate derived metadata and safe examples, and keep retrieved
third-party text and run outputs outside tracked files. The commit IDs and
private-archive references in provenance metadata remain useful for tracing the
released PMID lists.
