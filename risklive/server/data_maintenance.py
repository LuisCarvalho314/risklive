import os
import pandas as pd
from datetime import datetime, timedelta
import logging
import pytz
from ..config import SAVE_DIR
from ..utils.logging_config import setup_logging

logger = setup_logging(__name__)

def clean_old_data(days_to_keep=3):
    try:
        # cutoff_date = datetime.now() - timedelta(days=days_to_keep)
        cutoff_date = datetime.now(pytz.UTC) - timedelta(days=days_to_keep)
        csv_dir = SAVE_DIR['CSV_DATA_DIR']
        backup_dir = SAVE_DIR['CSV_DATA_BACKUP_DIR']
        os.makedirs(backup_dir, exist_ok=True)
        
        total_removed = 0
        for filename in os.listdir(csv_dir):
            if filename.endswith('.csv') and filename != 'df_report.csv':
                logger.info(f"Cleaning up {filename}")
                file_path = os.path.join(csv_dir, filename)
                backup_filename = f"{os.path.splitext(filename)[0]}.csv"
                backup_file_path = os.path.join(backup_dir, backup_filename)
                df = pd.read_csv(file_path)
                if len(df) > 0:
                    try:
                        df['Timestamp'] = pd.to_datetime(df['Timestamp'], format='ISO8601').dt.tz_convert('UTC')
                    except:
                        df['Timestamp'] = pd.to_datetime(df['Timestamp']).dt.tz_convert('UTC')
                                        
                    df_new = df[df['Timestamp'] >= cutoff_date]
                    df_to_backup = df[df['Timestamp'] < cutoff_date]
                    curr_removed = len(df_to_backup)    
                    total_removed += len(df_to_backup)
                    df_new.to_csv(file_path, index=False)
                    if os.path.exists(backup_file_path):
                        backup_df = pd.read_csv(backup_file_path)
                        df_to_backup = pd.concat([backup_df, df_to_backup]).drop_duplicates()
                    df_to_backup.to_csv(backup_file_path, index=False)
                    logger.info(f"Cleanup completed for {filename}. Records removed: {curr_removed}")
                    
        logger.info(f"Cleanup completed. Total records removed: {total_removed}")
        return total_removed
    except Exception as e:
        logger.error(f"Error during data cleanup: {str(e)}")
        raise