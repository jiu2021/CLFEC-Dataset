# Commercial Proofreading Data

This directory contains the **anonymized outputs of three commercial Chinese
proofreading products**, used in two different experiments in the paper.

We refer to the three products as **P1**, **P2**, and **P3**. Their identities
are anonymized to comply with their respective terms of use.

## Layout — what data backs which experiment

```
commercial_data/
├── error_map.json                      # shared: product type → unified category
│
├── on_clfec/                           # ─── used for Table 3 (baselines on CLFEC) ───
│   ├── raw/{P1,P2,P3}.xlsx              raw product output as exported (xlsx)
│   └── processed/{P1,P2,P3}.json        same predictions, in CLFEC prediction schema
│
└── on_corpus/                          # ─── used for the Motivation figure ───
    ├── products_annotated.xlsx          products' candidates on the source corpus
    │                                     plus human flags (one sheet per product)
    └── reproduce_motivation.py          script that reproduces the figure's numbers
```

The two subdirectories answer **different questions** and are not
interchangeable:

| Subdirectory | What it covers | Used in paper for |
|--------------|----------------|-------------------|
| `on_clfec/`  | Each product's predictions on the **925 paragraphs of `data/CLFEC.json`** | Commercial-baseline rows of Table 3 |
| `on_corpus/` | Each product's candidates on the **source corpus** (4M chars across 公文 / 县级门户 / 论坛 / 知乎), with **human flags** (1=correct, 0=false-positive, 2=partial, 3=uncertain) | Motivation figure (verified-error density) |

## `on_clfec/` — predictions on CLFEC

Each product was run on every paragraph in `data/CLFEC.json`. Some products
fail to ingest a small number of paragraphs; per-product coverage:

| Product | # paragraphs |
|---------|-------------:|
| P1      |          925 |
| P2      |          648 |
| P3      |          700 |

### `on_clfec/raw/Pn.xlsx`

Raw output as the products themselves return it. Each row is one paragraph
with three columns:

| Column | Description |
|--------|-------------|
| `内容`     | The input paragraph fed to the product |
| `错误数据` | A JSON-encoded list of the product's flagged errors |
| `文档名称` | Document identifier (always `input_text` here) |

### `on_clfec/processed/Pn.json`

The same predictions, parsed into the **CLFEC prediction schema** (matches
`../data/CLFEC.json`). These files can be passed directly to
`../eval/eval.py` via `--pred`:

```bash
cd ../../eval
python eval.py \
    --gold ../data/CLFEC.json \
    --pred ../commercial_data/on_clfec/processed/P1.json \
    --mode both --output-dir ./results_P1
```

## `on_corpus/` — candidates on the source corpus + human flags

Each product was run on a 4M-character sample of professional and UGC
Chinese text (1M characters each from 公文 / 县级门户 / 论坛 / 知乎). The
products' raw candidates were deduplicated, format / punctuation flags were
removed, and the remaining items were **manually annotated** with a `flag`:

| `flag` | Meaning |
|--------|---------|
| `1`    | Confirmed: span is genuinely erroneous and the suggestion is appropriate |
| `0`    | False positive: the original text is correct |
| `2`    | Partial: the span is erroneous but the suggested correction is suboptimal |
| `3`    | Uncertain |

### `on_corpus/products_annotated.xlsx`

One sheet per product (`P1`, `P2`, `P3`). Columns:

| Column | Description |
|--------|-------------|
| `file`   | Source filename (prefix indicates the source group: `gongwen-…`, `xianji-…`, `luntan-…`, `zhihu-…`) |
| `sent`   | Sentence containing the candidate |
| `start` / `end` | Character offsets of the candidate in `sent` |
| `error`  | Original (allegedly erroneous) span |
| `cand`   | Product's suggested correction |
| `type`   | Product's own type label (used for P1, P3) |
| `label`  | Product's secondary label (used for P2; unused for P1/P3) |
| `flag`   | Human annotation (see table above) |

### `on_corpus/reproduce_motivation.py`

A self-contained script that loads the workbook, applies `error_map.json`,
filters to confirmed (`flag == 1`) Word/Grammar/Fact candidates, and prints
the verified-error density table that backs the paper's motivation figure:

```bash
cd on_corpus
python reproduce_motivation.py
```

Expected output (per-product · per-source-group · per-type density per
10K characters):

```
type                   Word  Grammar  Fact  Total
product group
P1      Professional   5.70     0.62  0.46   6.78
        UGC           17.73     0.68  0.65  19.05
P2      Professional   2.19     0.50  0.38   3.06
        UGC            8.52     1.54  0.92  10.97
P3      Professional   2.13     0.18  0.02   2.33
        UGC           10.12     0.70  0.04  10.85
```

## `error_map.json`

A nested mapping `{product → {raw_type_label → unified_category}}` that
collapses each product's many internal error labels into the six unified
categories used in the paper:

| Unified category | Description |
|-------|-------------|
| `Word`    | Spelling, character confusion, redundancy, omission |
| `Grammar` | Word order, collocation, structure, semantics |
| `Punc`    | Punctuation misuse |
| `Fact`    | Factual / knowledge / entity errors |
| `Format`  | Whitespace, halfwidth/fullwidth, numerals, date format |
| `Skip`    | Politically sensitive content & similar non-linguistic flags excluded from analysis |

The keys are the products' own `type` strings (P1, P3) or `label` strings
(P2). A few labels missing from earlier exports were added by hand; some
labels that initially mapped to `Fact` were re-categorized as `Format` after
manual inspection (e.g., date-format normalization). The exact rules used in
the paper are exactly those committed here.

## Citation

If you use this data, please cite the paper (BibTeX in the top-level
`README.md`).
