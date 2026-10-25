"""Financial documents: invoice, utility bill, phone bill, bank statement, payslip."""
from __future__ import annotations

import random
from datetime import date, timedelta

from .. import ids, noise, world
from ..core import Doc, E, HC, K, text_of
from ..names import Cast, Person
from . import register
from .common import TODAY, amount, date_text, pick, recent_date

MON3 = [m[:3] for m in ids.MONTHS]


# --------------------------------------------------------------------------- local helpers
def merge_str(atoms: list) -> list:
    """Join consecutive plain-text atoms so noise.page_breaks can see paragraph breaks ("\\n\\n")
    that Doc.ln()/Doc.blank() leave split across separate atoms."""
    out: list = []
    for a in atoms:
        if isinstance(a, str) and out and isinstance(out[-1], str):
            out[-1] += a
        else:
            out.append(a)
    return out


def money_k(x: float, cur: bool = True) -> K:
    return K((f"£{x:,.2f}" if cur else f"{x:,.2f}"), "amount")


def pence_k(x: float) -> K:
    return K(f"{x:.2f}p", "amount")


def _len(x) -> int:
    return len(text_of(x))


def render_table(rng: random.Random, header: list[str], rows: list[list], style: str,
                 right: set[int] = frozenset(), sep: str = "  ") -> list:
    """Render a table as markdown ('md'), fixed-width columns ('fixed') or pipe text ('pipe').
    Cells are segments (str / E / K / list). Padding is always outside entity spans."""
    out: list = []
    if style == "md":
        out.append("| " + " | ".join(header) + " |\n")
        out.append("|" + "|".join("---:" if i in right else "---" for i in range(len(header))) + "|\n")
        for r in rows:
            out.append("| ")
            for i, c in enumerate(r):
                if i:
                    out.append(" | ")
                out.append(c)
            out.append(" |\n")
        return [HC("table_layout", out)]
    if style == "pipe":
        out.append(" | ".join(header) + "\n")
        for r in rows:
            for i, c in enumerate(r):
                if i:
                    out.append(" | ")
                out.append(c)
            out.append("\n")
        return [HC("table_layout", out)]
    widths = [len(h) for h in header]
    for r in rows:
        for i, c in enumerate(r):
            widths[i] = max(widths[i], _len(c))
    line = []
    for i, h in enumerate(header):
        line.append(h.rjust(widths[i]) if i in right else h.ljust(widths[i]))
    out.append(sep.join(line).rstrip() + "\n")
    if rng.random() < 0.5:
        out.append("-" * (sum(widths) + len(sep) * (len(widths) - 1)) + "\n")
    for r in rows:
        for i, c in enumerate(r):
            pad = " " * (widths[i] - _len(c))
            if i:
                out.append(sep)
            if i in right:
                out += [pad, c]
            elif i == len(r) - 1:
                out.append(c)
            else:
                out += [c, pad]
        out.append("\n")
    return [HC("table_layout", out)]


def table_style(rng: random.Random) -> str:
    return rng.choice(["md", "md", "fixed", "fixed", "pipe"])


def org_phone(rng: random.Random, ref: str | None = None) -> E:
    if rng.random() < 0.5:
        num = ids.from_pattern(rng, pick(rng, "0345 ### ####", "0330 ### ####", "0800 ### ####", "0333 ### ####"))
        return E(num, "PHONE", ref)
    return E(ids.landline_number(rng, rng.choice([0, 0, 1, 2])), "PHONE", ref)


def public_custom(rng: random.Random, kind: str) -> tuple[str, E]:
    pats = {
        "energy": [("Account number", "#### #### ####"), ("Account number", "A-########"),
                   ("Customer number", "##########"), ("Account no.", "###########")],
        "water": [("Customer reference", "## #### ####"), ("Account number", "#########"),
                  ("Customer number", "W#########")],
        "telecom": [("Account number", "#########"), ("Account number", "##########"),
                    ("Customer account", "@@#######"), ("Billing account", "###-###-####")],
    }
    lab, pat = rng.choice(pats[kind])
    return lab, E(ids.from_pattern(rng, pat), "CUSTOM", None, ("custom_org_id",))


def bic_for(code: str, rng: random.Random) -> K:
    return K(code + "GB" + rng.choice(["22", "2L", "21", "2B", "33"]), "bic")


def vat_number(rng: random.Random, sole_trader: bool = False, ref: str | None = None):
    """Checksum-valid GB VAT number. A company's VAT number is public (keep trap); a sole trader's
    VAT number identifies the person, so it is labelled CUSTOM."""
    txt = ids.format_vat(ids.vat_number(rng), rng.randrange(3))
    if sole_trader:
        return E(txt, "CUSTOM", ref, ("sole_trader_vat",))
    return K(txt, "vat_number")


def company_no(rng: random.Random) -> K:
    d = "".join(str(rng.randrange(10)) for _ in range(8))
    if rng.random() < 0.15:
        d = "SC" + d[2:]
    return K(d, "company_number")


def short_date(d: date, style: int) -> K:
    if style == 0:
        return K(f"{d.day:02d} {MON3[d.month - 1]}", "date")
    if style == 1:
        return K(f"{d.day:02d}/{d.month:02d}/{d.year}", "date")
    if style == 2:
        return K(f"{d.day:02d}/{d.month:02d}", "date")
    return K(f"{d.day} {MON3[d.month - 1]} {d.year % 100:02d}", "date")


# --------------------------------------------------------------------------- invoice
_TRADE_ITEMS = {
    "Plumbing": ["Call-out fee", "Replace kitchen mixer tap", "Fit new radiator valve", "Unblock bathroom sink",
                 "Parts: 15mm copper pipe and fittings", "Labour (hours)", "Annual boiler service"],
    "Electrical": ["EICR inspection", "Replace consumer unit", "Fit outdoor socket", "Labour (hours)",
                   "Install LED downlights", "Emergency call-out", "Parts and cable"],
    "Cleaning Services": ["End of tenancy clean - 2 bed flat", "Oven deep clean", "Carpet cleaning (3 rooms)",
                          "Regular clean (weekly)", "Window cleaning", "Materials"],
    "Consulting": ["Consultancy (day rate)", "Workshop facilitation", "Strategy review", "Travel expenses",
                   "Report preparation", "Project management (hours)"],
    "Design": ["Logo design", "Brand guidelines", "Website mock-ups", "Social media templates", "Revisions (hours)"],
    "Bookkeeping": ["Bookkeeping services - quarter", "VAT return preparation", "Payroll (monthly)",
                    "Year-end accounts", "Self assessment tax return"],
    "Landscaping": ["Garden clearance", "Hedge trimming", "Lawn treatment", "Green waste removal", "Turfing (m2)"],
    "Photography": ["Wedding photography package", "Headshots (half day)", "Image editing", "Travel"],
    "Tutoring": ["GCSE maths tutoring (hours)", "A-level chemistry tutoring (hours)", "Exam preparation pack"],
    "Web Design": ["Website maintenance - monthly", "Hosting (annual)", "SEO audit", "Content updates (hours)"],
    "Decorating": ["Paint living room and hallway", "Wallpaper bedroom", "Gloss skirting and doors", "Materials"],
    "Removals": ["Removal - 2 bed flat", "Packing service", "Storage (per week)", "Packing materials"],
}


