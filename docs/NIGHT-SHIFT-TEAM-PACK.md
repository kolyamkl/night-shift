# Night Shift Team Pack

> Historical hackathon planning snapshot. Requirements and proposed privacy gates below are not proof they were implemented. See the [current documentation](README.md), especially [Security](SECURITY.md).

Everything we researched, decided and plan to build for the Night Shift hackathon (Mubit, London, 23 to 25 Oct 2026), in one file.

- Written: Friday 23 Oct 2026, evening, before hacking starts.
- Labels: **[F]** fact seen in a source; **[I]** our inference; **[ASK]** must be confirmed with the Mubit team; **[E]** estimate.
- Detailed evidence (about 300 rows with checked quotes) lives in `docs/research/2026-10-23-mubit-audit/`.
- Writing rule for anything public (README, deck, UI copy): no em dashes. This file follows it too.

---

## 0. TL;DR

**Українською, коротко**

- **Що будуємо:** веб-чат, у якому користувач пише запит або прикріплює документ (PDF, договір, рахунок). Перед відправкою в Claude чи OpenAI наша модель ховає персональні дані: імена, адреси, рахунки, телефони, email. Модель навчена через Mubit і працює на інфраструктурі Mubit. Відповідь повертається з уже підставленими справжніми даними.
- **Навіщо Mubit:** він сам навчає маленьку модель-«чистильник» на наших викликах і оновлює її після виправлень людини. Тому персональні дані не потрапляють до OpenAI чи Anthropic, а модель з кожним виправленням ховає краще.
- **Що показати суддям:**
  1. модель пропустила дані;
  2. людина виправила;
  3. нова версія моделі вже ховає;
  4. цифри: витоки на 100 документів, якість відповіді, швидкість.
- **Найважливіше питання на kickoff:** чи наступні запити обслуговує вже оновлена модель і як це побачити в коді. Організаторський приклад PagerPal каже, що так.

**English summary**

