# Contracts sources (C1 to C12)

[Dataset schema and workflow](../../../data/README.md) · [Documentation index](../../../docs/README.md). Run commands from the repository root.

Builds `data/docs/contracts.jsonl` from the approved contract sources in the dataset
design (section 4). The answer key comes from this code, never from an LLM.

```
pip install -r training/sources/contracts/requirements.txt
python training/sources/contracts/fetch.py        # raw files and text go to /tmp/raw/contracts, manifest into the repo
python training/sources/contracts/build.py        # renders 5 fills per template, checks, writes the JSONL
python training/sources/contracts/build.py --check-only   # re-validate the committed JSONL and templates
python training/sources/contracts/build.py --selftest     # render every slot kind 60 times and run the check
```

Files:

| Path | What |
|---|---|
| `sources.py` | source table: URL, subtype, kind, licence, and for publication pages which attachment to take (`attachment_ext`, `attachment_hint`); eval sources in `EVAL_SOURCES` |
| `fetch.py` | downloads each source (descriptive User-Agent, only from the source's own hosts and the gov.uk asset host, redirects included), extracts plain text (HTML, PDF re-flowed into paragraphs, DOCX with list numbers, ODT, EDGAR .txt, markdown), writes `data/sources/contracts/manifest.json` |
| `build.py` | template parser, fake value generators, renderer, schema check |
| `data/templates/contracts/<id>.txt` | one slotted template per source, no real personal values |

## Adding a template for a blocked source

1. Run `fetch.py --only C4` from a network that can reach the host. Text lands in `/tmp/raw/contracts/text/C4.txt`.
2. Copy it to `data/templates/contracts/C4.txt`, add the `#!` header (source_id, title, url, licence, kind), and replace every personal value with a slot. Keep the whole document.
3. Run `build.py`. The check sweeps the template for leftover structured identifiers (emails, UK phones, postcodes, sort codes, 8-digit accounts, IBANs, NI numbers, Luhn-valid card numbers) and fails if it finds one. Names and street addresses are not caught by the sweep: read the document.

## Template syntax

Header lines start with `#!`. `#! key: value` sets metadata; `#! pool NAME: text` adds one entry to a
pool used by `{{TEXT:NAME}}` (write `\n` for a line break; entries may contain slots).

Slots are `{{KIND:arg|form}}`. A role (`p1`, `tenant`, `landlord`, ...) is one fake person with their own
address, email, phone, bank details and company, generated once per fill and reused by every slot that names it.

| Slot | Renders | Key |
|---|---|---|
| `{{PERSON:role\|form}}` | forms: `full`, `title_full`, `title_surname`, `initials_surname` (O. Kovalenko), `initials` (OK or O.K.), `first`, `surname`, `upper_full`, `surname_first` (KOVALENKO, Olena), `alt_full` (other transliteration or accent: Olena / Elena, Siobhán / Siobhan), `print` (one of full, upper, surname-first, titled, fixed per role) | PERSON, entity_id = role |
| `{{SIGNATURE:role}}` | the role's name as signed: `/s/ Name`, full, initials, first name or surname | PERSON; `/s/ ` stays outside |
| `{{ADDRESS:role\|form}}` | `oneline`, `multiline` or `any`; sometimes a flat, a building name or `c/o` another person | ADDRESS (lines and town, newlines inside) + POSTCODE (+ PERSON for c/o) |
| `{{NOTICE:role\|form}}` | email or postal address, fixed per role | EMAIL or ADDRESS + POSTCODE |
| `{{EMAIL:role}}`, `{{EMAIL:role\|alt}}` | main or second email | EMAIL |
| `{{PHONE:role}}` | UK number from the Ofcom ranges for fiction, several formats | PHONE |
| `{{BANK_ACCOUNT:role}}`, `\|last4` | 8-digit account, or its last 4 digits ("account ending 4821") | BANK_ACCOUNT |
| `{{SORT_CODE:role}}` | NN-NN-NN | SORT_CODE |
| `{{IBAN:role}}` | GB IBAN built from the role's sort code and account, valid checksum, compact or grouped | IBAN |
| `{{CARD:role}}`, `\|last4` | Luhn-valid 16-digit card, or its last 4 digits ("card ending 4821") | CARD |
| `{{NI_NUMBER:role}}`, `{{DOB:role}}`, `{{ID_DOC:role\|passport}}`, `{{ID_DOC:role\|licence}}` | valid patterns | NI_NUMBER, DOB, ID_DOC |
| `{{CUSTOM:name}}` | organisation-specific identifier; `client`, `matter`, `nda`, `acct`, `vendor`, `policy`, `dotted`, `ref_slash` pick that format, any other name picks one at random | CUSTOM |
| `{{COMPANY:role}}` | company name (often containing a surname: "Hughes and Bradley Ltd"), or for a sole trader the person's own name | none, or PERSON for a sole trader |
| `{{COMPANY:role\|registered}}` | a company name, never a sole trader, for text such as "a company registered in Scotland"; it must come before the role's other COMPANY and TITLE slots | none |
| `{{TITLE:role}}` | job title | none |
| `{{DATE:name}}`, `{{DATE:name\|+364}}` | ordinary date in the fill's date format; same name, same date. Dates without an offset fall within two weeks before the fill's base date; an offset puts the date exactly that many days after (or, with `-`, before) the base date, for terms such as "begins on ... ends on" | none |
| `{{TEXT:pool}}` | an entry from a header pool | whatever its slots produce |
| `{{CHECK:x}}`, `{{CHECK:o}}` | ticked or empty box in the fill's style | none |
| `{{TAG:name}}` | nothing; adds `name` to `hard_cases` (used for `over_redaction_trap`) | none |

Structure:

- `{{ALT}}a{{OR}}b{{/ALT}}` picks one branch per fill. `{{ALT:name}}` makes every ALT with that name pick the same branch.
- `{{SHUFFLE}}item{{ITEM}}item{{/SHUFFLE}}` reorders blocks; items are joined by a blank line. Use it only where order does not change meaning.

Every fill also varies: the date format, checkbox glyphs, dotted or plain initials, one-line or multi-line
addresses, the signature layout where the template offers one, an optional `Our ref:` style footer
(CUSTOM) at the top or bottom, and in about a third of fills hard line wraps at 72, 80 or 96 characters,
as in text extracted from PDF. A wrap is never put inside an entity.

## Labelling decisions

- A postal address is ADDRESS (building, street, town; one span, newlines kept when split over lines) plus a separate POSTCODE. `c/o` stays outside the entity; the person after it is a PERSON with their own entity_id.
- Titles are inside the PERSON span ("Ms Kovalenko"); possessive `'s` stays outside.
- "ending 4821": the 4 digits are labelled, BANK_ACCOUNT when the text says account, CARD when it says card or a card brand.
- A company name that contains a surname stays unlabelled. A sole trader's company field is the person's own name and is labelled PERSON with the same entity_id as the signatory. Trading names that merely contain the surname are not generated, to avoid ambiguous keys.
- Notice addresses are labelled whether they look like a home or a business address.
- Over-redaction traps (street or place names outside an address, "9 May 2026", amounts) are left unlabelled and tagged `over_redaction_trap`.