_PLACE_TRADES = {"Landscaping", "Photography", "Removals", "Cleaning Services", "Decorating"}
_INV_PLACES = ["the Rose Garden", "Victoria Park", "Hyde Park", "Millennium Square", "the Elm Grove allotments",
               "Grace Hall", "the Trafford Centre", "Canary Wharf", "the Oak Road community centre", "Station Road car park"]
_PRODUCT_TRADES = {"Plumbing": ["Worcester Bosch boiler", "Hive thermostat", "Grohe Eurosmart tap", "Vaillant ecoTEC plus"],
                   "Electrical": ["Ring doorbell", "Nest Mini", "Hive thermostat", "Philips Hue starter kit"]}


def _items(rng: random.Random, trade: str, n: int) -> list[tuple[str | list, float, float]]:
    pool = _TRADE_ITEMS.get(trade) or rng.choice(list(_TRADE_ITEMS.values()))
    chosen = rng.sample(pool, min(n, len(pool)))
    out = []
    for desc in chosen:
        qty = rng.choice([1, 1, 1, 2, 3, 4, 6, 8, 0.5, 1.5]) if "hours" in desc or "rate" in desc else rng.choice([1, 1, 1, 2, 3])
        unit = round(rng.uniform(12, 650), 2) if rng.random() < 0.7 else float(rng.randrange(20, 900, 5))
        d: str | list = desc
        r = rng.random()
        if trade in _PLACE_TRADES and r < 0.25:
            d = [desc + pick(rng, " - ", " at ", ", site: "), K(rng.choice(_INV_PLACES), "place_name")]
        elif trade in _PRODUCT_TRADES and r < 0.3:
            prod = K(rng.choice(_PRODUCT_TRADES[trade]), "product")
            d = [desc + " (", prod, ")"] if rng.random() < 0.5 else [desc + " - supply and fit ", prod]
        out.append((d, qty, unit))
    return out


