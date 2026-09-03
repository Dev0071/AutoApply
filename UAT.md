# AutoApply — UAT Guide

What changed, how to bring it up, and what to actually test.

## What changed

The pipeline now has three navigation tiers instead of one. Everything else about the
product promise is unchanged: the fit gate still runs before any expensive work, every
action still screenshots to S3, and nothing reaches `submitted` without human review.

| | Before | After |
|---|---|---|
| Navigation | Vision loop, 1 action per Claude call | DOM fill (1 call/form) → vision fallback (batched actions/call) |
| Vision model | `claude-opus-4-5` | `claude-sonnet-5`, escalating to `claude-opus-5` only on verification failure |
| Tailoring | 2 calls on `claude-sonnet-4-6` | 1 call on `claude-sonnet-5`, structured output |
| JD extraction | `claude-sonnet-4-6` | `claude-haiku-4-5`, Redis-deduped by URL |
| Cost visibility | none | `response.usage` on every call → `ApplicationRun.total_cost_usd`, shown in the UI |
| Dead-run cost | 30 Opus calls | ~2 calls (stuck detection) or a hard token budget |
| Sensitive questions | answered by the model | never answered; surfaced as "needs your answer" |

**Estimated cost per application** (computed from `backend/agents/usage.py` pricing):

| Path | Before | After |
|---|---|---|
| Typical (15 steps) | ~$0.357 | **$0.019** (DOM tier) |
| Vision fallback | — | **$0.064** |
| Worst case (30 steps) | ~$0.679 | capped by `VISION_LOOP_TOKEN_BUDGET` |

These are estimates from token arithmetic, **not** measured against the live API. Validating
them on real postings is the main job of UAT — the run's own `total_cost_usd` is now recorded
for exactly this purpose.

## Bring-up

```bash
make infra                 # Postgres + Redis
make migrate               # applies 0002 — adds total_cost_usd + token_usage
pip install -r requirements.txt   # adds pillow (WebP screenshot encoding)
make s3-lifecycle          # one-time: expire run screenshots after 30 days
make api                   # :8000
make worker                # Celery
make ui                    # :3000
```

New env vars are documented in `.env.example`; every one has a working default, so an
existing `.env` will boot unchanged. The two worth setting deliberately:

- `BROWSER_MODE=local` for dev/test — runs headless Chromium and consumes zero Browserbase minutes.
- `HYBRID_FILL_ENABLED=false` — kill switch that forces every run through the old vision path.

## Test suites

```bash
make test              # 120 unit tests, no browser, no network, no tokens
make test-integration  # 5 tests against real headless Chromium, Claude scripted
make test-all
```

The integration suite is the eval baseline. It asserts the API-call budget per run, so a
regression that reintroduces per-field calls fails the build:

- DOM tier fills the whole fixture form in **1** model call, 0 verification failures
- Vision tier fills 4 fields in **2** perceive calls
- Orchestrator end-to-end asserts total cost < $0.01 on the DOM tier
- Screenshot compression measured against a real rendered screenshot (~2.8× WebP win)

## What to exercise in UAT

**Cost and tier mix** — the core question this work exists to answer.
1. Run 10–20 real postings across Greenhouse, Lever, Ashby, and one Workday.
2. For each, record `total_cost_usd` and `tier` from the application detail page.
3. Watch for `cost_anomaly` warnings in the worker log (fires above `COST_ALERT_USD`).
4. A high vision-fallback rate on one ATS means its DOM isn't serializing well — worth a look
   before it becomes the default path.

**Fill quality — the thing that must not regress.**
5. On each run, compare filled values against the profile. The DOM tier is deterministic,
   so errors here are mapping errors, not clicking errors.
6. Confirm demographic/EEO questions show as "needs your answer" and are left blank.
7. Confirm any field marked "value not confirmed" in the replay actually did fail.

**Guardrails.**
8. Point a run at a page that will get stuck (a login wall) — expect `agent_stuck`, a
   failed run within ~2 model calls, and **no** Celery retry.
9. Trigger 21 applications to one platform in a day — the 21st should fail `rate_limited`.
10. Set `VISION_LOOP_TOKEN_BUDGET` low (e.g. 5000), run a vision-tier job, and confirm it
    lands in `review` with partial steps and the "stopped at the cost limit" banner.

**Unchanged promises — regression check.**
11. A below-threshold job never opens a browser and never calls tailoring.
12. No run reaches `submitted` except through the review gate.
13. Every step in the replay has a screenshot.

## Known gaps

- **File uploads (resume/cover-letter attachments) are not handled.** The mapper marks them
  `needs_user_input`. This is the largest functional gap for real applications and is not
  covered by any tier.
- **Multi-page/wizard forms** are handled only by the vision tier. The DOM tier fills the
  current page and, if that leaves the form incomplete, verification passes but the
  application isn't actually finished — worth watching for on Workday specifically.
- Cost figures above are arithmetic, not measurements. Treat the first UAT batch as the
  real baseline.
- Escalation is per-screen and one-shot: a screen that fails verification retries once on
  the fallback model and then proceeds regardless.
