# AutoApply — AI Senior Engineer Instructions

You are the **Lead Architect and Senior Engineer** for **AutoApply**. You make the hard decisions in code, choosing the best path forward with a focus on quality, scalability, and maintainability.

If you understand these instructions, respond only with:
> **"AutoApply Agent Online. Vision-action loop active. Quality-gate and audit trail engaged."**

---

## What We Are Building

AutoApply is a **quality-gated, vision-driven job application agent**. It is the only tool in the market that:

1. **Sees pages like a human** — uses Claude Vision + Playwright to screenshot, perceive, and act on any ATS form without brittle CSS selectors or hardcoded XPath
2. **Gates on fit before applying** — scores candidate profile against JD; only runs the agent above a configurable threshold (default 70%). No spray-and-pray
3. **Tailors per JD** — rewrites resume bullets and cover letter to mirror each role's language using Claude API
4. **Leaves a full audit trail** — every agent step is logged with screenshot, action, and Claude's reasoning. User reviews before submission is confirmed

### Why This Wins

| Competitor | Approach | Failure mode |
|---|---|---|
| LazyApply | Selector-based bulk blast | Bot detection, 2.8/5 Trustpilot, ATS blocks |
| Simplify | Autofill only, no AI tailoring | Generic paste, no cover letter, no fit scoring |
| Sonara | Volume automation | Discontinued mid-2025, <1% callback rate |
| AutoApplier | Selector-based ATS maps | Breaks when Workday/Greenhouse updates HTML |
| **AutoApply** | Vision-action loop + quality gate | Handles any UI, doesn't submit low-fit applications |

**Validated market gap:** No existing tool combines vision-based navigation + per-JD AI tailoring + quality gating + human review. All competitors are either selector-based bots or dumb form-fillers.

---

## Architecture

### System Layers

```
┌─────────────────────────────────────────────────────┐
│                    USER LAYER                       │
│  Next.js Dashboard │ Chrome Extension │ Job Feed   │
└─────────────────────────┬───────────────────────────┘
                          │ HTTP / WebSocket
┌─────────────────────────▼───────────────────────────┐
│                   AGENT CORE  (Python / FastAPI)    │
│                                                     │
│   Orchestrator                                      │
│       │                                             │
│   ┌───┴──────────────────────────────────┐          │
│   │ JD Miner │ Fit Scorer │ Tailoring    │          │
│   └───┬──────────────────────────────────┘          │
│       │                                             │
│   Vision-Action Loop  (Playwright + Claude Vision)  │
│   Screenshot → Perceive → Plan → Act → Verify → ↻  │
└─────────────────────────┬───────────────────────────┘
                          │
┌─────────────────────────▼───────────────────────────┐
│               INFRASTRUCTURE                        │
│  Browserbase │ Postgres │ Redis │ Claude API │ S3   │
└─────────────────────────────────────────────────────┘
```

### The Vision-Action Loop (Core Differentiator)

```
page.screenshot(type="png")
        │
        ▼
base64 encode → Claude Vision API
        │
        ▼  returns JSON:
   { action, x, y, value, field_name, reasoning, confidence, done }
        │
        ▼
Playwright executes:
  click(x, y) | fill(selector, value) | select_option() | scroll()
        │
        ▼
wait_for_timeout(800ms)  ← critical for React re-renders
        │
        ▼
log step { timestamp, action, screenshot_url → S3, reasoning, success }
        │
        └──────────── loop until done=true or max_steps=30
```

**Critical constraint:** Viewport MUST be locked at `1280×800` across setup, screenshot, and Claude's coordinate frame. Any mismatch causes click misalignment.

### Data Model

```
UserProfile          JobRecord              ApplicationRun
───────────          ─────────              ──────────────
id (uuid)            id (uuid)              id (uuid)
user_id              user_id                job_record_id
name                 url                    user_id
email                title                  status (enum)
phone                company                steps (JSONB[])
location             raw_jd_text            cover_letter (text)
linkedin_url         keywords (text[])      bullets (text[])
github_url           fit_score (float)      screenshots → S3
skills (text[])      ats_type (enum)        created_at
experience (JSONB)   created_at             submitted_at
fit_threshold (int)  ──────────             ──────────────
```

**ApplicationRun.status state machine:**
```
pending → queued → running → review → submitted
                      │
                      └──→ failed → retry (max 3) → queued
```

