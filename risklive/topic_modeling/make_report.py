import logging
import pandas as pd
from collections import Counter
from ..config import SAVE_DIR, PROMPTS
from .lm import initialize_client, api_call, load_prompt_template, format_prompt

def extract_information(client, user_prompt, prompt_type='EXTRACTION_PROMPT'):
    try:
        model = "gpt4o"
        response, price, token_usage = api_call(client, model, user_prompt=user_prompt)
        return response, price, token_usage
    except Exception as e:
        logging.error(f"Failed to extract information: {e}")
        return None, None, None  
    
def get_df():
    data_dir = SAVE_DIR["CSV_DATA_DIR"]
    file_path = f"{data_dir}/df_with_response_and_topics.csv"
    df = pd.read_csv(file_path)
    df = df[df["AlertFlag"] == "Red"]
    return df

def get_keywords_by_frequency(keywords_list):
    counts = Counter(keywords_list)
    sorted_counts = sorted(counts.items(), key=lambda x: x[1], reverse=True)
    return ", ".join([keyword for keyword, _ in sorted_counts[:5]])

def get_report():
    client = initialize_client()
    df = get_df()
    df_report = pd.DataFrame(columns=["topic", "keyword", "input_prompt", "response", "price", "token_usage"])
    prompt = PROMPTS["REPORT_PROMPT"]
    df_topic = df.groupby("topic")
    df_dict = {}
    for topic, group in df_topic:
        input_news = ""
        keywords = []
        for index, row in group.iterrows():
            input_news = input_news + row["ShortSummary"] + "\n"
            keywords = keywords + [item.strip() for item in row["RelevantKeywords"].split(",")]
        top_keywords = get_keywords_by_frequency(keywords)
        input_news = f"{prompt}\n{input_news}"
        response, price, token_usage = extract_information(client, input_news, prompt_type='REPORT_PROMPT')
        df_dict["topic"] = topic
        df_dict["keyword"] = top_keywords
        df_dict["input_prompt"] = input_news
        df_dict["response"] = response
        df_dict["price"] = price
        df_dict["token_usage"] = token_usage
        df_report = pd.concat([df_report, pd.DataFrame.from_dict(df_dict)], ignore_index=True)
    df_report.to_csv(f"{SAVE_DIR['CSV_DATA_DIR']}/df_report.csv", index=False)

