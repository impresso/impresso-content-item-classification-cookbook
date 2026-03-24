# Impresso Content Item Classification

This repository runs the Impresso content-item ad classifier on rebuilt
newspaper JSONL files and writes a reduced JSONL output for downstream use. The
shared build machinery lives in the `cookbook/` submodule; the task-specific
logic for this repository lives in the root `Makefile`, config, and
`lib/cli_content_item_classification.py`.

## Repository Layout

```text
.
├── Makefile
├── configs/
│   └── config-content-item-classification-multilingual_v1-0-0.mk
├── lib/
│   └── cli_content_item_classification.py
├── cookbook/                # shared Impresso make cookbook submodule
├── dotenv.sample
├── Pipfile
└── requirements.txt
```

## What It Produces

Input is expected to be rebuilt `jsonl` or `jsonl.bz2` newspaper content. The
pipeline writes one output row per input content item:

- non-article rows keep only `id` and `tp`
- article rows keep `id`, `tp`, and `ad_classification`

The current default run ID is derived from:

- process label: `content-item-classification`
- task: `base`
- model: `multilingual`
- run version: `v1-0-0`

## Setup

GNU Make 4 or newer is required. On macOS, that usually means using Homebrew
`gmake` instead of the system `make`.

```bash
git clone --recursive <repo-url>
cd impresso-content-item-classification-cookbook
cp dotenv.sample .env
pipenv install
gmake setup
```

If you do not use `pipenv`, install from `requirements.txt` instead.

## Usage

Show targets:

```bash
gmake help
```

Run one newspaper with the committed config:

```bash
gmake \
  CFG=configs/config-content-item-classification-multilingual_v1-0-0.mk \
  NEWSPAPER=BNL/actionfem \
  newspaper
```

Run a collection:

```bash
gmake \
  CFG=configs/config-content-item-classification-multilingual_v1-0-0.mk \
  COLLECTION_JOBS=4 \
  collection
```

The build first syncs rebuilt input data, then runs
`lib/cli_content_item_classification.py`, and finally uploads the output and log
back to S3.

## Configuration

Required environment variables go in `.env`:

```bash
SE_ACCESS_KEY=<YOUR VALUE>
SE_SECRET_KEY=<YOUR VALUE>
SE_HOST_URL=https://os.zhdk.cloud.switch.ch/
```

Useful runtime overrides:

- `CFG`: select a config file
- `NEWSPAPER`: process a single newspaper, default `BNL/actionfem`
- `COLLECTION_JOBS`: number of newspapers processed in parallel
- `NEWSPAPER_JOBS`: parallelism within one newspaper
- `LOGGING_LEVEL`: make and CLI logging verbosity

Task-specific defaults live in:

- `configs/config-content-item-classification-multilingual_v1-0-0.mk`
- `cookbook/paths_content_item_classification.mk`
- `cookbook/processing_content_item_classification.mk`