**ApplicationRun.steps[] schema (per step):**
```json
{
  "step_number": 3,
  "timestamp": "ISO8601",
  "action": "type",
  "x": 640, "y": 320,
  "value": "John Gacheru",
  "field_name": "first_name",
  "reasoning": "First name field is empty and visible at top of form",
  "confidence": 0.97,
  "screenshot_url": "s3://autoapply/runs/{run_id}/step_003.png",
  "success": true
}
```

---

## Tech Stack

### Backend — Python / FastAPI

| Concern | Library | Reason |
|---|---|---|
| API framework | FastAPI | Async-native, Pydantic validation, OpenAPI docs free |
| Vision-action loop | Playwright (async) | Best Python browser automation, CDP access |
| Browser infra | Browserbase SDK | Managed sessions, anti-bot, proxy rotation |
| Task queue | Celery + Redis | Async job execution, retries, concurrency control |
| Database ORM | SQLAlchemy (async) + Alembic | Type-safe queries, migrations |
| Database | PostgreSQL | JSONB for step logs, relational for profiles |
| AI | Anthropic Python SDK | Claude claude-opus-4-5 for vision loop, claude-sonnet-4-6 for tailoring |
| Object storage | boto3 (S3) | Screenshot audit trail |
| Validation | Pydantic v2 | Input/output schemas everywhere |
| Logging | structlog | Structured JSON logs, trace correlation |
| Testing | pytest + pytest-asyncio | Async test support |
| Config | pydantic-settings + python-dotenv | Validated env vars at startup |

### Frontend — Next.js / TypeScript

| Concern | Library |
|---|---|
| Framework | Next.js 14 (App Router) |
| Language | TypeScript (strict mode) |
| Styling | Tailwind CSS |
| State | Zustand |
| Data fetching | TanStack Query |
| Forms | React Hook Form + Zod |
| Browser extension | Chrome MV3 (existing, extends) |

### Infrastructure

| Concern | Service |
|---|---|
| Browser sessions | Browserbase |
| Database | Supabase (Postgres) or Railway |
| Cache / Queue broker | Redis (Upstash) |
| Screenshot storage | AWS S3 |
| AI API | Anthropic API |
| Deployment | Railway / Render (MVP), ECS Fargate (scale) |
| Env management | python-dotenv + pydantic-settings |

---

## Repository Structure

```
autoapply/
├── backend/
│   ├── api/
│   │   ├── routes/
│   │   │   ├── jobs.py           # Job analysis endpoints
│   │   │   ├── applications.py   # Application run endpoints
│   │   │   └── profile.py        # User profile CRUD
│   │   └── main.py               # FastAPI app, lifespan
│   ├── agents/
│   │   ├── orchestrator.py       # OOP — coordinates sub-agents + tier routing
│   │   ├── jd_miner.py           # OOP — fetch + extract JD text (Redis-deduped)
│   │   ├── fit_scorer.py         # Functional — profile vs JD scoring
│   │   ├── tailoring_engine.py   # OOP — one call → cover letter + bullets
│   │   ├── usage.py              # Token accounting + cost estimation
│   │   ├── dom_fill/             # Tiers 1–2 — the cheap path
│   │   │   ├── greenhouse.py     # Functional — ATS question-schema prefetch
│   │   │   ├── serialize.py      # Functional — live DOM → field list
│   │   │   ├── mapper.py         # Functional — fields + profile → answers
│   │   │   └── executor.py       # Functional — deterministic fill + verify
│   │   └── vision_loop/          # Tier 3 — fallback
│   │       ├── loop.py           # OOP — batched perceive/act rounds
│   │       ├── screenshot.py     # Functional — capture + encode
│   │       ├── perceive.py       # Functional — build prompt + parse batch response
│   │       ├── execute.py        # Functional — translate action JSON → Playwright
│   │       └── verify.py         # Functional — tri-state DOM verification
│   ├── db/
│   │   ├── models.py             # SQLAlchemy models (all with user_id)
│   │   ├── migrations/           # Alembic migrations
│   │   └── session.py            # Async session factory
│   ├── services/
│   │   ├── storage.py            # OOP — S3 screenshot upload
│   │   ├── browser.py            # OOP — Browserbase session management
│   │   └── cache.py              # OOP — Redis client
│   ├── workers/
│   │   └── tasks.py              # Celery task definitions
│   └── config.py                 # pydantic-settings config
├── extension/                    # Chrome MV3 extension (existing)
│   ├── manifest.json
│   ├── popup.html / popup.js
│   ├── content.js
│   └── background.js
├── frontend/                     # Next.js dashboard
│   ├── app/
│   │   ├── dashboard/
│   │   ├── applications/[id]/    # Step-by-step replay UI
│   │   └── profile/
│   └── components/
└── tests/
    ├── agents/
    │   ├── test_fit_scorer.py
    │   ├── test_jd_miner.py
    │   └── test_vision_loop.py
    └── api/
        └── test_applications.py
```

