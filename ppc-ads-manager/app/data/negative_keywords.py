"""Negative keywords applied to every estate-planning law firm campaign.

These filter out the traffic that reliably wastes budget in this vertical:
DIY/template shoppers, students/researchers, job seekers, and people looking
for free advice rather than a paid consultation.
"""

CAMPAIGN_LEVEL_NEGATIVES: list[str] = [
    "free", "diy", "do it yourself", "template", "form", "forms", "pdf",
    "sample", "how to write", "definition", "meaning", "what is",
    "job", "jobs", "salary", "hiring", "internship", "resume",
    "course", "class", "degree", "school", "certification",
    "wikipedia", "reddit",
    "software", "app",
]
