"""
Insert paragraph breaks into the "News body" column of a CSV using the exact same
splitting logic as paragraphAdd(text) in `src/website_management/pages/NewsAnnotationTool.js`.

This script can join paragraphs either with real newline characters (multi-line CSV fields)
or with the literal two-character sequence "\\n".

Usage:
  python src/website_management/helper_scripts/insert_paragraph_breaks_csv.py \
    --input public/article_dataset_versions/test3_encoding_fixed_300_700_words.csv \
    --output public/article_dataset_versions/test3_encoding_fixed_300_700_words_paragraphs.csv \
    --mode literal
"""

from __future__ import annotations

import argparse
import csv
from pathlib import Path


def paragraph_add(text: str) -> list[str]:
    # Mirror of paragraphAdd(text) from NewsAnnotationTool.js
    words = (text or "").split()
    paragraphs: list[str] = []
    paragraph = ""
    word_count = 0
    inside_quote = False

    for word in words:
        paragraph += word + " "
        word_count += 1

        # Detect quote entry/exit
        if '"' in word:
            quote_count = word.count('"')
            # Toggle quote status for each odd quote encountered
            if quote_count % 2 != 0:
                inside_quote = not inside_quote

        # Only insert break if:
        # - 150+ words
        # - Ends with a period
        # - Not inside a quote
        if word_count >= 150 and word.endswith(".") and not inside_quote:
            paragraphs.append(paragraph.strip())
            paragraph = ""
            word_count = 0

    if paragraph.strip():
        paragraphs.append(paragraph.strip())

    return paragraphs


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", required=True, help="Input CSV path")
    parser.add_argument("--output", required=True, help="Output CSV path")
    parser.add_argument(
        "--mode",
        choices=("literal", "actual"),
        default="literal",
        help="How to join paragraphs: 'literal' inserts the two-character sequence \\\\n; "
        "'actual' inserts real newline characters inside the CSV field.",
    )
    args = parser.parse_args()

    input_path = Path(args.input)
    output_path = Path(args.output)

    with input_path.open("r", encoding="utf-8", newline="") as infile:
        reader = csv.DictReader(infile)
        if not reader.fieldnames:
            raise SystemExit("Input CSV has no header row.")

        output_path.parent.mkdir(parents=True, exist_ok=True)
        with output_path.open("w", encoding="utf-8", newline="") as outfile:
            writer = csv.DictWriter(outfile, fieldnames=reader.fieldnames, quoting=csv.QUOTE_MINIMAL)
            writer.writeheader()

            joiner = "\\n" if args.mode == "literal" else "\n"

            for row in reader:
                body = row.get("News body", "")
                paragraphs = paragraph_add(body)
                row["News body"] = joiner.join(paragraphs)
                writer.writerow(row)

    print(f"Wrote: {output_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

