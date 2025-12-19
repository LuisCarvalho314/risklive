from risklive.server import tasks


tasks.save_regular_news(hours=168)
tasks.llm_info_extraction()
tasks.compute_save_topic_model()
tasks.generate_report()