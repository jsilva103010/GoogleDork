from app import store
from app.ai.optimizer import run_rules_engine
from app.models import (
    AdGroupState,
    Campaign,
    FirmProfile,
    KeywordState,
    MatchType,
    PracticeArea,
    ResponsiveSearchAd,
)


def _seed_campaign(target_cpa=250.0, daily_budget=200.0):
    firm = FirmProfile(
        name="Test Firm", website="https://example.com", phone="555-0100",
        city="Portland", state="OR", service_area="Portland",
        practice_areas=[PracticeArea.WILLS_TRUSTS], monthly_budget=6000,
        target_cpa=target_cpa, state_bar_jurisdiction="Oregon State Bar",
    )
    store.put("firms", firm)

    campaign = Campaign(firm_id=firm.id, name="Test Campaign", daily_budget=daily_budget)
    store.put("campaigns", campaign)

    ad_group = AdGroupState(
        campaign_id=campaign.id, name="Wills & Trusts", practice_area=PracticeArea.WILLS_TRUSTS,
        ad=ResponsiveSearchAd(headlines=["H1"], descriptions=["D1"], path1="wills", path2="trusts"),
    )
    store.put("ad_groups", ad_group)
    return firm, campaign, ad_group


def _keyword(ad_group_id, **overrides):
    defaults = dict(ad_group_id=ad_group_id, text="estate planning attorney", match_type=MatchType.EXACT, max_cpc=15.0)
    defaults.update(overrides)
    kw = KeywordState(**defaults)
    store.put("keywords", kw)
    return kw


def test_pauses_zero_conversion_high_spend_keyword():
    _, campaign, ad_group = _seed_campaign(target_cpa=250.0)
    _keyword(ad_group.id, clicks=20, cost=600.0, conversions=0)  # 2.4x target CPA-equivalent spend, no leads

    actions = run_rules_engine(campaign.id)

    assert any(a.action_type == "pause_keyword" for a in actions)


def test_lowers_bid_on_over_target_cpa():
    _, campaign, ad_group = _seed_campaign(target_cpa=200.0)
    _keyword(ad_group.id, clicks=20, cost=600.0, conversions=2)  # CPA = $300, 1.5x target

    actions = run_rules_engine(campaign.id)

    lower_bid_actions = [a for a in actions if a.action_type == "lower_bid"]
    assert len(lower_bid_actions) == 1
    assert lower_bid_actions[0].new_value < 15.0


def test_raises_bid_on_efficient_keyword():
    _, campaign, ad_group = _seed_campaign(target_cpa=200.0)
    _keyword(ad_group.id, clicks=20, cost=200.0, conversions=2)  # CPA = $100, well under target

    actions = run_rules_engine(campaign.id)

    raise_bid_actions = [a for a in actions if a.action_type == "raise_bid"]
    assert len(raise_bid_actions) == 1
    assert raise_bid_actions[0].new_value > 15.0


def test_ignores_keywords_below_click_threshold():
    _, campaign, ad_group = _seed_campaign(target_cpa=200.0)
    _keyword(ad_group.id, clicks=5, cost=200.0, conversions=0)  # too little data yet

    actions = run_rules_engine(campaign.id)

    assert not any(a.target_id for a in actions)