@register("invoice", weight=4)
def invoice(rng: random.Random, neg: bool) -> Doc:
    d = Doc("invoice", "invoice/v1")
    c = Cast(rng, common_word_rate=0.08)
    seller_kind = rng.choices(["sole", "ltd", "org"], [45, 40, 15])[0]
    d.v(seller_kind)
    trade = rng.choice(list(_TRADE_ITEMS))
    seller_person: Person | None = None
    seller_name_seg: list | K | str
    client_code: E | None = None
    s_addr = world.make_address(rng, flat_rate=0.15)
    s_domain = None
    if seller_kind == "sole":
        seller_person = c.new()
        seller_name_seg = world.sole_trader(rng, seller_person)
        trade_head = seller_name_seg
        s_ref = seller_person.ref
    elif seller_kind == "ltd":
        if rng.random() < 0.35:
            seller_person = c.new()
            seller_name_seg = world.company_name(rng, with_person_surname=seller_person.last)
        else:
            seller_name_seg = world.company_name(rng)
            if rng.random() < 0.6:
                seller_person = c.new()
        trade_head = seller_name_seg
        s_ref = None
    else:
        org = rng.choice(world.ORGS_BY_KIND[pick(rng, "accountant", "law", "letting")])
        seller_name_seg = org.name
        trade_head = org.name
        trade = "Bookkeeping" if org.kind == "accountant" else "Consulting"
        lab, client_code = org.custom(rng)
        seller_person = c.new()
        s_ref = None
        s_domain = org.domain
    if s_domain is None and seller_kind != "sole":
        s_domain = world.domain_for(text_of(seller_name_seg).replace(" Ltd", "").replace(" LLP", ""))
    # buyer
    buyer_person = c.new()
    buyer_company = world.company_name(rng) if rng.random() < 0.4 else None
    b_addr = world.make_address(rng)
    inv_date = recent_date(rng, 400)
    due = inv_date + timedelta(days=rng.choice([7, 14, 14, 30, 30, 60]))
    dstyle = rng.choice([0, 0, 1, 2, 5, 6])
    inv_no = world.doc_ref(rng, "invoice")
    if client_code is None and rng.random() < 0.35:
        client_code = E(ids.from_pattern(rng, pick(rng, "CL-#####", "C####", "CUST-####", "@@@###", "AC/####")),
                        "CUSTOM", None, ("custom_org_id",))

    # header
    layout = rng.randrange(3)
    d.v(f"L{layout}")
    if layout == 0:
        d.ln(trade_head)
        d.ln(s_addr.block(rng, s_ref))
        if seller_person is not None and rng.random() < 0.8:
            d.ln(pick(rng, "Tel: ", "Phone: ", "Mob: ", "T: "), seller_person.phone() if seller_kind == "sole" else org_phone(rng))
            d.ln(pick(rng, "Email: ", "E: ", ""), seller_person.email() if seller_kind == "sole"
                 else seller_person.work_email(s_domain))
        d.blank()
        d.ln(pick(rng, "INVOICE", "Invoice", "TAX INVOICE", "SALES INVOICE"))
        d.blank()
    elif layout == 1:
        d.ln(pick(rng, "INVOICE", "Invoice"), " ", inv_no)
        d.ln("From: ", trade_head)
        d.ln(s_addr.inline(rng, s_ref))
        d.blank()
    else:
        d.ln("# ", pick(rng, "Invoice", "INVOICE"))
        d.blank()
        d.ln("**", trade_head, "**  ")
        d.ln(s_addr.inline(rng, s_ref), "  ")
        if seller_person is not None:
            d.ln(seller_person.email() if seller_kind == "sole" else seller_person.work_email(s_domain))
        d.blank()
    # bill to
    d.ln(pick(rng, "Bill to:", "Invoice to:", "To:", "Customer:", "BILL TO"))
    if buyer_company is not None:
        d.ln(buyer_company)
        d.ln(pick(rng, "FAO ", "Attn: ", "For the attention of "), buyer_person.full())
    else:
        r = rng.random()
        d.ln(buyer_person.title_full() if r < 0.4 else (buyer_person.full() if r < 0.8 else buyer_person.initial_last()))
    d.ln(b_addr.block(rng, None if buyer_company is not None else buyer_person.ref))
    d.blank()
    meta = []
    if layout != 1:
        meta.append(("Invoice number", inv_no))
    meta.append(("Invoice date", K(ids.format_date(inv_date, dstyle), "date")))
    if rng.random() < 0.6:
        meta.append(("Due date", K(ids.format_date(due, dstyle), "date")))
    else:
        meta.append(("Payment terms", f"{(due - inv_date).days} days"))
    if client_code is not None and rng.random() < 0.6:
        meta.append((pick(rng, "Client code", "Customer ref", "Account ref", "Client ID"), client_code))
    if rng.random() < 0.3:
        meta.append(("PO number", world.doc_ref(rng, "order")))
    vat_reg = seller_kind != "sole" or rng.random() < 0.2
    if vat_reg and rng.random() < 0.8:
        meta.append(("VAT reg no", vat_number(rng, seller_kind == "sole")))
    for lab, val in meta:
        d.ln(lab, pick(rng, ": ", ":  ") if layout != 2 else ": ", val)
    d.blank()
    # items
    items = _items(rng, trade, rng.randint(1, 6))
    style = table_style(rng)
    cur = rng.random() < 0.5
    rows = []
    subtotal = 0.0
    for desc, qty, unit in items:
        line = round(qty * unit, 2)
        subtotal += line
        q = str(int(qty)) if qty == int(qty) else str(qty)
        rows.append([desc, q, money_k(unit, cur), money_k(line, cur)])
    d.v(style)
    if rng.random() < 0.2:  # simple list layout
        for desc, qty, unit in items:
            q = str(int(qty)) if qty == int(qty) else str(qty)
            d.ln(q, " x ", desc, " @ ", money_k(unit), " = ", money_k(round(qty * unit, 2)))
    else:
        d.add(render_table(rng, [pick(rng, "Description", "Item", "Service"), "Qty", pick(rng, "Unit price", "Rate", "Price"),
                                 pick(rng, "Amount", "Total", "Line total")], rows, style, right={1, 2, 3}))
    d.blank()
    subtotal = round(subtotal, 2)
    vat = round(subtotal * 0.2, 2) if vat_reg else 0.0
    total = round(subtotal + vat, 2)
    d.ln("Subtotal: ", money_k(subtotal))
    if vat_reg:
        d.ln(pick(rng, "VAT @ 20%: ", "VAT (20%): ", "VAT: "), money_k(vat))
    else:
        d.ln(pick(rng, "VAT: not registered", "No VAT charged (not VAT registered)", "VAT: 0.00"))
    tot_lab = pick(rng, "TOTAL DUE: ", "Total: ", "Amount due: ", "Balance due: ", "Total due: ")
    if layout == 2 and rng.random() < 0.5:
        d.ln("**", tot_lab, money_k(total), "**")
    else:
        d.ln(tot_lab, money_k(total))
    d.blank()
    # payment details
    payee: Person = seller_person if (seller_kind == "sole" and seller_person) else c.new()
    pay_rows = []
    pay_rows.append(("Bank", K(payee.bank_name, "public_company")))
    if seller_kind == "sole":
        pay_rows.append(("Account name", payee.full() if rng.random() < 0.7 else payee.caps()))
    else:
        pay_rows.append(("Account name", seller_name_seg))
    pay_rows.append(("Sort code", payee.sort_code()))
    pay_rows.append(("Account number", payee.account(spaced=rng.random() < 0.15)))
    if rng.random() < 0.3:
        pay_rows.append(("IBAN", payee.iban()))
        pay_rows.append(("BIC", bic_for(payee.bank[1], rng)))
    pay_rows.append(("Reference", client_code if client_code is not None and rng.random() < 0.7 else inv_no))
    pstyle = rng.randrange(3)
    d.ln(pick(rng, "Payment details", "How to pay", "PAYMENT INFORMATION", "Please pay by bank transfer to:"))
    if pstyle == 0:
        for lab, val in pay_rows:
            d.ln(lab, ": ", val)
    elif pstyle == 1:
        d.add(render_table(rng, ["Field", "Details"], [[lab, val] for lab, val in pay_rows], "md"))
    else:
        d.f("Please pay {amt} to sort code {sc}, account {acct}, quoting {ref}.\n", amt=money_k(total),
            sc=pay_rows[2][1], acct=pay_rows[3][1], ref=pay_rows[-1][1])
    d.blank()
    # footer
    foot = []
    if rng.random() < 0.5:
        foot.append(["Payment is due within ", str((due - inv_date).days), " days. Late payments may incur interest under the ",
                     K("Late Payment of Commercial Debts (Interest) Act 1998", "statute"), "."])
    if rng.random() < 0.5:
        foot.append([pick(rng, "Thank you for your business!", "Many thanks for your custom.", "Thanks again - it was a pleasure working with you.")])
    if seller_kind != "sole" and rng.random() < 0.6:
        foot.append(["Registered in England and Wales. Company number ", company_no(rng), "."])
    if seller_person is not None and seller_kind != "sole" and rng.random() < 0.5:
        foot.append(["Queries: contact ", seller_person.full(), " on ", org_phone(rng, seller_person.ref), "."])
    if buyer_person.common_word and rng.random() < 0.7:
        ph = world.common_word_phrase(rng, buyer_person.first)
        if ph:
            foot.append(ph)
    for f in foot:
        d.ln(f)
    if rng.random() < 0.3:
        d.atoms = noise.double_spaces(d.atoms, rng)
        d.v("dsp")
    return d


# --------------------------------------------------------------------------- utility bill
_TARIFFS_E = ["Fixed Saver June 2027", "Standard Variable", "Economy 7", "Fix'd 12M Oct 2026", "Simpler Energy",
              "1 Year Fixed v42", "Green Flex", "Tracker October 2025", "Price Cap Tariff", "Fixed 24M Green"]
_TARIFFS_OCTOPUS = ["Flexible Octopus", "Agile Octopus", "Cosy Octopus", "Octopus 12M Fixed"]
_TARIFFS_W = ["Metered (domestic)", "Assessed charge", "Unmetered (rateable value)", "WaterSure Plus"]


