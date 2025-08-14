import os
import pickle
import json
from collections import defaultdict

import pandas as pd
import plotly.express as px
import plotly.io as pio
import streamlit as st
import streamlit_analytics2 as streamlit_analytics
st.set_page_config(page_title="Risk Live", page_icon=':star', layout='wide')

margins_css = """
<style>
.appview-container .main .block-container{{
        padding-left: 0rem;
        }}
</style>
"""

st.markdown(margins_css, unsafe_allow_html=True)
IMG_DIR = "./results/images"
report_path = "./results/data/df_report.csv"
hkt_path = "./results/data/hkt_tree.json"

def get_figures():
    with open(os.path.join(IMG_DIR, '3d_time_plot.pkl'), 'rb') as f:
        fig1 = pickle.load(f)
    
    with open(os.path.join(IMG_DIR, 'treemap.pkl'), 'rb') as f:
        fig2 = pickle.load(f)
    
    json_files = ['topics.json', 'barchart.json', 'topics_over_time.json', 'documents.json', 'hierarchy.json']
    json_figures = [fig1]
    for file in json_files:
        with open(os.path.join(IMG_DIR, file), 'r') as f:
            fig = pio.from_json(f.read())
            json_figures.append(fig)
    json_figures.append(fig2)
    tree_path = os.path.join(IMG_DIR, 'topic_tree.txt')
    with open(tree_path, 'r') as f:
        tree = f.read()
    return json_figures, tree


def get_hkt_output():
    if not os.path.exists(hkt_path):
        return None
    with open(hkt_path, 'r') as f:
        data = json.load(f)
    word_dict = {int(k): v for k, v in data.get('word_dict', {}).items()}
    hkts = data.get('hkts', {})
    stats = data.get('stats', {})

    children_by_parent = defaultdict(list)
    for h in hkts.values():
        pid = h.get('parent_node_id')
        if pid:
            children_by_parent[pid].append(h)

    def build_tree_lines(hkt, depth=0):
        lines = []
        for node in hkt['nodes']:
            names = [word_dict.get(wid, '<refuge>') for wid in node['word_ids'] if wid > 0]
            label = ' '.join(names) if names else '<refuge>'
            lines.append(f"{'  '*depth}- {label} (#{len(node['source_ids'])} sources)")
            for child in children_by_parent.get(node['node_id'], []):
                lines.extend(build_tree_lines(child, depth + 1))
        return lines

    lines = []
    for root_hkt in hkts.values():
        if root_hkt.get('parent_node_id') == 0:
            lines.extend(build_tree_lines(root_hkt))

    treemap_data = [{"id": "root", "parent": "", "label": "", "value": 0}]

    def add_nodes(hkt, parent_id):
        for node in hkt['nodes']:
            node_id = f"node-{node['node_id']}"
            names = [word_dict.get(wid, '<refuge>') for wid in node['word_ids'] if wid > 0]
            label = ' '.join(names) if names else '<refuge>'
            treemap_data.append({
                'id': node_id,
                'parent': parent_id,
                'label': label,
                'value': len(node['source_ids']),
            })
            for child in children_by_parent.get(node['node_id'], []):
                add_nodes(child, node_id)

    for root_hkt in hkts.values():
        if root_hkt.get('parent_node_id') == 0:
            add_nodes(root_hkt, 'root')

    df = pd.DataFrame(treemap_data)
    fig = px.treemap(df, ids='id', names='label', parents='parent', values='value')
    return stats, "\n".join(lines), fig

def get_report():
    df = pd.read_csv(report_path)
    df = df[['keyword', 'response']]
    return df

def main():
    st.title("Risk Live: Topic Modeling")
    st.write("This app applies topic modeling on news articles from the past 72hours and visualizes them. There is a seperate tab for summary and alerts")

    json_figures, tree = get_figures()
    with st.expander("Daily Report"):
        df = get_report()
        keyword = st.selectbox("Select Topic", df['keyword'].unique(), key="topic_selector")
        response = df[df['keyword'] == keyword]['response'].values[0]
        st.write(response)
    with st.expander("Topic Tree"):
        st.text(tree)

    with st.expander("Hierarchical Knowledge Tree"):
        hkt_results = get_hkt_output()
        if not hkt_results:
            st.info("No HKT data available")
        else:
            stats, tree_lines, hkt_fig = hkt_results
            col1, col2, col3 = st.columns(3)
            col1.metric("Sources", stats.get("number_loaded"))
            col2.metric("HKTs", stats.get("number_of_hkts"))
            col3.metric("Nodes", stats.get("number_of_nodes"))
            st.caption(
                f"Words: {stats.get('number_of_words')} – Source/Word relations: {stats.get('update_source_word_relation_db')}"
            )
            st.text(tree_lines)
            st.plotly_chart(hkt_fig, use_container_width=True)
        
    st.plotly_chart(json_figures[6], use_container_width=True)
    
    st.plotly_chart(json_figures[0], use_container_width=True)
    st.plotly_chart(json_figures[1], use_container_width=True)
    st.plotly_chart(json_figures[2], use_container_width=True)
    st.plotly_chart(json_figures[3], use_container_width=True)
    st.plotly_chart(json_figures[4], use_container_width=True)
    st.plotly_chart(json_figures[5], use_container_width=True)

if __name__ == '__main__':
    with streamlit_analytics.track():
        main()