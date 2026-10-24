# Night Shift Hackathon: Project Brief for Claude Code

> Historical pre-build brief: the tenancy-checker direction and proposed learning loop are context, not the shipped product. Start with the [current documentation](README.md).

23 Oct 2026 · Nick

*Snapshot of the team's Claude Doc brief, exported 23 Oct 2026.*

## How to use this doc

We are building, in 36 hours at the Night Shift hackathon, an app that runs one recurring long-document review task through Mubit and visibly turns human corrections into better task-specific models. The leading candidate is a UK tenancy agreement compliance checker, but the domain is not locked: alternatives are in the Alternatives section and the architecture is meant to be domain-agnostic.

This doc is the full context handover for the Claude Code session that will implement the project. Read it end to end before writing code.

**Decided**

- Every LLM call goes through Mubit (hard rule).
- One narrow, repeated task with a fixed system prompt and fixed output schema, not "contract review in general".
- Long documents are split into clauses or chunks, and each chunk is its own call.
- Synthetic documents with deliberately planted issues give us ground-truth labels and an honest accuracy metric.
- The demo is designed around the correction → model update moment, because that is judging criterion #1.

**Still open**

- Final domain: tenancy (leading), insurance "am I covered?", NDA triage, or another.
- Whether our app can call a trained adapter directly, or only through the Mubit console. This decides the router design.
- How corrections are submitted to Mubit. Public docs only show Good/Bad ratings.
- Team size and members.

**Working conventions for Claude Code**

- No project code may exist before 19:30 Friday 23 Oct 2026. Research and notes are fine before then.
- The repo must be public on GitHub. Its URL is captured at team creation.
- Never commit API keys. Use a `.env` file listed in `.gitignore`.
- Nick wants direct, honest critique. Flag weak decisions instead of agreeing.
- No em dashes in any written output (README, deck text, UI copy).

## Event logistics and deadlines

The hard deadline is the code freeze at 05:00 Sunday 25 Oct (Discord rules). Aim to submit by midnight Saturday. All times are London.

- **Event:** Night Shift, a 42-hour overnight hackathon hosted by Mubit. It doubles as Mubit's product launch.
- **Venue:** WeWork, 9th floor, 30 Churchill Place, Canary Wharf, London E14 5RE. Mubit's own office is also at this WeWork.
- **Team:** 1 to 4 people, solo allowed. 18+, in person only.
- **Bring:** laptop, charger, photo ID, toiletries, and a sleeping bag if staying. Food is covered for all 42 hours, and you can go home and come back.
- **Team setup** via Max, the AI bot in the Mubit Discord. Read #night-shift-info first. One person runs `/team create` with the team name and a **public GitHub repo URL**, Max returns a join code, teammates run `/team join`, then everyone runs `/team accept`.

| When (London) | What |
|---|---|
| Fri 17:00 | Doors open, check-in |
| Fri 18:00 | Kickoff: Mubit walkthrough, tracks and rules. Ask the kickoff questions (Risks section) here |
| Fri 19:00 | Dinner and team matching |
| Fri 19:30 | Hacking starts. First line of project code allowed |
| Sat all day | Office hours with the Mubit team |
| Sat by 12:00 | Check-in 1 (via Max) |
| Sat 12:00 to 18:00 | Check-in 2 |
| Sat 20:00 | Submissions open (`/submit`) |
| Sat 24:00 | Target submission time |
| Sun 01:00 | Mubit's daily training limit resets (00:00 UTC). Clocks go back at 02:00 Sun |
| Sun 05:00 | **Code freeze**: hard deadline for code and submissions |
| Sun 10:30 | Judging round 1 (expo) |
| Sun 12:30 | Finalist demos on stage |
| Sun 13:30 | Awards |

**Schedule conflict:** the Luma page says the code freeze is 10:00 Sunday and submissions close then. The Discord rules say 05:00 Sunday and ask for submissions by midnight Saturday. The organizers' calls are final, so plan for 05:00 and confirm at kickoff.

**Training limit reset:** Mubit's limits reset at 00:00 UTC, which is 01:00 London on Friday and Saturday nights (BST, UTC+1). Getting the first training in before 01:00 Friday night uses Friday's allowance and keeps Saturday's free for retraining.

## Rules, submission and judging

The project must send all its LLM calls through Mubit, and the demo must show a human correction becoming a model update. Everything else is free.

**The brief:** build a product that sends its LLM calls through Mubit and turns your corrections into model updates for a recurring task.

