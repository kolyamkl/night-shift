"""Helpers shared by document generators."""
from __future__ import annotations

import random
from datetime import date, timedelta

from .. import ids
from ..core import E, HC, K
from ..names import Person
from ..world import Org

TODAY = date(2026, 10, 24)


def recent_date(rng: random.Random, days_back: int = 900, days_fwd: int = 0) -> date:
    return TODAY - timedelta(days=rng.randint(-days_fwd, days_back))


def date_text(rng: random.Random, d: date, style: int | None = None) -> K:
    if style is None:
        style = rng.choice([0, 0, 0, 1, 1, 2, 3, 5, 6, 8])
    return K(ids.format_date(d, style), "date")


def pick(rng: random.Random, *opts):
    return rng.choice(opts)


def greeting(rng: random.Random, p: Person, formal: bool = True) -> list:
    if formal:
        r = rng.random()
        if r < 0.55:
            return ["Dear ", p.title + " ", p.last_name("greeting_name"), ","]
        if r < 0.8:
            return ["Dear ", p.full("greeting_name"), ","]
        if r < 0.9:
            return ["Dear ", p.first_name("greeting_name"), ","]
        return ["Dear Sir or Madam,"]
    return [rng.choice(["Hi ", "Hello ", "Hey ", "Hi ", "Morning "]), p.first_name("greeting_name"),
            rng.choice([",", "!", " -", ","])]


SIGNOFFS_FORMAL = ["Yours sincerely,", "Yours faithfully,", "Kind regards,", "Best regards,", "Regards,"]
SIGNOFFS_INFORMAL = ["Thanks,", "Cheers,", "Many thanks,", "Best,", "Thanks again,", "Speak soon,", "Ta,", "x"]


def signoff(rng: random.Random, p: Person, formal: bool = True, org: Org | None = None,
            role: str | None = None, contact: bool = False, domain: str | None = None) -> list:
    """Closing + name (signature-only names are a hard case) + optional contact block."""
    out = [rng.choice(SIGNOFFS_FORMAL if formal else SIGNOFFS_INFORMAL), "\n"]
    if formal and rng.random() < 0.4:
        out.append("\n")
    r = rng.random()
    if formal:
        name = p.full("signature_name") if r < 0.75 else p.full_middle("signature_name")
    else:
        name = p.first_name("signature_name") if r < 0.6 else (p.nickname("signature_name") if r < 0.8 else p.full("signature_name"))
    out.append(name)
    if role:
        out += ["\n", role]
    if org is not None:
        out += ["\n", org.name_k()]
    if contact:
        out += contact_lines(rng, p, domain or (org.domain if org else None))
    return out


def contact_lines(rng: random.Random, p: Person, domain: str | None) -> list:
    out = []
    lab_t = rng.choice(["T: ", "Tel: ", "Phone: ", "Mob: ", "M: ", "", "Direct: "])
    lab_e = rng.choice(["E: ", "Email: ", "", "e: "])
    if rng.random() < 0.85:
        out += ["\n", lab_t, p.mobile() if rng.random() < 0.6 else p.landline()]
    if rng.random() < 0.8:
        out += ["\n", lab_e, p.work_email(domain) if domain else p.email()]
    return out


def amount(rng: random.Random, lo: float, hi: float, style: int | None = None, step: float | None = None) -> K:
    x = rng.uniform(lo, hi)
    if step:
        x = round(x / step) * step
    x = round(x, 2)
    from ..world import money_text
    st = rng.choice([0, 0, 0, 1]) if style is None else style
    return K(money_text(x, st), "amount")


def kv_block(rng: random.Random, rows: list[tuple[str, object]], style: int | None = None) -> list:
    """Render label/value rows as 'Label: value' lines, a markdown table, or aligned columns."""
    st = rng.choice([0, 0, 1, 2]) if style is None else style
    out: list = []
    if st == 1:
        out += ["| Field | Details |\n|---|---|\n"]
        for lab, val in rows:
            out += ["| ", lab, " | ", val, " |\n"]
        return [HC("table_layout", out)]
    width = max(len(r[0]) for r in rows) + 2
    for lab, val in rows:
        if st == 2:
            out += [(lab + ":").ljust(width), val, "\n"]
        else:
            out += [lab, ": ", val, "\n"]
    return out


def custom_id(rng: random.Random, org: Org, label: str | None = None) -> tuple[str, E]:
    return org.custom(rng, label)
