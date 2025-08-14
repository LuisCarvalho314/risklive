import os
import pandas as pd
from datetime import datetime
from ..data_extraction import aggregate_regular_news, aggregate_trending_news
from ..data_processing import process_df
from ..topic_modeling import compute_topic_modeling, get_report, compute_hkt_tree
import logging
from ..config import SAVE_DIR

def save_trending_news():
    try:
        logging.info("Starting aggregation of trending news data")
        _ = aggregate_trending_news(save_folder=SAVE_DIR["CSV_DATA_DIR"])
        logging.info("Trending news data aggregation completed successfully")
    except Exception as e:
        logging.error(f"Error during aggregation of trending news data: {e}")

def save_regular_news():
    try:
        logging.info("Starting aggregation of regular news data")
        _ = aggregate_regular_news(save_folder=SAVE_DIR["CSV_DATA_DIR"])
        logging.info("Regular news data aggregation completed successfully")
    except Exception as e:
        logging.error(f"Error during aggregation of regular news data: {e}")
        
def llm_info_extraction():
    try:
        logging.info("Starting extraction of information using LLM")
        full_df = pd.read_csv(os.path.join(SAVE_DIR['CSV_DATA_DIR'], 'news_data.csv'))
        _ = process_df(full_df, save_folder = SAVE_DIR['CSV_DATA_DIR'])
        logging.info("Information extraction completed successfully")
    except Exception as e:
        logging.error(f"Error during information extraction: {e}")
        
def compute_save_topic_model():
    try:
        logging.info("Starting topic modeling")
        df = pd.read_csv(os.path.join(SAVE_DIR['CSV_DATA_DIR'], 'news_data_with_llm_info.csv'))
        _ = compute_topic_modeling(df)
        compute_hkt_tree()
        logging.info("Topic modeling completed successfully")
    except Exception as e:
        logging.error(f"Error during topic modeling: {e}")

def generate_report():
    try:
        logging.info("Starting generation of report")
        _ = get_report()
        logging.info("Report generation completed successfully")
    except Exception as e:
        logging.error(f"Error during report generation: {e}")