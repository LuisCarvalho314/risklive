"""© 2025 University of Aberdeen. All rights reserved"""

REPORT_PROMPT = (
    """As an expert risk analyst at the Nuclear Decommissioning Authority (NDA), analyze these news articles and provide a risk assessment:

First, provide:
BRIEF SUMMARY (2-3 sentences summarizing key points from all articles)

Then analyze:

1. RISK ASSESSMENT
- Severity (Critical/High/Medium/Low)
- Geographic Scope
- Time Sensitivity
- Potential Cascading Effects

2. KEY RISKS & IMPACTS
- Technical/Safety Risks
- Regulatory/Compliance Issues
- Environmental Concerns
- Impact on NDA Operations
- Industry-Wide Implications

3. ACTIONS & STAKEHOLDERS
- Immediate Actions (24-48 hrs)
- Short-term Actions (1 week)
- Key Stakeholders to Notify
- Required Resources

4. MONITORING
- Key Metrics to Track
- Warning Indicators
- Reporting Requirements

Provide specific, actionable recommendations with clear timelines. Flag any urgent regulatory reporting needs.

Give only the report, no extra content. Think step by step. 

[News Articles Content Below]
"""
)

REPORT_MERGE_PROMPT = (
    """As an expert risk analyst at the Nuclear Decommissioning Authority (NDA), merge these partial topic reports into a single consolidated risk assessment.

Your task:
- Combine overlapping findings into one coherent final report.
- Remove duplicated points.
- Resolve minor wording differences by choosing the clearest, most actionable phrasing.
- Preserve concrete risks, actions, timelines, and stakeholders that appear across the partial reports.
- Produce one final keyword field that best represents the combined topic.

Give only the merged report, no extra content. Think step by step.

[Partial Topic Reports Below]
"""
)
