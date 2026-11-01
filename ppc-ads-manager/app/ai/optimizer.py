"""Bid/budget/pause rules engine, plus an optional Claude-generated strategic
narrative layered on top.

The rules engine is deterministic and requires no API key — it's what makes
this an "automated" ads manager rather than just an AI copywriting tool. The
AI narrative is a value-add summary for the human reviewing recommendations;
it never itself triggers an action.
"""

import time

from app import store
from app.ai.client import AIUnavailableError, get_client
from app.config import CLAUDE_MODEL
from app.models import Campaign, OptimizationAction

# Tunables for the rules engine. Kept as module constants rather than a config
# file since they're strategy decisions, not deployment config.
MIN_CLICKS_BEFORE_PAUSE_JUDGEMENT = 15
CPA_OVER_TARGET_TO_PAUSE = 2.0     # pause a keyword once its CPA is 2x target with no sign of improving
CPA_OVER_TARGET_TO_LOWER_BID = 1.3
CPA_UNDER_TARGET_TO_RAISE_BID = 0.6
BID_STEP = 0.15                    # +/-15% per adjustment, so changes compound gradually


def run_rules_engine(campaign_id: str) -> list[OptimizationAction]:
    campaign = store.get("campaigns", campaign_id)
    firm = store.get("firms", campaign.firm_id)
    target_cpa = firm.target_cpa

    actions: list[OptimizationAction] = []
    ad_groups = store.list_all("ad_groups", campaign_id=campaign_id)

    for ad_group in ad_groups:
        keywords = store.list_all("keywords", ad_group_id=ad_group.id)
        for keyword in keywords:
            if keyword.status != "active" or keyword.clicks < MIN_CLICKS_BEFORE_PAUSE_JUDGEMENT:
                continue

            cpa = (keyword.cost / keyword.conversions) if keyword.conversions else None

            if keyword.conversions == 0 and keyword.cost >= target_cpa * CPA_OVER_TARGET_TO_PAUSE:
                actions.append(OptimizationAction(
                    campaign_id=campaign_id, action_type="pause_keyword",
                    target=keyword.text, target_id=keyword.id,
                    reason=(
                        f"${keyword.cost:.0f} spent across {keyword.clicks} clicks with zero "
                        f"conversions (target CPA ${target_cpa:.0f}). Pausing to stop the bleed."
                    ),
                ))
            elif cpa is not None and cpa >= target_cpa * CPA_OVER_TARGET_TO_LOWER_BID:
                new_bid = round(keyword.max_cpc * (1 - BID_STEP), 2)
                actions.append(OptimizationAction(
                    campaign_id=campaign_id, action_type="lower_bid",
                    target=keyword.text, target_id=keyword.id, new_value=new_bid,
                    reason=(
                        f"CPA is ${cpa:.0f}, {cpa / target_cpa:.1f}x target. Lowering max CPC "
                        f"${keyword.max_cpc:.2f} -> ${new_bid:.2f}."
                    ),
                ))
            elif cpa is not None and cpa <= target_cpa * CPA_UNDER_TARGET_TO_RAISE_BID:
                new_bid = round(keyword.max_cpc * (1 + BID_STEP), 2)
                actions.append(OptimizationAction(
                    campaign_id=campaign_id, action_type="raise_bid",
                    target=keyword.text, target_id=keyword.id, new_value=new_bid,
                    reason=(
                        f"CPA is ${cpa:.0f}, well under target (${target_cpa:.0f}). Raising max "
                        f"CPC ${keyword.max_cpc:.2f} -> ${new_bid:.2f} to capture more volume."
                    ),
                ))

    budget_action = _check_budget_pacing(campaign)
    if budget_action:
        actions.append(budget_action)

    for action in actions:
        store.put("optimization_actions", action)
    return actions


def _check_budget_pacing(campaign: Campaign) -> OptimizationAction | None:
    from app.ads.performance import campaign_summary

    summary = campaign_summary(campaign.id)
    if summary["cost_per_conversion"] is None:
        return None

    firm = store.get("firms", campaign.firm_id)
    ratio = summary["cost_per_conversion"] / firm.target_cpa
    if ratio <= 0.7:
        # Efficient — there's room to spend more before diminishing returns.
        new_budget = round(campaign.daily_budget * 1.15, 2)
        return OptimizationAction(
            campaign_id=campaign.id, action_type="shift_budget",
            target="campaign daily budget", new_value=new_budget,
            reason=(
                f"Blended CPA (${summary['cost_per_conversion']:.0f}) is well under target "
                f"(${firm.target_cpa:.0f}). Raising daily budget "
                f"${campaign.daily_budget:.2f} -> ${new_budget:.2f}."
            ),
        )
    return None


def apply_action(action: OptimizationAction) -> None:
    """Push an action to the ads client (mock or live) and mark it applied."""
    from app.ads.google_ads_client import get_ads_client

    ads_client = get_ads_client()

    if action.action_type == "pause_keyword" and action.target_id:
        keyword = store.get("keywords", action.target_id)
        if keyword:
            ads_client.pause_keyword(keyword)
            store.update("keywords", keyword.id, status="paused")

    elif action.action_type in ("raise_bid", "lower_bid") and action.target_id and action.new_value:
        keyword = store.get("keywords", action.target_id)
        if keyword:
            ads_client.set_keyword_bid(keyword, action.new_value)
            store.update("keywords", keyword.id, max_cpc=action.new_value)

    elif action.action_type == "shift_budget" and action.new_value:
        campaign = store.get("campaigns", action.campaign_id)
        if campaign:
            ads_client.set_campaign_budget(campaign, action.new_value)
            store.update("campaigns", campaign.id, daily_budget=action.new_value)

    store.update("optimization_actions", action.id, applied=True, applied_at=time.time())


def generate_ai_insight(campaign_id: str, actions: list[OptimizationAction]) -> str:
    """Optional: ask Claude for a 2-4 sentence human-readable summary of what
    the rules engine did and why, in plain language a firm's managing partner
    (not a PPC specialist) can understand. Returns "" if no API key is set."""
    try:
        client = get_client()
    except AIUnavailableError:
        return ""

    campaign = store.get("campaigns", campaign_id)
    from app.ads.performance import campaign_summary

    summary = campaign_summary(campaign_id)
    actions_text = "\n".join(f"- {a.action_type}: {a.target} — {a.reason}" for a in actions) or "No changes this cycle."

    response = client.messages.create(
        model=CLAUDE_MODEL,
        max_tokens=400,
        system=(
            "You summarize Google Ads optimization cycles for a law firm's managing "
            "partner, who is not a marketing specialist. Be concise, plain-language, "
            "and specific about dollars and outcomes. 2-4 sentences, no jargon."
        ),
        messages=[{
            "role": "user",
            "content": (
                f"Campaign: {campaign.name}\n"
                f"This period: {summary['clicks']} clicks, ${summary['cost']:.0f} spent, "
                f"{summary['conversions']} leads.\n\n"
                f"Optimization actions taken:\n{actions_text}\n\n"
                "Summarize what happened and why in plain language."
            ),
        }],
    )
    return next((b.text for b in response.content if b.type == "text"), "")
