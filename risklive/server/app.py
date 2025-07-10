from flask import Flask, jsonify
from apscheduler.schedulers.background import BackgroundScheduler
from .tasks import save_trending_news, save_regular_news, llm_info_extraction, compute_save_topic_model, generate_report
from .data_maintenance import clean_old_data
from ..config import CLEANUP_DAYS_TO_KEEP
import logging
import os
from ..utils.logging_config import setup_logging

logger = setup_logging(__name__)

app = Flask(__name__)

def process_news_data():
    logger.info("Starting news data processing")
    try:
        llm_info_extraction()
        compute_save_topic_model()
        logger.info("News data processing completed successfully")
    except Exception as e:
        logger.error(f"Error in news data processing: {str(e)}", exc_info=True)

def hourly_task():
    logger.info("Starting hourly task")
    try:
        save_regular_news()
        clean_old_data()
        process_news_data()
        logger.info("Hourly task completed successfully")
    except Exception as e:
        logger.error(f"Error in hourly task: {str(e)}", exc_info=True)

def daily_task():
    logger.info("Starting daily task")
    try:
        save_trending_news()
        save_regular_news()
        clean_old_data()
        process_news_data()
        logger.info("Daily task completed successfully")
    except Exception as e:
        logger.error(f"Error in daily task: {str(e)}", exc_info=True)

def start_scheduler():
    logger.info("Starting scheduler")
    scheduler = BackgroundScheduler()
    scheduler.add_job(hourly_task, 'cron', hour='0-7,9-23')    
    scheduler.add_job(daily_task, 'cron', hour=7)
    scheduler.add_job(generate_report, 'cron', hour=7, minute=30)
    scheduler.add_job(clean_old_data, 'cron', hour=6, minute=30, args=[CLEANUP_DAYS_TO_KEEP])
    scheduler.start()
    logger.info("Scheduler started successfully")

@app.route('/')
def home():
    logger.info("Home route accessed")
    return jsonify({"status": "Server is running"})

@app.route('/trigger/regular')
def trigger_regular():
    logger.info("Manual trigger for regular news initiated")
    save_regular_news()
    clean_old_data()
    process_news_data()
    logger.info("Manual regular news processing completed")
    return jsonify({"status": "Regular news aggregation and processing triggered"})

@app.route('/trigger/trending')
def trigger_trending():
    logger.info("Manual trigger for trending news initiated")
    save_trending_news()
    save_regular_news()
    clean_old_data()
    process_news_data()
    logger.info("Manual trending news processing completed")
    return jsonify({"status": "Trending news aggregation and processing triggered"})

@app.route('/trigger/cleanup')
def trigger_cleanup():
    logger.info("Manual trigger for data cleanup initiated")
    try:
        removed_count = clean_old_data(CLEANUP_DAYS_TO_KEEP)
        logger.info(f"Data cleanup completed. Removed {removed_count} records.")
        return jsonify({"status": "Data cleanup and backup triggered", "removed_count": removed_count})
    except Exception as e:
        logger.error(f"Error during manual data cleanup: {str(e)}", exc_info=True)
        return jsonify({"status": "Error during data cleanup", "error": str(e)}), 500

@app.route('/trigger/generate_report')
def trigger_generate_report():
    logger.info("Manual trigger for report generation initiated")
    generate_report()
    logger.info("Manual report generation completed")
    return jsonify({"status": "Report generation triggered"})

@app.route('/health')
def health():
    return {'status': 'healthy'}, 200

def main():
    logger.info("Starting the application")
    start_scheduler()
    app.run(host='0.0.0.0', port=5000)
    logger.info("Application stopped")

if __name__ == '__main__':
    main()