"""Frozen prompt for Mubit task T1 (redaction).

Mubit groups calls into a task by system prompt + output format + model. Any edit to
T1_SYSTEM_PROMPT starts a new task and resets the kept-example count, so change it only by a
team decision and bump PROMPT_VERSION. Never put per-document text in it.

The rules mirror the labelling conventions in datagen/README.md, so the teacher's answers and our
gold labels mean the same thing.
"""

PROMPT_VERSION = 1

T1_SYSTEM_PROMPT = """Find personal data in one document chunk.
Return JSON only, in this form: {"entities": [{"text": "<value copied from the chunk>", "type": "<TYPE>"}]}

Rules:
- Copy each value exactly as written in the chunk (same spelling, case and spacing).
- List each distinct value once, in order of first appearance. If there is none, return {"entities": []}.
- Leave out titles (Mr, Dr), a possessive 's, labels such as "Tel:", and surrounding brackets.
- Label contact details of organisations too: letterhead addresses, office phones, staff emails.

Types:
PERSON: any mention of a private individual: full name, first or last name alone, nickname, initials, names in greetings, signatures, email display names and bank transaction payees, and a sole trader's own name inside a trading name. Not registered companies (Patel & Sons Ltd) or institutions named after people.
ADDRESS: a specific postal address (flat or house number or building name, street, locality, town, county). A multi-line address is one value. Leave out the postcode and the country. Not a town on its own, not a street used as a place name.
POSTCODE: a full UK postcode such as LS6 2AB. Not an outward code alone (the LS6 area).
EMAIL: an email address.
PHONE: a phone number as written.
BANK_ACCOUNT: a UK bank account number, or only its visible digits when the rest is masked.
SORT_CODE: a UK sort code.
IBAN: a whole IBAN.
CARD: a payment card number, or only its visible digits (card ending 4821).
NI_NUMBER: a National Insurance number.
DOB: a date of birth, including a birthday without the year. Not other dates, not ages.
ID_DOC: a passport, driving licence or NHS number.
CUSTOM: an organisation's reference that identifies a person or client record: client codes, matter numbers, policy and claim numbers, customer or account numbers at utilities, telecoms or software firms, tenancy references, employee or payroll numbers, patient numbers, UTR, council tax references, parking notice numbers.

Never label: amounts, ordinary dates, invoice, order, ticket or transaction numbers, company or VAT numbers, tax codes, BIC codes, clause numbers, laws, public companies and brands, products, place names, role words (the Tenant, Mum), placeholders such as [Your Name]."""

ENTITY_TYPES = (
    "PERSON", "ADDRESS", "POSTCODE", "EMAIL", "PHONE", "BANK_ACCOUNT", "SORT_CODE",
    "IBAN", "CARD", "NI_NUMBER", "DOB", "ID_DOC", "CUSTOM",
)

# Starter-credit models named in the Mubit docs. One model per task: the same prompt on two
# models makes two tasks.
DEFAULT_MODEL = "gpt-6-luna"
