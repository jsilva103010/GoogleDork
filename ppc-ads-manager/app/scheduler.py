"""Background scheduler that makes this an *automated* ads manager rather than
a click-a-button tool: on an interval, every active campaign gets a full
optimization cycle — pull performance, run the rules engine, optionally apply
the changes, optionally attach an AI narrative.

AUTO_APPLY_OPTIMIZATIONS=false (the default) runs everything except the final
`apply_action` call, so recommendations pile up for human review instead of
touching real ad spend unsupervised.
"""

import logging

from apscheduler.schedulers.background import BackgroundScheduler

from app import store
from app.ai.optimizer import apply_action, generate_ai_insight, run_rules_engine
from app.config import AUTO_APPLY_OPTIMIZATIONS, GOOGLE_ADS_MODE, OPTIMIZATION_INTERVAL_MINUTES

logger = logging.getLogger("ppc_manager.scheduler")

_scheduler: BackgroundScheduler | None = None


def run_optimization_cycle() -> None:
    campaigns = store.list_all("campaigns", status="active")
    for campaign in campaigns:
        try:
            _optimize_one(campaign.id)
        except Exception:
            logger.exception("Optimization cycle failed for campaign %s", campaign.id)


def _optimize_one(campaign_id: str) -> None:
    if GOOGLE_ADS_MODE == "mock":
        from app.ads.performance import simulate_day

        simulate_day(campaign_id)

    actions = run_rules_engine(campaign_id)
    logger.info("Campaign %s: %d optimization action(s) recommended", campaign_id, len(actions))

    if AUTO_APPLY_OPTIMIZATIONS:
        for action in actions:
            apply_action(action)

    if actions:
        insight = generate_ai_insight(campaign_id, actions)
        if insight:
            store.update("campaigns", campaign_id, strategy_notes=insight)


def start_scheduler() -> BackgroundScheduler:
    global _scheduler
    if _scheduler is not None:
        return _scheduler

    _scheduler = BackgroundScheduler(daemon=True)
    _scheduler.add_job(
        run_optimization_cycle,
        "interval",
        minutes=OPTIMIZATION_INTERVAL_MINUTES,
        id="optimization_cycle",
        next_run_time=None,  # first run is triggered manually / on demand, not at startup
    )
    _scheduler.start()
    logger.info(
        "Scheduler started: optimization cycle every %d minute(s), auto-apply=%s",
        OPTIMIZATION_INTERVAL_MINUTES, AUTO_APPLY_OPTIMIZATIONS,
    )
    return _scheduler


def stop_scheduler() -> None:
    global _scheduler
    if _scheduler is not None:
        _scheduler.shutdown(wait=False)
        _scheduler = None
