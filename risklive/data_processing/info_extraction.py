"""© 2025 University of Aberdeen. All rights reserved"""
import os
import logging
import pandas as pd
from ..config import PROMPTS
from datetime import datetime
from .lm import initialize_client, api_call, load_prompt_template, format_prompt

def extract_information(client, news_content, prompt_type='EXTRACTION_PROMPT'):
    try:
        prompt_template = PROMPTS[prompt_type]        
        user_prompt = format_prompt(prompt_template, news_content=news_content)
        model = "gpt-4o"
        response, price, token_usage = api_call(client, model, user_prompt=user_prompt)
        return response, price, token_usage
    except Exception as e:
        logging.error(f"Failed to extract information: {e}")
        return None, None, None  
    

def parse_json_info(response):
    if response is None:
        return {
            'RelevantKeywords': [],
            'ShortSummary': '',
            'Relevance': '',
            'RelevanceReason': '',
            'AlertFlag': '',
            'AlertReason': '',
            'NewsCategory': ''
        }
    relevant_keywords = response.get('RelevantKeywords', [])
    if isinstance(relevant_keywords, list):
        relevant_keywords = ', '.join(relevant_keywords)
    elif not isinstance(relevant_keywords, str):
        relevant_keywords = relevant_keywords

    return {
        'RelevantKeywords': relevant_keywords,
        'ShortSummary': response.get('ShortSummary', ''),
        'Relevance': response.get('Relevance', ''),
        'RelevanceReason': response.get('RelevanceReason', ''),
        'AlertFlag': response.get('AlertFlag', ''),
        'AlertReason': response.get('AlertReason', ''),
        'NewsCategory': response.get('NewsCategory', '')
    }
    
    
def extract_tokens(token_usage):
    return {
        'PromptTokens': token_usage.prompt_tokens,
        'CompletionTokens': token_usage.completion_tokens,
        'TotalTokens': token_usage.total_tokens
    }

def get_delta(full_df, df):
    return df[~df['URL'].isin(full_df['URL'])]

def process_df(df, prompt_type='EXTRACTION_PROMPT', save_folder=None):
    if os.path.exists(f"{save_folder}/news_data_with_llm_info.csv"):
        full_df = pd.read_csv(f"{save_folder}/news_data_with_llm_info.csv")
        df = get_delta(full_df, df)
        logging.info("Loaded existing DataFrame")
    else:
        os.makedirs(save_folder, exist_ok=True)
        full_df = pd.DataFrame()
    
    logging.info("Starting to process DataFrame")
    client = initialize_client()
    responses = []
    prices = []
    token_usages = []
    relevant_keywords_list = []
    short_summaries = []
    relevances = []
    relevance_reasons = []
    alert_flags = []
    alert_reasons = []
    news_categories = []
    
    prompt_tokens = []
    completion_tokens = []
    total_tokens = []
    api_timestamp = []

    # for index, row in df.iterrows():
    # print(list(full_df.iterrows()))
    for index, row in df.iterrows():
        title = row['Title']
        article_content = row['Description']
        input_text = f"{title}. {article_content}"
        curr_timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        response, price, token_usage = extract_information(client, input_text, prompt_type)
        print(response)
        if response is not None:
        
            parsed_info = parse_json_info(response)
            responses.append(response)
            prices.append(price)
            token_usages.append(token_usage)
            relevant_keywords_list.append(parsed_info['RelevantKeywords'])
            short_summaries.append(parsed_info['ShortSummary'])
            relevances.append(parsed_info['Relevance'])
            relevance_reasons.append(parsed_info['RelevanceReason'])
            alert_flags.append(parsed_info['AlertFlag'])
            alert_reasons.append(parsed_info['AlertReason'])
            news_categories.append(parsed_info['NewsCategory'])
            
            token_usage_dict = extract_tokens(token_usage)
            prompt_tokens.append(token_usage_dict['PromptTokens'])
            completion_tokens.append(token_usage_dict['CompletionTokens'])
            total_tokens.append(token_usage_dict['TotalTokens'])
            
            api_timestamp.append(curr_timestamp)
            
            logging.info(f"Processed row {index + 1}/{len(df)}")
        else:
            logging.error(f"Failed to process row {index + 1}/{len(df)}")
            responses.append(None)
            prices.append(None)
            token_usages.append(None)
            relevant_keywords_list.append(None)
            short_summaries.append(None)
            relevances.append(None)
            relevance_reasons.append(None)
            alert_flags.append(None)
            alert_reasons.append(None)
            news_categories.append(None)
            
            prompt_tokens.append(None)
            completion_tokens.append(None)
            total_tokens.append(None)
            api_timestamp.append(None)
            
    df['LLM_Response'] = responses
    df['LLM_Price'] = prices
    df['LLM_Token_Usage'] = token_usages
    df['PromptTokens'] = prompt_tokens
    df['CompletionTokens'] = completion_tokens
    df['TotalTokens'] = total_tokens
    df['RelevantKeywords'] = relevant_keywords_list
    df['ShortSummary'] = short_summaries
    df['Relevance'] = relevances
    df['RelevanceReason'] = relevance_reasons
    df['AlertFlag'] = alert_flags
    df['AlertReason'] = alert_reasons
    df['NewsCategory'] = news_categories
    df['API_Timestamp'] = api_timestamp
    
    if save_folder is not None:
        df = pd.concat([full_df, df])
        df.to_csv(f"{save_folder}/news_data_with_llm_info.csv", index=False)
    return df