@register("utility_bill", weight=3)
def utility_bill(rng: random.Random, neg: bool) -> Doc:
    d = Doc("utility_bill", "utility_bill/v1")
    c = Cast(rng, common_word_rate=0.06)
    water = rng.random() < 0.3
    kind = "water" if water else "energy"
    public = rng.random() < 0.5
    if public:
        sup_name = K(rng.choice(world.PUBLIC[kind]), "public_company")
        lab, acct = public_custom(rng, kind)
        site = text_of(sup_name).lower().replace(" ", "").replace(".", "") + ".co.uk"
        phone = None
    else:
        org = rng.choice(world.ORGS_BY_KIND[kind])
        sup_name = org.name
        lab, acct = org.custom(rng)
        site = org.domain
        phone = org_phone(rng)
    d.v(("pub" if public else "syn") + "-" + kind)
    cust = c.new()
    joint = c.new() if rng.random() < 0.15 else None
    addr = world.make_address(rng)
    supply_diff = rng.random() < 0.2
    supply = world.make_address(rng, flat_rate=0.5) if supply_diff else None
    bill_date = recent_date(rng, 500)
    days = rng.choice([28, 30, 31, 61, 90, 92])
    end = bill_date - timedelta(days=rng.randint(1, 6))
    start = end - timedelta(days=days - 1)
    dstyle = rng.choice([0, 1, 1, 5, 2])
    bill_no = world.doc_ref(rng, "bill")
    # header
    d.ln(sup_name)
    d.ln(pick(rng, "Your energy bill", "Your bill", "Statement of account", "Your electricity and gas bill")
         if not water else pick(rng, "Your water bill", "Water and sewerage charges", "Your bill"))
    d.blank()
    names = [cust.title_full() if rng.random() < 0.5 else cust.full()]
    if joint is not None:
        names += [" & ", joint.title_full() if rng.random() < 0.5 else joint.full()]
    d.ln(names)
    d.ln(addr.block(rng, cust.ref))
    d.blank()
    rows = [(lab, acct), ("Bill date", K(ids.format_date(bill_date, dstyle), "date")),
            ("Bill number", bill_no),
            ("Billing period", [K(ids.format_date(start, dstyle), "date"), " to ", K(ids.format_date(end, dstyle), "date")])]
    if rng.random() < 0.5:
        rows.insert(2, ("Customer name", cust.full()))
    rng.shuffle(rows)
    for lab_, val in rows:
        d.ln(lab_, ": ", val)
    if supply is not None:
        d.ln("Supply address: ", HC("supply_address", supply.inline(rng, None)))
    elif rng.random() < 0.4:
        d.ln("Supply address: as above")
    d.blank()
    # summary
    prev = round(rng.uniform(-80, 250), 2)
    paid = round(max(0.0, prev + rng.uniform(-20, 60)), 2)
    # charges
    lines = []
    total_new = 0.0
    if water:
        for nm in ["Water supply", "Wastewater (sewerage)", "Surface water drainage", "Standing charge"]:
            if nm == "Surface water drainage" and rng.random() < 0.5:
                continue
            v = round(rng.uniform(8, 140) * days / 30, 2)
            total_new += v
            lines.append([nm, K(rng.choice(_TARIFFS_W), "product") if nm == "Water supply" else "", money_k(v)])
        header = ["Charge", "Basis", "Amount"]
        right = {2}
    else:
        fuels = ["Electricity"] + (["Gas"] if rng.random() < 0.7 else [])
        for fuel in fuels:
            kwh = rng.randint(90, 1400) * days // 30
            rate = round(rng.uniform(5.5, 31.0) if fuel == "Gas" else rng.uniform(19.0, 34.0), 2)
            sc = round(rng.uniform(28.0, 62.0), 2)
            energy = round(kwh * rate / 100, 2)
            stand = round(days * sc / 100, 2)
            total_new += energy + stand
            lines.append([f"{fuel} ({kwh:,} kWh x ", pence_k(rate), "/kWh)", money_k(energy)])
            lines.append([f"{fuel} standing charge ({days} days x ", pence_k(sc), "/day)", money_k(stand)])
        header = None
        right = set()
    total_new = round(total_new, 2)
    vat_rate = 0 if water else 5
    vat = round(total_new * vat_rate / 100, 2)
    grand = round(total_new + vat, 2)
    balance = round(prev - paid + grand, 2)
    d.ln(pick(rng, "Summary", "Your account summary", "SUMMARY OF CHARGES", "## Summary"))
    d.ln("Previous balance: ", money_k(abs(prev)), " in credit" if prev < 0 else "")
    d.ln("Payments received: ", money_k(paid), pick(rng, " - thank you", "", ""))
    d.ln("New charges: ", money_k(grand))
    d.ln(pick(rng, "Balance to pay: ", "Amount due: ", "Your balance: "), money_k(abs(balance)), " in credit" if balance < 0 else "")
    d.blank()
    d.ln(pick(rng, "Your charges", "Charges this period", "DETAILS OF CHARGES", "What you're paying for"))
    if not water:
        tariff = K(rng.choice(_TARIFFS_OCTOPUS if text_of(sup_name) == "Octopus Energy" else _TARIFFS_E), "product")
        d.ln("Tariff: ", tariff)
        st = rng.choice(["md", "fixed", "plain"])
        if st == "plain":
            for ln in lines:
                d.ln(ln[:-1], ": ", ln[-1])
        else:
            rws = [[ln[:-1], ln[-1]] for ln in lines]
            d.add(render_table(rng, ["Item", "Amount"], rws, st, right={1}))
        d.ln(f"VAT at {vat_rate}%: ", money_k(vat))
        d.ln("Total new charges: ", money_k(grand))
    else:
        d.add(render_table(rng, header, lines, rng.choice(["md", "fixed", "pipe"]), right=right))
        d.ln("Total: ", money_k(grand))
    d.blank()
    # payment
    pay = rng.random()
    if pay < 0.6:
        dd_date = bill_date + timedelta(days=rng.randint(7, 21))
        d.f(pick(rng, "Your next Direct Debit of {amt} will be taken on or after {dt} from your account ending {acc}.\n",
                 "We'll collect {amt} by Direct Debit on {dt} (account ending {acc}).\n",
                 "Direct Debit: {amt} on {dt}, bank account ending {acc}.\n"),
            amt=money_k(round(rng.uniform(40, 220), 2)), dt=K(ids.format_date(dd_date, dstyle), "date"),
            acc=cust.account_last4())
    elif pay < 0.85:
        d.f("Please pay {amt} by {dt}. Pay online at {site} or by bank transfer quoting your {lab} {acct}.\n",
            amt=money_k(abs(balance)), dt=K(ids.format_date(bill_date + timedelta(days=14), dstyle), "date"),
            site=site, lab=lab.lower(), acct=E(acct.text, "CUSTOM", None, acct.hard))
    else:
        d.f("You paid by card ending {c} on {dt}. Thank you.\n", c=cust.card_last4(),
            dt=K(ids.format_date(bill_date - timedelta(days=rng.randint(1, 20)), dstyle), "date"))
    d.blank()
    contact = [pick(rng, "Questions about your bill? Visit ", "Manage your account at ", "Help and support: "), site]
    if phone is not None:
        contact += [pick(rng, " or call ", " or phone us on ", ". Tel "), phone]
    d.ln(contact, ".")
    if rng.random() < 0.4:
        d.ln(pick(rng, "If you are worried about paying, talk to us. You can also get free advice from ",
                  "Not happy? You can contact "), K(pick(rng, "Citizens Advice", "the Energy Ombudsman", "Ofgem", "CCW"), "public_company"), ".")
    if cust.common_word and rng.random() < 0.6:
        ph = world.common_word_phrase(rng, cust.first)
        if ph:
            d.ln(ph)
    if rng.random() < 0.45:
        acct_txt = acct.text

        def header_fn(page, total):
            return [text_of(sup_name) if isinstance(sup_name, str) else K(sup_name.text, "public_company"),
                    " | ", cust.full(), " | ", lab, " ", E(acct_txt, "CUSTOM", None, ("custom_org_id",))]

        def footer_fn(page, total):
            return [f"Page {page} of {total}"]

        d.atoms = noise.page_breaks(merge_str(d.atoms), rng, header_fn, footer_fn, every=rng.randint(450, 800))
        d.v("pages")
    return d


