# Correspondence templates

[Dataset schema and workflow](../../README.md) · [Documentation index](../../../docs/README.md). Paths in commands below are relative to the repository root.

One file per source: `R1.txt` to `R5.txt` (Enron email threads) and `R6.txt` to `R9.txt`
(UK letter templates, filled). Each file has a header (`# key: value` lines ending with
`# ---`) and the source text in which every personal value is a typed slot such as
`{{PERSON:usf_counsel|last_comma_first}}` or `{{EMAIL:usf_counsel|<last><f>@usfilter.com}}`.
Slot keys are roles, never real names. `[[opt:...]]` and `[[alt:a||b]]` blocks are added
text variations, not source text; they may be nested.

The full slot syntax is in the docstring of `training/sources/correspondence/build.py`,
which renders 5 fills per template into `data/docs/correspondence.jsonl` and writes the
answer key from the slots. Provenance and checksums of the raw sources are in
`data/sources/correspondence/manifest.json`.

Changes to the original text, applied to all five Enron threads:
- headers reduced to Date, From, To, Subject, Cc; display names taken from X-From/X-To;
  Message-ID, Bcc and the other X- headers dropped;
- names, emails, phones and every postal address replaced by slots, including the registered
  company addresses in R3 and the hotel's listing address in R4 (one address rule with the
  T1 prompt since 24 Oct); company and hotel names stay as text;
- R3: the Lotus Notes column table is flattened into plain header lines;
- R5: "?" encoding artefacts replaced by spaces;
- dates are `{{DATE:...}}` slots so each fill can move them by a calendar-preserving
  number of years and print them in US or UK style.

R6 to R9 (blank templates from justice.gov.uk, ico.org.uk and acas.org.uk):
- every bracketed field is filled with slots or `[[alt]]` text, and guidance notes, asterisks
  and "delete as appropriate" lines are removed; each header's `notes` lists what was added;
- every postal address in a sender, recipient, contact or notice role, a person's or an
  organisation's, is an ADDRESS slot with a separate POSTCODE (as in the T1 prompt);
- `locales: uk`, so dates and titles are always written in UK style;
- employers, firms, landlords and other organisations are invented.

R10 (sec.gov) is not used, by decision. R11 has no template: the letters linked from the
committee publication page sit behind a Cloudflare bot challenge on committees.parliament.uk
(see the manifest). A letter saved by hand from a browser as
`/tmp/raw/correspondence/R11_<document id>.pdf` is picked up by
`fetch.py --only R11`. Adding `R<n>.txt` here is enough for `build.py` to render it.
