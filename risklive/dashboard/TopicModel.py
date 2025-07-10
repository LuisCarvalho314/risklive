import os
import pickle
import pandas as pd
import streamlit as st
import plotly.io as pio
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