# --------------------------------------------------------------------------- phone bill
_PLANS = ["Unlimited Max", "SIM Only 30GB", "Essentials 12GB", "Unlimited Lite", "Pay Monthly 100GB",
          "Smarty Unlimited", "Value 5GB", "Unlimited Plus with Extras", "Family SIM 50GB", "Fibre 500 + Calls"]


def _call_number(rng: random.Random, compact: bool) -> str:
    if rng.random() < 0.78:
        nsn = ids.mobile_number(rng)
        return ids.format_mobile(nsn, 1 if compact else rng.choice([0, 0, 4]))
    s = ids.landline_number(rng, 0)
    return s.replace(" ", "") if compact else s


@register("phone_bill", weight=2.5)
def phone_bill(rng: random.Random, neg: bool) -> Doc:
    d = Doc("phone_bill", "phone_bill/v1")
    c = Cast(rng, common_word_rate=0.06)
    public = rng.random() < 0.6
    if public:
        net = K(rng.choice(world.PUBLIC["telecom"]), "public_company")
        lab, acct = public_custom(rng, "telecom")
        site = text_of(net).lower().replace(" ", "") + ".co.uk"
    else:
        org = rng.choice([o for o in world.ORGS_BY_KIND["telecom"]])
        net = org.name
        lab, acct = org.custom(rng)
        site = org.domain
    d.v("pub" if public else "syn")
    cust = c.new()
    addr = world.make_address(rng)
    bill_date = recent_date(rng, 400)
    start = (bill_date - timedelta(days=31)).replace(day=min(bill_date.day, 28))
    dstyle = rng.choice([0, 1, 5])
    compact = rng.random() < 0.5
    d.ln(net, " - ", pick(rng, "Your bill", "Monthly bill", "Bill summary", "Your monthly statement"))
    d.blank()
    if rng.random() < 0.7:
        d.ln(cust.title_full() if rng.random() < 0.5 else cust.full())
        d.ln(addr.block(rng, cust.ref))
        d.blank()
    rows = [(lab, acct), ("Bill date", K(ids.format_date(bill_date, dstyle), "date")),
            (pick(rng, "Your number", "Mobile number", "Phone number"), cust.mobile()),
            ("Plan", K(rng.choice(_PLANS), "product"))]
    if rng.random() < 0.4:
        rows.append(("Account holder", cust.full()))
    if rng.random() < 0.5:
        rows.append(("Bill number", world.doc_ref(rng, "bill")))
    for lab_, val in rows:
        d.ln(lab_, ": ", val)
    d.blank()
    plan = round(rng.uniform(6, 65), 2)
    n_rows = rng.randint(6, 30)
    contacts = [_call_number(rng, compact) for _ in range(rng.randint(3, 8))]
    calls = []
    extra = 0.0
    for _ in range(n_rows):
        day = start + timedelta(days=rng.randint(0, 30))
        t = f"{rng.randint(7, 23):02d}:{rng.randint(0, 59):02d}"
        kind = rng.choices(["Call", "Text", "Data", "Voicemail"], [60, 30, 6, 4])[0]
        if kind == "Data":
            calls.append((day, t, kind, f"{rng.uniform(0.1, 3.5):.2f}GB", "", None))
            continue
        if kind == "Voicemail":
            calls.append((day, t, kind, "Voicemail", "00:00:" + f"{rng.randint(5, 59):02d}", None))
            continue
        num = rng.choice(contacts)
        dur = f"00:{rng.randint(0, 45):02d}:{rng.randint(0, 59):02d}" if kind == "Call" else "-"
        cost = None
        if rng.random() < 0.15:
            cost = round(rng.uniform(0.05, 4.5), 2)
            extra += cost
        calls.append((day, t, kind, num, dur, cost))
    calls.sort(key=lambda r: (r[0], r[1]))
    extra = round(extra, 2)
    vat_incl = rng.random() < 0.7
    total = round(plan + extra, 2)
    d.ln(pick(rng, "Summary", "BILL SUMMARY", "What you owe"))
    d.ln("Monthly plan charge: ", money_k(plan))
    d.ln("Charges outside your plan: ", money_k(extra))
    d.ln("Total", " (inc. VAT)" if vat_incl else "", ": ", money_k(total))
    d.blank()
    pay = rng.random()
    if pay < 0.5:
        d.f("We will collect {amt} by Direct Debit from your account ending {a} on or after {dt}.\n",
            amt=money_k(total), a=cust.account_last4(), dt=K(ids.format_date(bill_date + timedelta(days=10), dstyle), "date"))
    else:
        d.f(pick(rng, "Paid by card ending {cd}. Thanks!\n", "Payment of {amt} taken from your card ending {cd}.\n",
                 "Your card ending {cd} will be charged {amt}.\n"), cd=cust.card_last4(), amt=money_k(total))
    d.blank()
    d.ln(pick(rng, "Itemised calls and texts", "ITEMISED USAGE", "Usage details", "Calls, texts and data"))
    style = table_style(rng)
    trows = []
    for day, t, kind, num, dur, cost in calls:
        num_seg = E(num, "PHONE") if kind in ("Call", "Text") else num
        trows.append([short_date(day, 0 if style != "fixed" else 2), t, kind, num_seg, dur,
                      money_k(cost) if cost is not None else pick(rng, "Included", "Inc", "0.00")])
    d.add(render_table(rng, ["Date", "Time", "Type", "Number", "Duration", "Cost"], trows, style, right={5}))
    d.blank()
    d.ln(pick(rng, "Manage your account at ", "View your bill online: ", "Questions? Go to "), site, ".")
    if rng.random() < 0.3:
        d.ln("Calls to 0800 and 0808 numbers are free. ", K("Ofcom", "public_company"), " rules apply to price rises.")
    return d


