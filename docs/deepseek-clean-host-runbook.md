_Created: 15-08-2026 · Last updated: 05-09-2026_

# DeepSeek clean-host runbook (openmodel.ai inference)

The DeepSeek runners cannot run from the editor's automation host: inference
POSTs to `api.openmodel.ai` are severed at the TLS-handshake level (DPI), while
`GET /v1/models` and YouTube remain reachable. The gateway itself is healthy
(web playground answers). This runbook runs the inference jobs from a
**clean-egress host** (cloud VPS in an unfiltered region, or a machine whose
network reaches `api.openmodel.ai` cleanly — verify with the smoke test first).

Prepared by the build session of 2026-06-22. Scripts referenced live in
[tools/](https://github.com/gasyoun/IndologyScholars/tree/main/tools).

## What is already done (on the editor host, committed)

- Caption track: 176 videos inventoried, **161 RU transcripts** parsed, 8 in the
  Whisper queue. Transcripts live under `scratch/` (untracked — see Step C).
- The three runners and the shared client are committed under `tools/`.
- `.env` keys are `OPENMODEL_API_KEY` / `OPENMODEL_BASE_URL` / `OPENMODEL_MODEL`
  (runners also accept the legacy `DEEPSEEK_*` names as a fallback).

## Confirmed gateway facts

| Field | Value |
| --- | --- |
| Host | `api.openmodel.ai` (NOT `.app` — that does not resolve) |
| Base URL | `https://api.openmodel.ai/v1` |
| Endpoint | `POST {base}/chat/completions` (OpenAI format) |
| Auth | `Authorization: Bearer <OPENMODEL_API_KEY>` (key format `om-…`) |
| Model | `deepseek-chat` (also `deepseek-v4-flash`, `deepseek-v4-pro`) |

## Step 0 — clone, install, configure

```bash
git clone https://github.com/gasyoun/IndologyScholars
cd IndologyScholars
python -m pip install -r requirements.txt   # needs at least: requests, python-dotenv

# create .env (do NOT commit it):
cat > .env <<'EOF'
OPENMODEL_API_KEY=om-XXXXXXXXXXXXXXXX
OPENMODEL_BASE_URL=https://api.openmodel.ai/v1
OPENMODEL_MODEL=deepseek-chat
EOF
```

## Step A — smoke test (must pass before anything else)

```bash
python tools/openmodel_client.py --selftest
# expect:  OK  <time>s  model=deepseek-chat ...
#          reply: 'OK'
python tools/openmodel_client.py --models      # optional: list available models
```

If `--selftest` prints `route not found`, a TLS error, or a timeout, this host
is **not** clean-egress for `api.openmodel.ai` — fix the network before
continuing (do not run the bulk jobs against a failing endpoint).

## Step B — k=5 classification (no data transfer needed)

`scratch/classification_input.csv` regenerates from the committed
`analytics_output/expanded_classification_deepseek.csv`, so this track runs from
a bare clone:

```bash
python tools/build_deepseek_inputs.py                       # writes scratch/classification_input.csv
python tools/run_kfold_classification.py --limit 40         # cheap trial first
python tools/run_kfold_classification.py --k 5 --temp 0.5   # full 1362, resumable
```

Notes:
- `--temp 0.5` is required: at temperature 0 all five runs are identical and
  agreement is meaningless. This pass writes to its **own** files and never
  overwrites `expanded_classification_deepseek.csv`.
- Resumable: a dropped connection re-uses
  `analytics_output/classification_kfold_runs.json`; just re-run the command.

Outputs:
- `analytics_output/classification_kfold.csv` — consensus + per-field agreement
- `analytics_output/classification_kfold_disagreements.csv` — human-review queue

## Step C — video alignment / session chaptering (needs transcripts)

The segmentation bundles need the parsed transcripts, which are untracked.
Either transfer them or re-pull on this clean host (YouTube is reachable):

```bash
# OPTION 1 — re-pull on the clean host (no transfer):
python tools/caption_inventory.py
python tools/pull_captions.py
python tools/parse_captions.py

# OPTION 2 — transfer from the editor host instead of re-pulling:
#   copy scratch/transcripts/ and scratch/youtube_captions/ over, then:
# (skip the three caption scripts above)

python tools/build_deepseek_inputs.py                # rebuilds scratch/segmentation_inputs/
python tools/run_video_segmentation.py --limit 3     # trial
python tools/run_video_segmentation.py               # full (or --task segment_session)
```

Output:
- `analytics_output/video_segment_candidates.csv` — review queue; rows with
  confidence ≥ 0.80 are tagged `status=auto`, the rest `todo`; uncertain matches
  carry an inline `(?)` marker.

## Step D — bring results back to the editor host

Copy the produced CSVs back into `analytics_output/` on the editor host:

- `classification_kfold.csv`, `classification_kfold_disagreements.csv`
- `video_segment_candidates.csv`

Then on the editor host do the curation/integration (separate, deliberate
steps — none of these auto-publish):

1. Review `classification_kfold_disagreements.csv`; reconcile against the
   published `expanded_classification_deepseek.csv` where the k-fold consensus
   disagrees with the current label.
2. Promote high-confidence rows from `video_segment_candidates.csv` into
   `analytics_output/video_presentation_mapping.csv`.
3. Rebuild + validate: `python validate_publication.py && python -m pytest`.

## Cost / scale note

Full classification is 1362 talks × 5 runs ≈ small; full video segmentation
chunks the long sessions (the largest is ~10h ≈ 123k tokens). Both are well
within an unlimited-budget week. Start with the `--limit` trials to confirm
output quality before the full runs.

_Dr. Mārcis Gasūns_
