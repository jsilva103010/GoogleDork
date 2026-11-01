# Estate Planning PPC Manager

An automated, AI-assisted Google Ads manager built specifically for estate
planning law firms (wills, trusts, probate, elder law, powers of attorney,
Medicaid/asset protection). Give it a firm's profile and budget; it generates
a full Search campaign structure with Claude, runs it through an
attorney-advertising compliance filter, and then keeps optimizing bids and
budget on a schedule.

## What it does

1. **AI campaign generation** — Claude (`claude-opus-4-8`) drafts ad groups,
   keywords (exact/phrase/broad), responsive search ads, sitelinks, and
   callouts, using structured output so the response is always
   schema-valid Python objects, not a JSON string to hope-and-parse.
2. **Compliance filter** — every headline, description, callout, and
   sitelink is scanned for outcome guarantees and unsubstantiated
   superlative claims ("guaranteed", "best lawyer", "#1 rated") before it's
   saved. Flagged lines are dropped, not just logged. A "Attorney
   Advertising" disclaimer sitelink is injected unconditionally. **This is a
   blunt safety net, not a substitute for review by the firm's bar counsel.**
3. **Automated optimization** — a rules engine (no API key required) pauses
   keywords burning budget with zero conversions, lowers bids on
   over-target-CPA keywords, raises bids on efficient ones, and nudges daily
   budget up when blended CPA is well under target. Runs on a schedule
   (`OPTIMIZATION_INTERVAL_MINUTES`, default hourly) and/or on demand.
4. **Human-in-the-loop by default** — `AUTO_APPLY_OPTIMIZATIONS=false` means
   recommendations queue up for one-click approve/dismiss in the dashboard
   instead of touching live ad spend unsupervised. Flip it once you trust it.
5. **AI insight narratives** — after each optimization cycle, an optional
   Claude call turns the rules engine's output into a 2-4 sentence plain-English
   summary for a managing partner who isn't a PPC specialist.
6. **Google Ads integration point** — ships in `mock` mode (a local traffic
   simulator with realistic estate-planning CPCs, no account needed) with a
   `live` mode stub wired for the real `google-ads` API client. See
   `app/ads/google_ads_client.py`.

## Quickstart (mock mode — no external accounts needed)

```bash
cd ppc-ads-manager
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env      # optionally add ANTHROPIC_API_KEY for AI features
python run.py
```

Open http://localhost:8000, add a firm, click **Generate AI Campaign**
(requires `ANTHROPIC_API_KEY`), then **Simulate a Day of Traffic** a few
times and **Run Optimization Cycle Now** to see recommendations appear.

Without an API key, everything except AI campaign generation and AI insight
narratives still works — the rules-engine optimizer and mock traffic
simulator have no AI dependency.

## Going live

- **Claude**: set `ANTHROPIC_API_KEY` in `.env`.
- **Google Ads**: set `GOOGLE_ADS_MODE=live` plus the developer token and
  OAuth credentials in `.env`, and `pip install google-ads`. The mutate
  operations in `LiveAdsClient` (`app/ads/google_ads_client.py`) are
  structural stubs — wire up resource names for your account (MCC vs. direct
  customer ID) before flipping this on, since it will spend real money.
  Start with `AUTO_APPLY_OPTIMIZATIONS=false` regardless.

## Architecture

```
app/
  models.py                 pydantic schemas (firm, campaign plan, runtime state)
  store.py                  JSON-file persistence (swap for Postgres in production)
  config.py                 env-driven configuration
  main.py                   FastAPI routes + Jinja2 dashboard
  data/
    practice_areas.py       keyword themes + CPC bands per practice area
    negative_keywords.py    universal negatives (DIY/template/job-seeker traffic)
    compliance.py           attorney-advertising phrase filter
  ai/
    client.py                Anthropic client, raises a clear error if no API key
    campaign_generator.py    Claude structured-output campaign generation
    optimizer.py              rules engine + optional AI narrative
  ads/
    google_ads_client.py     mock/live Google Ads interface
    campaign_builder.py      AI plan -> persisted campaign/ad-group/keyword state
    performance.py           mock traffic simulator + summary rollups
  scheduler.py               APScheduler background optimization cycles
  templates/, static/        server-rendered dashboard
```

## Why these design choices

- **Structured output over prefill/regex-parsing** — campaign generation uses
  `client.messages.parse(..., output_format=CampaignPlan)` so the response is
  a validated `CampaignPlan` object, not a JSON blob to defensively parse.
- **Deterministic compliance filter runs after every AI generation**,
  independent of prompt instructions — prompts can be circumvented by model
  variance; a regex safety net downstream can't.
- **Rules engine has no AI dependency** — the automated, scheduled part of
  "automated AI ads manager" needs to keep running even if the Anthropic API
  is briefly unavailable. AI is layered on for copywriting and narrative
  insight, not for the safety-critical pause/bid decisions.
- **Human review is the default posture** for an app that would otherwise
  autonomously spend a law firm's ad budget — `AUTO_APPLY_OPTIMIZATIONS`
  exists precisely so that's a deliberate opt-in, not a default.
