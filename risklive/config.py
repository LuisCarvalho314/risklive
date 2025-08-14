import os
import yaml
from dotenv import load_dotenv
from pathlib import Path
ROOT_DIR = Path(__file__).resolve().parent.parent

def load_config(file_path=None):
    if not file_path:
        file_path = ROOT_DIR / 'config' / 'config.yml'
        
    with open(file_path, 'r') as file:
        config = yaml.safe_load(file)
    return config

def load_prompts(prompt_paths):
    prompts = {}
    for key, path in prompt_paths.items():
        path = ROOT_DIR / path
        with open(path, 'r') as file:
            prompts[key] = file.read()
    return prompts

def save_directory(save_dir):
    SAVE_DIR = {}
    for key, path in save_dir.items():
        SAVE_DIR[key] = ROOT_DIR / path
        SAVE_DIR[key].parent.mkdir(parents=True, exist_ok=True)
    return SAVE_DIR

load_dotenv(ROOT_DIR / '.env')
CONFIG = load_config()

OPENAI_API_TYPE = "azure"
BING_API_KEY=os.getenv("BING_API_KEY")
SERP_API_KEY=os.getenv("SERP_API_KEY")
OPENAI_API_BASE=os.getenv("OPENAI_API_BASE")
OPENAI_API_KEY=os.getenv("OPENAI_API_KEY")
OPENAI_API_VERSION = os.getenv("OPENAI_API_VERSION")

CATEGORIES = CONFIG['CATEGORIES']
QUERIES = CONFIG['QUERIES']
PROMPT_PATHS = CONFIG['PROMPT_PATHS']
PROMPTS = load_prompts(PROMPT_PATHS)
SAVE_DIR = save_directory(CONFIG['SAVE_DIR'])
CLEANUP_DAYS_TO_KEEP = CONFIG['CLEANUP_DAYS_TO_KEEP']