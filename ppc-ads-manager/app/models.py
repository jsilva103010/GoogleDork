import time
import uuid
from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field


def new_id(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex[:10]}"


class PracticeArea(str, Enum):
    WILLS_TRUSTS = "wills_trusts"
    PROBATE = "probate"
    ELDER_LAW = "elder_law"
    POWER_OF_ATTORNEY = "power_of_attorney"
    ASSET_PROTECTION = "asset_protection"
    GUARDIANSHIP = "guardianship"
    SPECIAL_NEEDS_PLANNING = "special_needs_planning"
    MEDICAID_PLANNING = "medicaid_planning"


class MatchType(str, Enum):
    EXACT = "exact"
    PHRASE = "phrase"
    BROAD = "broad"


class FirmProfile(BaseModel):
    id: str = Field(default_factory=lambda: new_id("firm"))
    name: str
    website: str
    phone: str
    city: str
    state: str
    service_area: str = Field(description="Cities/counties served, comma separated")
    practice_areas: list[PracticeArea]
    monthly_budget: float = Field(gt=0)
    target_cpa: float = Field(gt=0, description="Target cost per lead (call or form fill)")
    unique_selling_points: list[str] = Field(default_factory=list)
    state_bar_jurisdiction: str = Field(description="State bar whose ad rules apply, e.g. 'California'")
    created_at: float = Field(default_factory=time.time)


# ---------------------------------------------------------------------------
# AI-generated campaign plan shapes (also used as the structured-output schema
# passed to client.messages.parse)
# ---------------------------------------------------------------------------


class Keyword(BaseModel):
    text: str
    match_type: MatchType


class Sitelink(BaseModel):
    text: str
    description1: str
    description2: str


class ResponsiveSearchAd(BaseModel):
    headlines: list[str]
    descriptions: list[str]
    path1: str
    path2: str


class AdGroupPlan(BaseModel):
    name: str
    practice_area: PracticeArea
    keywords: list[Keyword]
    negative_keywords: list[str]
    ad: ResponsiveSearchAd


class CampaignPlan(BaseModel):
    """Structured output schema requested from Claude."""

    campaign_name: str
    callouts: list[str]
    sitelinks: list[Sitelink]
    ad_groups: list[AdGroupPlan]
    strategy_notes: str = Field(description="1-3 sentences on targeting/budget strategy")


# ---------------------------------------------------------------------------
# Persisted / runtime campaign state
# ---------------------------------------------------------------------------


class KeywordState(BaseModel):
    id: str = Field(default_factory=lambda: new_id("kw"))
    text: str
    match_type: MatchType
    ad_group_id: str
    status: str = "active"  # active | paused
    max_cpc: float = 3.5
    bid_modifier_log: list[str] = Field(default_factory=list)

    # cumulative mock/live performance
    impressions: int = 0
    clicks: int = 0
    cost: float = 0.0
    conversions: int = 0


class AdGroupState(BaseModel):
    id: str = Field(default_factory=lambda: new_id("adg"))
    campaign_id: str
    name: str
    practice_area: PracticeArea
    negative_keywords: list[str] = Field(default_factory=list)
    ad: ResponsiveSearchAd
    status: str = "active"


class Campaign(BaseModel):
    id: str = Field(default_factory=lambda: new_id("camp"))
    firm_id: str
    name: str
    status: str = "active"  # active | paused
    daily_budget: float
    callouts: list[str] = Field(default_factory=list)
    sitelinks: list[Sitelink] = Field(default_factory=list)
    ad_schedule: str = "Mon-Fri 8:00-19:00, Sat 9:00-13:00 (America/New_York)"
    strategy_notes: str = ""
    compliance_notes: list[str] = Field(default_factory=list)
    created_at: float = Field(default_factory=time.time)


class OptimizationAction(BaseModel):
    id: str = Field(default_factory=lambda: new_id("opt"))
    campaign_id: str
    created_at: float = Field(default_factory=time.time)
    action_type: str  # pause_keyword | raise_bid | lower_bid | add_negative | shift_budget
    target: str
    target_id: Optional[str] = None
    reason: str
    new_value: Optional[float] = None  # new max_cpc or new daily_budget, depending on action_type
    applied: bool = False
    applied_at: Optional[float] = None
    source: str = "rules"  # rules | ai