**Tracks** (top 3 prizes are judged across all tracks, so the track doesn't limit prize chances):

1. **Recurring tasks:** a task the product runs again and again (extraction, triage, support replies, review, routing). Show corrections becoming model updates.
2. **Own your intelligence layer:** move a workload from a closed model onto a task-adapted open model. Show quality, cost and latency side by side.
3. **Fast refresh:** a workload that keeps changing (new data, customers, domains). Show model updates keeping pace.

A document-review project fits track 1 directly and can cover track 2 with a cost/latency comparison panel.

**Judging: four criteria, weighted equally**

1. **Use of Mubit:** show a correction turning into a model update in the demo.
2. **Usefulness:** a real recurring task someone would want handled.
3. **Technical execution:** it works, and it holds up under questions.
4. **Demo:** clear, live, and under the time limit (length not stated; ask at kickoff).

**Hard rules**

- All project code is written during the event, from 19:30 Friday. Open-source libraries and our own tooling are fine.
- Every project sends its LLM calls through Mubit.
- Two check-ins on Saturday: by 12:00, and between 12:00 and 18:00. A missed one can be made late, up to the code freeze.
- Repo URL is captured at team creation.
- At least one team member must be at Sunday's demos to win.
- Organizers' calls are final.

**Submission**

- Via `/submit` in Discord, open from Saturday 20:00. Resubmitting is allowed until the freeze, and the latest one counts.
- Two uploads, both required: an **MP4 or MOV video** and a **PDF deck**. YouTube links are not accepted.
- Uploads after the 05:00 Sunday freeze count only if an organizer accepts them.

**Not restricted by the rules:** sector or domain, base model, architecture, or consumer vs business product.

**Prizes and why winning matters**

- Cash: $15,000 / $10,000 / $5,000, plus $35,000 in AI credits (OpenAI and others). Mubit announced $10K+ more on launch day.
- $1.5M in Mubit credits shared across accepted hackers.
- Winners get a direct interview with Mubit's co-founders, and Mubit is hiring from attendees generally.

## What Mubit is and how it works

Mubit is a pass-through proxy that records your LLM calls, groups them into tasks, and trains a small open-model adapter per task that learns to imitate the closed model. The pitch is "stop renting intelligence, own it": once an adapter matches the closed model on a task, that task can run cheaper, faster and on a model you control.

Think of it as an apprentice watching an expert. GPT (the expert) does the real work and gets paid. Mubit records every question and answer. Once the apprentice has seen enough and passes a test, it can take over that one job.

**Company background**

- London startup (Canary Wharf WeWork), founded late 2025 by Shankha Dutta and Anil Peri, seed-funded (Hoxton Ventures, Heavybit).
- Started as an agent memory layer (durable memory, lessons, context for agents). It also has Minima, an open-source tool that recommends the cheapest model per task based on logged outcomes. The gateway plus adapters is the product they are launching at this event.
- Launched on event night: **Banyan Sapling**, an open-weight model that checks whether a claim is supported by a policy and evidence, with labels supported / violation / insufficient_information / inconsistent_context (base Qwen3-30B-A3B, attention LoRA plus a verification head, trained partly on ContractNLI, run on an H200, about 46 GB). And **Latte Bench**, a benchmark of whether models improve from feedback.

**The flow, from one user prompt** (*docs* = stated in Mubit's docs, *inferred* = our reading)

1. The user types a request in our app.
2. Our backend builds the call: a fixed system prompt plus the user content (e.g. one clause). It uses the normal OpenAI, Anthropic or Gemini SDK with Mubit's base URL and our Mubit key. It must run server-side, since the API answers no CORS preflight. *(docs)*
3. Mubit's gateway checks the Mubit key, swaps in our provider key (or the starter credit's), strips `x-middleware-*` headers and cookies, and forwards the call. *(docs)*
4. The closed model (GPT, Claude, Gemini) answers. The reply streams back through Mubit unchanged. **No open model is involved yet.** *(docs)*
5. Mubit records the request and reply, a request ID (`mreq_…`), a session ID, and a task fingerprint. *(docs)*
6. **Task grouping:** calls with the same model, instructions (system prompt), tools, tool choice and output format form one task. User messages, temperature and max_tokens don't count. Whitespace, numbers, dates, times and IDs in the instructions don't split a task, but other varying words do. *(docs)*
7. **Curation:** Mubit accepts some calls as "kept examples". Not every call is kept, and it sets some aside as test cases, separated by session. *(docs)*
8. **Trigger:** by default a task first trains at 25 kept examples, if the daily training limit and the pause between trainings allow. Status goes Collecting examples → Reviewing examples → Training → Testing. *(docs)*
9. **Training:** a LoRA-style adapter is trained on a frozen open base model, on Mubit's GPUs. The closed model's answers are effectively the labels, i.e. distillation. *(adapter testing is docs; labels and hardware are inferred)*
10. **Testing:** each version is graded on held-out test cases against the provider model's answers. Results: `Passed`, `Below target` (e.g. "Matched X% … needs Y%"), `Malformed tool calls`, `Prompt only` (the base model did as well with just the prompt, so no adapter was needed) or `Not tested`. *(docs)*
11. **Comparing:** a passing version can be compared side by side with the provider model in the console's **Try models** page. The first start of an adapter can take minutes. *(docs)*
12. **Refresh:** after a version, the next one trains once enough new examples arrive ("Next: a new version after N new examples"). There is no retry button; recovery is always new, different calls. *(docs)*
13. **Production switch:** the public docs give no way for our app to call an adapter. There is no Mubit model ID, and adapters are tried only in Try models. The hackathon build may expose more. **Ask at kickoff.** *(docs + open question)*

**What this means for us**

- During the event, every call our app makes still goes to the closed model. The value we demonstrate is the adapter catching up, plus the cost and latency it would save.
- Mubit teaches the adapter to copy the closed model. Our human corrections are the extra signal that should make it better than the closed model on the cases the closed model gets wrong. How Mubit ingests corrections is the key thing to confirm.
- Mubit's docs describe a "Rate this reply: Good / Bad" control per call in Requests. That is the only documented feedback mechanism.

## Mubit integration reference

Integration is a base URL and key swap. The real constraints are task fingerprinting, example counts and daily limits. Full docs: [docs.mubit.ai](https://docs.mubit.ai/), and for an LLM-readable dump, [llms-full.txt](https://docs.mubit.ai/llms-full.txt). Console: [app.mubit.ai](https://app.mubit.ai/). Use the base URL the console's **Connect** page shows if it differs from below.

**Base URLs and auth**

| Provider | SDK base URL | Key header |
|---|---|---|
| OpenAI | `https://api.mubit.ai/openai/v1` | `Authorization: Bearer <MUBIT_KEY>` |
| Anthropic | `https://api.mubit.ai/anthropic` (no `/v1`, the SDK adds it) | `x-api-key` or `Authorization: Bearer` |
| Gemini | `https://api.mubit.ai/gemini` (no `/v1beta`) | `x-goog-api-key` (never `?key=`) |
| OpenRouter / Groq / Together / Mistral | `https://api.mubit.ai/compat/{service}/v1` | `Authorization: Bearer` |

- Mubit keys start with `mbt_`. Two kinds exist: **Inference** (needed for calls) and **Read only** (calls get `403 key_permission`).
- Send only the Mubit key. A provider key, a sign-in token or a second key in the same call gets a `401`. Unset `ANTHROPIC_AUTH_TOKEN` / `GOOGLE_API_KEY` if they hold other credentials.
- Provider keys are added in the console under **Provider keys**, admins only. Otherwise calls use the **starter credit**, which serves a fixed model list, e.g. `gpt-6-luna`, `claude-haiku-4-5`, `gemini-3.8-flash`. Other models get `400 starter_credit_model`, and hosted tools like web search are refused.
- Model IDs stay as they are. Mubit strips date suffixes and `-latest` when grouping. **There is no Mubit model ID for adapters.**
- Server-side calls only, since browsers are blocked by CORS.

**Minimal call** (Python, OpenAI SDK, with a session per document)

```python
import os
from openai import OpenAI

client = OpenAI(
    base_url="https://api.mubit.ai/openai/v1",
    api_key=os.environ["MUBIT_API_KEY"],
)

SYSTEM_PROMPT = "..."  # FROZEN. Any change creates a new Mubit task.

resp = client.chat.completions.create(
    model="gpt-6-luna",
    messages=[
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": clause_text},  # variable content goes HERE
    ],
    response_format={"type": "json_object"},  # part of the task fingerprint, keep constant
    metadata={"session_id": f"doc-{doc_id}"},
)
# To get Mubit's request ID, call client.chat.completions.with_raw_response.create(...)
# and read raw.headers["x-middleware-request-id"]. resp._request_id is OpenAI's ID, not Mubit's.
```

The environment-variable alternative needs no code change: `OPENAI_BASE_URL=https://api.mubit.ai/openai/v1` and `OPENAI_API_KEY=$MUBIT_API_KEY`.

**Task fingerprint rules (critical)**

- A task is defined by model + system prompt + tools + tool choice + output format. Freeze all five before generating bulk traffic.
- Never put per-document text (names, addresses, clause text) in the system prompt. Varying words there split the task into many tiny ones. Numbers, dates and IDs are tolerated.
- Each distinct pipeline step (classify clause, check rule, summarise) is its own task with its own adapter. Fewer, high-volume steps reach training sooner.
- The task's display name is taken from the first words of the system prompt, so start it with a meaningful phrase.

**Sessions**

- Session ID comes from the first present of: `metadata.thread_id`, `metadata.session_id`, `metadata.conversation_id`, Anthropic's `metadata.user_id`, or OpenAI Responses' `prompt_cache_key`. Otherwise it is derived from the instructions plus the first user message.
- Test cases are set aside by session, so use one session per document. That stops a document's clauses leaking between train and test.

**Headers**

- Request: `x-middleware-store: false` or `x-middleware-record: metadata|off` reduces recording. **Never set these on calls we want trained on**, since unrecorded calls never become kept examples.
- Response: `x-middleware-request-id` (`mreq_` + 32 hex) on every answer. Store it next to each result so corrections can be linked to calls. `retry-after` comes on `429` and `503`.

**Limits and timings that affect the demo**

| Limit | Value | Impact |
|---|---|---|
| First training threshold | 25 kept examples (default) | Send 100+ diverse calls Friday night |
| Daily training limit | Unknown count, resets 00:00 UTC (01:00 London) | Get v1 trained before 01:00 Friday night |
| Pause between trainings | Unknown length | Can't retrain on demand during the demo |
| Retraining after a version | Needs N new examples | Save fresh data and corrections for v2 |
| Try models calls | Daily per-org limit | Don't burn them while testing |
| Adapter starts | 3 per org per UTC day, minutes each | Warm the adapter before the demo |
| Long examples | "examples too long to train on" can block training | Chunk documents into clauses |

**Console pages:** Requests (filters by task, served-by, errors, session; Good/Bad rating per call), Tasks (status, example counts), Adapters → History (test result per version, "Compare with your provider"), Try models (side by side, calls not stored), Overview, Import past calls (Langfuse, Braintrust, Pydantic Logfire, admins only).

**Common errors:** `missing_key`, `invalid_key`, `middleware_key_refused`, `provider_key_missing` (403), `starter_credit_model` / `starter_credit_route` / `starter_credit_tools`, `unknown_route` (404), `admin_path_refused` (403). Mubit's own errors have `type: middleware_gateway_error`.

**Claude Code through Mubit** (side quest bonus, optional): needs our own Anthropic API key under Provider keys. Pro or Max sign-ins are refused. Set `ANTHROPIC_BASE_URL=https://api.mubit.ai/anthropic`, `ANTHROPIC_AUTH_TOKEN=$MUBIT_API_KEY`, `CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC=1`, `ANTHROPIC_DEFAULT_HAIKU_MODEL=claude-haiku-4-5`, and unset `ANTHROPIC_API_KEY`. Test with `claude -p "Reply with exactly: pong"`. Keep this separate from the product's own calls so the coding traffic doesn't create noise tasks in the project, or confirm Mubit gives a separate project.

## Leading candidate: tenancy agreement compliance checker

The leading idea is a checker that splits a UK (England) residential tenancy agreement into clauses, flags clauses that break current law, and learns from reviewer corrections through Mubit. It is the closest to implementable in 36 hours, but it is not locked.

**Why it fits the judging**

- **Recurring task:** one fixed check per clause, hundreds of clauses per day for any agency. That is exactly what Mubit adapters are for.
- **Checkable answers:** each clause gets a label from a fixed list, so accuracy is measurable and corrections are unambiguous.
- **Long documents:** agreements run 10 to 30 pages, so the closed model's cost per document is large and the savings story is strong.
- **Relatable:** judges and students rent. Nick has signed London tenancies, so he knows the documents.
- **Timely:** the Renters' Rights Act 2025 came into force on 1 May 2026, which abolished section 21 "no fault" evictions, ended assured shorthold tenancies, and turned existing tenancies into periodic ones with no end date ([source](https://www.houst.com/blog/renters-rights-act-2026)). Many agreements and templates still in circulation contain clauses written for the old regime. That gives agencies a real, current reason to re-check documents at volume.

**Who the product is for (both audiences, one engine)**

- **Consumer:** a renter uploads their agreement and gets red flags in plain English: unlawful fees, an oversized deposit, outdated clauses.
- **Firm:** letting agencies, property managers, councils, advice charities and proptech platforms check hundreds of agreements before sending them, or audit a portfolio after the law change.
- Mubit counts volume per app, not per person. 50,000 renters each uploading one agreement is still 50,000 runs of the same task. The firm side supplies the business model and the reviewer corrections.

**Candidate rule checklist** (England only; verify each rule against legislation before relying on it)

| Rule | What to flag | Status |
|---|---|---|
| Tenant Fees Act 2019, permitted payments | Any fee not on the permitted list (rent, deposit, holding deposit, utilities, council tax, TV licence, communication services, tenant-requested variation, tenant-requested early termination, default fees) | Verified ([Oxford City Council](https://www.oxford.gov.uk/info/20267/private_housing_tenants/1327/tenant_fees_act_2019), [legislation.gov.uk](https://www.legislation.gov.uk/ukpga/2019/4/schedule/1/enacted)) |
| Holding deposit cap | Holding deposit above 1 week's rent | Verified ([legislation.gov.uk](https://www.legislation.gov.uk/ukpga/2019/4/schedule/1/enacted)) |
| Variation fee cap | Fee to change the tenancy above £50, unless reasonable costs are higher | Verified ([Oxford City Council](https://www.oxford.gov.uk/info/20267/private_housing_tenants/1327/tenant_fees_act_2019)) |
| Tenancy deposit cap | Deposit above 5 weeks' rent (annual rent under £50k) or 6 weeks' (£50k+) | Widely known, verify exact wording |
| Deposit protection | No commitment to protect the deposit in a government-approved scheme and give prescribed information within 30 days | Widely known, verify |
| Section 21 / no-fault eviction | Clauses relying on section 21 or a landlord's no-fault right to end the tenancy | Verified, abolished from 1 May 2026 ([source](https://www.augustapp.com/blog/renters-rights-post-commencement)) |
| Fixed term | Fixed-term or AST wording that conflicts with periodic assured tenancies | Verified ([source](https://www.augustapp.com/blog/renters-rights-post-commencement)) |
| Rent increases | Rent review clauses other than the statutory section 13 route | Verified that section 13 is now the only route ([source](https://www.augustapp.com/blog/renters-rights-post-commencement)) |
| Pets | Blanket "no pets" ban with no route to request | Verified that tenants gained a right to request a pet ([Generation Rent](https://www.generationrent.org/2025/11/14/government-announces-date-of-when-section-21-evictions-will-be-abolished-press-release/)); exact test to verify |
| Rent in advance, bidding | Large upfront rent demands | Unverified, check the Act before including |

The checklist is product logic, not legal advice. The UI must say so, and the scope is England only, since Wales and Scotland have different regimes.

**Honest weaknesses**

- Legal correctness is hard to guarantee. Keep the rule set small (5 to 8 rules) and well-sourced rather than broad.
- Synthetic agreements may look too clean. Base them on real public templates (e.g. the government's model tenancy agreement) and vary them.
- Consumer per-user frequency is low. Pitch the firm side as the main customer.

## Alternatives kept open

Any long, repetitive, checkable document task fits the same architecture. Insurance "am I covered?" is the strongest alternative to tenancy. Choose by data availability and how well we can explain the rules, not by novelty.

**What makes a sector a good Mubit fit** (use this to judge any new idea)

1. **Long inputs:** a 10-page document per call makes savings dramatic. A one-line chat message barely saves anything.
2. **Checkable answers:** a fixed label or field makes corrections and accuracy metrics clean. "A nice reply" is subjective.
3. **Data reachable in 36 hours:** a public dataset or believable synthetic data.
4. **Privacy angle:** regulated sectors make "own your model" a real argument, not just a cost argument.
5. **Both audiences:** one engine that serves a consumer question and a firm's bulk workflow.

**Strong alternatives**

| Idea | Consumer side | Firm side | Data | Notes |
|---|---|---|---|---|
| Insurance "am I covered?" | "Is my stolen phone covered by my home insurance?" checked against their 40-page policy | Brokers and insurers triage incoming claims against policy wording | Synthetic claims built on public UK policy wordings (many insurers publish PDFs) | Longest documents, biggest cost centre, same input shape as Banyan Sapling (policy + evidence + claim). Hardest to make realistic |
| NDA triage | Founder checking an NDA before signing | Law firms and in-house legal triage NDAs at volume | ContractNLI is built from NDAs | Proven, safest data. Less emotional. Banyan was trained partly on ContractNLI, so other teams may use it too |
| Employment contracts | "Is this notice period or non-compete normal?" | HR teams and recruitment agencies | Synthetic | Fewer clear-cut rules, harder to score |
| Subscription and service contracts | "What does it cost me to cancel?" (gym, broadband, phone) | Comparison sites, consumer-rights groups | Public T&Cs | Shorter documents, weaker savings story |
| Combined insurance + legal "document compliance engine" | Any of the above | Any of the above | Mix | Good as the pitch vision, but demo one document type deeply. Each type becomes its own Mubit task and adapter |

**Other sectors considered** (high volume, near-identical requests)

| Sector | Recurring work | Catch |
|---|---|---|
| Banking and finance ops | Transaction categorisation, AML/fraud alert triage, KYC checks, invoices | Nick's own domain. Real data locked down, so synthetic only |
| Healthcare admin | Clinical coding, referral triage, discharge summaries | Real data (e.g. MIMIC) needs credentialing that takes days. Safety questions |
| Customer support | Ticket routing, reply drafting | Short messages, small savings, half the room will build it |
| E-commerce catalogues | Product attributes, categorisation, listings | Less "wow" in a demo |
| Logistics and trade | Customs code classification, shipping documents | Judges may not relate |
| Hospitality and travel | Guest messages, reviews, booking changes | Short, cheap calls, weak savings story |
| Trust and safety | Moderation against a policy (fits the Fast refresh track) | Uncomfortable demo content |
| Education | Rubric grading, feedback | Fairness questions |
| Engineering ops | Log, alert and CI failure triage | Crowded, messy data |
| Market events (crypto) | Turn headlines into structured events; price reaction supplies some labels | Novel, but noisy labels draw hard questions |

**Rejected ideas and why**

- **A model that learns how Nick starts coding sessions** (e.g. always opening with clarifying questions). Rejected because one line in CLAUDE.md or a skill does this for about 50 tokens, so the judges' first question would be "why not a prompt?". It also duplicates Mubit's own Side Quest 1, and "correct opener" has no clean metric. The salvageable version was a spec pre-filler that predicts the user's likely answers, measured by % accepted unedited. It was parked in favour of document review.
- **General contract review.** Rejected because a vague prompt trains a weak adapter, many prompts split examples across tasks, there is no fixed answer to score, and the pitch is generic.
- **Replacing the closed model for open-ended reasoning or coding.** Rejected because adapters win on narrow tasks, not general intelligence.

## Proposed architecture

One backend splits each agreement into clauses and sends one fixed-prompt call per clause through Mubit. A review UI captures corrections, which feed the next adapter version. The design is domain-agnostic: swapping tenancy for insurance changes the prompt, the rules and the data, not the pipeline.

![Every clause call goes through Mubit; reviewer fixes feed the next adapter](architecture.svg)

*System architecture · runtime path on top, learning loop below*

The top row is what happens on every call. The bottom row is the learning loop. The dashed feedback arrow is the step whose mechanism we must confirm with Mubit.

**Components**

1. **Ingest:** upload a PDF or DOCX and extract text (`pdfplumber` / `pypdf`, `python-docx`). Keep page numbers for highlighting.
2. **Clause splitter:** deterministic. Split on numbered headings and paragraph breaks with regex, and merge tiny fragments. **No LLM here**, so we don't create an extra Mubit task on long inputs. Each clause gets `doc_id`, `clause_id`, text and position.
3. **Facts pass** (optional second task): extract structured numbers once per document (monthly rent, deposit, holding deposit, fees with amounts) from the payment-related clauses. Rule maths such as "deposit > 5 weeks' rent" is computed in code, never by the LLM.
4. **Clause check (main Mubit task):** one call per clause, with a frozen system prompt, the clause text as the user message, a JSON output, and `metadata.session_id = doc-<id>`.
5. **Results store:** SQLite. Per clause: model output, `x-middleware-request-id`, latency, tokens, cost estimate, model version.
6. **Review UI:** the document with clauses highlighted red / amber / green. Click a clause to see the rule, the explanation and the source link, then **Accept** or **Correct** (change label, rule or explanation).
7. **Corrections store:** the original output, the corrected output, the reviewer and a timestamp, linked to the Mubit request ID.
8. **Feedback to Mubit:** see "Correction loop" below. The mechanism must be confirmed at kickoff.
9. **Eval harness:** runs the held-out labelled set through the closed model and each adapter version (if callable). It reports accuracy, per-rule precision and recall, cost per document and latency p50/p95.
10. **Metrics panel:** versions over time, accuracy vs the closed model, cost per 1,000 clauses, % of traffic the adapter could take.
11. **Router** (stretch, only if adapters are callable): adapter first, escalate to the closed model when the output is `needs_review`, malformed, or low-confidence. The panel shows the adapter's share of traffic growing as corrections accumulate.

**Task design (main clause-check task)**

- Start the system prompt with a meaningful phrase, since Mubit names the task from its first words. For example: "Check one clause of an England residential tenancy agreement against the rules below."
- Put the full rule list (ids, one-line definitions) in the system prompt. It is fixed text, so the task stays stable.
- Output schema (keep it identical across every call):

```json
{
  "clause_type": "rent | deposit | holding_deposit | fees | termination | rent_increase | pets | repairs | other",
  "verdict": "compliant | violation | needs_review",
  "issues": [
    {"rule_id": "TFA_PROHIBITED_FEE", "severity": "high | medium | low", "explanation": "one sentence, plain English"}
  ],
  "amounts": [{"label": "admin fee", "value_gbp": 150}]
}
```

- Labels and rule IDs are fixed enums, so accuracy is computable and corrections are unambiguous.
- Use the same model ID for every call, e.g. `gpt-6-luna` on the starter credit. A different model makes a different task.

**Correction loop: options, in order of preference**

1. **Mubit's own correction API**, if the hackathon build exposes one (the brief says corrections become model updates). Ask at kickoff and use it as designed.
2. **Rate this reply (Good / Bad)** per request, linked by request ID. Documented in the console. Check whether there is an API for it.
3. **Fallback, if neither carries the corrected answer:** keep our own corrections dataset and show the improvement in our eval harness. Possibly also distil corrections into the system prompt's rule notes. But any prompt change creates a new task, so do this only as an explicit "v2 task" and explain it honestly.

**Stack suggestion** (Claude Code may adjust)

- Backend: Python 3.11+, FastAPI, the OpenAI SDK pointed at Mubit, SQLite (via SQLModel), and `pdfplumber`.
- Frontend: React + Vite (or Next.js) with a clean document viewer and side panel. Streamlit only as an emergency fallback, because demo polish is 25% of the score.
- Scripts: `generate_data.py` (synthetic agreements), `send_batch.py` (bulk traffic with sessions), `eval.py` (metrics).
- Config in `.env`: `MUBIT_API_KEY`, `MUBIT_BASE_URL`, `MODEL_ID`.

**Repo layout**

```
README.md                  # what it is, how to run, Mubit usage, demo script
backend/app/main.py        # FastAPI routes: upload, results, corrections, metrics
backend/app/mubit_client.py
backend/app/splitter.py
backend/app/rules.py       # rule ids, definitions, sources, deterministic checks
backend/app/prompts.py     # FROZEN system prompt(s) + version tag
backend/app/db.py
scripts/generate_data.py
scripts/send_batch.py
scripts/eval.py
data/templates/            # public base agreements
data/synthetic/            # generated docs + ground-truth labels (jsonl)
frontend/
```

## Data strategy

Generate synthetic agreements with deliberately planted issues, so every clause has a known correct label. Aim for 300 to 600 diverse clause calls before 01:00 Friday night, and keep a fresh batch back for Saturday's v2.

**Why synthetic with planted issues**

- We get ground truth for free, so the accuracy numbers are honest and not graded by the same LLM.
- We control the mix of compliant and violating clauses, and can deliberately include the subtle cases the closed model gets wrong. Those become the correction demo.
- No real personal data. Mubit records request and reply content by default, so use synthetic names and addresses only.

**Generator design** (`scripts/generate_data.py`, written after 19:30)

1. **Base templates:** public England tenancy templates (e.g. the government's model agreement; check which version reflects the Renters' Rights Act). Collecting and reading them before 19:30 is research, not code, so it's allowed.
2. **Clause variant library:** for each rule, several compliant and several violating phrasings. Write some by hand and paraphrase the rest with an LLM through Mubit, with a different system prompt so it becomes a separate task. The labels come from the variant metadata, never from the LLM.
3. **Document assembly:** pick a template and fill variables: fake names and addresses, monthly rent £800 to £3,500, deposit 4 to 7 weeks' rent, holding deposit 0.5 to 2 weeks. Swap in 0 to 4 violating clauses per document and shuffle formatting and clause order.
4. **Outputs:** document text, a rendered PDF for the demo, and `labels.jsonl` with one row per clause: `doc_id, clause_id, clause_type, verdict, issues[rule_id]`.

**Edge cases to include** (where the closed model is likely to slip)

- Deposit exactly at, just under, and just over 5 weeks' rent (the threshold maths is done in code).
- Prohibited fees disguised under other names: "contract fee", "check-out charge", "admin cost", "referencing contribution".
- Early termination fees requested by the landlord (unlawful) vs by the tenant (permitted, capped at loss).
- Outdated pre-May-2026 wording: section 21 notices, fixed terms, "assured shorthold tenancy", annual rent review clauses.
- Harmless clauses that mention money or eviction but are compliant, to catch over-flagging.

**Splits**

| Split | Size target | Sent how | Purpose |
|---|---|---|---|
| Training traffic | 300 to 600 clauses, Fri night | Normal calls through Mubit, recorded | Feed the first adapter version |
| Fresh batch | 200+ clauses, Sat | Normal calls through Mubit, recorded | New examples Mubit needs for v2 |
| Corrections | 20 to 50 clauses | Reviewed in our UI, fed back via the confirmed mechanism | The demo's correction story |
| Eval set | 100 to 200 clauses, never trained on | Through Mubit with `x-middleware-record: off`, so not recorded | Honest accuracy for the closed model vs each adapter |

- The eval set still goes through Mubit, which satisfies the routing rule, but the record-off header keeps it out of training. Confirm this is acceptable with Mubit.
- One `session_id` per document keeps all of a document's clauses on the same side of Mubit's train/test split.

**Cost sanity check** (estimate): a clause call is about 1,000 to 1,500 input tokens (the system prompt plus the clause) and 100 to 200 output tokens. 600 calls is under 1M tokens, cheap on a small model, but check the starter credit balance before bulk sends.

**Diversity over volume:** Mubit doesn't keep every call, and recovery always needs *new* messages. Near-duplicate clauses waste calls. Vary the wording, length, formatting and context.

## Demo and pitch plan

The demo is built around one moment: a clause the closed model got wrong, a reviewer's correction, and the next adapter version getting it right. Retraining can't happen live, so v2 must be trained before the demo and the moment shown with real recorded artefacts.

**Live demo script** (about 3 minutes; confirm the time limit at kickoff)

1. **Problem (20 s):** since 1 May 2026, agencies must re-check thousands of agreements against new rules. Doing it with a frontier model costs £X per 1,000 agreements and leaks client data to a third party.
2. **Product (40 s):** upload an agreement, and flagged clauses appear with the rule, a plain-English reason and the legal source. Show both views: renter ("what's wrong with my lease") and agency (portfolio of 200 checked).
3. **Mubit (40 s):** in the console, show Requests, the task with its kept-example count, and Adapter History (v1, v2 with test results).
4. **The correction moment (40 s):** a disguised "check-out charge" that the closed model passed. The reviewer marks it as a prohibited fee, and the correction flows to Mubit. Then the v2 adapter in Try models (or via our router) flags it correctly.
5. **Numbers (30 s):** accuracy on the held-out set for the closed model, v1 and v2, plus cost per 1,000 clauses and latency p50. One chart, one table.
6. **Close (10 s):** every document type becomes its own adapter. Insurance policies and employment contracts are next.

**Demo risk controls**

- Warm the adapter in Try models 10 to 15 minutes before judging, since there are only 3 starts per day and each takes minutes.
- Pre-load the demo agreement and keep screenshots of every console screen as a fallback.
- Keep a backup recording of the whole flow in case the Wi-Fi or Mubit fails.
- Use Try models calls sparingly on Saturday, since there is a daily per-org limit.

**Video (MP4 or MOV, required)**

- 2 to 3 minutes, a screen recording with voiceover that follows the live script.
- Record Saturday evening once v2 exists. Re-record before 05:00 Sunday if the numbers improve.

**PDF deck (required, 7 to 9 slides)**

1. Title + one-line pitch.
2. Problem: the volume of agreements, the law change, the cost of frontier models, data privacy.
3. Product: screenshots of the renter and agency views.
4. How it works: the architecture diagram from this doc.
5. The Mubit loop: calls → task → adapter → correction → v2.
6. Results: accuracy, cost and latency vs the closed model.
7. Business model: consumer free tier, agencies paying per document or a subscription.
8. Roadmap: more document types, router in production, more jurisdictions.
9. Team.

**Judge Q&A prep**

- *"Why not just prompt GPT?"* Cost and latency at volume, data control, and corrections that permanently improve the model instead of bloating the prompt.
- *"Open models are worse."* On general tasks, yes. On one narrow task with our corrections, the adapter matches or beats the closed model on our eval set. Show the numbers, including where it still loses.
- *"Is it legally reliable?"* A small, sourced rule set, `needs_review` routes uncertain clauses to a human, and it is not legal advice.
- *"Synthetic data?"* Built from real public templates, with planted issues giving honest ground truth. Real customer data would plug into the same pipeline.
- *"What if the adapter is wrong?"* The router escalates low-confidence outputs to the closed model, and every correction becomes training signal.

## Build timeline and checklist

The critical path is to freeze the prompt by about 21:30 Friday, send bulk traffic by 23:30, and see v1 training before 01:00. Everything else can slip; this can't.

**Friday before 19:30 (research only, no project code)**

- [ ] Join the Mubit Discord, read #night-shift-info, form the team via Max (`/team create` with a public, empty GitHub repo)
- [ ] Collect public England tenancy templates and the legislation pages for each rule. Pick the final 5 to 8 rules
- [ ] Draft the system prompt wording and the output schema on paper
- [ ] List the subtle edge cases for the correction demo
- [ ] Optional: Side Quest 1 model card upload (see Extras)

**Friday 18:00 kickoff**

- [ ] Ask the Mubit team every question in the Risks section, especially direct adapter inference and the correction mechanism
- [ ] Create the Mubit key and check the starter credit and allowed models in the console

**Friday 19:30 to 21:30: pipeline and frozen task**

- [ ] Scaffold the repo (backend, scripts, `.env`, `.gitignore`, README stub)
- [ ] `mubit_client.py` with session metadata and request-ID capture
- [ ] Clause splitter and the deterministic rule maths
- [ ] Freeze the system prompt, schema and model ID. Tag it `PROMPT_VERSION = 1`
- [ ] Send about 10 test calls and confirm in the console that they group into ONE task with a sensible name

**Friday 21:30 to 01:00: data and first training**

- [ ] Generator script and clause variant library
- [ ] Generate documents and labels. Split into training, fresh, correction and eval sets
- [ ] `send_batch.py`: 300 to 600 training clauses with a session per document. Watch the kept-example count
- [ ] Confirm the task shows Training or Testing before 01:00 London

**Saturday 09:00 to 12:00**

- [ ] Read v1's test result in Adapter History (Passed or Below target, and by how much)
- [ ] `eval.py`: closed model accuracy on the eval set, per-rule precision and recall, cost and latency
- [ ] Check-in 1 via Max before 12:00

**Saturday 12:00 to 18:00**

- [ ] Review UI: document view, clause flags, Accept / Correct
- [ ] Correction loop wired to the confirmed Mubit mechanism
- [ ] Send the fresh batch and the corrections so v2 can train
- [ ] Metrics panel (versions, accuracy vs the closed model, cost, latency)
- [ ] Check-in 2 via Max between 12:00 and 18:00

**Saturday 18:00 to 24:00**

- [ ] Router (stretch, only if adapters are callable)
- [ ] Polish the UI copy (no em dashes), add the "not legal advice" note, write the README with run steps and how Mubit is used
- [ ] Record the video and build the PDF deck
- [ ] `/submit` by midnight

**Sunday**

- [ ] 00:00 to 05:00 buffer: fix bugs, re-record if the numbers improve, resubmit before the 05:00 freeze
- [ ] Before 10:30: warm the adapter, pre-load the demo, test the backup recording
- [ ] 10:30 expo judging, 12:30 finalist demos (at least one team member present)

## Risks and kickoff questions

The biggest unknowns are whether our app can call an adapter and how corrections reach Mubit. Both decide the design of the correction loop and the router, so get answers at the 18:00 kickoff.

**Questions for the Mubit team** (in priority order)

1. Can our app call a trained adapter directly (API, model ID, header), or only through Try models?
2. How do corrections become model updates? Is there an API to submit a corrected answer for a request ID, or only Good/Bad ratings?
3. Which base model do adapters use, and how long does one training take?
4. What are the daily training limit and the pause between trainings for hackers? Can they be raised for the event?
5. Try models: how many calls per day, and are the 3 adapter starts per day raised?
6. How much starter credit do we get, and which models does it cover?
7. Is sending eval calls with `x-middleware-record: off` acceptable under the "every call through Mubit" rule?
8. Exact code freeze (05:00 vs 10:00 Sunday) and demo time limit.
9. Does the Claude Code side-quest traffic share a project with our app? We don't want coding traffic creating noise tasks.

**Risk register**

| Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|
| Adapter not callable from our app | Medium | No router, no live adapter in our UI | Show the adapter in Try models side by side, and frame the router as the production step |
| No API for corrections | Medium | Criterion #1 is weaker | Use Good/Bad ratings plus our own eval showing the improvement. Ask Mubit for the hackathon mechanism |
| v1 doesn't train before 01:00 | Medium | Lose a training slot | Freeze the prompt early, send 300+ diverse calls by 23:30, watch the Tasks page |
| Prompt changed after bulk send | Medium | New task, count resets | Version-tag the prompt and change it only with a deliberate decision |
| Adapter returns `Prompt only` or `Below target` | Medium | Weak story | Harder edge cases, more diverse examples, more fresh calls. `Prompt only` itself shows the base model is enough, which is a cost win |
| Clauses too long to train on | Low | Training fails | Clause-level chunking, and cap clause length |
| Starter credit runs out | Low | Calls fail with 403 | Check the balance, use a small model, add our own provider key |
| Legal rule wrong | Medium | Credibility hit in Q&A | Small rule set, each with a source link, plus a "not legal advice" note |
| Demo-day failure (Wi-Fi, cold start) | Medium | Bad live demo | Warm the adapter, keep a backup recording and screenshots |
| Crowded idea (contract review) | Medium | Less memorable | A specific, timely angle (the 1 May 2026 law change), real numbers, two audiences |

## Extras and sources

Side Quest 1 takes about 10 minutes and can win a Nintendo Switch 2. Do it before hacking starts, so it doesn't eat build time.

**Side Quest 1: Model Card**

1. Find session logs (JSONL): Claude Code in `~/.claude/projects/`, Codex in `~/.codex/sessions/`.
2. In Discord, run `/upload your@email.com` and upload the files. API keys and secrets are redacted before processing.
3. Mubit emails back a model card: the model your data would train, and the patterns you repeat that should become a model or a skill.
4. Post the card on X (tag @MubitLabs) and LinkedIn (tag Mubit), then drop both post links in #modelcards.
5. Prizes: Nintendo Switch 2, $100 and $25 in Mubit inference credits. One entry per person.

**Other extras**

- Bonus: route Claude Code or Codex through Mubit (setup in the integration reference section), so requests show up in the Mubit console.
- More side quests and two Switch 2s were announced for the weekend. Watch #announcements.
- Early bird: the first 50 accepted hackers get $50 in OpenAI API credits at check-in.
- Mubit is hiring and will invite people they meet to interview. Talking to the team at office hours helps both the project and the career angle.
- Launch-night releases worth referencing in the pitch: [Banyan Sapling](https://huggingface.co/MubitLabs/banyan-sapling) (policy, evidence and claim verification) and [Latte Bench](https://github.com/MubitLabs/latte-bench) (learning from feedback).

**Sources**

- Event info: the Luma page and blasts, the Discord announcements and the Night Shift rules (pasted by Nick; not public links)
- [Mubit docs](https://docs.mubit.ai/) and [full docs text](https://docs.mubit.ai/llms-full.txt): proxy, tasks, adapters, limits, headers, Claude Code setup
- [Banyan Sapling model card](https://huggingface.co/MubitLabs/banyan-sapling)
- [Minima (Mubit's model-routing tool)](https://github.com/mubit-ai/minima)
- [Tenant Fees Act 2019, Schedule 1](https://www.legislation.gov.uk/ukpga/2019/4/schedule/1/enacted) and [Oxford City Council summary](https://www.oxford.gov.uk/info/20267/private_housing_tenants/1327/tenant_fees_act_2019)
- Renters' Rights Act 2025 commencement: [Houst](https://www.houst.com/blog/renters-rights-act-2026), [August](https://www.augustapp.com/blog/renters-rights-post-commencement), [Generation Rent](https://www.generationrent.org/2025/11/14/government-announces-date-of-when-section-21-evictions-will-be-abolished-press-release/)
- [LLM-Adapters paper](https://arxiv.org/abs/2304.01933): adapter-tuned 7B models matching much larger models on narrow tasks (useful for the "open models are worse" question)