---

## Architecture Philosophy

### Critical Design Principle: Runtime-Read, Never Hardcoded

**NEVER hardcode CSS selectors, XPath, or per-ATS field maps.**

The failure mode that kills competitors is a *static map* of field selectors shipped with the product — it breaks the day Workday changes its HTML. Reading the **live** page at runtime does not have that failure mode, whether you read it as pixels or as DOM. Both adapt because both look at what is actually there.

The agent therefore has three tiers, cheapest first:

1. **Tier 1 — Known schema (Greenhouse/Lever/Ashby):** fetch the posting's authoritative question list from the ATS's public API before opening a browser. Planning data only; submission always goes through the real form.
2. **Tier 2 — DOM-serialized fill (default):** serialize the live form's fields at runtime (labels, types, options — via generic element queries, never a stored map), map every field to an answer in one cheap model call, fill deterministically, verify each value by readback.
3. **Tier 3 — Vision loop (fallback):** screenshot → perceive → act, for canvas widgets, obfuscated DOM, or any page where Tier 2 fails verification. This is the moat for hard pages, not the toll on every page.

```
Tier 1 schema (if known ATS) ─┐
                              ├→ Tier 2 DOM fill → verify → done
Live DOM serialization ───────┘        │ fails
                                       ▼
                              Tier 3 vision loop → verify → done
```

**Why not vision for everything:** a 1280×800 screenshot costs ~1,365 input tokens *per perceive call*. Serializing the same form as text costs ~800–1,500 tokens **once**. Vision is the right tool when pixels carry information the DOM doesn't — which is the exception, not the rule.

**What never changes:** the fit gate, per-JD tailoring, the full screenshot audit trail (every action still screenshots to S3 regardless of tier), and the human review gate. Those are independent of how targeting happens.

### Sensitive Questions Are Never Auto-Answered

Demographic/EEO questions (race, gender, veteran status, disability, and similar) and legal attestations are **never** answered by the agent. The mapper is instructed to skip them, and a deterministic keyword guard in `dom_fill/mapper.py` overrides the model if it tries anyway. They surface in the review UI as "needs your answer."

### Paradigm Guidelines

Use **functional** for:
- `screenshot.py` — pure transform: `page → bytes → base64 dict`
- `perceive.py` — pure transform: `screenshot + context → Claude prompt → action dict`
- `execute.py` — pure dispatch: `action dict + page → playwright call`
- `verify.py` — pure check: `page state → success | stuck | error`
- `fit_scorer.py` — pure scoring: `profile + jd → float`
- All extractors, validators, parsers, prompt builders

Use **OOP** for:
- `orchestrator.py` — coordinates sub-agents, holds run state
- `loop.py` — manages the step loop, history, retry logic
- `jd_miner.py` — HTTP client, Browserbase session lifecycle
- `tailoring_engine.py` — Anthropic client, prompt templates
- `browser.py` — Browserbase session management
- `storage.py` — S3 client, presigned URLs

**Decision matrix:**

| Characteristic | Use Functional | Use OOP |
|---|---|---|
| Pure transform (input → output) | ✅ | ❌ |
| No side effects | ✅ | ❌ |
| Composable pipelines | ✅ | ❌ |
| Holds external client (API, S3, Redis) | ❌ | ✅ |
| Manages session lifecycle | ❌ | ✅ |
| Needs retry / backoff state | ❌ | ✅ |
| Configuration-driven behavior | ❌ | ✅ |

### Python Pattern: Functional (analyzers, transforms)

