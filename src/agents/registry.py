"""© 2025 University of Aberdeen. All rights reserved"""

from agents.extraction import reset_extraction_agent
from agents.report import reset_report_agent


def reset_all_agents() -> None:
    reset_extraction_agent()
    reset_report_agent()
