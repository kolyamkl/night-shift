# PII dataset research (24 Oct 2026)

> Research snapshot, including earlier training designs and measurements. For the current app request shape and operational workflow, read [Mubit integration](../../MUBIT.md).

Overnight research and data build for Veil's redaction model (Mubit task T1).

**Start with [TRAINING-PLAN.md](TRAINING-PLAN.md).** Ukrainian summary: [summary-uk.md](summary-uk.md).

| File | What |
|---|---|
| [BAKEOFF.md](BAKEOFF.md) | Teacher vs student, what data Mubit expects, the two T1 pipelines, the three-approaches question, one command to compare designs and teachers without training |
| [TRAINING-PLAN.md](TRAINING-PLAN.md) | Bottom line, data inventory, round files, step-by-step commands, decisions, office-hours questions, risks |
| [work/mubit-training-guide.md](work/mubit-training-guide.md) | How Mubit trains, grades and serves; corrections; costs; gold-label import option; 12 questions |
| [work/datasets.md](work/datasets.md), [work/datasets.csv](work/datasets.csv) | 75 open datasets: size, labels, licence, real vs synthetic, recommended use, red flags |
| [work/external-datasets.md](work/external-datasets.md) | What we converted, label mappings, counts, quality issues, obligations |
| [work/methods.md](work/methods.md) | Approaches, models, benchmarks, metrics, placeholders, ICO position, recommendations |
| [work/uk-formats.md](work/uk-formats.md) | 13 UK identifier regexes and validators, tested |
| [work/hard-cases.md](work/hard-cases.md) | 108 hard cases and keep traps |
| [work/synthetic-stats.md](work/synthetic-stats.md) | Statistics of the 100k synthetic set |
| [work/baseline-results.md](work/baseline-results.md) | Regex baseline scores on both eval sets |
| [work/CONTEXT.md](work/CONTEXT.md) | Shared brief used by the research agents |
| `work/evidence-*.csv` | Evidence rows with quotes checked against saved pages |

Code: `datagen/` (generator), `dataconv/` (open-dataset converters), `evalkit/` (prompt, redaction, scoring, Mubit sender). Data: `data/` (gitignored).