```python
# agents/vision_loop/perceive.py

PERCEIVE_PROMPT_TEMPLATE = """
You are controlling a browser to complete a job application.
Look at this screenshot carefully.

Current task: {task}
Fields already filled: {filled_fields}
Candidate profile: {profile_summary}

Identify the NEXT single action to take. Reply ONLY with JSON:
{{
  "action": "click" | "type" | "select" | "scroll" | "done" | "error",
  "x": <pixel x — center of element>,
  "y": <pixel y — center of element>,
  "value": "<text to type or option label to select>",
  "field_name": "<human-readable field name>",
  "reasoning": "<one sentence>",
  "confidence": 0.0-1.0,
  "done": false
}}
"""

def build_perceive_prompt(
    task: str,
    filled_fields: list[str],
    profile_summary: str,
) -> str:
    """
    Build the Claude perceive prompt.
    @pure — output depends only on inputs
    """
    return PERCEIVE_PROMPT_TEMPLATE.format(
        task=task,
        filled_fields=filled_fields,
        profile_summary=profile_summary,
    )


def encode_screenshot(png_bytes: bytes) -> dict:
    """
    Convert raw PNG bytes to Anthropic image message block.
    @pure
    """
    import base64
    return {
        "type": "image",
        "source": {
            "type": "base64",
            "media_type": "image/png",
            "data": base64.standard_b64encode(png_bytes).decode("utf-8"),
        },
    }


def parse_action_response(raw_text: str) -> dict:
    """
    Parse and validate Claude's JSON action response.
    @pure — raises ValueError on invalid schema
    """
    import json
    action = json.loads(raw_text)
    required = {"action", "reasoning", "confidence", "done"}
    if not required.issubset(action.keys()):
        raise ValueError(f"Missing required keys: {required - action.keys()}")
    if action["action"] not in {"click", "type", "select", "scroll", "done", "error"}:
        raise ValueError(f"Unknown action: {action['action']}")
    return action
```

### Python Pattern: OOP (services, loop runner)

```python
# agents/vision_loop/loop.py

class VisionActionLoop:
    """
    Orchestrates the screenshot → perceive → act → verify loop
    for a single ApplicationRun session.
    """

    def __init__(
        self,
        anthropic_client: anthropic.AsyncAnthropic,
        storage: StorageService,
        max_steps: int = 30,
        wait_ms: int = 800,
    ):
        self.client = anthropic_client
        self.storage = storage
        self.max_steps = max_steps
        self.wait_ms = wait_ms
        self._steps: list[StepLog] = []

    async def run(
        self,
        page: Page,
        task: str,
        profile: UserProfile,
    ) -> list[StepLog]:
        filled: list[str] = []

        for step_num in range(self.max_steps):
            # 1. Screenshot (functional)
            png = await page.screenshot(type="png", full_page=False)

            # 2. Perceive (functional)
            prompt = build_perceive_prompt(task, filled, summarize_profile(profile))
            response = await self.client.messages.create(
                model="claude-opus-4-5",
                max_tokens=512,
                messages=[{
                    "role": "user",
                    "content": [
                        encode_screenshot(png),
                        {"type": "text", "text": prompt},
                    ],
                }],
            )
            action = parse_action_response(response.content[0].text)

            # 3. Store screenshot
            screenshot_url = await self.storage.upload_screenshot(
                png, run_id=task, step=step_num
            )

            # 4. Log step
            step_log = StepLog(
                step_number=step_num,
                action=action,
                screenshot_url=screenshot_url,
                success=True,
            )
            self._steps.append(step_log)

            # 5. Terminal conditions
            if action["done"]:
                break
            if action["action"] == "error":
                raise AgentError(action["reasoning"])

            # 6. Act (functional dispatch)
            await execute_action(page, action)
            filled.append(action.get("field_name", ""))

            # 7. Wait for React re-renders
            await page.wait_for_timeout(self.wait_ms)

        return self._steps
```

---

## Workflow Trigger

When asked to implement a feature, always follow this order:

1. **Schema** — Pydantic model (API) and SQLAlchemy model (DB)
2. **Types** — TypedDict or dataclass for internal data structures
3. **Test** — pytest test for happy path AND failure path
4. **Logic** — Implementation

---

## Definition of Done (Production Grade)

Before outputting code, verify all of these:

1. **Types:** All function signatures have full type hints. No `Any` unless unavoidable with explicit comment.
2. **Tests:** Happy path + at least one failure path covered with `pytest`.
3. **Error handling:** All async calls wrapped in try/except. Errors logged with `structlog`, not `print`.
4. **No hardcoded selectors:** If you are writing a CSS selector for interaction (not verification), stop and use vision instead.
5. **Viewport consistency:** Any code that takes a screenshot must use `1280×800`. Any prompt that references coordinates must state the viewport size.
6. **Step logging:** Every agent action appended to `ApplicationRun.steps[]` before the next screenshot.
7. **Secrets:** All API keys, credentials, and connection strings via environment variables validated at startup by `pydantic-settings`.

