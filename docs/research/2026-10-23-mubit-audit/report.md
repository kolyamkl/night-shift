# Night Shift: Mubit audit and idea research

> Dated product research; historical SDK, routing and company observations may change. Use [Mubit integration](../../MUBIT.md) for the current repository implementation.

Date: 2026-10-23, written 16:45 to 17:30 BST, before kickoff. Research only, no project code.
Method: three research agents (competitors, idea market, Mubit team and signals) plus first-hand reading of Mubit's docs, SDK and product sites. 180 evidence rows with checked quotes live in `evidence/`. Raw page copies stay local (copyright), not in this public repo.
Labels: **[F]** fact seen in a source, **[E]** estimate with method, **[I]** our inference.

---

## 0. Bottom line

1. **Mubit grades adapters on imitation, not on correctness.** A version "passes" when it "Matched X% of your provider model's answers". Human corrections are not in the public training path; the only documented feedback is a Good/Bad button in the console. The current brief's correction loop does not work without a mechanism Mubit has to confirm at kickoff. [F docs]
2. **The event product is Mubit Middleware.** It turns "application memory" (corrections, policies, examples) into lightweight model updates, with a change detector that triggers a refresh. Their own example: an escalation policy changes, and the model's escalation behaviour updates. [F middleware.now]
3. **The founders' thesis is "It has been reminded, not improved."** A note in a prompt is not learning; a weight update is. The judging rule is literal: "Show a correction turning into a model update in your demo." [F]
4. **Competitors are dying or consolidating.** OpenPipe shut on 30 Jul 2026, TensorZero wound down, Adaptive ML and Portkey were acquired. OpenAI is closing fine-tuning and distillation; new jobs end on 6 Jan 2027. That is a real "own your intelligence layer" hook. [F]
5. **Tenancy checker scores lowest of our shortlist (23/40).** 7+ AI tenancy checkers already live, some free. The one-off deadline (31 May 2026) has passed. The privacy angle is weak. A renting-agent project already took 2nd in a Mubit track in May 2026. [F]
6. **Recommendation: "Threshold", adverse-media hit triage for UK financial-crime teams.** Analysts already make a "discount or escalate" decision on every hit, so corrections are the normal workflow, not a demo trick. Frontier models over-flag marginal evidence (69% of AI false positives in Taktile's KYBench), and that gap is the firm's risk appetite, which only corrections can teach. Strong privacy case (customer PII, tipping-off rules). Low crowding. Fits Nick's banking-ops background.
7. **Runner-up: complaint triage for FCA firms (DISP and Consumer Duty).** 1.74m complaints per half-year, fixed regulator categories, and real labelled data with a clean licence (CFPB, CC0). Safer data, more relatable, a bit more crowded.
8. **Demo shape that fits the judges:** the same correction applied two ways, as memory now ("reminded") and as an adapter update next refresh ("improved"), measured on a held-out set. Then change the policy live (Track 3) and show the gate refusing to switch until the new version passes.

---

## 1. Mubit as a company

| Topic | What we found | Label |
|---|---|---|
| Legal entity | Reliable AI, Inc. (site footer). HQ listed as Aberdeen by investors, Canary Wharf WeWork per job ad | F |
| Founders | Anil Peri (CEO, Cranfield MSc) and Shankha Dutta (CTO, Lancaster MSc Data Science). Built companies together since 2020: SwiftSkill (esports analytics), Rice (org memory), Mubit from Nov 2025. Both on Forbes 30 Under 30 Europe 2026 | F |
| Team | About 7 people. One open role (Founding Engineer, on site). A host, Eldar, was hired from their first hackathon | F |
| Funding | About $2.1M (company-reported, Forbes, Apr 2026) from Hoxton Ventures (fund IV, Hussein Kanji on board) and Heavybit, plus Techstars and angels from Cloudflare, AWS and Mistral. Round label differs by source | F |
| Traction | "Nearly 1,500 engineers" on the waitlist (Apr 2026). No named customers or case studies anywhere. Only hackathon projects, all on the old memory product | F |
| Public output | 2 field notes (Minima; request-path authority), Latte Bench (do retained notes help a model improve: 7 of 11 models better, 4 worse), Banyan Sapling (policy/evidence/claim verifier on Qwen3-30B-A3B, uploaded 2026-10-22), Minima (advice-only model recommender, 2 stars) | F |
| Launch | Night Shift doubles as launch. "Launch week" 26 to 30 Oct 2026: five features in five days | F |

**Positioning over time [F, agent M]:**

| When | Headline |
|---|---|
| Feb 2026 | "Memory + State Infra for AI Agents" |
| Apr 2026 | "Operational Memory for Agent Systems", with a comparison table *against* fine-tuning ("No GPU costs") |
| Jun 2026 | "It has been reminded, not improved": memory notes are not enough |
| Sep 2026 | Middleware: "task-adapted open models from your model calls" |
| Oct 2026 | "Agentic runtime calibration. Build reliable agents with a model for every task" |

[I] A full reversal on weights in six months. Memory is now the *source of training signal* for model updates. A project that connects both halves (memory and weights) tells their own story back to them.

**What the founders repeat [F]:** "agents have no experience", "systems of experience for agents", "It has been reminded, not improved", "a set of corrections that keeps coming back. A field in an invoice. The wording in a support reply.", "own your intelligence layer". Shankha cares about an inspectable request path and reviewable, reversible edits. Their benchmark pages list what they do *not* prove. [I] They will reward measured, honest claims over hype.

---

## 2. How the product actually works (and what it means for us)

### 2.1 Facts from docs.mubit.ai

- **Gateway:** base URL + Mubit key swap for OpenAI, Anthropic, Gemini and OpenAI-compatible services (OpenRouter, Groq, Together, Mistral). Server-side only (no CORS).
- **Task** = same system prompt + tools + tool choice + output format + model. Numbers, dates and IDs in the prompt are tolerated; other changing words split the task. Task name comes from the first words of the system prompt.
- **Session** from `metadata.thread_id`, `session_id`, `conversation_id`, Anthropic `metadata.user_id`, or derived. Test cases are set aside **by session**.
- **Kept examples:** not every call is kept. First training at **25 kept examples** by default.
- **Test result per version:** Passed / Below target ("Matched {a}% of your provider model's answers on {n} test cases · needs {need}%") / Malformed tool calls / **Prompt only** (the base model with the prompt did as well) / Not tested.
- **Limits:** daily training limit (resets 00:00 UTC = 01:00 London), a pause between trainings, no retry button (recovery = new calls with new messages), "examples too long to train on". Try models: daily call limit, **3 adapter starts per org per UTC day**, first start takes minutes.
- **Serving:** "There is no Mubit model ID: you can't send a call to an adapter by naming it as the model." Yet Requests has a "Served by" column, and the homepage says it switches "only when it does better".
- **Feedback:** only "Rate this reply: Good or Bad" in the console.
- **Import past calls** (Langfuse, Braintrust, Logfire) reads only calls from before the project's first live call.
- **Headers:** `x-middleware-store: false` / `x-middleware-record: metadata|off` keep a call out of the record. Every answer carries `x-middleware-request-id` (`mreq_` + 32 hex).

### 2.2 Things the docs do not say, found elsewhere

- **The marketing site and the docs disagree.** `mubit.ai/agents.md` promises outcome attribution, prompt and skill optimization, and links to four docs pages that now return 404. [F]
- **The old memory SDK still ships:** `mubit-sdk` 0.13.2 on PyPI and `@mubit-ai/sdk` (0.14.0-rc.1 on 2026-09-03). Surface: `remember`, `recall`, `record_outcome`, `record_step_outcome`, `feedback`, `optimize_prompt`, prompt and skill versions with diffs and activation. `feedback(good=True|False)` credits recalled memory entries. [F]
- **Middleware page (the hackathon product):** a shared model component plus a generator that produces a small app-specific update, plus a change detector that monitors memory. It also says that its demonstrated path still uses a brief fitting step. [F] Related research: Text-to-LoRA (arXiv 2506.06105), Internalizer (arXiv 2610.11715, Oct 2026).

### 2.3 What this means for the build [I]

1. **Corrections vs imitation.** If our reviewer corrects GPT, the corrected answer is not what the adapter is graded against. Without an event-specific path, corrections either do nothing or *lower* the pass rate. Ask first (section 9).
2. **A path that works even if Mubit only distils: improve the teacher.**
   - Fast path, in seconds: store each correction as a precedent (in Mubit memory via the SDK, or our DB).
   - On the next similar call, put the top precedents in the **user** message, never the system prompt, so it stays one task. The frontier model now answers the corrected way. This is "reminded".
   - Slow path, next refresh: Mubit trains the next adapter version on those corrected answers. On a held-out set, show the adapter handling the case with fewer or no precedents. This is "improved".
   - This mirrors Middleware's own design (memory as the source of record, a refresh when enough has changed).
3. **Show the gate.** A "Prompt only" or "Below target" verdict is a feature: it proves Mubit does not switch blindly. Plan one task that will likely be "Prompt only".
4. **Plan around 01:00 London resets:** v1 before 01:00 Friday night, v2 on Saturday, and a possible v3 between 01:00 and the 05:00 Sunday freeze.

---

## 3. Market and competitors

### 3.1 What happened to the category [F, agent L]

| Player | Status 2026 |
|---|---|
| OpenPipe | Bought by CoreWeave (Sep 2025); platform stopped training and inference 30 Jul 2026 |
| Predibase | Bought by Rubrik (Jun 2025) |
| TensorZero (closest open-source twin) | Wound down Jun 2026, returning capital |
| Adaptive ML | Bought by Datadog (30 Jun 2026) |
| OpenAI fine-tuning / distillation | Closed to new orgs 7 May 2026; all new jobs end 6 Jan 2027 |
| Portkey / Helicone / Langfuse | Palo Alto Networks / Mintlify (frozen) / ClickHouse |
| OpenRouter | Stripe agreed to buy (not closed) |
| Martian / Not Diamond | Pivoted to research / narrowed to coding agents |
| **Experiential Labs** (YC S26, 2 people) | Most direct new rival: OSS zero-markup gateway, trains an owned model on Tinker, promises "at least 50% lower cost at the same or better quality" with an SLA |
| Inference.net | Closest product loop; a human approves each switch |
| Applied Compute | About $50M annualised revenue, consulting-heavy custom post-training |
| Trajectory, RELAI, Datawizz | New continual-learning startups (corrections → post-training, regression-controlled loops) |

Lesson [I]: a thin loop on someone else's traffic and GPUs gets bought or squeezed unless it owns a decision layer people trust.

### 3.2 Mubit vs the field

**Differentiated (documented):** automatic task discovery by fingerprint; honest gating with a "Prompt only" verdict; low first-training threshold (25); memory and adapters in one loop.
**Weak or unproven:** no measured results in public; imitation-only pass metric vs "switch only when it does better"; serving, weight export and privacy not documented; training not on for every workspace; tiny team; crowded "stop renting intelligence" slogan.

### 3.3 Market gaps nobody fills well

1. Proof before switching, graded on **outcomes**, with automatic rollback on drift.
2. Deciding **which layer** to fix: memory lesson, prompt, route or weights.
3. **Cost per successful task**, not cost per token (retries and human review erase small-model savings).
4. Self-serve post-training for teams with no ML staff, now that OpenPipe and TensorZero are gone.
5. **Refugees from OpenAI fine-tuning** before 6 Jan 2027.
6. Portability: exportable adapters, datasets and eval history (buyers were burned by shutdowns).

### 3.4 Where Mubit fits best (sectors) [I, using the docs' own mechanics]

Mubit pays off where five things hold at once: (a) the same narrow decision repeats thousands of times, (b) inputs are long enough that frontier cost hurts, (c) answers are fixed labels or fields, (d) a human already reviews outputs, so corrections exist for free, (e) data is regulated, so "own the model" is a requirement, not a nice-to-have.

| Sector | Recurring decision | Why it fits |
|---|---|---|
| Financial crime ops (banks, EMIs, fintechs) | Adverse-media and screening hit disposition, alert triage | Huge volume, 85 to 95% false positives (vendor-reported), analysts disposition every hit, strict privacy |
| Complaints and conduct (FCA firms) | Complaint classification, vulnerability, deadlines | 3.5m complaints a year, regulator-defined categories, Consumer Duty |
| Fraud reimbursement (PSPs) | APP scam claim triage | 248,070 cases in 2025, every claim needs an in-scope / exception decision |
| Housing (social landlords) | Awaab's Law hazard triage | Hard clocks (24h / 10 working days), a live rule change on 30 Nov 2026 |
| Contact centres and BPOs | QA scoring against a scorecard | 89% run calibration sessions (COPC 2022); per-client scorecards = per-client tasks |
| Employment law / HR | Claim and grievance coding | Employment Rights Act phases on 1 Oct, 30 Oct 2026, 1 Jan 2027 |

---

## 4. What the judges will reward

From the judging rules, founders' posts and past Mubit hackathons [F + I]:

1. **Hit the literal criterion live:** a correction, then a model update, then the same kind of input fixed.
2. **Measure like Latte Bench:** matched held-out inputs, with and without the update; quality, pass rate, cost per successful task, latency; say what the demo does not prove.
3. **Contrast "reminded" with "improved".** The same correction as a memory note vs as an adapter update.
4. **Make the gate the hero:** show a task where Mubit refuses to switch, and a rollback after drift.
5. **Fast refresh with a change detector:** change a policy mid-demo; their own example is an escalation policy.
6. **Avoid:** a single "distilled Llama is 90% cheaper" demo (looks like OpenPipe or Experiential); a routing cost dashboard; a chatbot that "remembers the user" (their old product, and past winners already did it); invoice-field or support-reply bots (the founders' own examples, so the most crowded).

---

## 5. Ideas: scored shortlist

Scoring 1 to 5 on what matters here. "Mubit fit" = long inputs + checkable labels + natural corrections. Totals out of 35.

| Idea | Mubit fit | Usefulness and volume | Data in 36h | Privacy case | Demo moment | Low crowding | Team fit | Total |
|---|---|---|---|---|---|---|---|---|
| **A. Threshold: adverse-media hit triage** | 5 | 5 | 4 (synthetic, labels by construction) | 5 | 5 | 5 | 5 | **34** |
| **B. Complaint triage (DISP, Consumer Duty)** | 5 | 5 | 5 (CFPB CC0 + UK synthetic) | 5 | 4 | 3 | 5 | **32** |
| C. APP scam reimbursement triage | 4 | 5 | 4 (Apache-2.0 scam dialogues + synthetic) | 5 | 4 | 3 | 5 | 30 |
| D. Awaab's Law hazard triage (Track 3) | 4 | 4 | 3 (synthetic only) | 4 | 5 | 4 | 2 | 26 |
| E. Motor finance redress eligibility | 4 | 4 (scheme partly suspended until Feb 2027 hearing) | 3 | 5 | 3 | 5 | 5 | 29 |
| F. Tenancy agreement checker (current brief) | 3 | 2 | 3 | 2 | 3 | 1 | 3 | **17** |

Agent I's independent scoring (8 criteria, /40) put complaint triage first (36) and tenancy last (23). It did not deep-dive adverse media; we did (section 5.1).

### 5.1 A. Threshold: adverse-media hit triage (recommended)

- **The recurring task:** a screening system matches a customer to a news article. An analyst decides: same person? Is the customer the subject or a victim or witness? Allegation, charge or conviction? In scope for financial crime? Recent enough? Then **discount or escalate**, with a written rationale for the audit file.
- **Volume and cost [F]:** UK firms spent £38.3bn on financial crime compliance in 2023, 66% of it on customer due diligence (LexisNexis Risk Solutions, survey of 254 firms; vendor source). Screening false positives run at 85 to 95% (Facctum, vendor-reported). Taktile estimates about 200,000 investigator-hours a year for a mid-size bank's KYB adverse-media work.
- **Why corrections matter here [F]:** Taktile's KYBench (Apr 2026, updated Sep 2026) found 69% of AI false positives were over-flagging real but marginal evidence (allegation stage, too old, peripheral role). Entity confusion was 1.5%. Hallucination was 0%. Their advice: build the review queue around "threshold adjudication". [I] That threshold is each firm's risk appetite, and analyst corrections are the only cheap way to teach it.
- **Privacy [I]:** customer names, dates of birth and suspicion are sensitive; tipping-off rules make leaking a suspicion a criminal matter. "We can't send this to a US API" is a real objection, and an owned open model answers it.
- **Data plan:** synthetic customer profiles plus synthetic news articles about fictional people, generated through Mubit as a separate task. Every hidden attribute (namesake, role, stage, category, event year) is chosen in code, so the correct disposition comes from a deterministic policy, not from an LLM. No real people, no defamation risk, no real PII in Mubit's recorder. Planted edge cases: namesakes with wrong age or city, the customer as victim, acquittals, civil disputes, traffic offences, 10-year-old events, company vs director, transliterated names, articles with several people.
- **Written vs tacit policy (the correction story):** the system prompt holds the firm's *written* policy, which is vague like real policies. Ground truth follows the analysts' *tacit* rules ("victims are discounted", "civil disputes are not financial crime", "events over 6 years old are discounted unless sanctions or terrorism"). GPT follows the written policy and over-flags. Analyst corrections teach the tacit rules.
- **Track 3 moment:** mid-demo the MLRO changes risk appetite ("allegation-stage articles about PEPs are now escalated"). The policy text is part of the system prompt, so the change creates a new task version. Show the change detector story: corrections on the new rule, refresh, the gate passes the new version, rollback kept.
- **Track 2 panel:** frontier vs adapter on the held-out set: accuracy, **escalation recall** (missing a true hit is the unacceptable error), false-escalation rate, cost per correct disposition, latency p50.
- **Incumbents [F/I]:** LexisNexis, Moody's, Dow Jones, ComplyAdvantage, Silent Eight, Quantexa, Taktile. Our wedge: mid-market fintechs and EMIs that cannot afford enterprise suites and still clear hits by hand.
- **Risks:** synthetic data may look too clean (base articles on real news styles, vary length and outlet); regulators expect a human to stay accountable (the model pre-dispositions, the analyst confirms); a missed true hit is worse than ten false ones (needs_review route, recall reported first).

### 5.2 B. Complaint triage for FCA firms (runner-up)

- **Task:** per complaint: is it a complaint under DISP, FCA product group and cause, vulnerability drivers (health, life events, resilience, capability), summary-resolution vs 8-week clock, and a risk that the ombudsman would uphold it.
- **Volume [F]:** 1.74m complaints at FCA firms in H2 2025 (1.83m in H1). The ombudsman received 305,726 new complaints in 2024/25, a six-year high.
- **Data [F]:** HF `CFPB/consumer-finance-complaints`, CC0, 1M to 10M real narratives with product and issue labels (US; labels chosen by complainants, so noisy). UK rules on top, UK synthetic complaints for the demo.
- **Do not scrape FOS decisions.** The ombudsman's site says you "must not reproduce our copyright material, or store any part of this site in any other website (or public or private electronic retrieval system), without our prior permission". Reading a few for realism is fine; a dataset is not. [F, financial-ombudsman.org.uk/legal-policy]
- **Crowding:** medium. Several vendors exist (Ctrl AI, ResolveCX, Good Outcomes, Malted) and "support" ideas will be common in the room.

### 5.3 Other candidates in one line each

- **C. APP scam reimbursement triage:** 248,070 cases and £576.4m losses in 2025; 89% of in-scope losses reimbursed. HF `BothBosu/multi-agent-scam-conversation` (Apache-2.0). Fraud is a popular theme.
- **D. Awaab's Law hazard triage:** the best live rule change (phase 2 on 30 Nov 2026 adds 7 hazard types), but short inputs, synthetic data only, weak team fit.
- **E. Motor finance redress:** 12.1m eligible agreements, numeric rules, but parts of the scheme are paused until the Feb 2027 hearing, and judges may ask "why not a rules engine?".
- **Contact-centre QA with calibration:** natural corrections (calibration sessions), long transcripts, per-client scorecards for Track 3. Incumbents (Tethr, MaestroQA, Observe.AI, Zendesk QA, Telonic). Fits Dmytro's support background; keep as a fallback.

---

## 6. Honest critique of the current brief

**Keep:** one frozen task, fixed schema, chunking, one session per document, synthetic data with planted labels, a record-off eval set, v1 before 01:00, warm adapter, backup video. All correct per the docs.

**Weak points:**
1. **The correction loop conflicts with how Mubit grades adapters** (section 2.3). Option 3 in the brief ("own dataset only") would fail criterion 1.
2. **Not really recurring.** The Renters' Rights Act spike was the 31 May 2026 information-sheet deadline. After that, agents reuse updated templates.
3. **The correction moment is contrived.** We plant issues and hope GPT misses them. With the rule list in the prompt, GPT will likely catch the disguised "check-out charge", and then there is nothing to correct.
4. **Already served:** at least 7 live AI tenancy checkers (Landlord HQ £9.99/mo, Contract Icks £49/scan, RightTo.Rent £99/property, LeaseScan $4.99, HomeLet/letting.zone and PAM free, HomeThink).
5. **Weak privacy case:** names and rent, low sensitivity.
6. **Judges have seen renting:** "Rentry", a renting agent with preference memory, took 2nd in the Mubit track at Zero to Agent (May 2026).
7. **Legal-liability Q&A risk:** a false "compliant" verdict can cost a landlord up to £7,000 in penalties.

If the team still wants housing, switch to Awaab's Law triage (live rule change on 30 Nov 2026) or to portfolio re-checks when rules change.

---

## 7. Recommended concept: Threshold

**One-liner:** Every "discount or escalate" decision your analysts make becomes your own model. Threshold clears adverse-media hits the way your team would, learns from every correction, and keeps customer data off third-party APIs.

**Pipeline (all calls through Mubit):**
1. **Hit disposition** (hero task, frozen prompt and schema): customer profile + article → `same_person`, `subject_role`, `stage`, `category`, `event_year`, `disposition` (escalate / discount / needs_review), `reason_code`, one-sentence rationale.
2. **File note** (second task): the audit rationale for the case file. It will likely pass fast or come back "Prompt only"; both are good to show the gate.
3. **Article generator** (data task, separate prompt): only for building the dataset.

**Learning loop (two speeds):**
- Analyst clicks Correct (disposition + reason code). The correction is stored as a precedent and sent to whatever path Mubit confirms at kickoff.
- **Now (reminded):** the next similar hit retrieves the precedent into the user message, so the frontier answer is already right.
- **Next refresh (improved):** the adapter version trained after corrections handles held-out cases of that type. Measure precedent-free.
- **Policy change (fast refresh):** MLRO edits risk appetite, a new task version starts, corrections flow, the gate decides when to switch.

**Demo, about 3 minutes:**
1. Problem (20 s): a fintech analyst clears dozens of adverse-media hits a day, and 85 to 95% are noise. Frontier models over-flag, and the bank cannot send customer data to them anyway.
2. Product (40 s): the hit queue, then one hit opened. The customer is the *victim* of the fraud in the article. GPT says escalate. The analyst corrects it to discount with reason R3 (victim).
3. Reminded (20 s): the next victim-type hit is already right, using the stored precedent.
4. Improved (40 s): Mubit console, task, adapter history v1 → v2. Held-out chart: GPT, v1, v2, and v2 without precedents. Escalation recall first.
5. Fast refresh (30 s): the MLRO changes the PEP rule. A new version is collecting, and the gate says "Below target" until enough corrections arrive. Show rollback kept.
6. Numbers and close (30 s): cost per correct disposition, latency p50, share of traffic the adapter can take. "OpenAI fine-tuning closes on 6 Jan 2027. This is the owned path."

**Metrics:** escalation recall, false-escalation rate, accuracy, cost per correct disposition, p50 latency, time from correction to fix (memory vs adapter), analyst minutes per 100 hits [E].

---

## 8. Business model

### 8.1 Mubit's model [I]
- **How it earns:** usage through the gateway plus training and hosting of task adapters on open models. On switched traffic it captures part of the gap between frontier prices and open-model serving costs. Free credits ($100 on the waitlist, $1.5M for hackers) drive adoption.
- **Strength:** zero-code start, automatic task discovery, low threshold, honest gate.
- **Risks:** an imitation ceiling (it cannot beat the teacher without outcome signals); frontier price cuts shrink the gap; serving and export not documented; a 7-person team against Experiential, Inference.net, Together and Fireworks; buyers burned by OpenPipe and TensorZero shutdowns will ask about continuity.
- **Openings:** OpenAI fine-tuning refugees, regulated sectors that must own models, "which layer to fix", cost per successful task. Vertical apps like ours are the proof they lack (no named customers yet).

### 8.2 Threshold's model [I, numbers are assumptions to validate]
- **Buyer:** MLRO or head of financial-crime operations at UK fintechs, EMIs, payment firms and challenger banks: regulated, high-volume, without enterprise-suite budgets.
- **Pricing options:** per hit dispositioned, or per screened customer per year, with an owned-model hosting fee. Anchor on analyst time saved, not tokens.
- **ROI formula:** (hits per month × minutes saved per hit × loaded analyst cost) − (platform fee + inference). Fill with the pilot's own numbers; do not quote invented ones on stage.
- **Moat:** each client's own adapters, calibration history and audit trail. No pooling of client data across firms; say so, since buyers will ask.
- **Expansion:** sanctions hits, transaction-monitoring alerts, periodic KYC reviews, then complaints (idea B) on the same engine.
- **Risks:** model-risk governance and regulator expectations, liability for a missed hit, incumbents bundling AI triage (Silent Eight, ComplyAdvantage, Taktile).

---

## 9. Kickoff questions (priority order)

1. Adapter versions are graded against the provider model's answers. **How do human corrections enter training?** An API that replaces a reply for a request ID? Does a Bad rating drop the example? Is Middleware's "application memory" the path, and through which API?
2. **Can our app call a passing adapter** (header, routing rule, "Served by")? Or only Try models?
3. Is the memory SDK (`mubit-sdk`, `/v2/control/*`) live for hackers, and does it feed Middleware refreshes?
4. Can the 25-example threshold or the pause between trainings be changed in Settings for the event?
5. Daily training limit; Try models calls per day; are the 3 adapter starts per day raised?
6. Which base model, and how long does one training take?
7. Starter credit amount and models; is `gpt-6-luna` the right teacher?
8. Is eval traffic with `x-middleware-record: off` acceptable under "every call through Mubit"?
9. Does a system-prompt policy change create a new task (we assume yes)? Is there a way to version a task instead?
10. Is Banyan Sapling hosted for hackers (it needs about 46 GB on an H200)?
11. Code freeze (05:00 or 10:00 Sunday), demo length, finals format.

---

## 10. Before 19:30 (no code)

- [ ] Team picks A or B in 10 minutes, using sections 5 and 6.
- [ ] Ask the section 9 questions at kickoff; note answers verbatim.
- [ ] On paper: written policy (vague), tacit rules (the ground truth), reason codes R1 to R8, output schema, 15 edge cases.
- [ ] Demo storyboard (section 7) with an owner for each part.
- [ ] Roles: data generator + eval (one person), backend + Mubit client (one), review UI + metrics panel (one), pitch + video + deck (one).

---

## 11. Sources (main)

Mubit and Middleware
- https://docs.mubit.ai/llms-full.txt (docs, read 2026-10-23)
- https://mubit.ai/agents.md and https://mubit.ai/llms.txt
- https://middleware.now/
- https://pypi.org/project/mubit-sdk/ (0.13.2)
- https://huggingface.co/MubitLabs/banyan-sapling
- https://mubit.ai/bench and https://github.com/MubitLabs/latte-bench
- https://github.com/MubitLabs/minima

Competitors
- https://openpipe.ai/blog/openpipe-training-inference-migrating-to-wandb
- https://www.coreweave.com/news/coreweave-to-acquire-openpipe-leader-in-reinforcement-learning
- https://www.tensorzero.com/ and https://news.ycombinator.com/item?id=48516504
- https://developers.openai.com/api/docs/deprecations and https://developers.openai.com/api/docs/guides/reinforcement-fine-tuning

Ideas and market
- https://labs.taktile.com/benchmarks/kybench (KYBench, updated 2026-09-07)
- https://risk.lexisnexis.co.uk/about-us/press-room/press-release/20240718-fighting-financial-crime-and-fraud
- https://www.zyphe.com/resources/blog/adverse-media-screening-aml-guide (cites Facctum false-positive range)
- https://www.fca.org.uk/data/aggregate-complaints-data-2025-h2
- https://www.financial-ombudsman.org.uk/businesses/resolving-complaint/our-insight/annual-complaints-data-insight-2024-25
- https://www.financial-ombudsman.org.uk/legal-policy (copyright terms)
- https://www.ukfinance.org.uk/news-and-insight/press-release/fraud-report-2026-press-release
- https://www.fca.org.uk/news/statements/fca-confirms-motor-finance-redress-scheme
- https://huggingface.co/datasets/CFPB/consumer-finance-complaints (CC0)
- https://cx.copc.com/hubfs/Global%20Benchmarking%20Series%202022_Contact%20Center%20Quality%20Assurance.pdf
- https://arxiv.org/abs/2506.06105 (Text-to-LoRA), https://arxiv.org/abs/2610.11715 (Internalizer)

Full evidence tables: `evidence/evidence-L.csv` (competitors), `evidence/evidence-I.csv` (ideas), `evidence/evidence-M.csv` (Mubit team). Detailed agent write-ups: `evidence/landscape.md`, `evidence/ideas-scan.md`, `evidence/mubit-signals.md`.
