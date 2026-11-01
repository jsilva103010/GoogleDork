from app import store
from app.ads.google_ads_client import get_ads_client
from app.data.practice_areas import PRACTICE_AREA_THEMES
from app.models import AdGroupState, Campaign, CampaignPlan, FirmProfile, KeywordState


def _initial_max_cpc(practice_area) -> float:
    low, high = PRACTICE_AREA_THEMES[practice_area]["cpc_range"]
    # Start bids at the low end of the vertical's range — the optimizer raises
    # bids on keywords that prove they convert rather than overpaying up front.
    return round(low * 0.6, 2)


def build_and_persist_campaign(firm: FirmProfile, plan: CampaignPlan) -> Campaign:
    campaign = Campaign(
        firm_id=firm.id,
        name=plan.campaign_name,
        daily_budget=round(firm.monthly_budget / 30.4, 2),
        callouts=plan.callouts,
        sitelinks=plan.sitelinks,
        strategy_notes=plan.strategy_notes,
    )
    store.put("campaigns", campaign)

    ad_groups: list[AdGroupState] = []
    keywords: list[KeywordState] = []

    for ag_plan in plan.ad_groups:
        ad_group = AdGroupState(
            campaign_id=campaign.id,
            name=ag_plan.name,
            practice_area=ag_plan.practice_area,
            negative_keywords=ag_plan.negative_keywords,
            ad=ag_plan.ad,
        )
        store.put("ad_groups", ad_group)
        ad_groups.append(ad_group)

        for kw_plan in ag_plan.keywords:
            keyword = KeywordState(
                ad_group_id=ad_group.id,
                text=kw_plan.text,
                match_type=kw_plan.match_type,
                max_cpc=_initial_max_cpc(ag_plan.practice_area),
            )
            store.put("keywords", keyword)
            keywords.append(keyword)

    get_ads_client().sync_campaign(campaign, ad_groups, keywords)
    return campaign
