"""© 2025 University of Aberdeen. All rights reserved"""
from __future__ import annotations

"""Utility helpers for loading and tokenising source data.

This module mirrors the C# `DataHelper` class used in the original
WinForms application but operates purely on local CSV data.  Each source
represents a single row in the dataset and includes the tokenised words
contained in the text.  Only very small pieces of the original
functionality are replicated which is sufficient for the demo Streamlit
front‑end.
"""

from dataclasses import dataclass
from pathlib import Path
import re
from typing import Dict, Iterable, List, Set

import pandas as pd

# A reasonably comprehensive list of English stop words.  The set is based on
# ``sklearn.feature_extraction.text.ENGLISH_STOP_WORDS`` with a few additional
# tokens used in the original C# implementation.  Duplicates are ignored by the
# ``set`` constructor.
STOP_WORDS: Set[str] = {
    "i",
    "me",
    "my",
    "myself",
    "we",
    "our",
    "ours",
    "ourselves",
    "you",
    "your",
    "yours",
    "yourself",
    "yourselves",
    "he",
    "him",
    "his",
    "himself",
    "she",
    "her",
    "hers",
    "herself",
    "it",
    "its",
    "itself",
    "they",
    "them",
    "their",
    "theirs",
    "themselves",
    "what",
    "which",
    "who",
    "whom",
    "this",
    "that",
    "these",
    "those",
    "am",
    "is",
    "are",
    "was",
    "were",
    "be",
    "been",
    "being",
    "have",
    "has",
    "had",
    "having",
    "do",
    "does",
    "did",
    "doing",
    "a",
    "an",
    "the",
    "and",
    "but",
    "if",
    "or",
    "because",
    "as",
    "until",
    "while",
    "of",
    "at",
    "by",
    "for",
    "with",
    "about",
    "against",
    "between",
    "into",
    "through",
    "during",
    "before",
    "after",
    "above",
    "below",
    "to",
    "from",
    "up",
    "down",
    "in",
    "out",
    "on",
    "off",
    "over",
    "under",
    "again",
    "further",
    "then",
    "once",
    "here",
    "there",
    "when",
    "where",
    "why",
    "how",
    "all",
    "any",
    "both",
    "each",
    "few",
    "more",
    "most",
    "other",
    "some",
    "such",
    "no",
    "nor",
    "not",
    "only",
    "own",
    "same",
    "so",
    "than",
    "too",
    "very",
    "query",
    "t",
    "can",
    "will",
    "just",
    "don",
    "should",
    "now",
    # Additional tokens mirroring the original NLP.cs implementation
    "amp",
    "im",
    "dont",
    "didnt",
    "doesnt",
    "ive",
    "youve",
    "isnt",
    "wasnt",
    "wont",
    "wouldnt",
    "like",
}

TOKEN_RE = re.compile(r"\b\w+\b", re.UNICODE)


@dataclass
class Source:
    """Container for a single data source."""

    source_id: int
    text: str
    category_id: int
    words: Iterable[str]


class DataHelper:
    """Load and prepare data for the simplified 1 algorithm."""

    def __init__(self, csv_path: str = "dataset.csv") -> None:
        self.csv_path = Path(csv_path)

    def load_sources(self) -> Dict[int, Source]:
        """Load sources from a CSV file.

        Returns a mapping of source id to :class:`Source` objects.  The loader
        accepts two schemas:

        1) Original dataset format with ``sourceId``, ``sourceText`` and
           ``categoryId`` columns.
        2) News dataset format with ``Title``, ``Description`` and ``Query``
           columns. ``sourceId`` values are generated from the row order and
           ``categoryId`` values are generated from the unique ``Query``
           strings in order of first appearance.
        """

        df = pd.read_csv(self.csv_path)
        sources: Dict[int, Source] = {}

        if {"sourceId", "sourceText", "categoryId"}.issubset(df.columns):
            for row in df.itertuples(index=False):
                tokens = self.tokenise(str(row.sourceText))
                sources[int(row.sourceId)] = Source(
                    source_id=int(row.sourceId),
                    text=str(row.sourceText),
                    category_id=int(row.categoryId),
                    words=tokens,
                )
            return sources

        if {"Title", "Description", "Query"}.issubset(df.columns):
            category_map: Dict[str, int] = {}

            def category_id(query: str) -> int:
                if query not in category_map:
                    category_map[query] = len(category_map) + 1
                return category_map[query]

            for idx, row in enumerate(df.itertuples(index=False), start=1):
                title = "" if pd.isna(row.Title) else str(row.Title)
                description = "" if pd.isna(row.Description) else str(row.Description)
                text = f"{title} {description}".strip()
                tokens = self.tokenise(text)
                sources[idx] = Source(
                    source_id=idx,
                    text=text,
                    category_id=category_id(str(row.Query)),
                    words=tokens,
                )
            return sources

        raise ValueError(
            "CSV schema not recognised. Expected columns: "
            "sourceId/sourceText/categoryId or Title/Description/Query."
        )

    # ------------------------------------------------------------------
    def tokenise(self, text: str) -> List[str]:
        """Tokenise ``text`` in a similar fashion to the C# NLP helper."""

        text = text.lower()
        text = re.sub(r"http\S+", "", text)  # remove hyperlinks
        text = re.sub(r"[^#0-9a-z\s]", " ", text)
        tokens = TOKEN_RE.findall(text)
        if tokens and tokens[0] == "rt":
            tokens = tokens[1:]

        cleaned: List[str] = []
        first = True
        for tok in tokens:
            if tok.startswith("@"):
                continue
            if tok in STOP_WORDS:
                continue
            if tok == "rt" and first:
                first = False
                continue
            cleaned.append(tok)
            first = False
        return cleaned
