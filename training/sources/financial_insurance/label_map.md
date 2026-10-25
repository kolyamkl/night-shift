# Gretel label mapping

Maps the PII labels of [gretelai/synthetic_pii_finance_multilingual](https://huggingface.co/datasets/gretelai/synthetic_pii_finance_multilingual) (Apache-2.0, by Gretel.ai) to our 13 entity types (design section 9.4, team pack 7.5).

`build_gretel.py` reads this table directly, so it is the only copy of the mapping. In the second column, `keep visible` means the label is dropped and the text stays as it is, and `drop document` means any document carrying the label is left out. A label that is missing from the table also drops its document, and the build reports it by name (`unmapped_label:<label>`), so the table can be extended.

**Checked against the data (24 Oct 2026)** at revision `7b844d16738527a04264f50214cb426a4cea0897`, both English files (`data/English_train-00000-of-00001.parquet`, 26,019 rows; `data/English_test-00000-of-00001.parquet`, 2,891 rows). `pii_spans` is a JSON list of `{start, end, label}` with no value field. The labels found are exactly the 29 below, the same set as the dataset card. Span counts in the train file: name 32,535, company 31,864, street_address 20,057, date 8,265, phone_number 4,782, email 2,559, time 2,216, first_name 1,454, date_of_birth 1,328, swift_bic_code 1,054, customer_id 958, last_name 926, employee_id 814, bban 803, iban 784, credit_card_security_code 751, bank_routing_number 733, passport_number 727, account_pin 726, credit_card_number 679, ssn 675, driver_license_number 665, ipv4 641, ipv6 545, date_time 510, user_name 509, api_key 497, password 461, local_latlng 447.

| Gretel label | Our type | Why |
|---|---|---|
| `name` | PERSON | Person name. The span must look like a name (see value checks below) |
| `first_name` | PERSON | Part of a person name. Adjacent first and last name spans (only spaces between) are merged into one PERSON span |
| `last_name` | PERSON | As above |
| `street_address` | ADDRESS | Any UK postcode inside the span is split out as its own POSTCODE entity; the ADDRESS parts of the span share one entity_id |
| `local_latlng` | ADDRESS | Coordinates given as a person's or property's location ("last known address of 60.60, -64.89"); ADDRESS is the closest type |
| `email` | EMAIL | All email addresses are EMAIL |
| `phone_number` | PHONE | All phone numbers are PHONE |
| `iban` | IBAN | |
| `bban` | BANK_ACCOUNT | Domestic account number. In the UK files about one in ten `bban` values is a full GB IBAN; a value with a valid IBAN checksum becomes IBAN instead |
| `bank_routing_number` | drop document | A US routing number. In the UK files the label sits either next to the words "routing number" (a non-UK document, already left out by the UK rule) or on some other number: a policy number, an account number, a registered office given as digits. Code cannot tell which type those should have, so the document is left out |
| `credit_card_number` | CARD | |
| `credit_card_security_code` | CARD | Card data (CVV). Not a card number, but CARD is the closest type and it must be hidden |
| `ssn` | ID_DOC | Not a UK NI number. In the UK files the values are US SSNs (NNN-NN-NNNN, which the UK rule already drops), Swedish personal numbers (600427-7817), Italian fiscal codes (MLNSPH31D16F536O) and 15-digit French numbers: national identity numbers, for which ID_DOC is the closest type. A value in UK NI format (two letters, six digits, one letter, as in ZZ 99 50 17 T) becomes NI_NUMBER instead |
| `date_of_birth` | DOB | |
| `driver_license_number` | ID_DOC | |
| `passport_number` | ID_DOC | |
| `customer_id` | CUSTOM | Customer identifier (design 9.4) |
| `employee_id` | CUSTOM | Identifier tied to a specific person |
| `user_name` | CUSTOM | Usernames map to CUSTOM (design 9.4) |
| `ipv4` | CUSTOM | IP addresses map to CUSTOM (design 9.4) |
| `ipv6` | CUSTOM | As above |
| `account_pin` | CUSTOM | Secret tied to one account holder. The design drops documents only for passwords and API keys, so the PIN is mapped to the closest type and hidden |
| `company` | keep visible | Company names stay visible (team pack 7.5). A hidden span that overlaps a company span is ambiguous (for example a sole trader's own name), so that document is dropped |
| `date` | keep visible | Ordinary date. Exception: a date written right after "Date of birth" or "DOB" becomes DOB (field-label sweep below) |
| `date_time` | keep visible | Ordinary date and time (same exception) |
| `time` | keep visible | Ordinary time |
| `swift_bic_code` | keep visible | Identifies a bank, not a person (design 9.4) |
| `password` | drop document | Design 9.4 |
| `api_key` | drop document | Design 9.4 |

Changes from the first version of this table (written from the dataset card, before the data could be read): `ssn` was NI_NUMBER and is now ID_DOC (NI_NUMBER only in UK NI format); `bank_routing_number` was SORT_CODE and now drops the document; `bban` values that are valid IBANs become IBAN.

## Value checks

The labels are noisy: the UK files contain `name` spans such as "[Secondee Name]", "impartial expert", "Shareholder 3" and "user_name: irene99", `email` spans such as "[insert customer support email]", and a `bban` span on the word "BBAN". A document is dropped when a span it relies on fails one of these checks (drop reason in brackets):

- the span contains `[ ] { } < >`, so it is template text, not a value (`template_placeholder_span`);
- a PERSON span has no capital letter, or contains a digit or one of `_ @ / \ : #` (`person_span_not_a_name`);
- a PHONE, BANK_ACCOUNT, SORT_CODE, IBAN, CARD, NI_NUMBER, DOB or ID_DOC span has no digit (`span_value_not_valid:<TYPE>`);
- a CUSTOM span has no digit or contains ": " (a `user_name` span instead must not contain whitespace) (`span_value_not_valid:CUSTOM`);
- an EMAIL span has no `@` (`email_span_without_at`).

A possessive ending inside a PERSON span ("Smith's") is trimmed off, so it stays outside the entity, and a title written right before a PERSON span (Mr, Mrs, Ms, Miss, Mx or Dr, with or without a dot) is moved inside it, as the T1 prompt asks.

## Other rules applied with the mapping

- **Span check:** a document is dropped if any span has invalid offsets, does not match the span's own value field (when the dataset gives one), or starts or ends in the middle of a word. Surrounding whitespace and trailing `.,;:` are trimmed from spans first.
- **Field-label sweep** (design 9.4, a fix that is unambiguous): a value written right after an explicit field label, where the dataset left it unlabelled, is added. "Date of birth" or "DOB" followed by a date gives DOB; "Sort code" followed by `NN-NN-NN`, `NN NN NN` or six digits gives SORT_CODE; "Account number", "Account no.", "Acct no." or "A/C no." followed by a value with digits gives BANK_ACCOUNT; "Passport number", "Driving licence number" or "Driver's license number" gives ID_DOC; "Policy", "Claim", "Customer", "Client", "Member", "Membership", "Case", "Patient", "Employee", "Applicant", "Application", "Loan", "Tax reference" or "UTR", followed by "number", "no.", "ID", "#", "ref", "reference", "code" or a colon, then a value of at least five characters with a digit that is not a year, gives CUSTOM. A field value that partly overlaps a labelled span drops the document (`field_partial_overlap:<TYPE>`).
- **Overlaps:** a duplicate or nested span of the same type is removed. Any other overlap between hidden spans drops the document.
- **Regex sweep** for structured identifiers outside every span (email, IBAN with a valid checksum, Luhn-valid card number, NI number, UK phone, UK postcode, sort code `NN-NN-NN`, standalone 8-digit number). A match inside a kept-visible span (such as a date) is ignored. A match is added as an entity only when it is unambiguous:
  - email, valid IBAN, NI number and postcode are always added;
  - a phone number is added when it is written with separators or `+`, or follows "tel", "phone", "mobile", "call", "fax" or "contact";
  - a card number is added when "card" appears in the 40 characters before it;
  - a sort code is added when "sort" appears in the 25 characters before it;
  - an 8-digit number becomes BANK_ACCOUNT when "account", "acct" or "a/c" comes shortly before it on the same line.

  Any other match drops the document (`sweep_ambiguous:<kind>`), and so does a match that partly overlaps a span.
- **Validator rules:** a document is dropped when an email address in it is not inside an EMAIL entity (`email_not_covered`, for example an email inside a company span), or when its text contains a bracketed token that the scorer would read as a placeholder, such as `[Address]`, `[Email]` or `[NAME_1]` (`placeholder_like_token`).
- **entity_id:** mentions with the same type and the same value (ignoring case, spacing and, for PERSON, a leading title) share an id. The ADDRESS parts of one street address share one id. A one-word PERSON mention joins the only longer PERSON name in the document that contains that word; when two longer names contain it, it keeps its own id.
