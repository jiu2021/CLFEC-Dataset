# CLFEC Evaluation

This directory contains the **standardized evaluation pipeline** used in the
paper. Scoring is a **two-step** process:

1. **Normalize** — convert raw model outputs (`(snippet, corrected_snippet)`
   pairs) into character-level standardized edits using a CHERRANT-style
   annotator.
2. **Score** — compare the standardized edits against the gold annotations in
   `../data/CLFEC.json` and report detection / correction metrics.

## Files

| File | Description |
|------|-------------|
| `normalize.py`    | Step 1: normalize raw model output → standardized predictions |
| `eval.py`         | Step 2: compute metrics against gold |
| `utils.py`        | `gen_cors()`: edit-pair → char-span normalization (used by `normalize.py`) |
| `annotator/`      | CHERRANT-style alignment & classification package |
| `run_eval.sh`     | Convenience wrapper: runs normalize + eval end-to-end |
| `requirements.txt`| Python dependencies for normalization |

## Setup

```bash
pip install -r requirements.txt
```

`eval.py` itself has **no** external dependencies. `normalize.py` depends on
`jieba`, `pypinyin`, `python-Levenshtein`, and `numpy`.

## Quick start

### End-to-end (recommended)

```bash
bash run_eval.sh /path/to/your_model_output.json ./results
```

This (1) normalizes your model's output and (2) scores it against
`../data/CLFEC.json`. Outputs go under `./results/`.

### Step by step

```bash
# 1) normalize raw outputs
python normalize.py \
    --input  /path/to/your_model_output.json \
    --output ./results/your_model_normalized.json

# 2) score
python eval.py \
    --gold ../data/CLFEC.json \
    --pred ./results/your_model_normalized.json \
    --mode both \
    --overlap-threshold 0.5 \
    --output-dir ./results
```

Two report files are written: a human-readable `*_详细评估结果.txt` and a
machine-readable `*_详细评估结果.json`.

## Input formats

### Raw model output (input to `normalize.py`)

A JSON list with one entry per gold paragraph:

```jsonc
[
  {
    "id":         "<gold-uuid>",         // must match an id in CLFEC.json
    "input_text": "<original paragraph>", // the text fed to the model
    "corrections": [
      {
        "original":  "<snippet from input_text containing the error>",
        "corrected": "<replacement snippet>",
        "reason":    "<optional, ignored by scorer>"
      }
      // ...
    ]
  }
  // ...
]
```

`normalize.py` aligns each `(original, corrected)` pair against `input_text`
and emits character-level edits. Edits that differ only in halfwidth /
fullwidth variants are dropped by default (CLFEC excludes such formatting
differences from its gold annotations).

### Standardized predictions (input to `eval.py`)

A JSON list with the same schema as `CLFEC.json`, but only `id`,
`input_text`, and `cors[*].{start, end, candidate_word}` are required:

```jsonc
[
  {
    "id":         "<gold-uuid>",
    "input_text": "<original paragraph>",
    "cors": [
      {
        "start": 49,
        "end":   51,
        "error_word":     "型势",
        "candidate_word": "形势",
        "item_id":        "<gold-uuid>"
      }
    ]
  }
]
```

If your model already emits this format directly, you can skip
`normalize.py` and call `eval.py` straight away.

## CLI options for `eval.py`

| Flag | Default | Description |
|------|---------|-------------|
| `--gold` | – | Path to `CLFEC.json` |
| `--pred` | – | Path to standardized predictions |
| `--mode` | `both` | `strict` / `loose` / `both` |
| `--overlap-threshold` | `0.5` | Overlap ratio used for loose match |
| `--output-dir` | `./data` | Where to write reports |
| `--is_limit_range` | off | Drop predictions outside any gold span before scoring (oracle-bound diagnostic) |

## Metrics

### Span matching

- **Strict**: predicted `(start, end)` must equal a gold `(start, end)`.
- **Loose**: the two intervals overlap, and the overlap covers at least
  `overlap-threshold` of the **shorter** interval.

### Per-prediction outcome

For each predicted edit, find the first not-yet-matched gold edit whose span
matches under the chosen mode:

- **Detection TP**: a gold span was matched (regardless of replacement text).
- **Correction TP**: a gold span was matched **and** `candidate_word` agrees.
- **FP / FN** are derived correspondingly.

### Reported numbers

For both `strict` and `loose`:

1. **Overall** detection / correction Precision · Recall · F1.
2. **By sample type** — same metrics restricted to ids of one of `mix`,
   `lec_only`, `fec_only`, `no_error`.
3. **By error type** — Detection recall over gold spans labeled
   `Word_Error` / `Fact_Error` / `Punc_Error` / `Grammar_Error`.

The `no_error` slice is particularly informative: any prediction on these
inputs is a false positive, so its FP count quantifies **over-correction**.

## Sanity check

Use the gold file as its own prediction → all metrics should be 1.0:

```bash
python eval.py \
    --gold ../data/CLFEC.json \
    --pred ../data/CLFEC.json \
    --mode both \
    --output-dir /tmp/clfec_sanity
```
