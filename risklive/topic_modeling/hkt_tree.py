from __future__ import annotations

import json
import os
from typing import Dict, Any

from ..config import SAVE_DIR
from ..HKT.data_helper import DataHelper
from ..HKT.hkt_algorithm import HKTAlgorithm


def compute_hkt_tree(
    csv_path: str | None = None,
    save_path: str | None = None,
    **algo_kwargs: Any,
) -> Dict[str, Any]:
    """Generate a Hierarchical Knowledge Tree from the main dataset.

    Parameters
    ----------
    csv_path:
        Optional path to the CSV file. Defaults to the main application's
        ``news_data_with_llm_info.csv``.
    save_path:
        Optional path where the resulting tree will be stored as JSON. Defaults
        to ``hkt_tree.json`` inside the application's ``CSV_DATA_DIR``.
    **algo_kwargs:
        Additional keyword arguments passed to :class:`HKTAlgorithm`.

    Returns
    -------
    dict
        Dictionary containing the serialized HKTs and statistics.
    """

    helper = DataHelper(csv_path)
    sources = helper.load_sources()
    algo = HKTAlgorithm(**algo_kwargs)
    hkts, stats = algo.build(sources)

    def serialize_hkt(hkt):
        return {
            "hkt_id": hkt.hkt_id,
            "parent_node_id": hkt.parent_node_id,
            "nodes": [
                {
                    "node_id": n.node_id,
                    "word_ids": list(n.word_ids),
                    "source_ids": list(n.source_ids),
                    "top_words": n.top_words,
                }
                for n in hkt.nodes
            ],
        }

    payload = {
        "stats": stats,
        "hkts": {hid: serialize_hkt(h) for hid, h in hkts.items()},
        "word_dict": algo.wordDS,
    }

    if save_path is None:
        save_path = os.path.join(SAVE_DIR["CSV_DATA_DIR"], "hkt_tree.json")
    with open(save_path, "w") as f:
        json.dump(payload, f, indent=2)

    return payload

__all__ = ["compute_hkt_tree"]
