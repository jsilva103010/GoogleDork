import logging
from pathlib import Path
from urllib.parse import quote

from fastapi import FastAPI, Form, Request
from fastapi.responses import RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from app import store
from app.ads.campaign_builder import build_and_persist_campaign
from app.ads.performance import campaign_summary, simulate_day
from app.ai.campaign_generator import generate_campaign_plan
from app.ai.client import AIUnavailableError
from app.ai.optimizer import apply_action, generate_ai_insight, run_rules_engine
from app.config import AUTO_APPLY_OPTIMIZATIONS, GOOGLE_ADS_MODE, has_anthropic_key
from app.models import FirmProfile, PracticeArea
from app.scheduler import start_scheduler, stop_scheduler

logging.basicConfig(level=logging.INFO)

BASE_DIR = Path(__file__).resolve().parent
templates = Jinja2Templates(directory=str(BASE_DIR / "templates"))

app = FastAPI(title="Estate Planning PPC Manager")
app.mount("/static", StaticFiles(directory=str(BASE_DIR / "static")), name="static")


@app.on_event("startup")
def _startup() -> None:
    start_scheduler()


@app.on_event("shutdown")
def _shutdown() -> None:
    stop_scheduler()


def _redirect(path: str, message: str = "", error: bool = False) -> RedirectResponse:
    q = ""
    if message:
        param = "error" if error else "message"
        q = f"?{param}={quote(message)}"
    return RedirectResponse(url=f"{path}{q}", status_code=303)


@app.get("/")
def index(request: Request):
    firms = store.list_all("firms")
    campaigns_by_firm = {firm.id: store.list_all("campaigns", firm_id=firm.id) for firm in firms}
    return templates.TemplateResponse(request, "index.html", {
        "firms": firms,
        "campaigns_by_firm": campaigns_by_firm,
        "has_key": has_anthropic_key(),
        "google_ads_mode": GOOGLE_ADS_MODE,
        "auto_apply": AUTO_APPLY_OPTIMIZATIONS,
    })


@app.get("/firms/new")
def new_firm_form(request: Request):
    return templates.TemplateResponse(request, "firm_new.html", {"practice_areas": list(PracticeArea)})


@app.post("/firms")
def create_firm(
    request: Request,
    name: str = Form(...),
    website: str = Form(...),
    phone: str = Form(...),
    city: str = Form(...),
    state: str = Form(...),
    service_area: str = Form(...),
    practice_areas: list[str] = Form(...),
    monthly_budget: float = Form(...),
    target_cpa: float = Form(...),
    unique_selling_points: str = Form(""),
    state_bar_jurisdiction: str = Form(...),
):
    firm = FirmProfile(
        name=name, website=website, phone=phone, city=city, state=state,
        service_area=service_area,
        practice_areas=[PracticeArea(p) for p in practice_areas],
        monthly_budget=monthly_budget, target_cpa=target_cpa,
        unique_selling_points=[s.strip() for s in unique_selling_points.split(",") if s.strip()],
        state_bar_jurisdiction=state_bar_jurisdiction,
    )
    store.put("firms", firm)
    return _redirect(f"/firms/{firm.id}", "Firm profile created.")


@app.get("/firms/{firm_id}")
def firm_detail(request: Request, firm_id: str):
    firm = store.get("firms", firm_id)
    if firm is None:
        return _redirect("/", "Firm not found.", error=True)
    campaigns = store.list_all("campaigns", firm_id=firm_id)
    return templates.TemplateResponse(request, "firm_detail.html", {
        "firm": firm,
        "campaigns": campaigns,
        "has_key": has_anthropic_key(),
    })


@app.post("/firms/{firm_id}/generate-campaign")
def generate_campaign(request: Request, firm_id: str):
    firm = store.get("firms", firm_id)
    if firm is None:
        return _redirect("/", "Firm not found.", error=True)

    try:
        plan, compliance_notes = generate_campaign_plan(firm)
    except AIUnavailableError as exc:
        return _redirect(f"/firms/{firm_id}", str(exc), error=True)

    campaign = build_and_persist_campaign(firm, plan)
    if compliance_notes:
        store.update("campaigns", campaign.id, compliance_notes=compliance_notes)

    return _redirect(f"/campaigns/{campaign.id}", "Campaign generated.")


@app.get("/campaigns/{campaign_id}")
def campaign_detail(request: Request, campaign_id: str):
    campaign = store.get("campaigns", campaign_id)
    if campaign is None:
        return _redirect("/", "Campaign not found.", error=True)

    firm = store.get("firms", campaign.firm_id)
    ad_groups = store.list_all("ad_groups", campaign_id=campaign_id)
    keywords_by_ad_group = {ag.id: store.list_all("keywords", ad_group_id=ag.id) for ag in ad_groups}
    actions = sorted(
        store.list_all("optimization_actions", campaign_id=campaign_id),
        key=lambda a: a.created_at, reverse=True,
    )
    pending_actions = [a for a in actions if not a.applied]
    applied_actions = [a for a in actions if a.applied]

    return templates.TemplateResponse(request, "campaign_detail.html", {
        "campaign": campaign,
        "firm": firm,
        "ad_groups": ad_groups,
        "keywords_by_ad_group": keywords_by_ad_group,
        "summary": campaign_summary(campaign_id),
        "pending_actions": pending_actions,
        "applied_actions": applied_actions,
        "auto_apply": AUTO_APPLY_OPTIMIZATIONS,
        "google_ads_mode": GOOGLE_ADS_MODE,
        "has_key": has_anthropic_key(),
    })


@app.post("/campaigns/{campaign_id}/simulate")
def simulate(request: Request, campaign_id: str):
    if GOOGLE_ADS_MODE != "mock":
        return _redirect(f"/campaigns/{campaign_id}", "Simulation only available in mock mode.", error=True)
    totals = simulate_day(campaign_id)
    return _redirect(
        f"/campaigns/{campaign_id}",
        f"Simulated a day: {totals['clicks']} clicks, ${totals['spend']:.2f} spent, {totals['conversions']} leads.",
    )


@app.post("/campaigns/{campaign_id}/optimize")
def optimize_now(request: Request, campaign_id: str):
    actions = run_rules_engine(campaign_id)
    insight = generate_ai_insight(campaign_id, actions)
    if insight:
        store.update("campaigns", campaign_id, strategy_notes=insight)
    message = f"{len(actions)} recommendation(s) generated." if actions else "No changes recommended this cycle."
    return _redirect(f"/campaigns/{campaign_id}", message)


@app.post("/optimization-actions/{action_id}/apply")
def apply_optimization(request: Request, action_id: str):
    action = store.get("optimization_actions", action_id)
    if action is None:
        return _redirect("/", "Recommendation not found.", error=True)
    apply_action(action)
    return _redirect(f"/campaigns/{action.campaign_id}", "Recommendation applied.")


@app.post("/optimization-actions/{action_id}/dismiss")
def dismiss_optimization(request: Request, action_id: str):
    action = store.get("optimization_actions", action_id)
    if action is None:
        return _redirect("/", "Recommendation not found.", error=True)
    campaign_id = action.campaign_id
    store.delete("optimization_actions", action_id)
    return _redirect(f"/campaigns/{campaign_id}", "Recommendation dismissed.")
