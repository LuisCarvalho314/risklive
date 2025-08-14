from __future__ import annotations

from collections import defaultdict

import streamlit as st
import pandas as pd
import plotly.express as px

from .data_helper import DataHelper
from .hkt_algorithm import HKTAlgorithm


st.set_page_config(layout="wide", page_title="NewHKT Streamlit")
st.title("NewHKT – Streamlit Edition")

st.sidebar.header("Parameters")
num_of_ctg = st.sidebar.number_input(
    "Number of categories per experiment", min_value=1, value=1, step=1
)
min_threshold = st.sidebar.number_input(
    "Minimum threshold against max word count", min_value=0.0, value=0.0
)
similarity_threshold = st.sidebar.number_input(
    "Similarity threshold", min_value=0.0, max_value=1.0, value=0.5
)
min_sources_important = st.sidebar.number_input(
    "Min sources for important words", min_value=1, value=1
)
min_sources_branch = st.sidebar.number_input(
    "Min sources to create branch for node", min_value=1, value=1
)

load = st.sidebar.button("Load Data")

if load:
    helper = DataHelper()
    sources = helper.load_sources()
    algo = HKTAlgorithm(
        minimum_threshold_against_max_word_count=min_threshold,
        similarity_threshold=similarity_threshold,
        minimum_sources_important=min_sources_important,
        minimum_sources_branch=min_sources_branch,
    )
    hkts, stats = algo.build(sources)

    children_by_parent = defaultdict(list)
    for h in hkts.values():
        if h.parent_node_id:
            children_by_parent[h.parent_node_id].append(h)

    def build_treemap_data(hkts, algo):
        data = [{"id": "root", "parent": "", "label": "", "value": 0}]

        def add_nodes(hkt, parent_id):
            for node in hkt.nodes:
                node_id = f"node-{node.node_id}"
                names = [algo.wordDS.get(wid, "<refuge>") for wid in node.word_ids if wid > 0]
                label = " ".join(names) if names else "<refuge>"
                data.append(
                    {
                        "id": node_id,
                        "parent": parent_id,
                        "label": label,
                        "value": len(node.source_ids),
                    }
                )
                for child in children_by_parent.get(node.node_id, []):
                    add_nodes(child, node_id)

        for root_hkt in hkts.values():
            if root_hkt.parent_node_id == 0:
                add_nodes(root_hkt, "root")

        return data

    st.success("Analysis completed")

    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("Sources", stats["number_loaded"])
    with col2:
        st.metric("HKTs", stats["number_of_hkts"])
    with col3:
        st.metric("Nodes", stats["number_of_nodes"])

    st.caption(
        f"Words: {stats['number_of_words']} – Source/Word relations: {stats['update_source_word_relation_db']}"
    )

    st.subheader("Tree View")

    def build_tree_lines(hkt, depth=0):
        lines = []
        for node in hkt.nodes:
            names = [algo.wordDS.get(wid, "<refuge>") for wid in node.word_ids if wid > 0]
            label = " ".join(names) if names else "<refuge>"
            lines.append(f"{'  ' * depth}- {label} (#{len(node.source_ids)} sources)")
            for child in children_by_parent.get(node.node_id, []):
                lines.extend(build_tree_lines(child, depth + 1))
        return lines

    lines = []
    for root_hkt in hkts.values():
        if root_hkt.parent_node_id == 0:
            lines.extend(build_tree_lines(root_hkt))
    if lines:
        st.markdown("\n".join(lines))
    else:
        st.info("No data to display")

    st.subheader("Treemap")
    treemap_data = build_treemap_data(hkts, algo)

    if treemap_data:
        df = pd.DataFrame(treemap_data)
        fig = px.treemap(
            df, ids="id", names="label", parents="parent", values="value"
        )
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.info("No data to display")
else:
    st.info("Use the controls in the sidebar to load and analyse the CSV data.")