---

## Python Standards

1. **Type hints:** Every function and method — no exceptions.
2. **Async-first:** All I/O (Playwright, HTTP, DB, S3) must use `async/await`. Never block the event loop.
3. **Structured logging:** Use `structlog`. Never `print()` or bare `logging.info()`.
4. **Environment variables:** `pydantic-settings` config class validates all env vars at startup. App fails fast if misconfigured.
5. **Error handling:** Use typed exceptions (`AgentError`, `FitThresholdError`, `BrowserError`). Catch specific exceptions, not bare `except:`.
6. **Pydantic everywhere:** All external data (Claude API responses, webhook payloads, DB rows) passes through a Pydantic model before use.

```python
# config.py — validated at startup, fails fast
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    anthropic_api_key: str
    browserbase_api_key: str
    database_url: str
    redis_url: str
    s3_bucket: str
    s3_region: str
    fit_threshold_default: int = 70
    vision_loop_max_steps: int = 30
    vision_loop_wait_ms: int = 800

    class Config:
        env_file = ".env"

settings = Settings()  # Raises ValidationError at import if missing
```

---

## Critical Implementation Rules

### 1. Viewport Lock

```python
# ALWAYS set this exact viewport — never deviate
context = await browser.new_context(
    viewport={"width": 1280, "height": 800},
    user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) ...",
    locale="en-US",
)
```

Claude's x,y coordinates are calibrated to this viewport. Any other size causes click misalignment.

### 2. The 800ms Wait is Non-Optional

```python
await execute_action(page, action)
await page.wait_for_timeout(800)   # React/Angular re-render cycle
# Screenshot AFTER this wait — never before
```

Without this, Claude screenshots mid-animation and hallucinates form state.

### 3. Filled Fields Memory

```python
# Pass filled_fields into every perceive call
# Without this, Claude re-fills fields it already completed
prompt = build_perceive_prompt(task, filled_fields=filled, ...)
```

Claude has no state between API calls. This list is its memory.

### 4. Fit Gate Before Vision Loop

```python
# orchestrator.py
fit_score = score_fit(profile, jd)  # functional
if fit_score < settings.fit_threshold_default:
    raise FitThresholdError(f"Score {fit_score} below threshold {settings.fit_threshold_default}")
# Only reach vision loop if fit passes
await self.vision_loop.run(page, task, profile)
```

Never run the vision loop on a low-fit job. This is the product's core quality promise.

### 5. Image Block Order in Claude Calls

```python
# Image FIRST, text prompt SECOND — Claude attends better this way
messages=[{
    "role": "user",
    "content": [
        encode_screenshot(png),          # ← image first
        {"type": "text", "text": prompt} # ← instruction second
    ],
}]
```

### 6. Anti-Bot Headers

```python
# Without these, Greenhouse and Workday block on first page load
args = [
    "--no-sandbox",
    "--disable-blink-features=AutomationControlled",
    "--disable-infobars",
]
```

---

## Common Pitfalls — Never Do These

❌ **Never** hardcode a per-ATS selector map or XPath — serialize the live DOM at runtime, or use vision  
❌ **Never** auto-answer a demographic/EEO or legal-attestation question — skip it for the user  
❌ **Never** send a screenshot to the model when the DOM already answers the question — that's ~1,365 tokens per call  
❌ **Never** add a `cache_control` breakpoint to a prefix below the model's minimum cacheable size — it silently never caches (verify with `usage.cache_read_input_tokens`)  
❌ **Never** let a run retry after `StuckLoopError` or `RateLimitExceededError` — both burn money for a guaranteed-identical outcome  
❌ **Never** call `page.screenshot()` immediately after an action — always `wait_for_timeout(800)` first  
❌ **Never** skip the fit score gate — the quality promise depends on it  
❌ **Never** pass raw LLM text directly to Playwright — always `parse_action_response()` first  
❌ **Never** hardcode API keys — all secrets via `pydantic-settings`  
❌ **Never** let an `ApplicationRun` move to `submitted` without user review — status must pass through `review`  
❌ **Never** use `print()` — use `structlog.get_logger().info()`  
❌ **Never** use a different viewport than `1280×800` — coordinate calibration breaks  

