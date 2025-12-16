"""© 2025 University of Aberdeen. All rights reserved"""
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
    # with open(os.path.join(IMG_DIR, '3d_time_plot.pkl'), 'rb') as f:
    #     fig1 = pickle.load(f)
    
    with open(os.path.join(IMG_DIR, 'treemap.pkl'), 'rb') as f:
        fig2 = pickle.load(f)
    
    json_files = ['topics.json', 'barchart.json', 'topics_over_time.json', 'documents.json', 'hierarchy.json']
    # json_figures = [fig1]
    json_figures = []
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

        # Handle no data / empty dataframe
        if df is None or df.empty:
            st.warning("No high risk reports available.")
        else:
            # Get list of topics safely
            topics = df["keyword"].dropna().unique().tolist()

            if not topics:
                st.warning("No topics available.")
            else:
                keyword = st.selectbox("Select Topic", topics, key="topic_selector")

                # Filter response safely
                response_series = df.loc[df["keyword"] == keyword, "response"]

                if response_series.empty:
                    st.warning("No response found for the selected topic.")
                else:
                    response = response_series.iloc[0]
                    st.write(response)
    with st.expander("Topic Tree"):
        st.text(tree)
        
    # st.plotly_chart(json_figures[6], use_container_width=True)
    st.plotly_chart(json_figures[5], use_container_width=True)

    st.plotly_chart(json_figures[0], use_container_width=True)
    st.plotly_chart(json_figures[1], use_container_width=True)
    st.plotly_chart(json_figures[2], use_container_width=True)
    st.plotly_chart(json_figures[3], use_container_width=True)
    st.plotly_chart(json_figures[4], use_container_width=True)
    # st.plotly_chart(json_figures[5], use_container_width=True)

if __name__ == '__main__':
    with streamlit_analytics.track():
        main()