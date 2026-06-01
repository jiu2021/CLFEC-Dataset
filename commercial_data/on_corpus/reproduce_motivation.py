#!/usr/bin/env python3
"""
reproduce_motivation.py — reproduce the verified-error-density numbers
behind the paper's motivation figure.

Reads:
  - products_annotated.xlsx (sheets P1 / P2 / P3, this directory)
  - ../error_map.json

Outputs a table of per-product / per-source-group / per-error-type density
(per 10K characters), restricted to human-confirmed candidates (flag == 1).

Source group definitions (each group = 2M characters):
  - Professional = gongwen + xianji
  - UGC          = luntan + zhihu
"""
import json
import os
import sys

import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
XLSX = os.path.join(HERE, "products_annotated.xlsx")
EMAP = os.path.join(HERE, "..", "error_map.json")

# Each text source contributes 1M characters (公文/县级/论坛/知乎/其他)
GROUP_MAP = {"Professional": ["gongwen", "xianji"], "UGC": ["luntan", "zhihu"]}
GROUP_CHARS = 200  # in 10K-char units (= 2M chars per group)
VALID_PREFIXES = {"gongwen", "xianji", "luntan", "zhihu"}
CORE_TYPES = ["Word", "Grammar", "Fact"]

# P2 uses the `label` field, P1 and P3 use `type`
TYPE_FIELD = {"P1": "type", "P2": "label", "P3": "type"}


def get_prefix(file_val):
    if pd.isna(file_val) or not isinstance(file_val, str):
        return None
    name = file_val.split("news//")[-1] if "news//" in file_val else file_val
    prefix = name.split("-")[0] if "-" in name else None
    return prefix if prefix in VALID_PREFIXES else None


def main():
    with open(EMAP, "r", encoding="utf-8") as f:
        emap = json.load(f)

    rows = []
    for product in ("P1", "P2", "P3"):
        df = pd.read_excel(XLSX, sheet_name=product)
        df["unified"] = df[TYPE_FIELD[product]].apply(
            lambda x: emap[product].get(x, "Unknown") if pd.notna(x) else "Unknown"
        )
        df["prefix"] = df["file"].apply(get_prefix)

        confirmed = df[
            (df["prefix"].notna())
            & (df["unified"].isin(CORE_TYPES))
            & (df["flag"] == 1)
        ]

        for group_name, prefixes in GROUP_MAP.items():
            sub = confirmed[confirmed["prefix"].isin(prefixes)]
            for t in CORE_TYPES:
                count = int((sub["unified"] == t).sum())
                rows.append({
                    "product": product,
                    "group": group_name,
                    "type": t,
                    "count": count,
                    "density_per_10k": round(count / GROUP_CHARS, 3),
                })

    out = pd.DataFrame(rows)
    print(out.to_string(index=False))

    # Pretty pivot
    print("\nDensity (per 10K characters):")
    pivot = out.pivot_table(
        index=("product", "group"), columns="type",
        values="density_per_10k", aggfunc="first",
    )[CORE_TYPES]
    pivot["Total"] = pivot.sum(axis=1)
    print(pivot.round(2).to_string())


if __name__ == "__main__":
    sys.exit(main())
