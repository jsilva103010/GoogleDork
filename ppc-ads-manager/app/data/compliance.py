"""Attorney-advertising compliance checks.

State bar rules vary, but a few restrictions are close to universal (ABA
Model Rule 7.1 and its state analogues): no guarantees or promises about
outcomes, no unsubstantiated superlative claims ("best", "#1"), and no
specific case results without the required disclaimers. This module is a
blunt, deterministic safety net that runs on every AI-generated ad — it
does not replace review by the firm's bar counsel.
"""

import re

REQUIRED_DISCLAIMER = "Attorney Advertising. Prior results do not guarantee a similar outcome."

# Phrases that create outcome guarantees or unsubstantiated superlative claims.
BANNED_PATTERNS: list[re.Pattern] = [
    re.compile(r"\bguarantee(d)?\b", re.I),
    re.compile(r"\b100%\s*(success|win|guaranteed)\b", re.I),
    re.compile(r"\bwe (will |always )?win\b", re.I),
    re.compile(r"\bbest (lawyer|attorney|law firm)\b", re.I),
    re.compile(r"#\s?1\s*(lawyer|attorney|law firm|rated)\b", re.I),
    re.compile(r"\bno win no fee\b", re.I),  # not applicable to flat-fee estate planning work
    re.compile(r"\bfree consultation guaranteed\b", re.I),
]


def scan_text(text: str) -> list[str]:
    """Return a list of human-readable violation descriptions found in text."""
    hits = []
    for pattern in BANNED_PATTERNS:
        if pattern.search(text):
            hits.append(f"Flagged phrase matching /{pattern.pattern}/ in: {text!r}")
    return hits


def review_campaign_plan(plan) -> list[str]:
    """Scan every headline/description/callout/sitelink in a CampaignPlan.

    Returns a list of violation notes. Does not mutate the plan — flagged
    lines are dropped by the caller (see campaign_builder.sanitize_plan).
    """
    notes: list[str] = []
    for callout in plan.callouts:
        notes.extend(scan_text(callout))
    for sitelink in plan.sitelinks:
        notes.extend(scan_text(sitelink.text))
        notes.extend(scan_text(sitelink.description1))
        notes.extend(scan_text(sitelink.description2))
    for ad_group in plan.ad_groups:
        for headline in ad_group.ad.headlines:
            notes.extend(scan_text(headline))
        for description in ad_group.ad.descriptions:
            notes.extend(scan_text(description))
    return notes