# --------------------------------------------------------------------------- bank statement
_DESC_STYLE = ["upper", "mixed"]


def _tx_person_name(rng: random.Random, p: Person) -> E:
    r = rng.random()
    if r < 0.45:
        txt = f"{p.first[0]} {p.last}".upper()
    elif r < 0.7:
        txt = p.full_text.upper()
    elif r < 0.85:
        txt = f"{p.last} {p.first[0]}".upper()
    else:
        txt = f"{p.first[0]}{(p.middle[:1] if p.middle else '')} {p.last}".upper()
    from ..names import ascii_fold
    if rng.random() < 0.5:
        txt = ascii_fold(txt)
    return E(txt, "PERSON", p.ref, ("name_in_transaction",) + p._hard())


@register("bank_statement", weight=3.5)
def bank_statement(rng: random.Random, neg: bool) -> Doc:
    d = Doc("bank_statement", "bank_statement/v1")
    c = Cast(rng, common_word_rate=0.06)
    holder = c.new()
    joint = c.new() if rng.random() < 0.15 else None
    bank_name, code, sc, acct = holder.bank
    bank = K(bank_name, "public_company")
    addr = world.make_address(rng)
    period_end = recent_date(rng, 500)
    days = rng.choice([30, 31, 28, 30, 91])
    period_start = period_end - timedelta(days=days - 1)
    dstyle = rng.choice([1, 1, 0, 5])
    others = [c.new() for _ in range(rng.randint(2, 5))]
    landlord = rng.choice(others)
    employer = world.public_company(rng, "employer") if rng.random() < 0.4 else world.company_name(rng)
    law = rng.choice(world.SYNTH_ORGS) if rng.random() < 0.35 else None
    # transactions
    n = rng.randint(10, 60) if days < 60 else rng.randint(35, 60)
    bal = round(rng.uniform(-300, 4500), 2)
    opening = bal
    txs = []
    salary_day = rng.randint(24, 28)
    for _ in range(n):
        day = period_start + timedelta(days=rng.randint(0, days - 1))
        r = rng.random()
        if r < 0.35:
            shop = rng.choice(world.PUBLIC["retail"] + world.PUBLIC["transport"])
            town = rng.choice(world.TOWN_NAMES).upper()
            desc = [pick(rng, "CARD PAYMENT TO ", "POS ", "DEB ", "Card purchase "), K(shop.upper() if rng.random() < 0.6 else shop, "public_company"),
                    pick(rng, f" {town}", "", f" {rng.randint(1000, 9999)}", f" ON {day.day:02d} {MON3[day.month - 1].upper()}")]
            if rng.random() < 0.2:
                desc += [" CARD ", holder.card_last4()]
            out_, in_ = round(rng.uniform(1.2, 140), 2), None
        elif r < 0.52:
            co = rng.choice(world.PUBLIC["energy"] + world.PUBLIC["water"] + world.PUBLIC["telecom"] + world.PUBLIC["insurer"])
            desc = [pick(rng, "DIRECT DEBIT ", "DD ", "Direct Debit to "), K(co.upper() if rng.random() < 0.5 else co, "public_company")]
            if rng.random() < 0.3:
                desc += [" REF ", world.doc_ref(rng, "txn")]
            out_, in_ = round(rng.uniform(8, 160), 2), None
        elif r < 0.64:
            p = rng.choice(others)
            if rng.random() < 0.5:
                desc = [pick(rng, "FASTER PAYMENT TO ", "FPO ", "TFR TO ", "Payment to "), _tx_person_name(rng, p),
                        pick(rng, "", " REF DINNER", " REF THANKS", " REF FLAT DEPOSIT", " REF BILLS", " REF CAR SHARE")]
                out_, in_ = round(rng.uniform(5, 450), 2), None
            else:
                desc = [pick(rng, "FASTER PAYMENT FROM ", "FPI ", "FROM ", "Payment from "), _tx_person_name(rng, p),
                        pick(rng, "", " REF RENT SHARE", " REF BIRTHDAY", " REF TICKETS", " REF LOAN")]
                out_, in_ = None, round(rng.uniform(5, 600), 2)
        elif r < 0.7:
            p = rng.choice(others)
            desc = [pick(rng, "TFR TO ", "TRANSFER TO "), p.sort_code(style=rng.choice([0, 2])).with_hard("account_next_to_amount"),
                    " ", p.account().with_hard("account_next_to_amount")]
            out_, in_ = round(rng.uniform(20, 1500), 2), None
        elif r < 0.74:
            desc = [pick(rng, "STANDING ORDER ", "SO "), _tx_person_name(rng, landlord), " RENT"]
            out_, in_ = round(rng.uniform(450, 1800), 2), None
        elif r < 0.78 and law is not None:
            _, cid = law.custom(rng)
            desc = ["BILL PAYMENT TO ", law.name.upper(), " REF ", cid]
            out_, in_ = round(rng.uniform(50, 2500), 2), None
        elif r < 0.84:
            desc = [pick(rng, "CASH WITHDRAWAL ", "ATM ", "CASH "), pick(rng, "LINK ATM ", "NOTEMACHINE ", ""), rng.choice(world.TOWN_NAMES).upper()]
            out_, in_ = float(rng.choice([10, 20, 30, 40, 50, 100, 200])), None
        elif r < 0.88:
            day = period_start + timedelta(days=min(days - 1, salary_day))
            desc = [pick(rng, "BGC ", "BANK GIRO CREDIT ", "Salary "), K(text_of(employer).upper(), employer.kind), pick(rng, " SALARY", " PAYROLL", "")]
            out_, in_ = None, round(rng.uniform(1300, 4800), 2)
        elif r < 0.92:
            desc = [pick(rng, "INTEREST PAID", "MONTHLY ACCOUNT FEE", "ARRANGED OVERDRAFT INTEREST", "CASHBACK")]
            out_, in_ = (round(rng.uniform(0.5, 15), 2), None) if "FEE" in desc[0] or "OVERDRAFT" in desc[0] else (None, round(rng.uniform(0.1, 9), 2))
        else:
            co = rng.choice(world.PUBLIC["tech"] + world.PUBLIC["retail"])
            desc = [pick(rng, "REFUND FROM ", "CARD REFUND "), K(co.upper(), "public_company")]
            out_, in_ = None, round(rng.uniform(3, 120), 2)
        txs.append((day, desc, out_, in_))
    txs.sort(key=lambda t: t[0])
    # keep the account plausible: opening balance covers most of the period's net outflow
    net_out = sum(t[2] or 0 for t in txs) - sum(t[3] or 0 for t in txs)
    if net_out > 0:
        bal = round(max(bal, net_out + rng.uniform(-400, 1800)), 2)
    opening = bal
    tstyle = rng.choice(["md", "fixed", "fixed", "pipe"])
    sd_style = rng.choice([0, 1, 3])
    rows = []
    tot_in = tot_out = 0.0
    for day, desc, out_, in_ in txs:
        if out_:
            bal -= out_
            tot_out += out_
        if in_:
            bal += in_
            tot_in += in_
        bal = round(bal, 2)
        rows.append([short_date(day, sd_style), desc, money_k(out_, False) if out_ else "",
                     money_k(in_, False) if in_ else "", money_k(bal, False) if bal >= 0 else K(f"{-bal:,.2f}OD", "amount")])
    closing = bal
    # header block
    d.ln(bank, pick(rng, "", " plc", " UK"), pick(rng, " - Statement", "\nStatement of account", "\nCurrent account statement", "\nYOUR STATEMENT"))
    d.blank()
    holder_names = [holder.title_full() if rng.random() < 0.6 else holder.caps()]
    if joint is not None:
        holder_names += [pick(rng, " & ", " and "), joint.title_full()]
    d.ln(holder_names)
    d.ln(addr.block(rng, holder.ref))
    d.blank()
    info = [("Account name", holder_names if rng.random() < 0.5 else (holder.full() if joint is None else holder_names)),
            ("Sort code", holder.sort_code()), ("Account number", holder.account()),
            ("Statement period", [K(ids.format_date(period_start, dstyle), "date"), " to ", K(ids.format_date(period_end, dstyle), "date")])]
    if rng.random() < 0.6:
        info.append(("IBAN", holder.iban()))
        info.append(("BIC", bic_for(code, rng)))
    if rng.random() < 0.3:
        info.append(("Statement number", str(rng.randint(1, 240))))
    istyle = rng.randrange(3)
    if istyle == 0:
        for lab, val in info:
            d.ln(lab, ": ", val)
    elif istyle == 1:
        d.add(render_table(rng, ["", ""], [[lab, val] for lab, val in info], "md"))
    else:
        d.ln("Sort code ", info[1][1], "   Account number ", info[2][1])
        d.ln("Statement period ", info[3][1])
        for lab, val in info[4:]:
            d.ln(lab, " ", val)
    d.blank()
    d.ln(pick(rng, "Account summary", "Your account summary", "Balance summary"))
    d.ln("Opening balance: ", money_k(opening))
    d.ln("Money in: ", money_k(round(tot_in, 2)))
    d.ln("Money out: ", money_k(round(tot_out, 2)))
    d.ln("Closing balance: ", money_k(closing) if closing >= 0 else [money_k(-closing), " overdrawn"])
    d.blank()
    header = ["Date", pick(rng, "Description", "Details", "Transaction"), pick(rng, "Money out", "Paid out", "Debit"),
              pick(rng, "Money in", "Paid in", "Credit"), "Balance"]
    per_page = rng.randint(14, 26)
    pages = [rows[i:i + per_page] for i in range(0, len(rows), per_page)]
    total_pages = len(pages)
    for pi, page_rows in enumerate(pages):
        d.add(render_table(rng, header, page_rows, tstyle, right={2, 3, 4}))
        if pi < total_pages - 1:
            d.blank()
            d.add(HC("pdf_header_footer",
                     [pick(rng, "Page ", "Page ", "- "), f"{pi + 1} of {total_pages}", "\n\n",
                      bank, " | ", holder.full(), " | Sort code ", holder.sort_code(), " | Account ", holder.account(), "\n"]))
            d.blank()
            d.v("pages")
    d.blank()
    if rng.random() < 0.6:
        d.ln(pick(rng, "Your deposits are eligible for protection by the Financial Services Compensation Scheme (FSCS) up to ",
                  "Eligible deposits are protected up to "), K("£85,000", "amount"), ".")
    if rng.random() < 0.4:
        d.ln("If you have a question about a transaction, call us or visit any branch. Lost or stolen card? Freeze it in the app.")
    if holder.common_word and rng.random() < 0.6:
        ph = world.common_word_phrase(rng, holder.first)
        if ph:
            d.ln(ph)
    return d


