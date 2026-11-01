"""Mock traffic simulator.

In mock mode there's no real Google Ads account generating impressions, so
"Simulate a day" advances every active keyword's cumulative stats with
randomized-but-plausible numbers for the estate-planning vertical (this is
a genuinely expensive legal niche — $20-90+ CPC is normal), then applies the
campaign's daily budget as a spend cap, same as real Google Ads pacing does.

In live mode, `pull_live_metrics` would replace this with a GoogleAdsService
search query against the account instead (see the stub below).
"""

import random

from app import store
from app.data.practice_areas import PRACTICE_AREA_THEMES
from app.models import Campaign, KeywordState, MatchType

# Rough relative search-volume and conversion-rate multipliers by match type.
_MATCH_TYPE_PROFILE = {
    MatchType.EXACT: {"impressions": (15, 90), "ctr": (0.06, 0.11), "conv_rate": (0.035, 0.07)},
    MatchType.PHRASE: {"impressions": (25, 160), "ctr": (0.04, 0.08), "conv_rate": (0.02, 0.045)},
    MatchType.BROAD: {"impressions": (40, 300), "ctr": (0.02, 0.05), "conv_rate": (0.008, 0.025)},
}


def simulate_day(campaign_id: str) -> dict:
    campaign = store.get("campaigns", campaign_id)
    if campaign is None or campaign.status != "active":
        return {"spend": 0.0, "clicks": 0, "conversions": 0}

    ad_groups = [ag for ag in store.list_all("ad_groups", campaign_id=campaign_id) if ag.status == "active"]
    day_deltas: list[tuple[KeywordState, dict]] = []

    for ad_group in ad_groups:
        keywords = [kw for kw in store.list_all("keywords", ad_group_id=ad_group.id) if kw.status == "active"]
        for keyword in keywords:
            profile = _MATCH_TYPE_PROFILE[keyword.match_type]
            impressions = random.randint(*profile["impressions"])
            ctr = random.uniform(*profile["ctr"])
            clicks = round(impressions * ctr)

            cpc_low, cpc_high = PRACTICE_AREA_THEMES[ad_group.practice_area]["cpc_range"]
            # Actual CPC is bounded by the keyword's max bid (Ad Rank auctions
            # never charge more than your bid).
            avg_cpc = min(keyword.max_cpc, random.uniform(cpc_low, cpc_high) * random.uniform(0.7, 1.05))
            cost = round(clicks * avg_cpc, 2)

            conv_rate = random.uniform(*profile["conv_rate"])
            conversions = sum(1 for _ in range(clicks) if random.random() < conv_rate)

            day_deltas.append((keyword, {
                "impressions": impressions, "clicks": clicks, "cost": cost, "conversions": conversions,
            }))

    total_cost = sum(d["cost"] for _, d in day_deltas)
    scale = 1.0
    if total_cost > campaign.daily_budget > 0:
        # Budget-limited pacing: Google Ads throttles delivery once the daily
        # budget is exhausted, so scale everything down proportionally.
        scale = campaign.daily_budget / total_cost

    totals = {"spend": 0.0, "clicks": 0, "conversions": 0}
    for keyword, delta in day_deltas:
        clicks = round(delta["clicks"] * scale)
        cost = round(delta["cost"] * scale, 2)
        conversions = round(delta["conversions"] * scale)
        impressions = round(delta["impressions"] * scale)

        store.update(
            "keywords", keyword.id,
            impressions=keyword.impressions + impressions,
            clicks=keyword.clicks + clicks,
            cost=round(keyword.cost + cost, 2),
            conversions=keyword.conversions + conversions,
        )
        totals["spend"] += cost
        totals["clicks"] += clicks
        totals["conversions"] += conversions

    totals["spend"] = round(totals["spend"], 2)
    return totals


def pull_live_metrics(campaign: Campaign) -> None:  # pragma: no cover - live mode only
    """Live-mode equivalent of simulate_day: query the Google Ads Reporting
    API (GoogleAdsService.search with a GAQL query against
    ad_group_criterion / metrics) and update each KeywordState with the
    incremental impressions/clicks/cost/conversions since the last pull.
    Left as a stub — see google-ads-python examples/reporting/get_keyword_stats.py.
    """
    raise NotImplementedError("Wire up a GAQL metrics query for live accounts.")


def campaign_summary(campaign_id: str) -> dict:
    keywords = []
    for ad_group in store.list_all("ad_groups", campaign_id=campaign_id):
        keywords.extend(store.list_all("keywords", ad_group_id=ad_group.id))

    impressions = sum(k.impressions for k in keywords)
    clicks = sum(k.clicks for k in keywords)
    cost = sum(k.cost for k in keywords)
    conversions = sum(k.conversions for k in keywords)

    return {
        "impressions": impressions,
        "clicks": clicks,
        "cost": round(cost, 2),
        "conversions": conversions,
        "ctr": round(clicks / impressions * 100, 2) if impressions else 0.0,
        "avg_cpc": round(cost / clicks, 2) if clicks else 0.0,
        "cost_per_conversion": round(cost / conversions, 2) if conversions else None,
    }