1. **Product (working name: Veil):** a privacy middleware with a chat UI. Every user prompt or document passes through a redaction model trained and hosted via Mubit. Personal data is replaced with placeholders, only the redacted text goes to Claude or OpenAI, and the real values are put back into the answer locally.
2. **Why Mubit is central:** redaction is a narrow, high-volume, checkable recurring task. Mubit discovers it, distils a task-specific open model from the frontier teacher, and turns human corrections ("you missed this account number") into model updates. The frontier providers never see the personal data once the adapter serves.
3. **Demo:** document in, "what Claude saw" with placeholders, correct answer with names restored. Then a missed entity, a correction, and the next model version catching it. Close with numbers: leak rate, answer quality parity, latency and cost.
4. **Biggest unknown [ASK]:** how we know a call was served by our adapter rather than the provider, and whether corrections are made in the console (as the organisers' sample project PagerPal says) or via an API.
5. **Critical path:** freeze the redaction prompt and schema by about 21:30 Friday, send 300 to 500 diverse synthetic calls by 23:30, and get v1 training before 01:00 London, when Mubit's daily training limit resets.

---

## 1. The event: rules, schedule, submission, judging

### 1.1 Basics [F]
- **What:** Night Shift, a 42-hour overnight hackathon hosted by Mubit. It doubles as Mubit's launch. 500 builders.
- **Where:** WeWork, 9th floor, 30 Churchill Place, Canary Wharf, London E14 5RE (per the teammate's brief; Luma hides the venue).
- **Teams:** 1 to 4 people, 18+, in person. At least one member must be at Sunday's demos to win.
- **Bring:** laptop, charger, photo ID, toiletries, sleeping bag if staying.
- **Hosts:** Eldar Utiushev, Anil Peri, Lily Jahan. Judges are not announced yet.

### 1.2 Prizes [F]
- Cash: 1st $15,000, 2nd $10,000, 3rd $5,000. The top 3 are judged across all tracks.
- $35,000 in credits (OpenAI and others). $1.5M in Mubit credits shared across accepted hackers. Mubit announced $10K+ more on launch day (per brief).
- Early bird: the first 50 accepted hackers get $50 in OpenAI credits at check-in.
- Winners get a direct interview with Mubit's co-founders. Mubit hires from attendees (a host was hired from their first hackathon).

### 1.3 The brief and tracks [F]
> "Build a product that routes its LLM calls through Mubit and turns your corrections into model updates for a recurring task."

- **Track 1, Recurring tasks:** a task the product runs again and again (extraction, triage, support replies, review, routing). Show corrections becoming model updates.
- **Track 2, Own your intelligence layer:** move a closed-model workload onto a task-adapted open model. Show quality, cost and latency side by side.
- **Track 3, Fast refresh:** a workload that keeps changing (new data, customers, domains). Show model updates keeping pace.

**Our fit:** Track 1 is primary (redaction runs on every prompt). Track 2 is natural: redaction moves from GPT to our adapter, with quality, cost and latency side by side. Track 3 is possible: a new document type or a new client-specific identifier (for example, "matter numbers"), and the model catches up after corrections.

### 1.4 Judging: four criteria, equal weight [F]
1. **Use of Mubit:** "Show a correction turning into a model update in your demo."
2. **Usefulness:** "A real recurring task someone would want handled."
3. **Technical execution:** "It works, and it holds up under questions."
4. **Demo:** "Clear, live, and under the time limit."

### 1.5 Hard rules [F]
- All project code is written during the event, from 19:30 Friday. Open-source libraries and our own tooling are fine. Research and notes before then are fine.
- Every project routes its LLM calls through Mubit.
- The repo must be public on GitHub. Its URL is captured at team creation.
- Two check-ins on Saturday via Max (the Discord bot): one by 12:00, one between 12:00 and 18:00. A missed one can be made up until the freeze.
- Organisers' calls are final.

### 1.6 Team setup [F]
- In the Mubit Discord, read `#night-shift-info`.
- One person runs `/team create` with the team name and the public GitHub repo URL. Max returns a join code.
- Teammates run `/team join`, then everyone runs `/team accept`.

### 1.7 Submission requirements [F]
- Via `/submit` in Discord. Opens **Saturday 20:00**. You can resubmit until the freeze; the latest counts.
- **Two uploads, both required:**
  1. **Video:** MP4 or MOV. YouTube links are not accepted. Length not stated; plan 2 to 3 minutes.
  2. **Deck:** PDF.
- Uploads after the freeze count only if an organiser accepts them.
- **Freeze conflict [ASK]:** Discord rules say code freeze **05:00 Sunday** and ask for submissions by midnight Saturday. Luma says 10:00 Sunday. Plan for 05:00 and confirm.
- The live demo is judged separately (criterion 4). The video is the required submission and our backup.

### 1.8 Schedule (London time) [F]

| When | What |
|---|---|
| Fri 17:00 | Doors open, check-in |
| Fri 18:00 | Kickoff: Mubit walkthrough, tracks, rules. **Ask our questions (section 13)** |
| Fri 19:00 | Dinner, team matching |
| Fri 19:30 | Hacking starts. First line of code allowed |
| Sat 01:00 | Mubit daily training limit resets (00:00 UTC) |
| Sat all day | Office hours with the Mubit team |
| Sat by 12:00 | Check-in 1 (Max) |
| Sat 12:00 to 18:00 | Check-in 2 (Max) |
| Sat 20:00 | Submissions open (`/submit`) |
| Sat 24:00 | Our target submission time |
| Sun 01:00 | Training limit resets again (00:00 UTC; still BST until 02:00) |
| Sun 02:00 | Clocks go back to 01:00. Extra hour |
| Sun 05:00 | Code freeze (Discord rules) [ASK vs 10:00] |
| Sun 10:30 | Judging round 1, expo (judges at our table, live) |
| Sun 12:30 | Finalist demos on stage |
| Sun 13:30 | Awards |
| Sun 14:00 | Close |

### 1.9 Side quests [F, from the brief]
- **Side Quest 1, model card:** upload Claude Code / Codex session logs via `/upload your@email.com` in Discord. Mubit emails a model card. Post it on X (tag @MubitLabs) and LinkedIn (tag Mubit), drop both links in `#modelcards`. Prizes: Nintendo Switch 2, $100, $25 in Mubit credits. About 10 minutes; do it before hacking.
- **Bonus:** route Claude Code through Mubit. Needs our own Anthropic API key under Provider keys (Pro/Max sign-ins are refused). Use a separate Mubit project so coding traffic does not create noise tasks in our product project.

---

## 2. Mubit as a company (audit)

### 2.1 Facts [F]
| Topic | Finding |
|---|---|
| Entity | Reliable AI, Inc. Investors list HQ as Aberdeen; the job ad says Canary Wharf WeWork |
| Founders | Anil Peri (CEO, Cranfield MSc) and Shankha Dutta (CTO, Lancaster MSc Data Science). Building companies together since 2020: SwiftSkill (esports analytics), Rice (org memory), Mubit since Nov 2025. Both Forbes 30 Under 30 Europe 2026 |
| Team | About 7 people. One open role (Founding Engineer, on site) |
| Funding | About $2.1M (company-reported, Forbes Apr 2026). Hoxton Ventures (fund IV, Hussein Kanji on the board), Heavybit, Techstars, angels from Cloudflare, AWS and Mistral |
| Traction | "Nearly 1,500 engineers" on the waitlist (Apr 2026). No named customers or case studies anywhere |
| Launch | Night Shift is the launch. "Launch week" 26 to 30 Oct: five features in five days |

### 2.2 Positioning over time [F]
| When | Headline |
|---|---|
| Feb 2026 | "Memory + State Infra for AI Agents" |
| Apr 2026 | "Operational Memory for Agent Systems", with a comparison table *against* fine-tuning ("No GPU costs") |
| Jun 2026 | "It has been reminded, not improved": memory notes are not enough |
| Sep 2026 | Middleware: "task-adapted open models from your model calls" |
| Oct 2026 | "Agentic runtime calibration. Build reliable agents with a model for every task" |

[I] A full reversal on weights in six months. Memory is now the source of training signal for model updates.

### 2.3 What the founders repeat [F]
- "agents have no experience", "systems of experience for agents"
- "It has been reminded, not improved" (a note in a prompt does not make the model better; a weight update does)
- "a set of corrections that keeps coming back. A field in an invoice. The wording in a support reply."
- "own your intelligence layer", "You own what's built", "Your frontier models stay"
- Shankha on trust in the request path: "We would rather build the routing layer that cannot mark your requests than the one that promises it will not." [I] Our privacy middleware speaks directly to this.
- House style: rigour plus open limits. Their benchmark pages list what they do not prove. [I] Judges will reward measured, honest claims.

### 2.4 Their products [F]
- **Middleware / gateway** (the event product): base URL swap; records calls; groups recurring tasks; trains a task adapter on an open base model; tests it against the provider; switches over "only when it does better". middleware.now: "Middleware uses application memory to refresh task-specific model behavior", with a change detector that triggers refreshes (their example: an escalation policy changes).
- **Memory SDK** (older, still shipping): `mubit-sdk` 0.13.2 on PyPI, `@mubit-ai/sdk` (0.14.0-rc.1, Sep 2026). `remember`, `recall`, `record_outcome`, `feedback`, `optimize_prompt`, prompt and skill versions. Is it live for hackers? [ASK]
- **Banyan Sapling** (uploaded 22 Oct): open-weight verifier. Inputs `policy`, `evidence`, `claim` (text only, English, up to 16,384 tokens). Outputs `supported` / `violation` / `insufficient_information` / `inconsistent_context` plus calibrated `unsure`. Trained on 42,809 synthetic policy cases + 7,191 ContractNLI. Strong on short explicit rules (100% raw, 77% answered on synthetic), weak on long contracts (answers 0.82%) and insurance claims. About 46 GB, H200, `production_ready: false`. Not what Mubit trains for us.
- **Latte Bench:** do retained text notes help a model improve at a planning task? Mixed: 7 of 11 models better, 4 worse.
- **Minima:** advice-only model recommender that learns from reported outcomes (not a proxy).

---

## 3. How Mubit actually works (product mechanics)

### 3.1 Connecting [F]
| SDK | Base URL | Key header |
|---|---|---|
| OpenAI | `https://api.mubit.ai/openai/v1` | `Authorization: Bearer <MUBIT_KEY>` |
| Anthropic | `https://api.mubit.ai/anthropic` (no `/v1`) | `x-api-key` or `Authorization: Bearer` |
| Gemini (google-genai) | `https://api.mubit.ai/gemini` (no `/v1beta`) | `x-goog-api-key` (never `?key=`) |
| OpenAI SDK on Gemini | `https://api.mubit.ai/gemini/v1beta/openai` | Bearer |
| OpenRouter / Groq / Together / Mistral | `https://api.mubit.ai/compat/{service}/v1` | Bearer |

- Use the base URL the console's **Connect** page shows if it differs.
- **Server-side only:** the API answers no CORS preflight, so browsers cannot call it.
- Keys start with `mbt_`. Two kinds: **Inference** (needed for calls) and **Read only** (calls get `403 key_permission`). A key is tied to one project (`403 key_scope` otherwise).
- **Send only the Mubit key.** A provider key, a sign-in token or a second credential gets a 401 (`provider_key_refused`, `extra_credential_refused`, `subscription_token_refused`). Unset `ANTHROPIC_AUTH_TOKEN` if it holds something else.
- Provider keys live in the console under **Provider keys** (admins only). Without them, calls use the **starter credit**, which serves a fixed model list. Models named in the docs: `gpt-6-luna`, `claude-haiku-4-5`, `gemini-3.8-flash`. Other models get `400 starter_credit_model`. Hosted tools such as web search are refused.
- Starter credit body limits: at most 8 MiB, plain JSON, arrives within 60 s.

### 3.2 Tasks, sessions, kept examples [F]
- **A task** = same instructions (system prompt) + tools + tool choice + output format + model. User messages, `temperature` and `max_tokens` do not count.
- Whitespace runs, numbers, dates, times and IDs in the instructions do not split a task. **Other changing words do** (a customer name in the system prompt makes one task per name).
- The task's display name comes from the first words of the system prompt. Start it with a meaningful phrase.
- Model date suffixes and `-latest` are ignored when grouping. The same instructions on two models are two tasks.
- **Session** is taken from the first present of `metadata.thread_id`, `metadata.session_id`, `metadata.conversation_id`, Anthropic `metadata.user_id`, OpenAI Responses `prompt_cache_key`; otherwise derived from the instructions plus the first user message. Values over 200 chars are hashed.
- **Test cases are held out by session.** Use one session per document so a document's chunks never leak between train and test.
- **Kept examples:** not every call is kept. By default a task first trains at **25 kept examples** (the console count is the source of truth). Near-duplicates waste calls.

### 3.3 Training and test results [F]
- Status flow: Collecting examples, Reviewing examples, Training, Testing.
- Each version gets one result:
  - **Passed:** answers close enough to the provider model. Console: "v1 passed its tests".
  - **Below target:** "Matched {a}% of your provider model's answers on {n} test cases · needs {need}%".
  - **Malformed tool calls:** "{k} of {n} tool calls were malformed · needs 0".
  - **Prompt only:** the base model with the prompt did as well; no adapter needed. Cannot be tried in Try models.
  - **Not tested.**
- **Waits:** "today's training limit" (resets 00:00 UTC), "the pause between trainings", "Waiting for more examples: {k} of {need}", "Waiting for new examples" (after a failed training).
- **Can't train:** "too few examples", "examples too long to train on", "the training run failed", "the first training stopped".
- **No retry button.** Recovery always means new calls with new messages. After a version: "Next: a new version after {need} new examples".
- [I] **Grading is imitation:** by default the adapter is graded on matching the provider. Corrections must reach training through Mubit's own mechanism (see 3.6).

### 3.4 Try models and serving [F]
- **Try models** compares a passing version with the provider model side by side. Daily per-org call limit. **3 adapter starts per org per UTC day.** The first start takes minutes (the page re-sends every 15 s for up to 20 minutes). Calls there are not stored.
- Public docs: "There is no Mubit model ID: you can't send a call to an adapter by naming it as the model."
- But the console shows **"Adapters serving"** and a **SERVING** column, and Requests has a **Served by** column and filter. The homepage promises "switching over only when it does better". [I] Serving by adapter exists. How we detect it per call: [ASK].

### 3.5 Headers, limits, errors [F]
- `x-middleware-store: false` or `x-middleware-record: metadata` keeps request and answer out of the record. `x-middleware-record: off` also drops the task fingerprint. Never set these on calls we want trained on.
- Every answer carries `x-middleware-request-id` (`mreq_` + 32 hex, sortable by time). Read it with `client.chat.completions.with_raw_response.create(...)` then `raw.headers["x-middleware-request-id"]`. `resp._request_id` is OpenAI's ID, not Mubit's.
- The console's own Request ID under Details is **not** the `mreq_` ID. The Session filter lives in the page URL, so we can deep-link a document's session.
- Limits: connect 10 s (one retry), first byte 610 s, silence 15 min, total 60 min. Mubit records up to 32 MiB of a request, and the first 4 MiB + last 256 KiB of an answer.
- Retries: Mubit retries only if nothing was sent. Our SDK owns retries; respect `retry-after` on 429/503.
- Mubit's own errors have type `middleware_gateway_error`. An answer without `x-middleware-request-id` did not come through Mubit.

### 3.6 How corrections become model updates [F + ASK]
- Public docs only show **"Rate this reply: Good / Bad"** per call in Requests.
- **PagerPal**, a public sample project (account e1daru, probably the host Eldar; inference), describes the event flow:
  - "the engineer corrects that answer in the Mubit console, and Mubit turns the correction into a model update for PagerPal's triage task";
  - "later suggestions come from the updated model. PagerPal's code doesn't change";
  - each suggestion shows its `x-middleware-request-id`, and a `/history` page shows whether each suggestion was right.
- So, likely: **corrections are made in the console on a specific request**, and **later calls are served by the updated model**. [ASK] Is there an API for corrections, so we can put the button in our own UI? Nobody has done that yet.
- **Fallback if corrections cannot reach training in time:** store corrections as precedents and pass them in the user message of later calls ("reminded"); Mubit distils those corrected teacher answers into the next version ("improved").

### 3.7 Our console (from the screenshot) [F]
- Org workspace with **up to 5 projects**. Use separate projects for: (1) the product, (2) Claude Code side-quest traffic.
- Getting started: Connect data (Import past calls or Connect with API), Set up billing (Stripe), Create a Mubit key. **Do not add a card unless organisers say so.** We need only "Create a Mubit key".
- "First trains at 25 examples", "Found once calls arrive".
- Import past calls (Langfuse, Braintrust, Logfire) reads only calls before a project's first live call. Not needed.

---

## 4. Market and competitors

### 4.1 Mubit's own category [F]
| Player | Status 2026 |
|---|---|
| OpenPipe | Bought by CoreWeave (Sep 2025). Training and inference stopped 30 Jul 2026 |
| TensorZero (closest open-source twin) | Wound down Jun 2026, returning capital |
| Predibase / Adaptive ML | Acquired by Rubrik (Jun 2025) / Datadog (Jun 2026) |
| OpenAI fine-tuning and distillation | Closed to new orgs 7 May 2026; all new jobs end **6 Jan 2027** |
| Portkey / Helicone / Langfuse | Palo Alto Networks / Mintlify (frozen) / ClickHouse |
| OpenRouter | Stripe agreed to acquire (not closed) |
| Experiential Labs (YC S26) | Most direct new rival: OSS gateway, owned model on Tinker, "at least 50% lower cost" SLA |
| Inference.net, Applied Compute, Trajectory, RELAI, Datawizz | Active |

- **Mubit strengths:** automatic task discovery by fingerprint; honest gate ("Prompt only"); first training at 25 examples; memory and adapters in one loop.
- **Mubit weaknesses:** no public measured results; imitation-only grading vs "does better"; serving, export and privacy undocumented; tiny team; crowded slogan.
- **Gaps nobody fills well:** proof before switching graded on outcomes; deciding which layer to fix; cost per *successful* task; refugees from OpenAI fine-tuning; portability.

### 4.2 Our product's market: PII redaction for LLM use [F/I]
- **Existing tools:** Microsoft Presidio (open source, rule + NER, custom recognisers), AWS Comprehend PII detection, Google Cloud Sensitive Data Protection, Private AI, Nightfall, Skyflow (privacy vault). Secret scanners (gitleaks, trufflehog) for credentials.
- **What they do well:** structured identifiers (emails, card numbers, phone numbers) and common entity types.
- **Where they are weak [I]:** context-dependent names and addresses in messy text, organisation-specific identifiers (client codes, matter numbers, internal project names), consistent reversible placeholders that keep the LLM's answer useful, and learning from a reviewer's corrections.
- **Our angle:** a redaction model that (1) runs on Mubit, not on the frontier provider, (2) keeps answers useful through consistent placeholders that are restored locally, (3) learns each organisation's identifiers from corrections, (4) is measured by leak rate, not by claims.

---

## 5. Mubit's past hackathons: what they reward

### 5.1 Events (all London) [F]
| Event | Date | Mubit prize | Mubit winner |
|---|---|---|---|
| Unicorn Mafia "To The Americas" (their first) | 25-26 Apr | "Best use of Mubit": £500 + $8k credits (participant copy) | Not found |
| Vercel Zero to Agent | 2 May | $100k credits for "the best build on the Mubit platform" | **Rentry** (also 2nd overall) |
| Pop the Bubble | 5-7 Jun | Bonus: "+4 for bolted-on use", "+10 when the core product genuinely relies on Mubit" | No separate prize; joanie 2nd overall |
| {Tech: Europe} London | 27 Jun | Credits for top 3 overall; Minima on offer | No Mubit track |
| Night Shift | 23-25 Oct | Cash + credits | Tonight |

### 5.2 Projects that placed with Mubit [F]
- **Rentry:** London rental agent that remembered user preferences across sessions. Demo: "it still knows you", a "remembered from last session" badge. Pitch notes: one verb per sponsor ("Mubit REMEMBERS"), a badge on every remembered item, a log strip of real API calls for technical judges, a pre-seeded returning user, a hardcoded fallback line.
- **joanie:** AI phone receptionist that remembers callers. Claimed a paying customer and an LOI during the event.
- **CafeTwin:** cafe CCTV to layout changes; remembered operator accept/reject; "seen 3× before" chip. 4th overall.
- **Frame Mog** (no placement): pose coach that "by session three" had adapted to the user, shown live.
- 13 more projects used Mubit with no placement. Most used it as invisible plumbing.

### 5.3 What Mubit showcases in its own demos [F]
- Always **with vs without** the learning loop on held-out cases.
- Always **counted savings:** LLM calls, tokens, $, latency.
- Learning curves, including across **drift**.
- An audit trail: request ids, history pages, approve/reject diffs.

### 5.4 Patterns [F/I]
1. A learning loop you can **see on stage**. Unchanged since April. Tonight it must be a model update, not memory.
2. A real person or small business with a real recurring job, ideally real users or money.
3. A small stack and a demo that cannot break.
4. Measured with-vs-without numbers.
5. Mubit visible, never invisible plumbing.

### 5.5 Openings nobody has used yet [I]
- A correction turning into a model update shown on stage.
- Adapter vs frontier side by side (quality, cost, latency).
- Fast refresh under drift.
- **Correcting inside the product's own UI** (even PagerPal corrects in the console).

**Crowded tonight or too close to Mubit's own examples:** on-call / incident triage (their reference demo), invoice and company-accounts readers, claim verification with Sapling, AI phone receptionists.

---

## 6. Decision log: ideas we considered

Scoring: seven criteria, 1 to 5 each (Mubit fit, usefulness/volume, data in 36 h, privacy case, demo moment, low crowding, team fit), out of 35.

| Idea | Score | Verdict and main reason |
|---|---|---|
| UK tenancy agreement checker (original brief) | 17 | Dropped. 7+ live AI tenancy checkers, the 31 May 2026 deadline spike has passed, weak privacy case, staged correction moment, a renting agent already won a Mubit track |
| Threshold: adverse-media hit triage for fin-crime teams | 34 | Strong. Kept as the best alternative |
| Broker client onboarding check | 33 | Strong; same engine as Threshold |
| Background check / BPSS-style screening for employers | 32 | Good; one engine, many client rubrics |
| FCA complaint triage (DISP, Consumer Duty) | 32 | Good; real CC0 data (CFPB), more crowded |
| **PII redaction middleware (chosen)** | **31-32** | **Chosen.** Crisp, visual correction moment; Track 2 fits naturally; speaks to Mubit's request-path trust theme. Depends on adapter serving |
| APP scam reimbursement triage | 30 | Good volume, fraud is a common theme |
| Motor finance redress | 29 | Scheme partly paused until Feb 2027 hearing |
| Export-control classification (defence) | 29 | Needs expertise we lack |
| AI recruiter (CV screening) | 27 | Most common hackathon idea, ATS incumbents, bias questions |
| Awaab's Law hazard triage | 26 | Best live rule change, synthetic only, weak team fit |
| Dossier + trust score + LinkedIn scraping | 19 | Rejected: platform terms, UK GDPR, discrimination, little LLM work |

**Why the redaction middleware won the team vote [I]:**
- Every prompt is a call: the most recurring task possible.
- Labels are checkable (found / missed / over-redacted), so accuracy and corrections are unambiguous.
- Synthetic data with ground truth by construction is easy (fake people, known spans).
- The before/after is visual: highlighted placeholders, then a restored answer.
- Track 2 is built in: redaction moves off GPT onto our own model.

**Legal and ethics notes we learned along the way (not legal advice):**
- Scraping LinkedIn or Instagram breaks their terms even with the person's consent. Consent buried in T&Cs is not valid UK GDPR consent. Collecting "everything" fails data minimisation.
- Criminal records in the UK come only via DBS / Disclosure Scotland / AccessNI; spent convictions mostly cannot be used.
- Weapons, targeting and surveillance of people are off limits (provider policies, and our own line).
- **For our product:** placeholders with a key vault are **pseudonymisation**, not anonymisation. It reduces exposure; it is not a legal guarantee. Context can still identify people (job title + small town). Say this honestly if asked.

---

## 7. Product spec: Veil (working name)

### 7.1 One-liner
Veil is a privacy layer for using ChatGPT and Claude with real documents: it hides personal data before the prompt leaves, using a model that learns from every correction, and puts the real values back into the answer.

### 7.2 Problem [I]
- Agencies, law firms, accountants, letting agents and HR teams paste contracts, bills, bank statements and client emails into frontier LLMs every day.
- Their clients' personal data then sits with a third-party model provider. Many firms forbid this, so staff either do it anyway or lose the productivity.
- Rule-based redaction misses names and addresses in messy text, and it does not know each firm's own identifiers (client codes, matter numbers).

### 7.3 Users
- **End user:** a staff member who wants to ask an LLM about a document.
- **Reviewer:** a privacy or compliance person who checks redactions and corrects misses.
- **Buyer:** head of operations, DPO or IT at a firm with client data (legal, property, accounting, HR, insurance; defence contractors as a high-stakes example).

### 7.4 Threat model
- **Trusted:** our backend and Mubit (the gateway, its record, and the adapter it hosts on its infrastructure).
- **Not trusted with personal data:** OpenAI and Anthropic (the frontier providers).
- **Goal:** no personal data in any request that reaches a frontier provider, once our adapter serves the redaction task.
- **Bootstrap caveat:** until the adapter serves, redaction calls go to the provider as the teacher. So training uses **synthetic documents only**, and real documents are blocked until serving is confirmed (FR-9).

### 7.5 What to hide and what to keep

**Hide (entity types):**

| Type | Examples | Detected by |
|---|---|---|
| `PERSON` | Names in text, signatures, headers, "my sister Olena" | Model |
| `ADDRESS` | Street addresses, multi-line addresses | Model |
| `POSTCODE` | UK postcodes | Regex + model |
| `EMAIL` | Email addresses | Regex |
| `PHONE` | UK and international numbers | Regex |
| `BANK_ACCOUNT` | 8-digit account numbers | Regex + model (context) |
| `SORT_CODE` | NN-NN-NN | Regex |
| `IBAN` | GB + 2 digits + 4 letters + 14 digits (22 chars) | Regex |
| `CARD` | 13 to 19 digits, Luhn check | Regex |
| `NI_NUMBER` | Two letters, six digits, one letter (e.g. QQ123456C) | Regex |
| `DOB` | Dates of birth (not other dates) | Model |
| `ID_DOC` | Passport, driving licence numbers | Regex + model |
| `CUSTOM` | Org-specific identifiers: client codes, matter numbers, policy numbers | Model, learned from corrections |

**Keep:** amounts, ordinary dates, contract terms, clause text, public company names (unless the company is clearly a sole trader's name), product names.

### 7.6 Functional requirements
- **FR-1 Input:** the chat accepts typed text and an attached PDF (text-based; no scans or OCR in scope).
- **FR-2 Extraction:** extract PDF text per page and split into chunks of at most about 1,500 tokens on paragraph boundaries.
- **FR-3 Regex layer:** detect structured identifiers (email, phone, card with Luhn, sort code, account, IBAN, NI number, postcode) before the model.
- **FR-4 Model layer (Mubit task T1):** for each chunk, call the redaction task through Mubit. It returns a JSON list of entities `{text, type}`. Code does the replacement, so the model never rewrites the document.
- **FR-5 Consistent placeholders:** the same real value always gets the same placeholder within a conversation (`[PERSON_1]`, `[ACCOUNT_1]`). Mapping stored in a per-conversation vault.
- **FR-6 Answer (Mubit task T2):** send only the redacted text and the user's question to Claude or OpenAI through Mubit. The system prompt tells the model to keep placeholders exactly as written.
- **FR-7 Restore:** replace placeholders in the answer with real values. Tolerate small variations ("PERSON 1").
- **FR-8 Three-panel view:** original, "what the provider saw" (placeholders highlighted), answer with real values.
- **FR-9 Serving guard:** a "real data" mode refuses to send documents to T1 unless the redaction call was served by our adapter. Synthetic mode is always allowed. Detection method [ASK].
- **FR-10 Corrections:** the reviewer marks a missed span (select text, choose type) or an over-redaction (click a placeholder). Store each correction with the `mreq_` request id, chunk, before, after, timestamp.
- **FR-11 Correction to Mubit:** send corrections through the confirmed mechanism (console on the request, or an API if available). Show a deep link to the document's session in the Mubit console.
- **FR-12 History and metrics:** a page showing per model version: leak rate, over-redaction rate, documents with zero leaks, p50 latency and cost of the redaction step, share of calls served by the adapter.
- **FR-13 Request id everywhere:** every result shows its `mreq_` id (like PagerPal and Rentry's log strip).
- **FR-14 (stretch) Drop-in proxy:** our own OpenAI-compatible endpoint so any app gets redaction by changing its base URL.

### 7.7 Non-functional requirements
- **NFR-1 Leaks:** on the held-out set, zero leaked values of high-risk types (account, card, NI number, IBAN). Report overall recall honestly.
- **NFR-2 Answer quality:** answers on redacted documents match answers on originals on our Q&A set (target: no meaningful drop; report the number).
- **NFR-3 Latency:** report p50 and p95 of the redaction step per chunk; target well under the frontier answer time.
- **NFR-4 Secrets:** no API keys in the repo; `.env` in `.gitignore`.
- **NFR-5 Data:** only synthetic people in anything sent through Mubit during the event.
- **NFR-6 Demo safety:** a pre-loaded demo state that works offline from cached results if the network fails.

### 7.8 Out of scope
- Scanned PDFs and images (OCR), audio.
- Indirect identifiers by inference (job title + town). Mention as roadmap.
- A desktop app. The web app is enough.

---

## 8. Architecture

### 8.1 Flow
```
Browser (chat: text or PDF)
  -> Our backend (FastAPI)
       1. PDF -> text -> chunks (FR-2)
       2. Regex layer (FR-3)
       3. Mubit task T1 "Find personal data in one document chunk" (per chunk, session = doc id)
          -> entities JSON -> code replaces with placeholders, vault stores mapping (FR-4, FR-5)
       4. Mubit task T2 (Claude or OpenAI via Mubit): redacted text + question -> answer with placeholders (FR-6)
       5. Restore placeholders from the vault (FR-7)
  <- Browser: original | what the provider saw | answer (FR-8), corrections (FR-10)
Mubit console: tasks T1 and T2, adapter versions, Try models, corrections, Served by
```

### 8.2 Mubit tasks
| Task | System prompt starts with | Output | Model | Session | Role |
|---|---|---|---|---|---|
| **T1 Redaction** (hero) | "Find personal data in one document chunk." | JSON `{"entities":[{"text","type"}]}` with `response_format: json_object` | One fixed model, e.g. `gpt-6-luna` | `doc-<id>` | The adapter we train and show |
| T2 Answer | "Answer the user's question about a redacted document." | Free text that keeps placeholders | e.g. `claude-haiku-4-5` via `/anthropic` | `conv-<id>` | Shows that the provider only sees placeholders |
| T3 Data generator | "Write one synthetic document of the given type." | Text | Any | `gen-<id>` | Only for building data; separate task |

**Prompt rules (critical):**
- Freeze T1's system prompt, schema and model before bulk traffic. Tag `PROMPT_VERSION = 1`. Any change creates a new task and resets the count.
- Never put per-document text, names or client names into the system prompt. The entity type list goes in the system prompt (fixed text).
- Keep chunks short enough to avoid "examples too long to train on".
- Return entities, not the rewritten document: far fewer output tokens and no risk of the model altering the text.

### 8.3 T1 output schema (draft)
```json
{
  "entities": [
    {"text": "Oleksandra Kovalenko", "type": "PERSON"},
    {"text": "Flat 3, 12 Oak Road, Leeds", "type": "ADDRESS"},
    {"text": "LS6 2AB", "type": "POSTCODE"},
    {"text": "CL-20931", "type": "CUSTOM"}
  ]
}
```

### 8.4 T2 system prompt (draft idea)
"Answer the user's question about a redacted document. Values in square brackets such as [PERSON_1] or [ACCOUNT_2] stand for hidden real values. Keep every placeholder exactly as written. Never guess the hidden values."

### 8.5 Stack
- Backend: Python 3.11+, FastAPI, OpenAI and Anthropic SDKs pointed at Mubit, SQLite (SQLModel), pdfplumber or pypdf, Faker (`en_GB`) for synthetic data.
- Frontend: React + Vite (three panels + chat). Fallback: FastAPI + Jinja templates (what PagerPal uses).
- Run the demo on a laptop (`localhost`). Deploy to Render or Railway only if time allows.
- `.env`: `MUBIT_API_KEY`, `MUBIT_OPENAI_BASE_URL`, `MUBIT_ANTHROPIC_BASE_URL`, `MODEL_REDACT`, `MODEL_ANSWER`.

### 8.6 Repo layout (proposed)
```
README.md                     what it is, how to run, how Mubit is used, demo script
backend/app/main.py           FastAPI routes: /chat, /upload, /corrections, /history, /metrics
backend/app/mubit_client.py   clients for both SDKs, session ids, mreq_ capture
backend/app/redact.py         regex layer, T1 call, placeholder vault, restore
backend/app/prompts.py        FROZEN prompts + PROMPT_VERSION
backend/app/pdf.py            extraction and chunking
backend/app/store.py          SQLite: docs, chunks, entities, corrections, results
scripts/gen_docs.py           synthetic documents + ground-truth spans (labels.jsonl)
scripts/send_batch.py         bulk T1 traffic, concurrency 10-20, retry-after
scripts/eval_redaction.py     recall, precision, leak rate per type and per version
scripts/eval_answers.py       answer parity: redacted vs original on the Q&A set
data/synthetic/{train,fresh,corrections,eval}/
frontend/
```

---

## 9. Data plan

### 9.1 Why synthetic
- Real sources need accreditation or contracts, and real personal data must not pass through Mubit's record during the event.
- Ground truth comes for free: we place every fake name, address and number ourselves, so accuracy is honest and not graded by an LLM.
- Pitch line: "We generate documents in the same formats real firms use, and the correct answers are set by code."

### 9.2 Document types (templates)
Tenancy agreement, utility or phone bill, bank statement, invoice, employment contract, NDA, client email thread, letter of engagement, insurance claim letter, payslip.

### 9.3 Generator design
1. Templates per document type, with slots for people, addresses, numbers, dates, amounts.
2. Fill with Faker `en_GB` plus hand-made hard cases. Record every inserted span with its type in `labels.jsonl`.
3. Vary layout, length, wording, order; paraphrase some passages with T3 (a separate Mubit task).
4. Render a PDF for demo documents; send text chunks for bulk training.

### 9.4 Hard cases to plant (where models and regex slip)
- Names that are common words: Will, Rose, Mark, Grace, Bill, Hope, May.
- Names only in signatures, headers, footers, "Dear Mr Patel", "Kind regards, Jo".
- Possessives and initials: "Kovalenko's", "O. Kovalenko", "OK".
- Transliterated and non-English names (Oleksandr / Alexander, Siobhán).
- Addresses split across lines or inside tables; flat numbers; "c/o".
- Account numbers next to amounts; partial numbers ("ending 4821").
- Company names that contain a person's name ("Smith & Co Ltd") vs a sole trader.
- Org-specific identifiers: client codes "CL-20931", matter numbers "M/2024/118", policy numbers.
- The same person written three different ways in one document (consistency).
- Over-redaction traps: "Oak Road" in a clause about road works, "Rose Garden" as a place, dates that are not DOBs, amounts.

### 9.5 Splits and volumes
| Split | Size | Sent how | Purpose |
|---|---|---|---|
| Training traffic | 100 docs, about 300 to 500 chunks, Fri night | Normal calls through Mubit | First adapter version |
| Fresh batch | 60+ docs, about 200 chunks, Sat | Normal calls | New examples for v2 |
| Corrections | 30 to 50 chunks | Reviewed in our UI, fed via the confirmed mechanism | The demo's correction story |
| Eval | 40 to 60 docs, about 150 chunks, never trained on | Through Mubit with `x-middleware-record: off` [ASK if acceptable] | Honest numbers for GPT vs each version |

- One session per document. Diversity over volume; Mubit discards near-duplicates.
- Cost sanity [E]: a chunk call is about 800 to 1,500 input tokens and under 200 output tokens. 600 calls is well under 1M tokens. Check the starter credit balance first.

### 9.6 Baselines to report
1. Regex only.
2. Presidio (open source).
3. GPT teacher (T1 on the provider).
4. Adapter v1.
5. Adapter v2 (after corrections).

---

## 10. Metrics and evaluation
- **Leak rate:** share of ground-truth personal values that appear in any text sent to T2. Per type and overall. Headline: leaks per 100 documents.
- **Recall / precision per type** (entity level).
- **Documents with zero leaks.**
- **Over-redaction rate:** placeholders on values we keep (amounts, ordinary dates).
- **Answer parity:** a Q&A set per synthetic document with known answers ("What is the monthly rent?", "Who is the landlord?", "When does the tenancy start?"). Compare T2 answers on redacted vs original documents (exact-match on fields).
- **Latency:** p50 / p95 of the redaction step; adapter vs GPT.
- **Cost:** per document for redaction, adapter vs GPT.
- **Served by adapter:** share of T1 calls served by our model.
- **Time to fix:** from correction to the first version that catches that pattern.
- Say what the numbers do **not** prove (synthetic distribution, English UK documents only).

---

## 11. Demo, video, deck

### 11.1 Live demo script (about 3 minutes; confirm the limit)
| Time | Beat |
|---|---|
| 0:00 | Problem: staff paste client contracts into ChatGPT every day. Firms forbid it. Rules miss names in messy text |
| 0:20 | Attach a tenancy agreement, ask "When can the landlord raise the rent?" Show three panels: original, what Claude saw (placeholders highlighted), answer with real names |
| 0:50 | A miss: a client code "CL-20931" in a footer went through. Reviewer marks it as CUSTOM. Request id shown |
| 1:20 | Mubit console: the redaction task, adapter history v1 to v2, test result, Try models side by side |
| 1:50 | Same kind of document again: v2 catches the client code. History page shows the leak rate dropping |
| 2:20 | Numbers: leaks per 100 docs (regex, Presidio, GPT, v1, v2), answer parity, p50 latency, cost per document |
| 2:40 | Close: "Every correction makes your own privacy model better, and your clients' data never reaches the model provider." |

### 11.2 Demo risk controls
- Warm the adapter in Try models 10 to 15 minutes before judging (3 starts per day only).
- Pre-load demo documents and cached results. Keep screenshots of every console screen.
- Keep a backup recording of the full flow.
- Use Try models calls sparingly on Saturday (daily limit).

### 11.3 Video (MP4 or MOV, required)
- 2 to 3 minutes, screen recording with voiceover, same beats as the live script.
- Record Saturday evening once v2 exists. Re-record before the freeze if numbers improve.

### 11.4 Deck (PDF, required, 7 to 9 slides)
1. Title + one-liner.
2. Problem: documents with personal data, staff using frontier LLMs, rules that miss context.
3. Product: the three-panel screenshot.
4. How it works: the flow diagram (section 8.1).
5. The Mubit loop: calls, task, adapter, correction, v2, served by adapter.
6. Results: leak rate table, answer parity, latency and cost.
7. Business model.
8. Roadmap: drop-in proxy, more document types, OCR, per-firm models, indirect identifiers.
9. Team.

---

## 12. Build timeline and owners

Roles (merge if fewer than 4): **A** data + eval, **B** backend + Mubit, **C** frontend, **D** pitch + video + deck + Q&A.

**Before 19:30 (no code)**
- [ ] Team created via Max with the public repo URL.
- [ ] Side Quest 1 (model card) if someone has session logs.
- [ ] Kickoff questions asked; answers written down verbatim (section 13).
- [ ] Mubit key created; stored only in `.env`. Separate project for Claude Code traffic if used.
- [ ] On paper: T1 system prompt, entity types, output schema, document types, hard-case list.

**Fri 19:30 to 21:30**
- [ ] B: repo scaffold, `.env`, `.gitignore`, Mubit clients, `mreq_` capture, session ids.
- [ ] B: freeze T1 prompt, schema, model (`PROMPT_VERSION = 1`).
- [ ] B: 10 test calls; confirm in the console they form ONE task with a sensible name.
- [ ] A: generator skeleton with labels.

**Fri 21:30 to 01:00 (critical)**
- [ ] A: generate train, fresh, corrections, eval splits.
- [ ] B: `send_batch.py` with the training split, concurrency 10 to 20, respect `retry-after`.
- [ ] All: watch the kept-example count. Target: Training or Testing before **01:00**.
- [ ] C: chat skeleton calling the backend.

**Sat 09:00 to 12:00**
- [ ] B: read v1's test result (Passed / Below target / Prompt only).
- [ ] A: `eval_redaction.py` for regex, Presidio, GPT, v1.
- [ ] C: three-panel view.
- [ ] Check-in 1 before 12:00.

**Sat 12:00 to 18:00**
- [ ] C: correction UI, history page, metrics panel.
- [ ] B: corrections through the confirmed mechanism; fresh batch; serving guard.
- [ ] A: `eval_answers.py` (answer parity).
- [ ] Check-in 2.

**Sat 18:00 to 24:00**
- [ ] D: README (run steps, how Mubit is used, demo script), deck, video.
- [ ] All: polish UI copy (no em dashes), demo rehearsal, fallback cache.
- [ ] `/submit` by midnight.

**Sun 00:00 to 05:00**
- [ ] After the 01:00 reset, optional v3. Re-record if numbers improve. Resubmit before 05:00.

**Sun before 10:30**
- [ ] Warm the adapter, pre-load the demo, test the backup video.

**Cut order if behind:** drop-in proxy (FR-14), then Presidio baseline, then answer-parity Q&A, then PDF rendering (paste text instead). Never cut: T1, corrections, v1 to v2, the leak-rate numbers.

---

## 13. Kickoff questions (priority order)
1. **Corrections:** do we correct a reply in the console on its request (as PagerPal describes), and is there an API so we can correct from our own UI?
2. **Serving:** after an update, are later calls served by the adapter automatically? How do we tell per call (header, field, "Served by")? Can we force a call to the adapter?
3. Where does the adapter run, and is there any way to export or self-host it later?
4. Training limits for hackers: trainings per day, pause between trainings, time per training. Can the 25-example threshold be changed in Settings?
5. Try models: calls per day; are the 3 adapter starts per day raised?
6. Base model for adapters.
7. Starter credit amount and models.
8. Is eval traffic with `x-middleware-record: off` acceptable under "every call through Mubit"?
9. Is the memory SDK (`mubit-sdk`) live for hackers?
10. Code freeze 05:00 or 10:00 Sunday? Demo length? Finals format?

---

## 14. Judge Q&A prep
- **"Why not Presidio or regex?"** Show the baseline table. Regex catches structured numbers; it misses names and addresses in messy text and firm-specific codes. Our model learns those from corrections.
- **"Doesn't Mubit see the data?"** Yes, by design: Mubit is the trusted processor hosting the open model. The frontier providers never see personal data. In production this runs under a data processing agreement, and self-hosting the adapter is a roadmap question for Mubit.
- **"How did you train without leaking?"** Only synthetic documents with fake people. Real documents are blocked until the adapter serves (FR-9).
- **"What if it misses something?"** Regex safety net for high-risk numbers, leak rate measured per type, a block mode for uncertain chunks, and every miss becomes a correction and a model update.
- **"Does redaction hurt the answer?"** Answer-parity numbers on our Q&A set.
- **"Is this anonymisation?"** No, it is pseudonymisation: the vault can reverse it. It reduces exposure; context can still identify people. We say so.
- **"Your data is synthetic."** Real sources need contracts; labels come from code, not from an LLM; the eval set was never trained on.
- **"Why does an adapter beat GPT here?"** It does not need to beat GPT on general redaction; it needs to match it while keeping data in, and it beats GPT on each firm's own identifiers after corrections.
- **"Latency?"** Show p50 and p95 for the redaction step.
- **"What does this not prove?"** English UK documents only, synthetic distribution, no OCR, no indirect identifiers.

---

## 15. Business model [I]
- **Buyers:** law firms, letting and estate agencies, accountancies, HR teams, insurers, brokers; defence contractors as a high-stakes segment.
- **Pricing:** per seat for the chat, plus per document or per 1,000 API calls for the drop-in proxy. Free tier for individuals.
- **Value:** staff keep using frontier LLMs without breaking client confidentiality; fewer leaks than rules; each firm's identifiers learned automatically.
- **Moat:** each firm's correction history and its own redaction model; never pooled across firms.
- **Risks:** incumbents (Private AI, Nightfall, Skyflow, cloud DLP), dependence on Mubit's serving and export, liability for misses.
- **Expansion:** OCR for scans, more languages, indirect identifiers, browser extension, Slack and email integrations.

---

## 16. Risks and mitigations
| Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|
| Corrections cannot reach training in time | Medium | Criterion 1 weak | Console corrections per PagerPal; precedent fallback; ask at kickoff |
| Adapter cannot serve or we cannot detect serving | Medium | Core promise breaks | Ask first; show Try models side by side; frame serving as the production step |
| v1 does not train before 01:00 | Medium | Lose a training slot | Freeze prompt early; 300+ diverse calls by 23:30 |
| Prompt changed after bulk send | Medium | New task, count resets | Version tag; change only by team decision |
| Result is "Prompt only" | Medium | No visible update | Harder cases and custom identifiers; "Prompt only" itself is a cost win, explain it |
| GPT teacher already perfect | Low-Medium | Nothing to correct | Org-specific CUSTOM identifiers the prompt does not describe |
| Examples too long | Low | Training fails | Chunk at about 1,500 tokens |
| Starter credit runs out | Low | Calls fail | Check balance; small model; own provider key |
| Demo-day failure | Medium | Bad demo | Warm adapter, cached demo, backup video |
| Crowded PII space | Medium | Less memorable | Corrections in our own UI, leak-rate numbers, Track 2 side by side |

---

## 17. Sources (main)

**Mubit:**
- Docs: https://docs.mubit.ai/llms-full.txt
- Site: https://mubit.ai/agents.md
- Middleware: https://middleware.now/
- SDK: https://pypi.org/project/mubit-sdk/
- Banyan Sapling: https://huggingface.co/MubitLabs/banyan-sapling
- Latte Bench: https://mubit.ai/bench
- PagerPal sample project: https://github.com/e1daru/pagerpal

**Event:**
- https://luma.com/nightshift-london
- The Discord rules and the teammate's brief (pasted, not public)

**Past events:**
- https://luma.com/p7pnjcu8 (Zero to Agent)
- https://github.com/dotruru/popthebubble (Pop the Bubble rubric)
- https://github.com/shumengliu/zero-to-agent (Rentry)

**Competitors:**
- https://openpipe.ai/blog/openpipe-training-inference-migrating-to-wandb
- https://www.tensorzero.com/
- https://developers.openai.com/api/docs/deprecations

**Full research:** `docs/research/2026-10-23-mubit-audit/`
- `report.md`: company, market, ideas
- `past-hackathons.md`
- `summary-uk.md`
- `evidence/`: CSV tables and agent write-ups
