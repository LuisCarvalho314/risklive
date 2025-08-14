"""Python re-implementation of the original C# 1 algorithm.

The WinForms application included in the repository contains the reference
implementation of the Hierarchical Knowledge Tree (1) algorithm.  The
Streamlit demo originally shipped with a very small approximation of this
behaviour that merely counted words per category.  For the unit tests we
require behaviour that mirrors the real algorithm much more closely.  This
module is therefore a direct port of the C# logic written in a Pythonic
style.  Database interactions and user interface updates from the original
code have been removed but the algorithmic steps and data structures remain
the same.

The implementation below supports the following parameters:

``minimum_threshold_against_max_word_count``
    The proportion of the maximum word frequency a word must reach to be
    considered part of the same 1.

``similarity_threshold``
    Minimum fraction of overlapping sources required for a word to collide
    with an existing node.

``minimum_sources_important``
    The initial filter applied to words – only words that appear in at least
    this many sources are considered.

``minimum_sources_branch``
    Minimum number of sources a node must contain before a child 1 (branch)
    is created for it.

Only the pieces of the original system that are necessary for constructing
the tree are implemented; the classes mirror the structure of the C# types
(`SourceWord`, `Node` and `1`).
"""

from __future__ import annotations

from collections import Counter, OrderedDict
from copy import deepcopy
from dataclasses import dataclass, field
from typing import Dict,  List, Optional, Set, Tuple

from .data_helper import Source


# ---------------------------------------------------------------------------
# Data classes


@dataclass
class SourceWord:
    """Represents a word appearing in a particular source."""

    source_word_id: int
    source_id: int
    word_id: int
    word: str
    word_no_of_sources: int


@dataclass
class Node:
    """A node inside an :class:`1`."""

    node_id: int
    hkt_id: int
    word_ids: Set[int] = field(default_factory=set)
    source_ids: Set[int] = field(default_factory=set)
    top_words: List[int] = field(default_factory=list)


@dataclass
class HKT:
    """A Hierarchical Knowledge Tree."""

    hkt_id: int
    nodes: List[Node] = field(default_factory=list)
    expected_words: List[int] = field(default_factory=list)
    parent_node_id: int = 0


# ---------------------------------------------------------------------------
# Algorithm implementation


