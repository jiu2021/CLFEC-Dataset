# CLFEC Dataset

This directory contains the **CLFEC** benchmark — a paragraph-level Chinese
proofreading dataset for **unified linguistic and factual error correction** in
professional writing.

## File

| File           | Format                    | Size    |
| -------------- | ------------------------- | ------- |
| `CLFEC.json` | UTF-8 JSON, list of dicts | ~3.1 MB |

## Schema

Each item in `CLFEC.json` has the following fields:

```jsonc
{
  "id": "ff1d570c-2caa-4b5b-9686-63d025ea22c6",   // unique id (UUID)
  "domain": "Law",                                  // one of: "Current Affairs", "Finance", "Law", "Medicine"
  "type":   "lec_only",                             // one of: "mix", "lec_only", "fec_only", "no_error"
  "input_text":     "...",                          // paragraph with errors injected
  "corrected_text": "...",                          // gold paragraph after correction
  "cors": [                                         // edit list (empty for "no_error")
    {
      "start": 49,
      "end":   51,
      "error_word":     "型势",
      "candidate_word": "形势",
      "error_type":     "Word_Error",               // one of: Word_Error, Grammar_Error, Fact_Error, Punc_Error
      "item_id":        "ff1d570c-..."              // same as parent id
    }
  ]
}
```

`start` / `end` are character offsets into `input_text` (left-closed,
right-open). Applying every `(start, end) → candidate_word` substitution to
`input_text` yields `corrected_text`.

## Statistics

- 925 paragraphs · 430,706 characters · 2,108 annotated errors
- Average paragraph length: 465.6 chars · Error density: **48.94 / 10K chars**

### Sample type × Domain

| Domain          |           mix |      lec_only |      fec_only |      no_error |         total |
| --------------- | ------------: | ------------: | ------------: | ------------: | ------------: |
| Current Affairs |           105 |            53 |            48 |            27 |           233 |
| Finance         |           113 |            66 |            57 |            32 |           268 |
| Law             |           100 |            51 |            49 |            20 |           220 |
| Medicine        |            89 |            46 |            47 |            22 |           204 |
| **Total** | **407** | **216** | **201** | **101** | **925** |

### Error type × Sample type

| Sample type     |          Word |       Grammar |          Punc |          Fact |           total |
| --------------- | ------------: | ------------: | ------------: | ------------: | --------------: |
| **Total** | **844** | **213** | **307** | **744** | **2,108** |

## Diagnostic splits

The four `type` values define the diagnostic splits used in the paper:

- **`mix`** — paragraphs containing both linguistic (Word / Grammar / Punc) and
  factual errors. The hardest setting; tests joint correction.
- **`lec_only`** — only linguistic errors. Tests pure LEC.
- **`fec_only`** — only factual errors. Tests pure FEC with
  evidence-grounded reasoning.
- **`no_error`** — clean paragraphs. Used to measure over-correction
  (a system should produce zero edits here).

## Usage

```python
import json
data = json.load(open("CLFEC.json", encoding="utf-8"))
for item in data:
    inp  = item["input_text"]
    gold = item["corrected_text"]
    edits = item["cors"]
    # ... your model
```

For evaluating your system's predictions, see `../eval/README.md`.

## Construction

Briefly: clean professional paragraphs were collected from authoritative
sources in four domains. Errors were then injected through a multi-stage
pipeline — LLM-based generation for word/punctuation errors with subtype
sampling, manual annotation for grammar errors, and domain-expert injection
for factual errors — followed by iterative model-in-the-loop annotation
review. Full details are in §3 of the paper.

## Citation

If you use this dataset, please cite the accompanying paper (BibTeX in the
top-level [`README.md`](../README.md)).