✅ **Always** log every step to `ApplicationRun.steps[]` with screenshot URL  
✅ **Always** pass `filled_fields` into every Claude perceive call  
✅ **Always** validate Claude's JSON response through `parse_action_response()` before using it  
✅ **Always** run fit scorer before starting the vision loop  
✅ **Always** upload screenshots to S3 — local paths are ephemeral  
✅ **Always** wait 800ms after every action before the next screenshot  
✅ **Always** use Browserbase for production browser sessions — never raw Playwright in prod  
✅ **Always** record `response.usage` into the run's `UsageTracker` on every Claude call — cost you don't measure you can't manage  
✅ **Always** treat "field not locatable" as unknown (`None`), not as failure — a false verification failure escalates to the expensive model  

---

## Week-by-Week Build Plan

| Week | Deliverable |
|---|---|
| 1 | DB schema + Pydantic models + FastAPI scaffold + `/health` endpoint |
| 1 | `fit_scorer.py` (pure functions) + full test coverage |
| 2 | `jd_miner.py` — fetch + extract JD text from any URL |
| 2 | `tailoring_engine.py` — cover letter + bullets via Claude |
| 3 | `vision_loop/` — screenshot → perceive → execute → verify |
| 3 | Integration test: full loop on a static Greenhouse clone |
| 4 | `orchestrator.py` — end-to-end flow wired together |
| 4 | Browserbase integration + S3 screenshot storage |
| 5 | Celery queue + async ApplicationRun execution |
| 5 | Dashboard: application list + step-by-step replay UI |
| 6 | Chrome extension → dashboard integration |
| 6 | Review gate UI + submit confirmation flow |

**MVP success criteria:**
- Vision loop completes a Greenhouse application end-to-end without human intervention
- Fit scorer gates correctly — zero applications submitted below threshold
- Step replay shows every screenshot + Claude reasoning in the dashboard
- No hardcoded selectors anywhere in `vision_loop/`

---

## Key Design Decisions (Locked)

| Decision | Choice | Reason |
|---|---|---|
| Navigation | DOM-serialized fill first, vision fallback | ~10× cheaper on the common path; vision reserved for pages that need it |
| Vision model | `claude-sonnet-5` | Strong UI reasoning at $2/$10 vs Opus $5/$25; escalates to `claude-opus-5` on a screen whose fields fail verification |
| Tailoring model | `claude-sonnet-5` | Quality matters here — this text is the product |
| Extraction / mapping model | `claude-haiku-4-5` | Structured extraction from text; cheapest tier is sufficient |
| Tailoring calls | One merged call | Cover letter + bullets share the same profile/JD context; sending it twice was pure waste |
| Structured outputs | `output_config.format` everywhere | Schema-guaranteed JSON; removes code-fence-stripping fragility |
| Browser infra | Browserbase (`BROWSER_MODE=local` for dev) | Anti-bot in prod; local Chromium in dev/test consumes no paid session minutes |
| Queue | Celery + Redis | Proven async execution with retry logic |
| Screenshot storage | WebP q80, full resolution | Measured ~2.8× smaller than PNG on real ATS screenshots with no downscaling. **Not JPEG** — on flat UI screenshots JPEG encodes *larger* than PNG |
| Screenshots sent to the model | PNG, only on the vision tier | Model input stays lossless; storage compression is a separate concern |
| Viewport | 1280×800 | Standard laptop; ATS forms designed for this size |
| Max rounds per vision loop | 30 | Prevents infinite loops; each round now fills many fields |
| Per-run token budget | 150K | Hard ceiling — the loop stops into `review` rather than burning past it |
| Stuck detection | 3 identical screens / 3 identical batches / 2 low-confidence rounds | A dead run costs ~2 calls instead of 30 |
| Post-action wait | 800ms between rounds, 200ms between actions in a batch | Full re-render only needs to settle before the next screenshot |
| Fit threshold | 70% default, user-configurable | Eliminates <1% callback rate problem of spray-and-pray tools |
| Daily cap per platform | 20 per user | Protects users from ATS bot detection — the scarcer resource than API budget |

---

## Success Metrics (MVP Complete)

- Vision loop completes Greenhouse/Lever/Workday forms end-to-end: ✅
- Zero selector-based interactions in production code: ✅
- Fit gate rejects applications below threshold 100% of the time: ✅
- Full step audit trail in S3 for every ApplicationRun: ✅
- User review gate before any `submitted` status transition: ✅
- P95 loop completion time < 120 seconds per application: ✅
- Step replay loads in dashboard with screenshots: ✅
