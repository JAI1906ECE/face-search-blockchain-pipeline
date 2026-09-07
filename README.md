# Face Search & Blockchain Verification Pipeline

This is a command-line proof of concept for Task 3:

```text
authorized face image
        ↓
InsightFace detection + encoding
        ↓
Google Lens reverse-image search
        ↓
real social-media result + metadata
        ↓
SHA-256 fingerprint
        ↓
append-only local blockchain (Web3-style hash chain)
        ↓
recompute and verify → MATCHED / MISMATCHED
```

The demo is deliberately scoped to images you are authorized to process. It
does not attempt to identify an unknown person from a face embedding, and it
does not substitute a preselected URL when search returns no match.

## What it demonstrates

1. `InsightFace` detects the face and produces an embedding summary.
2. The input image is uploaded to Google's public Lens upload flow on every
   run. The adapter extracts links from the live results page and requires at
   least one recognized social-media domain.
3. The input image hash and discovered post metadata are written into a
   canonical JSON payload.
4. The payload is SHA-256 hashed and anchored in an append-only local chain.
5. Verification recomputes the payload hash, block hash, and previous-block link.

The local chain is intentionally wallet-free and offline after the search step.
It uses Web3.py's Keccak implementation for block integrity and SHA-256 for the
evidence fingerprint. It is suitable for a screen-recorded demonstration of
tamper evidence, but it is not a public consensus blockchain. A production
deployment can replace `LocalBlockchain` with a Web3.py contract adapter while
keeping the payload and verification contract the same.

## Setup

Python 3.11+ is required. From the repository root:

```bash
uv sync
```

The first face scan may download InsightFace's `buffalo_l` model files.

## Run the complete pipeline

Use a clear image of a person you are authorized to process:

```bash
uv run face-chain run \
  --image ./examples/authorized-face.jpg \
  --state ./.face-chain/chain.json \
  --output ./evidence/result.json
```

The terminal prints the stages from the assignment and ends with:

```text
✓ MATCHED
Record ID: ...
Block hash: ...
```

The live reverse-image search can fail if Google changes the public upload
flow, blocks the request, or finds no public social result. The CLI reports
that failure instead of quietly using fake data. Use a distinctive image that
already appears publicly when recording the demo.

## Re-verify the anchored record

Copy the record ID printed by `run`:

```bash
uv run face-chain verify \
  --record-id <record-id> \
  --state ./.face-chain/chain.json
```

To demonstrate tamper evidence during a recording, edit the matching payload
file under `.face-chain/` and run `verify` again. It will return `MISMATCHED`.
Do not commit the generated `.face-chain/` or `evidence/` directories.

## Project layout

```text
face_pipeline/
  face.py        InsightFace detector and embedding summary
  search.py      live Google Lens reverse-image adapter
  blockchain.py  local append-only hash chain and verification
  pipeline.py    end-to-end orchestration
  cli.py         recording-friendly command-line interface
```

## Known limitations

- Google Lens's upload route is a public, undocumented web flow and may
  change or rate-limit automated requests.
- Social result extraction depends on public result links; private posts are
  not accessible.
- The default chain is local and simulated for reproducibility, not a public
  blockchain with external consensus.
- InsightFace's embedding is used to prove face processing occurred. Reverse
  image search is performed on the original authorized image because ordinary
  web search engines accept image uploads, not a raw face vector.
- This is a demonstration, not a biometric identity or law-enforcement tool.

## Submission checklist

- [ ] Push the full source to a GitHub repository.
- [ ] Record `uv run face-chain run ...` from upload through `✓ MATCHED`.
- [ ] Optionally show `face-chain verify ...` and a deliberate tamper check.
- [ ] Submit the GitHub URL and recording URL through the assignment form.