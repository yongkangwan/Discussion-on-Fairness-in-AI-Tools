# Git history cleanup before making the repository public

The current `main` tree no longer contains the raw working JSONL datasets, but those files still exist in older Git commits. Do **not** change the repository visibility to public until the history rewrite below is complete.

GitHub recommends using `git-filter-repo` for removing files from all repository history.

## Files to remove from every historical ref

The following paths existed in the private working history and should be removed from all branches/tags/refs:

```text
china_8000.jsonl
positive_chunks.jsonl
positive_chunks_china.jsonl
positive_chunks_dedup_pubpeer.jsonl
top_china.jsonl
top_other_train.jsonl
top_other_prove.jsonl
top_taiwan.jsonl
derived/china_5000.jsonl
derived/china_5000.jsonl.manifest.json
derived/other_5000.jsonl
derived/other_5000.jsonl.manifest.json
derived/top_other_prove_clean.jsonl
derived/top_other_prove_clean.jsonl.manifest.json
EXPERIMENT_REPORT.md
negtive_exclude_positive.py
```

## macOS cleanup commands

Install a recent `git-filter-repo`:

```bash
brew install git-filter-repo
```

Clone a fresh copy of the private repository:

```bash
git clone https://github.com/yongkangwan/Discussion-on-Fairness-in-AI-Tools.git
cd Discussion-on-Fairness-in-AI-Tools
```

Rewrite all refs to remove the old private artifacts:

```bash
git filter-repo --sensitive-data-removal --invert-paths \
  --path china_8000.jsonl \
  --path positive_chunks.jsonl \
  --path positive_chunks_china.jsonl \
  --path positive_chunks_dedup_pubpeer.jsonl \
  --path top_china.jsonl \
  --path top_other_train.jsonl \
  --path top_other_prove.jsonl \
  --path top_taiwan.jsonl \
  --path derived/china_5000.jsonl \
  --path derived/china_5000.jsonl.manifest.json \
  --path derived/other_5000.jsonl \
  --path derived/other_5000.jsonl.manifest.json \
  --path derived/top_other_prove_clean.jsonl \
  --path derived/top_other_prove_clean.jsonl.manifest.json \
  --path EXPERIMENT_REPORT.md \
  --path negtive_exclude_positive.py
```

Verify that the historical paths are gone:

```bash
git log --all -- \
  china_8000.jsonl \
  positive_chunks.jsonl \
  positive_chunks_china.jsonl \
  positive_chunks_dedup_pubpeer.jsonl \
  top_china.jsonl \
  top_other_train.jsonl \
  top_other_prove.jsonl \
  top_taiwan.jsonl \
  derived/ \
  EXPERIMENT_REPORT.md \
  negtive_exclude_positive.py
```

The command above should return no commits for those paths.

Check which pull-request refs were affected:

```bash
grep -c '^refs/pull/.*/head$' .git/filter-repo/changed-refs || true
```

Then force-push the rewritten refs:

```bash
git push --force --mirror origin
```

If `git-filter-repo` removed the `origin` remote, restore it first:

```bash
git remote add origin https://github.com/yongkangwan/Discussion-on-Fairness-in-AI-Tools.git
git push --force --mirror origin
```

After the rewrite, the old `public-release-draft` branch is no longer needed. Delete it from GitHub or run:

```bash
git push origin --delete public-release-draft
```

## After the force-push

1. Re-clone the repository rather than continuing to use any old clone.
2. Ask collaborators to discard/re-clone old copies so the removed history is not accidentally pushed back.
3. Confirm the current `main` tree still contains the README, docs, code, CI, and `data/paper_results/` aggregate tables.
4. Confirm GitHub Actions passes on the rewritten `main`.
5. Only then change repository visibility to public.

Because the removed material is not a leaked credential, GitHub Support may not purge cached objects merely on request. The important public-release step is to ensure no branch/tag/ref in the repository still points to the old raw-data history.