# --------------------------------------------------------------------------- payslip
_DEPTS = ["Warehouse", "Finance", "Customer Service", "Operations", "IT", "Care", "Kitchen", "Sales", "HR",
          "Maintenance", "Teaching", "Logistics", "Marketing", "Facilities"]


@register("payslip", weight=3)
def payslip(rng: random.Random, neg: bool) -> Doc:
    d = Doc("payslip", "payslip/v1")
    c = Cast(rng, common_word_rate=0.07)
    emp = c.new(max_age=67)
    synth = rng.random() < 0.7
    if synth:
        org = rng.choice(world.ORGS_BY_KIND["employer"])
        employer = org.name
        elab, eid = org.custom(rng)
    else:
        employer = world.company_name(rng) if rng.random() < 0.7 else world.public_company(rng, "employer")
        elab = pick(rng, "Employee No", "Employee number", "Payroll No", "Staff ID", "Works No")
        eid = E(ids.from_pattern(rng, pick(rng, "#####", "E####", "######", "PR####", "@@####")), "CUSTOM", None, ("custom_org_id",))
    weekly = rng.random() < 0.2
    pay_date = recent_date(rng, 500)
    year_start = date(pay_date.year if pay_date >= date(pay_date.year, 4, 6) else pay_date.year - 1, 4, 6)
    period = ((pay_date - year_start).days // 7 + 1) if weekly else ((pay_date.month - 4) % 12 + 1)
    dstyle = rng.choice([0, 0, 1, 5])
    tax_code = K(pick(rng, "1257L", "1257L", "1257L", "BR", "K475", "1257L M1", "S1257L", "C1257L", "0T", "1100L", "D0"), "tax_code")
    ni_cat = pick(rng, "A", "A", "A", "B", "C", "H", "M", "J")
    d.v(("weekly" if weekly else "monthly") + ("-synth" if synth else "-other"))
    # earnings
    if weekly:
        hours = round(rng.uniform(16, 48), 2)
        rate = round(rng.uniform(12.21, 22.0), 2)
        basic = round(hours * rate, 2)
        earnings = [([f"Basic pay ({hours:g} hrs @ ", money_k(rate), ")"], basic)]
    else:
        salary = rng.randrange(19000, 85000, 250)
        basic = round(salary / 12, 2)
        earnings = [("Basic salary", basic)]
    if rng.random() < 0.4:
        earnings.append(("Overtime", round(rng.uniform(20, 420), 2)))
    if rng.random() < 0.2:
        earnings.append(("Holiday pay", round(rng.uniform(80, 900), 2)))
    if rng.random() < 0.15:
        earnings.append(("Bonus", round(rng.uniform(100, 1500), 2)))
    if rng.random() < 0.1:
        earnings.append(("Statutory Sick Pay", round(rng.uniform(30, 120), 2)))
    gross = round(sum(v for _, v in earnings), 2)
    deds = [("Income Tax (PAYE)", round(max(0.0, gross * rng.uniform(0.08, 0.24)), 2)),
            ("National Insurance", round(max(0.0, gross * rng.uniform(0.04, 0.08)), 2))]
    if rng.random() < 0.85:
        deds.append(("Pension (employee)", round(gross * rng.choice([0.03, 0.04, 0.05, 0.06]), 2)))
    if rng.random() < 0.25:
        deds.append((pick(rng, "Student loan (Plan 2)", "Student loan (Plan 1)", "Postgraduate loan"), round(gross * rng.uniform(0.01, 0.05), 2)))
    if rng.random() < 0.1:
        deds.append(("Union subs", round(rng.uniform(8, 20), 2)))
    if rng.random() < 0.08:
        deds.append(("Cycle to work", round(rng.uniform(20, 80), 2)))
    tot_ded = round(sum(v for _, v in deds), 2)
    net = round(gross - tot_ded, 2)
    # header
    layout = rng.randrange(3)
    d.v(f"L{layout}")
    d.ln(employer, pick(rng, "", "", " - Payslip", "\nPAYSLIP", "\nPay Advice"))
    if rng.random() < 0.3:
        d.ln(world.make_address(rng, flat_rate=0).inline(rng, None))
    d.blank()
    if rng.random() < 0.3:
        d.ln(pick(rng, "PRIVATE & CONFIDENTIAL", "Private and confidential"))
        d.ln(emp.title_full() if rng.random() < 0.5 else emp.full())
        d.ln(world.make_address(rng).block(rng, emp.ref))
        d.blank()
    name_seg = pick(rng, emp.caps(), emp.full(), emp.last_comma_first(), emp.full_middle(),
                    E(f"{emp.last.upper()} {emp.first[0]}", "PERSON", emp.ref, emp._hard()))
    info = [("Employee", name_seg), (elab, eid), ("NI number", emp.ni()), ("Tax code", tax_code), ("NI category", ni_cat),
            ("Pay date", K(ids.format_date(pay_date, dstyle), "date")),
            ("Tax period", f"{'Week' if weekly else 'Month'} {period}"),
            ("Department", rng.choice(_DEPTS))]
    if rng.random() < 0.4:
        info.append(("Employer PAYE ref", K(ids.from_pattern(rng, "###/@@#####"), "employer_reference")))
    if rng.random() < 0.3:
        info.append(("Date of birth", emp.dob()))
    if layout == 1:
        d.add(render_table(rng, ["Detail", "Value"], [[a, b] for a, b in info], "md"))
    elif layout == 2:
        for i in range(0, len(info), 2):
            pair = info[i:i + 2]
            d.ln(*[[lab, ": ", val, "    " if j == 0 and len(pair) > 1 else ""] for j, (lab, val) in enumerate(pair)])
    else:
        for lab, val in info:
            d.ln(lab, ": ", val)
    d.blank()
    style = rng.choice(["md", "fixed", "fixed", "pipe"])
    if rng.random() < 0.5:
        d.ln(pick(rng, "PAYMENTS", "Earnings", "Payments"))
        d.add(render_table(rng, ["Description", "Amount"], [[a, money_k(v, False)] for a, v in earnings], style, right={1}))
        d.ln("Gross pay: ", money_k(gross))
        d.blank()
        d.ln(pick(rng, "DEDUCTIONS", "Deductions"))
        d.add(render_table(rng, ["Description", "Amount"], [[a, money_k(v, False)] for a, v in deds], style, right={1}))
        d.ln("Total deductions: ", money_k(tot_ded))
    else:
        rows = []
        for i in range(max(len(earnings), len(deds))):
            e_ = earnings[i] if i < len(earnings) else ("", None)
            dd = deds[i] if i < len(deds) else ("", None)
            rows.append([e_[0], money_k(e_[1], False) if e_[1] is not None else "", dd[0], money_k(dd[1], False) if dd[1] is not None else ""])
        rows.append(["Total gross pay", money_k(gross, False), "Total deductions", money_k(tot_ded, False)])
        d.add(render_table(rng, ["Payments", "Amount", "Deductions", "Amount"], rows, style, right={1, 3}))
    d.blank()
    d.ln(pick(rng, "NET PAY: ", "Net pay: ", "Take-home pay: ", "**Net pay** "), money_k(net))
    d.blank()
    ytd_mult = max(1, period)
    ytd = [("Taxable pay to date", round(gross * ytd_mult * rng.uniform(0.95, 1.02), 2)),
           ("Tax paid to date", round(deds[0][1] * ytd_mult, 2)),
           ("NI to date", round(deds[1][1] * ytd_mult, 2))]
    if len(deds) > 2 and deds[2][0].startswith("Pension"):
        ytd.append(("Pension to date", round(deds[2][1] * ytd_mult, 2)))
    d.ln(pick(rng, "Year to date", "YEAR TO DATE", "Cumulative totals"))
    for lab, v in ytd:
        d.ln(lab, ": ", money_k(v))
    d.blank()
    pr = rng.random()
    if pr < 0.5:
        d.f(pick(rng, "Paid by BACS to account ending {a}.\n", "Payment method: BACS ({bank} ****{a})\n",
                 "Net pay credited to {bank} account ending {a} on {dt}.\n"),
            a=emp.account_last4(), bank=K(emp.bank_name, "public_company"), dt=K(ids.format_date(pay_date, dstyle), "date"))
    elif pr < 0.7:
        d.ln("Payment method: BACS")
    if rng.random() < 0.3:
        d.ln(pick(rng, "Your P60 for the 2025/26 tax year is available in the employee portal.",
                  "Pension contributions are made to NEST under auto-enrolment.",
                  "Please check your details and tell Payroll about any changes.",
                  "Holiday remaining: " + str(rng.randint(0, 28)) + " days."))
    if emp.common_word and rng.random() < 0.5:
        ph = world.common_word_phrase(rng, emp.first)
        if ph:
            d.ln(ph)
    return d