class HKTAlgorithm:
    """Port of the original algorithm used in the C# implementation."""

    def __init__(
        self,
        minimum_threshold_against_max_word_count: float = 0.0,
        similarity_threshold: float = 0.5,
        minimum_sources_important: int = 1,
        minimum_sources_branch: int = 1,
    ) -> None:
        self.minimum_threshold_against_max_word_count = (
            minimum_threshold_against_max_word_count
        )
        self.similarity_threshold = similarity_threshold
        self.minimum_sources_important = minimum_sources_important
        self.minimum_sources_branch = minimum_sources_branch

        # Datasets mirroring the C# fields ---------------------------------
        self.sourceDS: Dict[int, Source] = {}
        self.wordDS: Dict[int, str] = {}
        self.nodeDS: Dict[int, Node] = {}
        self.HKTDS: Dict[int, HKT] = {}

    # Public API -----------------------------------------------------------

    def build(self, sources: Dict[int, Source]) -> Tuple[Dict[int, HKT], Dict[str, int]]:
        """Build HKTs from ``sources``.

        Returns a tuple ``(hkts, stats)`` where ``hkts`` is a dictionary of
        :class:`1` objects indexed by their id and ``stats`` contains summary
        information similar to the status panel in the original application.
        """

        self.sourceDS = sources
        self.nodeDS = {}
        self.HKTDS = {}
        self.wordDS = {}

        # ------------------------------------------------------------------
        # Step 1 – gather all words and their counts across sources
        word_counts: Counter[str] = Counter()
        all_words: Set[str] = set()
        for src in sources.values():
            unique_words = set(src.words)
            word_counts.update(unique_words)
            all_words.update(unique_words)

        number_of_words = len(all_words)

        # Assign ids to words that pass the important-word threshold
        word_to_id: Dict[str, int] = {}
        next_id = 1
        for word, count in word_counts.items():
            if count >= self.minimum_sources_important:
                word_to_id[word] = next_id
                next_id += 1

        self.wordDS = {wid: w for w, wid in word_to_id.items()}

        # Build the SourceWord dataset (step 2 in the C# code)
        source_words: List[SourceWord] = []
        sw_id = 1
        for src in sources.values():
            for word in set(src.words):  # only count once per source
                if word in word_to_id:
                    source_words.append(
                        SourceWord(
                            source_word_id=sw_id,
                            source_id=src.source_id,
                            word_id=word_to_id[word],
                            word=word,
                            word_no_of_sources=word_counts[word],
                        )
                    )
                    sw_id += 1

        update_source_word_relation_db = len(source_words)

        # Sort by number of sources descending to mirror the C# dictionaries
        sorted_sw = sorted(
            source_words,
            key=lambda sw: (-sw.word_no_of_sources, sw.word_id),
        )

        main_word_ds: "OrderedDict[int, SourceWord]" = OrderedDict(
            (i, sw) for i, sw in enumerate(sorted_sw, start=1)
        )
        source_word_ds: "OrderedDict[int, SourceWord]" = OrderedDict(
            (k, deepcopy(v)) for k, v in main_word_ds.items()
        )

        # ------------------------------------------------------------------
        # Step 3 – create the first 1 and recursively build branches
        hkt = self.create_hkt(source_word_ds, parent_node_id=0)
        if hkt:
            self.HKTDS[hkt.hkt_id] = hkt
            self.create_branches(hkt, main_word_ds)

        stats = {
            "number_loaded": len(sources),
            "number_accepted_sources": len(sources),
            "number_of_words": number_of_words,
            "update_source_word_relation_db": update_source_word_relation_db,
            "number_of_hkts": len(self.HKTDS),
            "number_of_nodes": len(self.nodeDS),
        }

        return self.HKTDS, stats

    # Core algorithm ------------------------------------------------------

    def find_expected_words_general(
        self, source_word_ds: "OrderedDict[int, SourceWord]"
    ) -> List[int]:
        if not source_word_ds:
            return []
        maximum = next(iter(source_word_ds.values())).word_no_of_sources
        expected: List[int] = []
        seen: Set[int] = set()
        for sw in source_word_ds.values():
            if maximum == 0:
                break
            ratio = sw.word_no_of_sources / maximum
            if ratio >= self.minimum_threshold_against_max_word_count and sw.word_id not in seen:
                expected.append(sw.word_id)
                seen.add(sw.word_id)
            elif ratio < self.minimum_threshold_against_max_word_count:
                break
        return expected

    def create_node(
        self,
        new_node_id: int,
        hkt_id: int,
        source_word_ds: "OrderedDict[int, SourceWord]",
        word_id: int,
    ) -> Node:
        node = Node(node_id=new_node_id, hkt_id=hkt_id)
        node.word_ids.add(word_id)
        for sw in source_word_ds.values():
            if sw.word_id == word_id:
                node.source_ids.add(sw.source_id)
        return node

    def create_node_for_refuge_sources(
        self, new_node_id: int, hkt_id: int, refuge_sources: Set[int]
    ) -> Node:
        node = Node(node_id=new_node_id, hkt_id=hkt_id)
        node.word_ids.add(-1)
        node.source_ids.update(refuge_sources)
        return node

    def remove_word_from_source_word_ds(
        self, word_id: int, source_word_ds: "OrderedDict[int, SourceWord]"
    ) -> None:
        for key in [k for k, sw in source_word_ds.items() if sw.word_id == word_id]:
            del source_word_ds[key]

    def remove_word_from_expected_words(
        self, expected_words: List[int], word_id: int
    ) -> None:
        try:
            expected_words.remove(word_id)
        except ValueError:
            pass

    def create_hkt(
        self,
        source_word_ds: "OrderedDict[int, SourceWord]",
        parent_node_id: int,
    ) -> Optional[HKT]:
        expected_words = self.find_expected_words_general(source_word_ds)
        if not expected_words:
            return None

        hkt_id = len(self.HKTDS) + 1
        hkt = HKT(hkt_id=hkt_id, expected_words=expected_words, parent_node_id=parent_node_id)

        # Create first node based on the most frequent word
        first_word_id = next(iter(source_word_ds.values())).word_id
        new_node_id = len(self.nodeDS) + 1
        new_node = self.create_node(new_node_id, hkt_id, source_word_ds, first_word_id)
        hkt.nodes.append(new_node)
        self.nodeDS[new_node_id] = new_node

        self.remove_word_from_source_word_ds(first_word_id, source_word_ds)
        self.remove_word_from_expected_words(expected_words, first_word_id)

        # Process remaining expected words ---------------------------------
        for expected_word in list(expected_words):
            sources_of_expected = {
                sw.source_id for sw in source_word_ds.values() if sw.word_id == expected_word
            }

            collided_nodes: Dict[int, float] = {}
            for previous_node in hkt.nodes:
                node_sources = previous_node.source_ids
                if not node_sources:
                    continue
                inter = len(node_sources & sources_of_expected)
                union = len(node_sources)
                if union and (inter / union) >= self.similarity_threshold:
                    collided_nodes[previous_node.node_id] = inter / union

            if collided_nodes:
                best_node_id = max(collided_nodes.items(), key=lambda x: x[1])[0]
                best_node = next(n for n in hkt.nodes if n.node_id == best_node_id)
                best_node.word_ids.add(expected_word)
                best_node.source_ids.update(sources_of_expected)
                self.nodeDS[best_node.node_id].word_ids.add(expected_word)
                self.nodeDS[best_node.node_id].source_ids.update(sources_of_expected)
                self.remove_word_from_source_word_ds(expected_word, source_word_ds)
            else:
                other_node_id = len(self.nodeDS) + 1
                other_node = self.create_node(
                    other_node_id, hkt_id, source_word_ds, expected_word
                )
                hkt.nodes.append(other_node)
                self.nodeDS[other_node_id] = other_node
                self.remove_word_from_source_word_ds(expected_word, source_word_ds)

        # Refugee sources ---------------------------------------------------
        refugee_sources = {sw.source_id for sw in source_word_ds.values()}
        node_sources: Set[int] = set()
        for node in hkt.nodes:
            node_sources.update(node.source_ids)
        refugee_sources.difference_update(node_sources)

        if refugee_sources:
            ref_node_id = len(self.nodeDS) + 1
            ref_node = self.create_node_for_refuge_sources(
                ref_node_id, hkt_id, refugee_sources
            )
            hkt.nodes.append(ref_node)
            self.nodeDS[ref_node_id] = ref_node

        return hkt

    # Branch creation -----------------------------------------------------

    def create_branches(
        self, hkt: HKT, source_word_ds: "OrderedDict[int, SourceWord]"
    ) -> None:
        for node in hkt.nodes:
            if len(node.source_ids) > self.minimum_sources_branch:
                temp_source_word_ds: "OrderedDict[int, SourceWord]" = OrderedDict()

                if -1 not in node.word_ids:  # not a refuge node
                    for key, sw in source_word_ds.items():
                        if sw.word_id not in node.word_ids and sw.source_id in node.source_ids:
                            temp_source_word_ds[key] = deepcopy(sw)
                else:
                    for key, sw in source_word_ds.items():
                        if sw.source_id in node.source_ids:
                            temp_source_word_ds[key] = deepcopy(sw)

                self.update_word_no_of_sources(temp_source_word_ds)

                main_word_ds = OrderedDict(
                    sorted(
                        temp_source_word_ds.items(),
                        key=lambda item: (-item[1].word_no_of_sources, item[1].word_id),
                    )
                )

                if main_word_ds:
                    self.add_node_top_words(node, main_word_ds)
                    new_source_word_ds = OrderedDict(
                        (k, deepcopy(v)) for k, v in main_word_ds.items()
                    )
                    hkt_child = self.create_hkt(new_source_word_ds, node.node_id)
                    if hkt_child:
                        self.HKTDS[hkt_child.hkt_id] = hkt_child
                        if new_source_word_ds:
                            self.create_branches(hkt_child, main_word_ds)

    # Helper methods ------------------------------------------------------

    def add_node_top_words(
        self, node: Node, main_word_ds: "OrderedDict[int, SourceWord]"
    ) -> None:
        if -1 not in node.word_ids:
            for wid in node.word_ids:
                node.top_words.append(wid)
            for sw in main_word_ds.values():
                if sw.word_id not in node.top_words:
                    node.top_words.append(sw.word_id)
                if len(node.top_words) >= 10:
                    break

    def update_word_no_of_sources(
        self, temp_source_word_ds: "OrderedDict[int, SourceWord]"
    ) -> None:
        counts = Counter()
        for sw in temp_source_word_ds.values():
            counts[sw.word_id] += 1
        for sw in temp_source_word_ds.values():
            sw.word_no_of_sources = counts[sw.word_id]


__all__ = [
    "HKTAlgorithm",
    "HKT",
    "Node",
    "SourceWord",
]

