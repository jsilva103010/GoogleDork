from app.ai.client import get_client
from app.config import CLAUDE_MODEL
from app.data.compliance import REQUIRED_DISCLAIMER, review_campaign_plan
from app.data.negative_keywords import CAMPAIGN_LEVEL_NEGATIVES
from app.data.practice_areas import PRACTICE_AREA_THEMES
from app.models import CampaignPlan, FirmProfile, Sitelink

SYSTEM_PROMPT = """\
You are a senior Google Ads strategist who specializes exclusively in estate \
planning law firms (wills, trusts, probate, elder law, powers of attorney, \
Medicaid/asset protection planning). You build Search campaign structures: \
tightly themed ad groups, high-intent keywords, and responsive search ads.

Hard requirements, because this is regulated attorney advertising:
- Never imply a guaranteed, promised, or certain legal outcome.
- Never use unsubstantiated superlative claims ("best", "#1", "top rated") \
unless the firm's unique selling points explicitly support it.
- Never promise "free" services unless the firm profile says so.
- Write for a reader who is worried and researching, not one who is ready to \
buy a product — the tone is reassuring and clear, not salesy.
- Every ad group must be tightly themed to ONE practice area and its keywords \
must all be relevant to that ad group's ad copy (Google Ads quality score \
depends on this).

Google Ads Responsive Search Ad limits to respect:
- Headlines: exactly 10-15 headlines, each <=30 characters.
- Descriptions: exactly 3-4 descriptions, each <=90 characters.
- path1/path2 (URL display paths): each <=15 characters, no spaces, e.g. "probate".
- Sitelinks: 4-6, each text <=25 characters, each description line <=35 characters.
- Callouts: 6-8, each <=25 characters.
- Keywords: each ad group should have 8-15 keywords across exact/phrase/broad \
match types, focused on high commercial intent (e.g. "probate attorney near me") \
rather than informational queries (e.g. "what is probate").
"""


def _build_user_prompt(firm: FirmProfile) -> str:
    theme_lines = []
    for area in firm.practice_areas:
        theme = PRACTICE_AREA_THEMES[area]
        theme_lines.append(f"- {theme['label']}: seed terms like {', '.join(theme['seed_terms'])}")

    return f"""\
Build a complete Google Ads Search campaign for this estate planning law firm.

Firm: {firm.name}
Website: {firm.website}
Phone: {firm.phone}
Location: {firm.city}, {firm.state}
Service area: {firm.service_area}
Monthly budget: ${firm.monthly_budget:,.0f}
Target cost per lead (call/form fill): ${firm.target_cpa:,.0f}
Unique selling points: {"; ".join(firm.unique_selling_points) or "none provided"}
State bar jurisdiction (advertising rules apply): {firm.state_bar_jurisdiction}

Requested practice area ad groups:
{chr(10).join(theme_lines)}

Create one ad group per requested practice area. Mention the city or service \
area naturally in at least one headline per ad group for local relevance. \
Include the firm's phone number readability isn't required in ad text (Google \
Ads call extensions handle that), but you may reference "free case review" \
only if it's implied by the firm's unique selling points."""


def generate_campaign_plan(firm: FirmProfile) -> tuple[CampaignPlan, list[str]]:
    """Ask Claude for a full campaign structure, then run it through the
    deterministic compliance filter. Returns (plan, compliance_notes).
    Flagged lines are dropped from the plan and a note is added.
    """
    client = get_client()
    response = client.messages.parse(
        model=CLAUDE_MODEL,
        max_tokens=8000,
        system=SYSTEM_PROMPT,
        messages=[{"role": "user", "content": _build_user_prompt(firm)}],
        output_format=CampaignPlan,
    )
    plan = response.parsed_output

    compliance_notes = review_campaign_plan(plan)
    _sanitize_plan(plan)
    _enforce_limits(plan)
    _inject_disclaimer(plan)

    return plan, compliance_notes


def _sanitize_plan(plan: CampaignPlan) -> None:
    """Drop any line that still trips the compliance scanner after generation
    (belt-and-suspenders — the system prompt should prevent this)."""
    from app.data.compliance import scan_text

    plan.callouts = [c for c in plan.callouts if not scan_text(c)]
    plan.sitelinks = [
        s for s in plan.sitelinks if not (scan_text(s.text) or scan_text(s.description1) or scan_text(s.description2))
    ]
    for ad_group in plan.ad_groups:
        ad_group.ad.headlines = [h for h in ad_group.ad.headlines if not scan_text(h)]
        ad_group.ad.descriptions = [d for d in ad_group.ad.descriptions if not scan_text(d)]


def _enforce_limits(plan: CampaignPlan) -> None:
    """Google Ads rejects text over these limits outright — truncate defensively
    since the structured-output schema can't enforce string length server-side."""
    plan.callouts = [c[:25] for c in plan.callouts][:8]
    plan.sitelinks = [
        Sitelink(text=s.text[:25], description1=s.description1[:35], description2=s.description2[:35])
        for s in plan.sitelinks
    ][:6]
    for ad_group in plan.ad_groups:
        ad_group.ad.headlines = [h[:30] for h in ad_group.ad.headlines][:15]
        ad_group.ad.descriptions = [d[:90] for d in ad_group.ad.descriptions][:4]
        ad_group.ad.path1 = ad_group.ad.path1.replace(" ", "")[:15]
        ad_group.ad.path2 = ad_group.ad.path2.replace(" ", "")[:15]
        ad_group.negative_keywords = list(set(ad_group.negative_keywords) | set(CAMPAIGN_LEVEL_NEGATIVES))


def _inject_disclaimer(plan: CampaignPlan) -> None:
    """Attach the attorney-advertising disclaimer as a sitelink so it's always
    present regardless of what the model generated — this is not optional."""
    if not any("attorney advertising" in s.text.lower() for s in plan.sitelinks):
        plan.sitelinks = (plan.sitelinks[:5]) + [
            Sitelink(text="Disclaimer", description1=REQUIRED_DISCLAIMER[:35], description2=REQUIRED_DISCLAIMER[35:70])
        ]
