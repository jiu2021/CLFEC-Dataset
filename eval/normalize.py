#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
normalize.py — Convert model outputs to standardized CLFEC prediction format.

Many proofreading models output raw (snippet, corrected_snippet) pairs. To
score them with eval.py, those pairs first need to be aligned against the
input text and turned into character-level (start, end, error_word,
candidate_word) edits. This script does exactly that.

Input format (JSON list, one item per gold paragraph):

    [
      {
        "id":         "<gold-uuid>",
        "input_text": "<original paragraph>",
        "corrections": [
          {"original":  "<snippet from input>",
           "corrected": "<snippet replacement>",
           "reason":    "<optional, ignored>"}
        ]
      }
      ...
    ]

Output format (a JSON list of items in the same schema as CLFEC.json):

    [
      {
        "id":         "<gold-uuid>",
        "input_text": "<original paragraph>",
        "cors": [
          {"start": int, "end": int,
           "error_word": str, "candidate_word": str,
           "item_id": "<gold-uuid>"}
        ]
      }
      ...
    ]

The output file can be passed directly to eval.py via --pred.
"""
import argparse
import json
import os
import sys

from utils import gen_cors


def is_only_fullwidth_difference(s1: str, s2: str) -> bool:
    """Return True if s1 and s2 differ only in halfwidth/fullwidth variants."""
    def to_half(s):
        out = []
        for ch in s:
            code = ord(ch)
            if code == 0x3000:
                out.append(chr(0x0020))
            elif 0xFF01 <= code <= 0xFF5E:
                out.append(chr(code - 0xFEE0))
            else:
                out.append(ch)
        return "".join(out)
    return to_half(s1) == to_half(s2)


def normalize_item(item: dict, drop_fullwidth_only: bool = True) -> dict:
    item_id = item["id"]
    input_text = item["input_text"]
    corrections = item.get("corrections", [])

    new_cors = []
    for cor in corrections:
        original = cor.get("original", "")
        corrected = cor.get("corrected", "")
        if not original:
            continue

        edits = gen_cors(item_id, input_text, original, corrected)
        for e in edits:
            if drop_fullwidth_only and is_only_fullwidth_difference(
                e["error_word"], e["candidate_word"]
            ):
                continue
            new_cors.append(e)

    out = {
        "id": item_id,
        "input_text": input_text,
        "cors": new_cors,
    }
    # Pass through any optional fields if present
    for k in ("corrected_text", "domain", "type"):
        if k in item:
            out[k] = item[k]
    return out


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--input", required=True,
                    help="Path to model-output JSON (corrections-style)")
    ap.add_argument("--output", required=True,
                    help="Where to write the standardized predictions")
    ap.add_argument("--keep-fullwidth-only-edits", action="store_true",
                    help="Keep edits that differ only in fullwidth/halfwidth "
                         "variants. Default: drop them, since CLFEC excludes "
                         "such formatting differences from gold edits.")
    args = ap.parse_args()

    with open(args.input, "r", encoding="utf-8") as f:
        items = json.load(f)

    out_items = []
    for it in items:
        out_items.append(
            normalize_item(it, drop_fullwidth_only=not args.keep_fullwidth_only_edits)
        )

    os.makedirs(os.path.dirname(os.path.abspath(args.output)) or ".", exist_ok=True)
    with open(args.output, "w", encoding="utf-8") as f:
        json.dump(out_items, f, ensure_ascii=False, indent=2)

    n_in = sum(len(it.get("corrections", [])) for it in items)
    n_out = sum(len(it["cors"]) for it in out_items)
    print(f"Read {len(items)} items, {n_in} raw corrections.")
    print(f"Wrote {len(out_items)} items, {n_out} standardized cors -> {args.output}")


if __name__ == "__main__":
    main()
