import os
import openai
import logging
import json
from ..config import OPENAI_API_BASE, OPENAI_API_KEY, OPENAI_API_VERSION
from tenacity import retry, stop_after_attempt, wait_fixed, retry_if_exception_type

def initialize_client():
    try:
        client = openai.AzureOpenAI(
            api_key=OPENAI_API_KEY,
            api_version=OPENAI_API_VERSION,
            azure_endpoint=OPENAI_API_BASE
        )
        logging.info("Client initialized successfully")
        return client
    except Exception as e:
        logging.error(f"Failed to initialize client: {e}")
        raise

def pricing(token_usage, model):
    if model=="openai_chat":
        price = (token_usage.prompt_tokens * 0.003 + token_usage.completion_tokens * 0.0004) / 1000
    elif model=="gpt4":
        price = (token_usage.prompt_tokens * 0.048 + token_usage.completion_tokens * 0.096) / 1000
    elif model=="gpt4o":
        price = (token_usage.prompt_tokens * 0.004 + token_usage.completion_tokens * 0.0119) / 1000
    return price

def load_prompt_template(file_path):
    with open(file_path, 'r') as file:
        prompt_template = file.read()
    return prompt_template

def format_prompt(prompt_template, **kwargs):
    return prompt_template.format(**kwargs)

def is_rate_limit_error(exception):
    return isinstance(exception, Exception) and '429' in str(exception)

@retry(
    retry=retry_if_exception_type(Exception),
    stop=stop_after_attempt(2),
    wait=wait_fixed(60),
    retry_error_callback=lambda retry_state: (None, None, None)
)
def api_call(client, model, user_prompt, system_prompt="You are a useful assistant.", temperature=0, max_tokens=1000):
    try:
        response = client.chat.completions.create(
            model=model,
            temperature=float(temperature),
            max_tokens=int(max_tokens),
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ]
        )
        response_output = response.choices[0].message.content
        token_usage = response.usage
        price = pricing(token_usage, model)
        
        logging.info("API call successful")
        logging.info(f"Price: {price} USD")
        logging.info(f"Response: {response_output}")
        
        return response_output, price, token_usage
    except Exception as e:
        if is_rate_limit_error(e):
            logging.warning(f"Rate limit exceeded. Retrying in 60 seconds: {e}")
            raise
        else:
            logging.error(f"API call failed: {e}")
            return None, None, None
