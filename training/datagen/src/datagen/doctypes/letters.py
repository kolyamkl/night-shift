"""Letters: insurance claim letter, council / HMRC / DVLA-style letter, GP / hospital letter."""
from __future__ import annotations

import random
from datetime import date, timedelta

from .. import ids, noise, world
from ..core import Doc, E, HC, K, text_of
from ..names import Cast, Person
from . import register
from .common import TODAY, amount, date_text, greeting, kv_block, pick, recent_date, signoff

WEEKDAYS = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
NAMED_STORMS = ["Storm Babet", "Storm Ciarán", "Storm Isha", "Storm Jocelyn", "Storm Henk", "Storm Darragh",
                "Storm Bert", "Storm Éowyn", "Storm Amy", "Storm Floris", "Storm Eunice", "Storm Arwen"]


def money_k(x: float) -> K:
    return K(f"£{x:,.2f}", "amount")


def letter_date(rng: random.Random, d: date, style: int) -> K:
    return K(ids.format_date(d, style), "date")


def org_phone(rng: random.Random) -> E:
    if rng.random() < 0.5:
        return E(ids.from_pattern(rng, pick(rng, "0345 ### ####", "0330 ### ####", "0800 ### ####", "0300 ### ####")), "PHONE")
    return E(ids.landline_number(rng, rng.choice([0, 0, 1, 2])), "PHONE")


def recipient_block(rng: random.Random, p: Person, addr, joint: Person | None = None) -> list:
    out = []
    r = rng.random()
    if joint is not None:
        out += [p.title_full() if r < 0.5 else p.initial_last(), pick(rng, " & ", " and "),
                joint.title_full() if r < 0.5 else joint.initial_last(), "\n"]
    elif r < 0.55:
        out += [p.title_full(), "\n"]
    elif r < 0.75:
        out += [p.title + " ", p.initial_last(), "\n"]
    elif r < 0.9:
        out += [p.caps(), "\n"]
    else:
        out += [p.full_middle(), "\n"]
    out += [addr.block(rng, p.ref), "\n"]
    return out


# --------------------------------------------------------------------------- insurance claim letter
_INCIDENTS = [
    ("escape_of_water", "Escape of water",
     ["water leaking from the flat above damaged the kitchen ceiling and flooring",
      "a burst pipe in the loft caused water damage to two bedrooms",
      "the washing machine hose failed and water came through to the room below"]),
    ("theft", "Theft",
     ["a bicycle was stolen from the locked shed in the rear garden",
      "the property was entered through a rear window and jewellery and a laptop were taken",
      "a handbag containing a phone and purse was stolen from the car"]),
    ("storm", "Storm damage",
     ["roof tiles were dislodged and the fence panels blown down during {storm}",
      "a tree branch fell on the conservatory roof during {storm}"]),
    ("motor", "Accidental damage (motor)",
     ["the vehicle was scraped while parked in the {shop} car park",
      "another vehicle reversed into the insured vehicle at {place}"]),
    ("accidental", "Accidental damage",
     ["the television was knocked off its stand and the screen cracked",
      "red wine was spilled on the living room carpet",
      "a {prod} was dropped and the screen broke"]),
]


@register("insurance_claim_letter", weight=3)
def insurance_claim_letter(rng: random.Random, neg: bool) -> Doc:
    d = Doc("insurance_claim_letter", "insurance_claim_letter/v1")
    c = Cast(rng, common_word_rate=0.07)
    ph = c.new()
    joint = c.new() if rng.random() < 0.12 else None
    handler = c.new()
    addr = world.make_address(rng)
    synth = rng.random() < 0.65
    if synth:
        org = rng.choice(world.ORGS_BY_KIND["insurer"])
        ins_name: str | K = org.name
        labs = list(org.ids)
        pol_lab, policy = org.custom(rng, labs[0])
        clm_lab, claim = org.custom(rng, labs[1])
        domain = org.domain
    else:
        org = None
        ins_name = K(rng.choice(world.PUBLIC["insurer"]), "public_company")
        pol_lab, clm_lab = pick(rng, "Policy number", "Policy no."), pick(rng, "Claim number", "Claim reference", "Claim ref")
        policy = E(ids.from_pattern(rng, pick(rng, "@@#########", "P########", "###-#######-##", "HOM########")), "CUSTOM", None, ("custom_org_id",))
        claim = E(ids.from_pattern(rng, pick(rng, "CL########", "#########", "@@/{yy}/######", "C-#######")), "CUSTOM", None, ("custom_org_id",))
        domain = world.domain_for(text_of(ins_name))
    kind, loss_type, descs = rng.choice(_INCIDENTS)
    desc = rng.choice(descs).format(storm="\x01", shop="\x02", place="\x03", prod="\x04")
    desc_seg: list = []
    for part in desc.replace("\x01", "\x00S\x00").replace("\x02", "\x00R\x00").replace("\x03", "\x00P\x00").replace("\x04", "\x00D\x00").split("\x00"):
        if part == "S":
            desc_seg.append(K(rng.choice(NAMED_STORMS), "named_storm"))
        elif part == "R":
            desc_seg.append(world.public_company(rng, "retail"))
        elif part == "P":
            desc_seg.append(world.place_trap(rng))
        elif part == "D":
            desc_seg.append(world.product(rng))
        else:
            desc_seg.append(part)
    incident = recent_date(rng, 300)
    ldate = incident + timedelta(days=rng.randint(3, 60))
    dstyle = rng.choice([1, 1, 0, 2, 5])
    variant = rng.choices(["ack", "settle", "decline", "third_party", "summary"], [25, 30, 15, 15, 15])[0]
    d.v(variant + ("-syn" if synth else "-pub"))
    # letterhead
    d.ln(ins_name, pick(rng, "", "", " - Claims Department", "\nMotor Claims" if kind == "motor" else "\nHome Claims Team"))
    if rng.random() < 0.7:
        d.ln(world.make_address(rng, flat_rate=0).block(rng, None))
    d.ln(pick(rng, "Tel: ", "Claims line: ", "Call us: "), org_phone(rng), pick(rng, "", f"  |  {domain}", f"\n{domain}"))
    d.blank()
    if variant == "summary":
        d.ln(pick(rng, "CLAIM SUMMARY", "First notification of loss", "Claim details"))
        d.blank()
        rows = [("Policyholder", ph.full()), (pol_lab, policy), (clm_lab, claim),
                ("Date of incident", letter_date(rng, incident, dstyle)), ("Type of loss", loss_type)]
        if rng.random() < 0.6:
            rows.append(("Date of birth", ph.dob()))
        rows.append(("Address", HC("address_in_table", addr.inline(rng, ph.ref))))
        rows.append(("Contact number", ph.phone()))
        if rng.random() < 0.6:
            rows.append(("Email", ph.email()))
        rows.append(("Estimated value", amount(rng, 150, 12000)))
        if kind in ("motor", "escape_of_water") and rng.random() < 0.6:
            tp = c.new()
            rows.append(("Third party", tp.full()))
            rows.append(("Third party insurer", world.public_company(rng, "insurer")))
        rows.append(("Handler", handler.full()))
        d.add(kv_block(rng, rows))
        d.blank()
        d.ln("Description: ", "On ", letter_date(rng, incident, dstyle), " ", desc_seg, ".")
        return d
    d.ln(letter_date(rng, ldate, dstyle))
    d.blank()
    d.add(recipient_block(rng, ph, addr, joint))
    d.blank()
    d.ln("Our ref: ", claim)
    d.ln(pol_lab, ": ", policy)
    if rng.random() < 0.3:
        d.ln("Your ref: ", ph.last_name() if rng.random() < 0.5 else ph.initials())
    if rng.random() < 0.25:
        d.ln("Date of birth: ", ph.dob())
    d.blank()
    d.ln(greeting(rng, ph))
    d.blank()
    d.ln(pick(rng, "Re: Your claim ", "RE: CLAIM ", "Your claim ", "Claim "), claim, pick(rng, "", f" - {loss_type}", f" ({loss_type.lower()})"))
    d.blank()
    when = letter_date(rng, incident, dstyle)
    if variant == "ack":
        d.ln(pick(rng, "Thank you for letting us know about your claim. ", "We are sorry to hear about your loss. "),
             "We understand that on ", when, " ", desc_seg, ".")
        d.blank()
        d.ln("Your claim has been registered under policy ", E(policy.text, "CUSTOM", None, policy.hard),
             " and ", handler.full(), " will be handling it.")
        d.blank()
        d.ln("To help us progress your claim, please send us:")
        items = ["photographs of the damage", "receipts or proof of ownership for any items claimed",
                 "a copy of any repair estimate", "the police crime reference number"]
        for it in rng.sample(items, rng.randint(2, 4)):
            d.ln("- ", it)
        if kind == "theft" and rng.random() < 0.6:
            d.blank()
            d.ln("We note the crime reference ", E(ids.from_pattern(rng, pick(rng, "##/######/{yy}", "CRI#######", "@@-{yyyy}-#####")),
                                                   "CUSTOM", None, ("custom_org_id",)), " provided when you called.")
    elif variant == "settle":
        gross = round(rng.uniform(250, 9000), 2)
        excess = float(rng.choice([100, 150, 250, 350, 500]))
        net = round(gross - excess, 2)
        d.ln("We have now assessed your claim for the incident on ", when, ", when ", desc_seg, ".")
        d.blank()
        d.ln("We are pleased to offer ", money_k(gross), " in settlement. After deducting your policy excess of ",
             money_k(excess), ", we will pay ", money_k(net), ".")
        d.blank()
        r = rng.random()
        if r < 0.45:
            d.ln("Payment will be made by bank transfer to the account ending ", ph.account_last4(),
                 " within ", str(rng.choice([5, 7, 10])), " working days.")
        elif r < 0.8:
            d.ln("Please check the bank details you gave us:")
            d.ln("Account name: ", ph.full() if rng.random() < 0.7 else ph.initial_last())
            d.ln("Sort code: ", ph.sort_code())
            d.ln("Account number: ", ph.account())
            d.ln("If these are wrong, call us before ", letter_date(rng, ldate + timedelta(days=14), dstyle), ".")
        else:
            d.ln("A cheque for ", money_k(net), " payable to ", ph.full(), " will be sent to the address above.")
    elif variant == "decline":
        d.ln("Thank you for your claim for the incident on ", when, ". We have reviewed the information provided.")
        d.blank()
        d.ln("Unfortunately we are unable to accept your claim. Section ", K(f"{rng.randint(2, 9)}.{rng.randint(1, 8)}", "clause_number"),
             " of your policy wording excludes ", pick(rng, "gradual leaks and wear and tear", "loss when the property is unoccupied for more than 30 days",
                                                          "damage caused by poor workmanship", "items left in an unattended vehicle"), ".")
        d.blank()
        d.ln("If you are unhappy with our decision you can complain to us, and then to ",
             K("the Financial Ombudsman Service", "public_company"), " within six months.")
    else:  # third party
        tp = c.new()
        tp_addr = world.make_address(rng, flat_rate=0.4)
        d.ln("We have received a claim against your policy from ", tp.title_full() if rng.random() < 0.5 else tp.full(), " of ",
             tp_addr.inline(rng, tp.ref), ".")
        d.blank()
        d.ln(tp.mention(rng), " says that on ", when, " ", desc_seg, ".")
        d.blank()
        d.ln("Please let us have your account of what happened within 14 days. Do not contact ",
             tp.mention(rng), " directly or admit liability.")
    d.blank()
    if rng.random() < 0.4:
        d.ln("Your policy is underwritten in accordance with the ", K("Insurance Act 2015", "statute"), ".")
        d.blank()
    if ph.common_word and rng.random() < 0.6:
        p_ = world.common_word_phrase(rng, ph.first)
        if p_:
            d.ln(p_)
            d.blank()
    if org is not None:
        d.ln(signoff(rng, handler, True, org, pick(rng, "Claims Handler", "Senior Claims Handler", "Claims Technician", "Loss Adjuster"),
                     contact=rng.random() < 0.6))
    else:
        d.ln(signoff(rng, handler, True, None, pick(rng, "Claims Handler", "Claims Team Leader"), contact=rng.random() < 0.5, domain=domain))
        d.ln(ins_name)
    if rng.random() < 0.3:
        d.atoms = noise.double_spaces(d.atoms, rng)
        d.v("dsp")
    return d


# --------------------------------------------------------------------------- sentence-pool helpers
def opt(*variants):
    """An optional sentence slot (included with probability p_opt)."""
    return ("?", list(variants))


def para(d: Doc, rng: random.Random, slots: dict, *specs, p_opt: float = 0.5, bullet: bool = False) -> None:
    """Write one paragraph. Each spec is a list of variant templates (one is chosen) or opt(...)."""
    parts = []
    for s in specs:
        if isinstance(s, tuple):
            if rng.random() > p_opt:
                continue
            s = s[1]
        parts.append(rng.choice(s) if isinstance(s, list) else s)
    if not parts:
        return
    if bullet:
        for p_ in parts:
            d.f("- " + p_ + "\n", **slots)
    else:
        d.f(" ".join(parts) + "\n", **slots)
    d.blank()


def extras(d: Doc, rng: random.Random, slots: dict, pool: list[list[str]], lo: int, hi: int) -> None:
    """Optional boiler-plate paragraphs: pick k themes, one or two sentences each, random order."""
    k = rng.randint(lo, min(hi, len(pool)))
    for theme in rng.sample(pool, k):
        n = 1 if len(theme) < 3 or rng.random() < 0.35 else 2
        d.f(" ".join(rng.sample(theme, n)) + "\n", **slots)
        d.blank()


def labelled(d: Doc, rng: random.Random, rows: list[tuple[list[str], object]], style: int | None = None) -> None:
    """Reference block: each row has label variants; layout varies."""
    st = rng.randrange(3) if style is None else style
    for labs, val in rows:
        lab = rng.choice(labs)
        if st == 0:
            d.ln(lab, ": ", val)
        elif st == 1:
            d.ln(lab, " ", val)
        else:
            d.ln(lab.upper(), ": ", val)
    d.blank()


# --------------------------------------------------------------------------- government letters
def _council_town(name: str) -> str:
    for t in world.TOWN_NAMES:
        if t in name:
            return t
    if "Kirklees" in name:
        return "Huddersfield"
    return "London"


_COUNCIL_STOP = {"City", "Council", "London", "Borough", "of", "Royal"}

_COUNCIL_EXTRAS = [
    ["You can pay by Direct Debit, online, by phone using our automated line, or at any Post Office or PayPoint using the barcode on this letter.",
     "The easiest way to pay is by Direct Debit. You can choose to pay on the 1st, 15th or 28th of the month.",
     "If you pay by bank transfer, use your account reference as the payment reference so we can match your payment.",
     "Pay online at {site} 24 hours a day. Have your account reference ready."],
    ["If you are on a low income you may be able to get Council Tax Reduction.",
     "Struggling to pay? Contact us as soon as possible. We can often agree an affordable payment plan.",
     "Free, confidential debt advice is available from {advice}.",
     "You may be entitled to a discount or exemption, for example if you are a student, a carer or have a disability."],
    ["We are required by law to protect the public funds we administer and may share information with other bodies to prevent and detect fraud.",
     "This council takes part in the National Fraud Initiative.",
     "Giving false information to obtain a discount is a criminal offence."],
    ["This letter is available in large print, Braille or other languages on request.",
     "If you need this information in another format, please let us know.",
     "Translation and interpreting services are available free of charge."],
    ["Our phone lines are open Monday to Friday, 9am to 5pm.",
     "Lines are busiest on Mondays and at the start of the month, so it may be quicker to contact us online.",
     "You can manage your account, sign up for e-billing and report a change online."],
    ["Tell us straight away if anyone moves in or out of the property.",
     "You must tell us within 21 days about any change that could affect your bill.",
     "If you are moving home, let us know your new address and the date you are leaving."],
    ["Council Tax is charged under the {ctstat}.",
     "Your property's band is set by the Valuation Office Agency, not by the council.",
     "If you think your band is wrong you can ask the Valuation Office Agency to review it."],
]
_HMRC_EXTRAS = [
    ["You can check your details at any time in your personal tax account.",
     "The HMRC app lets you check your tax code and see your National Insurance record.",
     "Sign in to your personal tax account to see this letter online."],
    ["Beware of scams. HMRC will never ask for your bank details by text or email.",
     "If you get a call, text or email asking for personal information, it may be a scam.",
     "We will never ask you to pay using gift cards or cryptocurrency."],
    ["If you need extra support because of a health condition or personal circumstances, tell us and we will help.",
     "We can send letters in Braille, large print or audio if you need them.",
     "Someone else can contact us for you if you give them permission."],
    ["Keep this letter for your records.", "You may need this letter if you apply for a mortgage or a loan.",
     "Please keep this notice safe as you may need it later."],
    ["You can get help from a tax adviser or from TaxAid if you are on a low income.",
     "If you have a question, have your National Insurance number ready before you call.",
     "Our phone lines are busiest in January and July. Using the app is usually quicker."],
    ["We will write to you again if anything changes.", "You do not need to reply to this letter unless something is wrong.",
     "This letter replaces any earlier notice for the same period."],
    ["If you think the figures are wrong, contact us within 60 days.",
     "We use the information your employer and pension provider send us to work this out.",
     "If any of your details have changed, please tell us so we can update your record."],
]
_DVLA_EXTRAS = [
    ["Do not send your licence unless we ask for it.", "Do not send any documents unless we ask for them.",
     "Please do not send cash through the post."],
    ["You can view your driving record and check your licence details online.",
     "Use the online service to update your details. It is quicker than writing to us."],
    ["It is a criminal offence to make a false declaration.",
     "You can be fined up to {fine} if you do not tell us about a change of address."],
    ["We aim to reply within 10 working days.", "Most applications are dealt with within 3 weeks.",
     "Applications may take longer if we need to make further checks."],
    ["We will write to you again once we have a decision.", "Please quote your reference in all correspondence.",
     "Keep this letter with your licence or logbook."],
    ["Beware of websites that charge extra for our services. Use gov.uk.", "We will never email or text you asking for bank details."],
    ["This letter is available in large print or Braille on request.",
     "If you need help with this form, ask someone you trust or contact us."],
]


def _site_for(council_text: str) -> str:
    site = next(w for w in council_text.replace("&", "").split() if w not in _COUNCIL_STOP).lower()
    return f"{site}.gov.uk/counciltax"


def _gov_header(rng: random.Random, d: Doc, body: K, depts: list[str], with_addr: bool) -> None:
    d.ln(body)
    if rng.random() < 0.7:
        d.ln(rng.choice(depts))
    if with_addr and rng.random() < 0.45:
        d.ln(world.make_address(rng, flat_rate=0, building_rate=0.6).block(rng, None))
    r = rng.random()
    if r < 0.35:
        d.ln(pick(rng, "Tel: ", "Phone: ", "Telephone "), org_phone(rng))
    elif r < 0.55:
        d.ln(pick(rng, "Contact us: ", "Web: ", "Online: "), pick(rng, "gov.uk", "www.gov.uk", "our website"))
    d.blank()


def _council_tax(rng: random.Random, d: Doc, c: Cast):
    p = c.new()
    joint = c.new() if rng.random() < 0.2 else None
    council = K(rng.choice(world.COUNCILS), "public_company")
    town = _council_town(council.text)
    addr = world.make_address(rng, town=town)
    acct_pat = pick(rng, "########", "#########", "CT########", "60#######", "##########", "@########")
    acct = E(ids.from_pattern(rng, acct_pat), "CUSTOM", None, ("custom_org_id",))
    kind = rng.choices(["bill", "reminder", "final", "spd", "moved", "ctr"], [30, 18, 12, 14, 14, 12])[0]
    d.v("ctax-" + kind)
    year = rng.choice([2024, 2025, 2026])
    issue = date(year, 3, rng.randint(1, 20)) if kind == "bill" else date(year, rng.randint(4, 12), rng.randint(1, 28))
    dstyle = rng.choice([0, 1, 1, 2, 5])
    band = rng.choice("ABCDEFG")
    annual = round(rng.uniform(1200, 3600), 2)
    inst = round(annual / 10, 2)
    due = issue + timedelta(days=rng.choice([7, 10, 14]))
    site = _site_for(council.text)
    slots = dict(
        name=p.title_last(), fname=p.full(), prop=addr.inline(rng, p.ref), acct=E(acct.text, "CUSTOM", None, acct.hard),
        amt=money_k(inst), bal=money_k(round(annual - inst * rng.randint(0, 6), 2)), annual=money_k(annual),
        costs=money_k(float(rng.choice([65, 70, 79.5, 85, 92, 105]))), due=letter_date(rng, due, dstyle),
        date=letter_date(rng, issue - timedelta(days=rng.randint(5, 40)), dstyle), band=band,
        site=site, council=K(council.text, "public_company"), year=K(f"{year}/{(year + 1) % 100:02d}", "date"),
        advice=K(pick(rng, "Citizens Advice", "StepChange", "National Debtline", "Citizens Advice or StepChange"), "public_company"),
        ctstat=K(pick(rng, "Local Government Finance Act 1992", "Council Tax (Administration and Enforcement) Regulations 1992"), "statute"),
        week=money_k(round(rng.uniform(3, 32), 2)), income=money_k(round(rng.uniform(90, 420), 2)),
        ph1=K("[name]", "placeholder"), ph2=K("[date]", "placeholder"),
    )
    _gov_header(rng, d, council, ["Revenues and Benefits", "Council Tax Section", "Revenues Service", "Local Taxation",
                                  "Council Tax and Business Rates", "Customer Services - Council Tax"], True)
    title = {"bill": pick(rng, "Council Tax Bill", "Council Tax demand notice", "COUNCIL TAX BILL", "Your Council Tax bill for"),
             "reminder": pick(rng, "Council Tax reminder notice", "REMINDER NOTICE", "Reminder: Council Tax instalment overdue", "First reminder"),
             "final": pick(rng, "FINAL NOTICE", "Council Tax final notice", "Final notice before court action"),
             "spd": pick(rng, "Single person discount review", "Review of your Council Tax discount", "Council Tax: please confirm your discount"),
             "moved": pick(rng, "Change of address confirmation", "Council Tax: you have moved", "Your Council Tax account has been updated", "Moving home - Council Tax"),
             "ctr": pick(rng, "Council Tax Reduction decision", "Notification of Council Tax Reduction", "Your Council Tax Support award")}[kind]
    d.ln(title, " ", slots["year"] if kind == "bill" else "")
    d.blank()
    d.add(recipient_block(rng, p, addr, joint))
    d.blank()
    rows = [(["Account reference", "Council Tax account number", "Account no", "Reference number", "Account ref", "Your reference"], acct),
            (["Date of issue", "Date", "Issue date", "Letter date"], letter_date(rng, issue, dstyle))]
    if rng.random() < 0.6:
        rows.append((["Property", "Property address", "Address of property", "Chargeable property"],
                     HC("address_in_table", addr.inline(rng, p.ref)) if rng.random() < 0.6 else "as above"))
    if kind in ("bill", "spd", "reminder") and rng.random() < 0.7:
        rows.append((["Valuation band", "Band", "Council Tax band"], band))
    rng.shuffle(rows)
    labelled(d, rng, rows)
    if rng.random() < 0.85:
        d.ln(greeting(rng, p))
        d.blank()
    if kind == "bill":
        para(d, rng, slots,
             ["This is your Council Tax bill for {year}.", "Please find below your Council Tax bill for the year {year}.",
              "Here is your Council Tax bill for the coming year {year}.", "Your Council Tax for {year} is shown below."],
             opt("It replaces any earlier bill for this period.", "Please read the notes overleaf.",
                 "It shows how your charge has been worked out."))
        parts = [("Council", rng.uniform(1100, 2300)), ("Adult social care precept", rng.uniform(120, 300)),
                 ("Police and crime", rng.uniform(180, 320)), ("Fire and rescue", rng.uniform(60, 110))]
        if rng.random() < 0.3:
            parts.append((pick(rng, "Parish council", "Town council"), rng.uniform(20, 90)))
        rng.shuffle(parts)
        total = round(sum(v for _, v in parts), 2)
        d.ln(pick(rng, "How your bill is made up", "Charges for the year", "Breakdown", "Your charge"))
        for lab, v in parts:
            d.ln(lab, pick(rng, ": ", " "), money_k(round(v, 2)))
        d.ln(pick(rng, "Annual charge: ", "Total for the year: ", "Gross charge: "), money_k(total))
        disc = 0.0
        if rng.random() < 0.35:
            disc = round(total * 0.25, 2)
            d.ln(pick(rng, "Less single person discount (25%): ", "Discount: ", "Single person discount: -"), money_k(disc))
        dueamt = round(total - disc, 2)
        d.ln(pick(rng, "Amount payable: ", "Total to pay: ", "Net amount due: "), money_k(dueamt))
        d.blank()
        n = rng.choice([10, 10, 12])
        ins = round(dueamt / n, 2)
        d.ln(pick(rng, "Instalments", "Your instalments", "Payment dates", "Payment plan"))
        day = rng.choice([1, 1, 15, 28])
        ist = rng.choice([0, 1, 5])
        rows_i = []
        for i in range(n):
            m = (4 + i - 1) % 12 + 1
            y = year if m >= 4 else year + 1
            rows_i.append([K(ids.format_date(date(y, m, day), ist), "date"), money_k(ins if i else round(dueamt - ins * (n - 1), 2))])
        if rng.random() < 0.5:
            d.add(HC("table_layout", ["| Date | Amount |\n|---|---:|\n"] + [["| ", r[0], " | ", r[1], " |\n"] for r in rows_i]))
        else:
            for r in rows_i:
                d.ln(r[0], pick(rng, "  ", " - ", "    "), r[1])
        d.blank()
    elif kind == "reminder":
        para(d, rng, slots,
             ["Our records show that the instalment of {amt} due on {date} has not been paid.",
              "We have not received your Council Tax instalment of {amt}, which was due on {date}.",
              "Your Council Tax payment of {amt} is overdue. It should have reached us by {date}."],
             ["Please pay this amount by {due}.", "You need to pay {amt} within 7 days of the date of this notice.",
              "Please make sure the payment reaches us no later than {due}."])
        para(d, rng, slots,
             ["If you do not pay, you will lose the right to pay by instalments and the full balance of {bal} will become due.",
              "If the instalment is not paid you will have to pay the full balance for the year, which is {bal}.",
              "If you miss this payment, the whole of the remaining balance ({bal}) becomes payable at once."],
             opt("This is your first reminder this year.", "If you receive a second reminder, you will lose the right to pay by instalments.",
                 "Further reminders may lead to a summons and extra costs."))
        para(d, rng, slots, ["If you have already paid, thank you, and please ignore this reminder.",
                             "If you have paid in the last few days, please accept our thanks.",
                             "If your payment has crossed with this letter, no further action is needed."])
    elif kind == "final":
        para(d, rng, slots,
             ["You have now lost the right to pay by instalments.", "You have not paid the amount asked for in our reminder.",
              "Despite our earlier reminders, your account is still in arrears."],
             ["The full balance of {bal} must be paid within 7 days.", "You must now pay the full outstanding balance of {bal}.",
              "The amount now due is {bal}, payable immediately."])
        para(d, rng, slots,
             ["If you do not pay we will apply to the magistrates' court for a liability order, and costs of {costs} will be added.",
              "If the balance is not paid we will issue a summons. Court costs of {costs} will be added to your account.",
              "Failure to pay will result in a summons being issued and costs of {costs} being charged."],
             opt("A liability order lets us take money from your wages or benefits.",
                 "Enforcement agents may be instructed to collect the debt.",
                 "We may also pass the debt to enforcement agents."))
        para(d, rng, slots, ["If you are having difficulty paying, please contact us now.",
                             "Contact us urgently if you cannot pay. Do not ignore this notice.",
                             "If you need help, speak to us or to {advice} before the court date."])
    elif kind == "spd":
        para(d, rng, slots,
             ["You currently receive a 25% discount because you have told us you are the only adult living at {prop}.",
              "Our records show that a single person discount is applied to your account for {prop}.",
              "We are reviewing all single person discounts in the borough, including the one on your account."],
             ["Please confirm by {due} whether this is still correct.", "We need you to confirm your circumstances by {due}.",
              "Please reply to this letter by {due}."])
        para(d, rng, slots,
             ["If anyone aged 18 or over has moved in, tell us their name and the date they moved in.",
              "If another adult now lives with you, give us their full name and the date they moved in: {ph1}, {ph2}.",
              "If your household has changed, please complete the form below."],
             opt("Some adults, such as full-time students and carers, are not counted.",
                 "Do not include anyone under 18.", "You can complete this review online."),
             p_opt=0.6)
        para(d, rng, slots, ["If you do not reply, we may remove your discount and send you a new bill.",
                             "If we do not hear from you, the discount may be cancelled from {date}.",
                             "Failure to reply may result in a penalty of £70 and removal of the discount."])
    elif kind == "moved":
        new = world.make_address(rng, town=town if rng.random() < 0.7 else None)
        acct2 = E(ids.from_pattern(rng, acct_pat), "CUSTOM", None, ("custom_org_id",))
        slots.update(new=new.inline(rng, p.ref), acct2=acct2)
        para(d, rng, slots,
             ["Thank you for telling us that you moved from {prop} to {new} on {date}.",
              "We have updated our records to show that you left {prop} on {date}.",
              "You told us that you moved home on {date}. Your new address is {new}."],
             ["We have closed your account for your old address.", "Your account for the old property is now closed.",
              "We have ended your liability at your previous address."])
        para(d, rng, slots,
             ["A final bill of {amt} for your old address is enclosed.", "Your final bill for the old property shows {amt} to pay.",
              "There is a balance of {amt} left on your old account."],
             opt("Your new account reference is {acct2}.", "Please quote {acct2} for your new address from now on.",
                 "A new bill for your new address, account {acct2}, will follow."), p_opt=0.7)
    else:  # council tax reduction
        para(d, rng, slots,
             ["We have assessed your claim for Council Tax Reduction.", "Thank you for your application for Council Tax Support.",
              "We have worked out your entitlement to Council Tax Reduction."],
             ["From {date} you will receive a reduction of {week} a week.", "You are entitled to a reduction of {week} a week from {date}.",
              "Your award is {week} a week, starting on {date}."])
        para(d, rng, slots,
             ["This is based on a household income of {income} a week.", "We have used a weekly income of {income} in our calculation.",
              "The calculation uses your earnings and benefits, which total {income} a week."],
             opt("If your income changes, you must tell us within 21 days.",
                 "If you disagree with this decision you can ask us to look at it again within one month.",
                 "A revised bill will be sent to you separately."), p_opt=0.7)
    extras(d, rng, slots, _COUNCIL_EXTRAS, 3, 6)
    d.ln(pick(rng, "Yours sincerely,", "Yours faithfully,", "Thank you,", "Regards,"))
    d.ln(pick(rng, "Revenues Manager", "Council Tax Team", "Revenues and Benefits Service", "Head of Revenues", "Local Taxation Manager"))


def _hmrc(rng: random.Random, d: Doc, c: Cast):
    p = c.new()
    addr = world.make_address(rng)
    kind = rng.choice(["p800", "simple", "taxcode", "sa", "ni", "nirecord", "marriage"])
    d.v("hmrc-" + kind)
    ldate = recent_date(rng, 500)
    dstyle = rng.choice([1, 1, 0, 2])
    ty = rng.choice([2022, 2023, 2024, 2025])
    emp = world.company_name(rng) if rng.random() < 0.6 else world.public_company(rng, "employer")
    slots = dict(
        name=p.title_last(), ty=[K(f"6 April {ty}", "date"), " to ", K(f"5 April {ty + 1}", "date")],
        ty_short=K(f"{ty} to {ty + 1}", "date"), ty_next=K(f"{ty + 1} to {ty + 2}", "date"),
        amt=money_k(round(rng.uniform(40, 2400), 2)), amt2=money_k(round(rng.uniform(12000, 70000), 2)),
        amt3=money_k(round(rng.uniform(800, 14000), 2)), pa=money_k(12570.0), ma=money_k(1260.0), maxsave=money_k(252.0),
        emp=emp, paye=K(ids.from_pattern(rng, "###/@@#####"), "employer_reference"),
        deadline=letter_date(rng, date(ty + 2, 1, 31), dstyle), oct=K(f"31 October {ty + 1}", "date"),
        apr=K(f"6 April {ty + 2}", "date"), pen=money_k(100.0), c3=money_k(round(rng.uniform(17.0, 18.5), 2)),
        years=str(rng.randint(8, 34)), gapy=K(f"{ty - rng.randint(2, 6)} to {ty - rng.randint(0, 1)}", "date"),
        code=K(pick(rng, "1257L", "1185L", "K497", "1100L", "BR", "S1257L", "C1257L", "1257L M1", "1383M", "1131N"), "tax_code"),
        reason=pick(rng, "your tax code was wrong for part of the year", "you had more than one job",
                    "your employer did not use the right tax code", "you received taxable benefits",
                    "your State Pension was not taxed at source", "you had untaxed savings interest"),
        due=letter_date(rng, ldate + timedelta(days=rng.choice([30, 60, 90])), dstyle),
        dwp=K("the DWP", "public_company"), ni=p.ni(),
    )
    _gov_header(rng, d, K(pick(rng, "HM Revenue & Customs", "HMRC", "HM Revenue and Customs"), "public_company"),
                ["Pay As You Earn and Self Assessment", "PAYE", "Self Assessment", "National Insurance Contributions and Employer Office",
                 "Customer Compliance Group", "Individuals and Pensions"], False)
    d.add(recipient_block(rng, p, addr))
    d.blank()
    rows = [(["Date", "Issue date", "Date of this letter"], letter_date(rng, ldate, dstyle))]
    if kind in ("p800", "taxcode", "ni", "nirecord", "marriage", "simple") or rng.random() < 0.5:
        rows.append((["National Insurance number", "NI number", "Your National Insurance number"], p.ni()))
    if kind in ("sa", "simple") or rng.random() < 0.3:
        rows.append((["Unique Taxpayer Reference (UTR)", "UTR", "Reference"],
                     E(ids.utr(rng, rng.random() < 0.6), "CUSTOM", p.ref, ("custom_org_id",))))
    if kind in ("p800", "taxcode") and rng.random() < 0.5:
        rows.append((["Employer PAYE reference", "Employer reference", "PAYE ref"], slots["paye"]))
    rng.shuffle(rows)
    labelled(d, rng, rows)
    d.ln(greeting(rng, p))
    d.blank()
    if kind == "p800":
        over = rng.random() < 0.5
        d.ln(pick(rng, "Tax calculation for the year ", "Your tax calculation: ", "P800 - tax year "), slots["ty"])
        d.blank()
        para(d, rng, slots,
             ["You paid {amt} too much tax." if over else "You paid {amt} too little tax.",
              "Our records show you have overpaid {amt} in tax." if over else "Our records show you owe {amt} in tax.",
              "We owe you a refund of {amt}." if over else "You have underpaid {amt}."],
             ["This is because {reason}.", "The main reason is that {reason}.", "This happened because {reason}."])
        d.ln(pick(rng, "Employer: ", "Pay from ", "Employment: "), slots["emp"], pick(rng, ", PAYE reference ", ", PAYE ref ", " - "),
             slots["paye"])
        d.ln(pick(rng, "Pay from this employer: ", "Total pay: ", "Taxable pay: "), slots["amt2"])
        d.ln(pick(rng, "Tax paid: ", "Tax deducted: ", "Tax taken off: "), slots["amt3"])
        d.blank()
        if over:
            if rng.random() < 0.5:
                d.ln(pick(rng, "You can claim online to get the money into your account ending ", "We can pay the refund into your account ending "),
                     p.account_last4(), pick(rng, " faster.", ".", " within 5 working days."))
            else:
                para(d, rng, slots, ["You can claim your refund online.", "We will send you a cheque within 14 days.",
                                     "If you do not claim online within 21 days, we will send a cheque."])
        else:
            para(d, rng, slots, ["We will collect this through your tax code from {apr}.",
                                 "We will adjust your tax code from {apr} to collect it.",
                                 "You do not need to do anything. We will collect it through your tax code."],
                 opt("If you prefer, you can pay it in one go.", "If the amount is over £3,000 we will contact you about paying."))
    elif kind == "simple":
        d.ln(pick(rng, "Simple Assessment for the tax year ", "PA302 Tax calculation ", "Your tax bill for "), slots["ty_short"])
        d.blank()
        para(d, rng, slots, ["You owe {amt} for the tax year {ty_short}.", "Our calculation shows you need to pay {amt}.",
                             "You have {amt} of tax to pay for {ty_short}."],
             ["You need to pay by {deadline}.", "Please pay by {deadline}.", "Payment must reach us by {deadline}."])
        para(d, rng, slots, ["This is because {reason}.", "We worked this out because {reason}."],
             opt("You do not need to fill in a tax return.", "This is not a Self Assessment tax return."),
             opt("If you think it is wrong, tell us within 60 days.", "You can query this calculation within 60 days."), p_opt=0.6)
    elif kind == "taxcode":
        para(d, rng, slots, ["Your tax code for {ty_next} is {code}.", "We have changed your tax code. From now on it is {code}.",
                             "This notice tells you your new tax code, {code}, for {ty_next}."],
             ["We use your tax code to tell {emp} (PAYE reference {paye}) how much tax to take from your pay.",
              "Your employer, {emp}, will use this code from your next payday.",
              "We have sent this code to {emp}."])
        d.ln(pick(rng, "Personal Allowance: ", "Your tax-free amount: "), slots["pa"])
        if rng.random() < 0.6:
            d.ln(pick(rng, "Less company benefits: ", "Minus benefits in kind: ", "Less untaxed interest: "),
                 money_k(round(rng.uniform(300, 6000), 2)))
        d.blank()
        para(d, rng, slots, opt("If your circumstances change, tell us so we can update your code.",
                                "Check that the figures are right.", "You do not need to do anything if the details are correct."), p_opt=0.8)
    elif kind == "sa":
        d.ln(pick(rng, "Self Assessment tax return for ", "Notice to complete a tax return: ", "Your tax return for "), slots["ty"])
        d.blank()
        para(d, rng, slots, ["You need to send us a tax return for the year {ty_short}.", "We need a tax return from you for {ty_short}.",
                             "This notice requires you to complete a tax return."],
             ["The deadline for online returns is {deadline}.", "Online returns must reach us by {deadline}.",
              "Send it online by {deadline}, or on paper by {oct}."])
        para(d, rng, slots, ["If your return is late you will have to pay a penalty of {pen}.", "A late return means an automatic penalty of {pen}.",
                             "You will be charged a {pen} penalty if your return is late, even if you have no tax to pay."],
             opt("Use your UTR when you contact us.", "Quote your UTR on all correspondence.", "Your UTR is shown at the top of this letter."),
             opt("Interest is charged on late payments.", "You may also need to make payments on account."), p_opt=0.6)
    elif kind == "ni":
        para(d, rng, slots, ["Your National Insurance number is {ni}.", "We have registered you for National Insurance. Your number is {ni}.",
                             "This letter confirms your National Insurance number: {ni}."],
             opt("Keep this letter safe.", "Please keep this letter in a safe place.", "You will need this number throughout your life."))
        para(d, rng, slots, ["Your National Insurance number stays the same all your life.", "Your number is unique to you and never changes."],
             ["Give it to your employer and use it when you contact us or {dwp}.", "You will need it when you start work or claim benefits.",
              "Your employer needs it so that your contributions are recorded correctly."], p_opt=0.6)
    elif kind == "nirecord":
        d.ln(pick(rng, "Your National Insurance record", "National Insurance contributions statement", "Gaps in your National Insurance record"))
        d.blank()
        para(d, rng, slots, ["Your record shows that you have {years} qualifying years.", "You currently have {years} full years on your record.",
                             "We have checked your record. It shows {years} qualifying years."],
             ["You usually need 35 qualifying years to get the full new State Pension.", "The full new State Pension needs 35 qualifying years.",
              "You need at least 10 qualifying years to get any State Pension."])
        para(d, rng, slots, ["There are gaps in your record for the years {gapy}.", "Your record is not complete for {gapy}.",
                             "Some years between {gapy} are not full years."],
             ["You can pay voluntary Class 3 contributions of {c3} a week to fill these gaps.",
              "Voluntary contributions cost {c3} a week.", "You may be able to fill the gaps by paying {c3} a week."],
             opt("Check whether paying will increase your pension before you pay.", "You can usually only pay for the past 6 years."))
    else:  # marriage allowance
        partner = c.new()
        slots.update(partner=partner.full(), pn=partner.title_last())
        para(d, rng, slots, ["Your claim to transfer part of your Personal Allowance to {partner} has been accepted.",
                             "Thank you for applying for Marriage Allowance for you and {partner}. We have accepted your claim.",
                             "You have transferred {ma} of your Personal Allowance to your partner, {partner}."],
             ["This means {pn} could pay up to {maxsave} less tax each year.", "Your partner's tax bill could reduce by up to {maxsave} a year.",
              "{pn} will get the benefit through their tax code."])
        para(d, rng, slots, ["Your own Personal Allowance will go down by {ma}.", "Your tax code will change to reflect the transfer."],
             opt("The allowance will continue each year until one of you cancels it.", "You must tell us if you divorce or separate."), p_opt=0.7)
    extras(d, rng, slots, _HMRC_EXTRAS, 3, 6)
    d.ln(pick(rng, "Yours sincerely", "Yours faithfully", "Thank you", ""))
    d.ln({"p800": pick(rng, "HMRC", "PAYE Operations"), "taxcode": pick(rng, "HMRC", "PAYE Operations"), "simple": "HMRC",
          "sa": pick(rng, "HMRC", "Self Assessment team"), "ni": pick(rng, "HMRC", "National Insurance Registrations"),
          "nirecord": pick(rng, "HMRC", "National Insurance Contributions Office"), "marriage": pick(rng, "HMRC", "Marriage Allowance team")}[kind])


def _dvla(rng: random.Random, d: Doc, c: Cast):
    p = c.new(min_age=17, max_age=85)
    addr = world.make_address(rng)
    kind = rng.choice(["renew", "address", "medical", "v5c", "passport", "pp_renew"])
    d.v("dvla-" + kind)
    ldate = recent_date(rng, 400)
    dstyle = rng.choice([1, 0, 2, 5])
    slots = dict(name=p.title_last(), fine=money_k(1000.0), fee=money_k(14.0), fee2=money_k(17.0),
                 exp=letter_date(rng, ldate + timedelta(days=rng.randint(30, 90)), dstyle),
                 sold=letter_date(rng, ldate - timedelta(days=rng.randint(3, 30)), dstyle),
                 valid=letter_date(rng, ldate + timedelta(days=3650), dstyle),
                 car=K(pick(rng, "Ford Focus", "Vauxhall Corsa", "Volkswagen Golf", "Nissan Qashqai", "Toyota Yaris", "Kia Sportage", "BMW 1 Series"), "product"),
                 pfee=money_k(float(rng.choice([88.5, 94.5, 100.0, 107.0]))), days=str(rng.choice([21, 28, 42])))
    if kind in ("passport", "pp_renew"):
        _gov_header(rng, d, K("HM Passport Office", "public_company"), ["Passport Customer Services", "Customer Services", "Durham office"], False)
    else:
        _gov_header(rng, d, K(pick(rng, "DVLA", "Driver and Vehicle Licensing Agency", "DVLA Swansea"), "public_company"),
                    ["Drivers Customer Services", "Drivers Medical Group", "Vehicles Customer Services", "Customer Enquiries"], False)
    d.add(recipient_block(rng, p, addr))
    d.blank()
    rows = [(["Date", "Our date", "Date of issue"], letter_date(rng, ldate, dstyle))]
    if kind in ("passport", "pp_renew"):
        rows.append((["Application reference", "Reference number", "Your reference"],
                     E(ids.from_pattern(rng, pick(rng, "####-####-####-####", "PEX#########", "##########")), "CUSTOM", p.ref, ("custom_org_id",))))
        if kind == "pp_renew":
            rows.append((["Passport number", "Current passport number"], p.passport()))
    elif kind != "v5c":
        rows.append((["Driving licence number", "Driver number", "Licence no"], p.licence()))
    if rng.random() < 0.6:
        rows.append((["Date of birth", "DOB"], p.dob()))
    rng.shuffle(rows)
    labelled(d, rng, rows)
    d.ln(greeting(rng, p))
    d.blank()
    if kind == "renew":
        para(d, rng, slots, ["Your photocard driving licence will expire on {exp}.", "The photo on your driving licence runs out on {exp}.",
                             "This is a reminder that your licence photocard expires on {exp}."],
             ["You must renew it to keep driving.", "You need to renew your photocard before this date.", "Please renew it as soon as you can."])
        para(d, rng, slots, ["You can renew online at gov.uk for {fee}.", "It costs {fee} online or {fee2} by post.",
                             "The quickest way is to apply online, which costs {fee}."],
             opt("You will need a valid UK passport to apply online.", "If you apply by post, send a new photo with the form."),
             opt("Your licence entitlements will not change.", "You can keep driving while we process your application."))
    elif kind == "address":
        d.ln(pick(rng, "We have updated your driving licence record with your new address:", "Your new address has been recorded as:",
                  "Change of address confirmed. We now hold:"))
        d.ln(addr.block(rng, p.ref))
        d.blank()
        para(d, rng, slots, ["Your new licence should arrive within 3 weeks.", "A new photocard will be sent to you shortly.",
                             "Please destroy your old licence when the new one arrives."],
             opt("Your licence number has not changed.", "Your driver number stays the same."))
    elif kind == "medical":
        para(d, rng, slots, ["You told us about a medical condition that may affect your driving.", "We have been told about a health condition that could affect your driving.",
                             "We need more information about your medical condition before we can decide on your licence."],
             ["Please complete the enclosed questionnaire and return it within {days} days.", "Please fill in the enclosed form and send it back within {days} days.",
              "We need you to return the enclosed questionnaire within {days} days."])
        para(d, rng, slots, ["We may ask your doctor for information.", "With your permission we will contact your GP or consultant.",
                             "We may ask you to have an examination or eyesight test."],
             opt("You can usually keep driving while we make enquiries, unless your doctor has told you not to.",
                 "If your doctor has told you to stop driving, you must not drive."),
             opt("There is no charge for this.", "We will write to you once we have made a decision."))
    elif kind == "v5c":
        keeper = c.new()
        slots.update(keeper=keeper.full())
        d.ln(pick(rng, "Vehicle registration certificate (V5C)", "Confirmation: you are no longer the keeper", "Change of keeper notification"))
        d.blank()
        para(d, rng, slots, ["You told us you sold or transferred your {car} on {sold}.", "We have updated our records to show that you are no longer the keeper of your {car}.",
                             "Thank you for telling us about the sale of your vehicle on {sold}."],
             ["The new keeper, {keeper}, will receive a new V5C within 4 weeks.", "We have recorded {keeper} as the new keeper.",
              "A new logbook will be sent to the new keeper, {keeper}."])
        para(d, rng, slots, ["You will get a refund for any full months of vehicle tax left.", "Any vehicle tax refund will be sent automatically.",
                             "Your Direct Debit for vehicle tax has been cancelled."],
             opt("If you did not make this change, contact us straight away.", "If any of this information is wrong, tell us immediately."))
    elif kind == "passport":
        pp_ = p.passport()
        slots.update(pp=pp_)
        para(d, rng, slots, ["Your new passport, number {pp}, has been issued.", "We have issued your new passport (number {pp}).",
                             "Your passport application is complete. Your passport number is {pp}."],
             ["It will be delivered by secure courier.", "It will arrive by courier within 5 working days.", "It has been sent to you by secure delivery."],
             ["Your old passport has been cancelled.", "Your previous passport is no longer valid for travel.", "Any old passport has been cancelled."])
        d.ln(pick(rng, "Valid until: ", "Expiry date: ", "Date of expiry: "), slots["valid"])
        d.blank()
    else:
        para(d, rng, slots, ["Your passport will expire on {exp}.", "We are writing to remind you that your passport runs out on {exp}.",
                             "The passport shown above expires soon, on {exp}."],
             ["You can renew online for {pfee}.", "It costs {pfee} to renew online.", "Online renewal costs {pfee}."],
             opt("Some countries need at least 6 months left on your passport.", "Check the entry rules for the country you are visiting."))
    extras(d, rng, slots, _DVLA_EXTRAS, 3, 5)
    d.ln(pick(rng, "Yours sincerely,", "Yours faithfully,", "Thank you,"))
    d.ln(pick(rng, "Drivers Customer Services", "Drivers Medical Group", "Customer Services", "Vehicles Customer Services")
         if kind not in ("passport", "pp_renew") else pick(rng, "HM Passport Office", "Passport Customer Services"))


_GOV_NEG_POOLS = {
    "council_tax_spend": [
        "This leaflet explains how the charge for each band is worked out.",
        "Amounts shown are for the whole year and assume no discounts.",
        "Most households pay in 10 monthly instalments, but you can ask to pay over 12 months.",
        "The adult social care precept rose by {pct} this year.",
        "Every {amt} of Council Tax pays for bin collections, libraries, roads and social care.",
        "If you live alone you may get a 25% single person discount.",
        "Students in full-time education do not usually pay Council Tax.",
        "Properties are placed in bands by the Valuation Office Agency, not by the council.",
        "The charges are set under the {statute}.",
        "Bills for {year} will be sent out from {date}.",
    ],
    "bins": [
        "From {date} general waste will be collected every two weeks.",
        "Recycling collections stay weekly.",
        "The household waste site at {place} will stay open until 6pm in summer.",
        "Garden waste permits cost {amt} a year.",
        "Please put your bin out by 7am on your collection day.",
        "Collections may be a day late in the week after a bank holiday.",
        "Food waste caddies are free. Order one online.",
        "Side waste next to your bin will not be collected.",
        "Bulky waste collections cost {amt} for up to three items.",
    ],
    "sa_dates": [
        "Register for Self Assessment by {date} if you need to send a return for the first time.",
        "Paper returns are due by 31 October and online returns by 31 January.",
        "A late return means a penalty of {amt}, even if you owe no tax.",
        "You may need to make payments on account each January and July.",
        "Keep your records for at least five years after the deadline.",
        "You can pay in instalments if your tax bill is under {amt2}.",
        "Use the HMRC app to check what you owe.",
        "Interest is charged on tax paid late.",
        "You can register for Self Assessment online.",
        "Partners in a business must each send a return.",
        "Income from renting out property may mean you need to file a return.",
        "The deadline to pay any tax you owe is the same as the online filing deadline.",
        "If you no longer need to file, tell HMRC as soon as possible.",
    ],
    "tax_code": [
        "Your tax code is usually 1257L if you have one job and no taxable benefits.",
        "The Personal Allowance is {amt} for the {year} tax year.",
        "Check your tax code in your personal tax account or the HMRC app.",
        "An emergency tax code such as 1257L W1 may be used when you start a new job.",
        "If your code is wrong you could pay too much or too little tax.",
        "Tell HMRC if you start receiving a company car or medical insurance.",
        "Codes starting with K mean you have income that is not taxed another way.",
        "The letter L means you get the standard tax-free Personal Allowance.",
        "BR means all your income from this job is taxed at the basic rate.",
        "A code ending in M or N relates to Marriage Allowance.",
        "Scottish taxpayers have codes starting with S; Welsh taxpayers have codes starting with C.",
        "Your employer cannot change your tax code. Only HMRC can.",
        "You can have different tax codes for different jobs or pensions.",
        "If you get a new code part way through the year, any over or underpayment is usually sorted out automatically.",
    ],
    "licence_renewal": [
        "Photocard driving licences must be renewed every 10 years.",
        "It costs {amt} to renew online and more by post.",
        "You need a valid UK passport to renew online.",
        "Most applications are processed within one week.",
        "You can keep driving while your renewal is being processed in most cases.",
        "From age 70 you must renew every three years. This is free.",
        "Tell DVLA about medical conditions that could affect your driving.",
        "You can be fined up to {amt3} for driving with an out-of-date photo.",
        "Your photo must be a true likeness of you.",
        "Check that your address is up to date before you apply.",
        "Paper licences issued before 1998 stay valid until you change your details.",
        "Lorry and bus drivers must renew more often and may need a medical.",
        "You will be sent a reminder about 8 weeks before your photocard expires.",
    ],
}
_GOV_NEG_TITLES = {
    "council_tax_spend": ["How your Council Tax is spent in {year}", "Council Tax {year}: a guide", "Your Council Tax explained"],
    "bins": ["Changes to bin collections from {date}", "Your new collection calendar", "Recycling and waste: what is changing"],
    "sa_dates": ["Self Assessment: key dates for {year}", "Get ready for Self Assessment", "Self Assessment tax returns: a guide"],
    "tax_code": ["Check your tax code", "Understanding your tax code", "Tax codes explained for {year}"],
    "licence_renewal": ["Renewing your photocard driving licence", "Is your driving licence photo out of date?", "Licence renewals: what you need"],
}


def _gov_negative(rng: random.Random, d: Doc):
    topic = rng.choice(list(_GOV_NEG_POOLS))
    d.v("neg-" + topic)
    year = rng.choice([2024, 2025, 2026])
    when = date(year, rng.randint(1, 12), rng.randint(1, 28))
    slots = dict(year=K(f"{year}/{(year + 1) % 100:02d}" if rng.random() < 0.5 else f"{year} to {year + 1}", "date"),
                 date=K(ids.format_date(when, rng.choice([1, 1, 2, 0])), "date"), place=world.place_trap(rng),
                 amt=money_k(float(rng.choice([1, 14, 17, 45, 52, 60, 65, 100, 12570]))),
                 amt2=money_k(float(rng.choice([30000, 10000, 3000]))), amt3=money_k(float(rng.choice([1000, 500]))),
                 pct=K(f"{rng.choice([1, 2, 3])}%", "amount"), statute=K("Local Government Finance Act 1992", "statute"))
    if topic in ("council_tax_spend", "bins"):
        d.ln(K(rng.choice(world.COUNCILS), "public_company"))
    else:
        d.ln(K(pick(rng, "HMRC", "HM Revenue & Customs") if topic != "licence_renewal" else pick(rng, "DVLA", "Driver and Vehicle Licensing Agency"),
               "public_company"))
    d.f(rng.choice(_GOV_NEG_TITLES[topic]) + "\n", **slots)
    d.blank()
    pool = _GOV_NEG_POOLS[topic]
    chosen = rng.sample(pool, rng.randint(4, min(9, len(pool))))
    bullets = rng.random() < 0.5
    for sent in chosen:
        d.f(("- " if bullets else "") + sent + ("\n" if bullets or rng.random() < 0.5 else " "), **slots)
    if rng.random() < 0.6:
        d.blank()
        d.ln(pick(rng, "Questions?", "Need help?", "What to do next", "Contact us"))
        d.ln(pick(rng, "Most questions are answered on gov.uk.", "You can find answers to common questions online.",
                  "Check our website before you call, as most things can be done online.",
                  "If you cannot use the internet, ask a friend or family member to help."),
             pick(rng, "", " Lines are busy on Mondays.", " We cannot give advice about individual cases in this leaflet.",
                  " This leaflet does not cover every situation."))
    if topic == "council_tax_spend" and rng.random() < 0.6:
        band_d = round(rng.uniform(1850, 2600), 2)
        d.blank()
        d.add(HC("table_layout", ["| Band | Annual charge |\n|---|---:|\n"] +
                 [["| ", b, " | ", money_k(round(band_d * r / 9, 2)), " |\n"] for b, r in zip("ABCDEFGH", [6, 7, 8, 9, 11, 13, 15, 18])]))
    d.blank()
    d.ln(pick(rng, "More information: gov.uk", "Find out more at gov.uk", "Visit our website for details.", "This leaflet is available in large print."))


@register("gov_letter", weight=3, neg_weight=4)
def gov_letter(rng: random.Random, neg: bool) -> Doc:
    d = Doc("gov_letter", "gov_letter/v2")
    if neg:
        _gov_negative(rng, d)
        return d
    c = Cast(rng, common_word_rate=0.06)
    fn = rng.choices([_council_tax, _hmrc, _dvla], [40, 38, 22])[0]
    fn(rng, d, c)
    if rng.random() < 0.25:
        d.atoms = noise.double_spaces(d.atoms, rng)
        d.v("dsp")
    return d


# --------------------------------------------------------------------------- medical letter
_SPECIALTIES = ["Dermatology", "Cardiology", "Ophthalmology", "General Surgery", "Rheumatology", "Orthopaedics",
                "Gastroenterology", "ENT", "Respiratory Medicine", "Physiotherapy", "Diabetes and Endocrinology",
                "Urology", "Neurology", "Audiology", "Vascular Surgery", "Pain Management", "Plastic Surgery"]
_HOSPITALS = ["St James's University Hospital", "the Royal Infirmary", "Queen Elizabeth Hospital", "Northern General Hospital",
              "the Royal Victoria Infirmary", "City Hospital", "the General Hospital", "Princess Royal Hospital",
              "St Thomas' Hospital", "Wythenshawe Hospital", "Southmead Hospital", "the Freeman Hospital",
              "Chapel Allerton Hospital", "the Queen's Medical Centre", "Seacroft Hospital", "Musgrove Park Hospital"]
_CLINICS = ["Outpatients B, Level 1", "Clinic 4, Ground Floor", "the Chapel Allerton Wing", "Outpatient Department 2",
            "the Day Case Unit", "Clinic C, Brotherton Wing", "the Eye Clinic, Level 3", "Physiotherapy, Gledhow Wing",
            "the Treatment Centre", "Ward 12 Day Unit", "the Pre-assessment Unit, Level 2", "the Diagnostic Centre"]
_WARDS = ["Ward 7", "Ward 22", "the Surgical Assessment Unit", "Ward J14", "the Short Stay Unit", "Ward 4B", "the Day Surgery Unit"]
_GENERIC_REASONS = ["a routine review", "a follow-up appointment", "a new patient appointment", "a blood test",
                    "a routine check of your progress", "an assessment following your GP's referral", "a review of your treatment"]
_GP_PRACTICES = ["Oakwood Medical Centre", "Riverbank Surgery", "Elmtree Health Centre", "The Grove Practice", "Park View Surgery",
                 "Hillside Family Practice", "Meadowbank Health Centre", "Church Lane Surgery"]
_SCREENING = ["bowel cancer screening", "breast screening", "abdominal aortic aneurysm (AAA) screening", "diabetic eye screening",
              "cervical screening"]

_MED_EXTRAS = [
    ["Please bring a list of your current medicines.", "Bring any medicines, inhalers or sprays you use with you.",
     "Please bring this letter and your glasses or hearing aids if you use them."],
    ["If you need an interpreter, please tell us at least 48 hours before your appointment.",
     "Interpreters, including British Sign Language, can be booked for you.",
     "Let us know if you have any access needs so we can help."],
    ["Car parking on site is limited and charges apply.", "Please allow extra time to park. The {hosp} car park is often full.",
     "Public transport is the easiest way to reach {hosp}."],
    ["You may bring a relative or friend with you.", "You are welcome to bring someone with you for support.",
     "Children should not be brought to the clinic unless they are the patient."],
    ["Please allow up to two hours for your visit.", "Clinics can run late. We are sorry for any wait.",
     "You may need tests on the day, so please allow extra time."],
    ["If your condition gets worse before your appointment, contact your GP or call NHS 111.",
     "In an emergency always call 999.", "If you feel unwell before your appointment, speak to your GP."],
    ["Your personal information is held securely in line with the {dpa}.", "We share information about your care with your GP.",
     "You can ask to see the information we hold about you."],
    ["We are a teaching hospital and students may be present. You can ask for them not to be.",
     "Medical students may be involved in your care. Please tell us if you would prefer them not to be."],
    ["Each missed appointment costs the NHS money and delays care for others.",
     "If you no longer need this appointment, please let us know so it can be given to someone else.",
     "Text CANCEL to the number on your reminder if you cannot attend."],
]


def _appt_time(rng: random.Random) -> str:
    return pick(rng, f"{rng.randint(8, 16)}:{rng.choice(['00', '15', '30', '45', '10', '40'])}",
                f"{rng.randint(8, 11)}.{rng.choice(['00', '15', '30', '45'])}am", f"{rng.randint(1, 4)}.{rng.choice(['00', '20', '30', '40'])}pm")


def _med_negative(rng: random.Random, d: Doc, trust: K, hospital: K, spec: str) -> None:
    topic = rng.choice(["outpatient", "visiting", "preop", "parking", "screening"])
    d.v("neg-" + topic)
    pools = {
        "outpatient": ["Bring a list of the medicines you take, including any you buy yourself.", "Please arrive 15 minutes before your appointment time.",
                       "If you need an interpreter, let the appointments team know at least 48 hours before.", "You may need a blood test on the day.",
                       "Clinics can run late. Please allow up to two hours.", "If you cannot attend, please tell us so we can offer the slot to someone else.",
                       "Wear loose clothing if you are seeing the physiotherapy team.", "Write down any questions you want to ask.",
                       "You can bring a friend or relative with you.", "The {spec} clinic is now based in {clinic}."],
        "visiting": ["Visiting times are 11am to 8pm every day.", "Two visitors per bed at any one time.", "Please do not visit if you have been unwell with diarrhoea or vomiting.",
                     "Children under 12 must be with an adult.", "Please clean your hands when you enter and leave the ward.",
                     "Flowers are not allowed on some wards.", "Mealtimes are protected. Please avoid visiting between 12 and 1pm.",
                     "You can phone the ward for an update. We can only share details with the patient's permission.",
                     "Please keep noise to a minimum, especially at night.", "Mobile phones may be used on most wards.",
                     "Open visiting may be arranged for carers.", "Hot food should not be brought onto the ward."],
        "preop": ["A pre-operative assessment checks that you are fit for your operation.", "The nurse will check your blood pressure, heart rate and weight.",
                  "You may need blood tests, swabs or a heart tracing (ECG).", "Bring all your medicines in their original boxes.",
                  "The appointment can take up to three hours.", "Tell us if you have had problems with an anaesthetic before.",
                  "You will be told when to stop eating and drinking before surgery.", "Arrange for an adult to take you home after day surgery.",
                  "You may be asked to stop some medicines before your operation.", "Remove nail varnish and jewellery before surgery.",
                  "Stopping smoking before an operation lowers the risk of problems.", "Tell us if you have a cold or infection close to your operation date."],
        "parking": ["Parking charges are {park} per hour.", "Blue Badge holders can park free in marked bays.", "The main car park at {hosp} fills up by 10am.",
                    "Concessions are available for frequent visitors.", "Bus routes stop outside the main entrance.", "Cycle racks are available near outpatients.",
                    "Drop-off bays are limited to 20 minutes."],
        "screening": ["Screening is offered to people with no symptoms.", "Screening can find problems early, when treatment works best.",
                      "It is your choice whether to take part.", "Screening does not find every problem.",
                      "If you have symptoms, do not wait for screening. See your GP.", "Results are usually sent within two weeks.",
                      "You will be invited again at regular intervals.", "You can opt out of screening at any time.",
                      "Some people need further tests after screening. Most of them are found to be fine.",
                      "Screening tests are free on the NHS.", "Ask your GP if you are not sure whether screening is right for you.",
                      "If you have moved, make sure your GP has your new address so invitations reach you."],
    }
    titles = {"outpatient": ["Preparing for your outpatient appointment", "Information for patients: your clinic visit", "Coming to hospital: a guide"],
              "visiting": ["Visiting our wards", "Information for visitors", "Visiting times and guidance"],
              "preop": ["Your pre-operative assessment", "Getting ready for your operation", "Pre-assessment: what to expect"],
              "parking": ["Car parking and travel", "Getting to hospital", "Travel and parking information"],
              "screening": ["NHS screening: making a choice", "About your screening invitation", "Screening explained"]}
    slots = dict(spec=spec, clinic=K(rng.choice(_CLINICS), "place_name"), hosp=K(hospital.text, "place_name"),
                 park=money_k(float(rng.choice([2.5, 3.0, 3.5, 4.0]))))
    d.ln(trust)
    d.ln(rng.choice(titles[topic]))
    d.blank()
    bullets = rng.random() < 0.6
    for sent in rng.sample(pools[topic], rng.randint(5, min(10, len(pools[topic])))):
        d.f(("- " if bullets else "") + sent + ("\n" if bullets or rng.random() < 0.5 else " "), **slots)
    d.blank()
    if rng.random() < 0.5:
        d.ln("From ", K(ids.format_date(recent_date(rng, 30, 90), rng.choice([1, 2, 0])), "date"), " some clinics are moving to ",
             K(rng.choice(_CLINICS), "place_name"), ".")
    d.ln(pick(rng, "For more information visit the trust website or nhs.uk.", "More information: nhs.uk", "Ask a member of staff if you have questions.",
              "This leaflet is available in other languages and formats."))


@register("medical_letter", weight=3, neg_weight=3)
def medical_letter(rng: random.Random, neg: bool) -> Doc:
    d = Doc("medical_letter", "medical_letter/v2")
    trust = K(rng.choice(world.HOSPITAL_TRUSTS), "public_company")
    hospital = K(rng.choice(_HOSPITALS), "place_name")
    spec = rng.choice(_SPECIALTIES)
    if neg:
        _med_negative(rng, d, trust, hospital, spec)
        return d
    c = Cast(rng, common_word_rate=0.06)
    pt = c.new(min_age=16, max_age=95)
    doc_ = c.new()
    gp = c.new()
    doc_.title = gp.title = "Dr"
    addr = world.make_address(rng)
    use_gp = rng.random() < 0.25
    ldate = recent_date(rng, 200)
    appt = ldate + timedelta(days=rng.randint(7, 70))
    dstyle = rng.choice([1, 0, 0, 2, 5])
    hosp_no = E(ids.from_pattern(rng, pick(rng, "@#######", "RR8######", "@@######", "#######@", "########")),
                "CUSTOM", pt.ref, ("custom_org_id",))
    if use_gp:
        variant = rng.choice(["gp_invite", "results", "screening"])
    else:
        variant = rng.choices(["appointment", "referral_ack", "cancelled", "results", "preop", "discharge", "screening", "clinic_letter"],
                              [20, 12, 12, 10, 12, 12, 8, 14])[0]
    d.v(variant + ("-gp" if use_gp else "-trust"))
    practice = K(rng.choice(_GP_PRACTICES), "org_name")
    when = K(WEEKDAYS[appt.weekday()] + " " + ids.format_date(appt, 1), "date") if rng.random() < 0.5 else letter_date(rng, appt, dstyle)
    slots = dict(
        name=pt.title_last(), doc=doc_.full(), docl=doc_.last_name(), gp=gp.full(), gpl=gp.last_name(), spec=spec,
        specl=spec if spec.isupper() else spec.lower(), hosp=K(hospital.text, "place_name"), clinic=K(rng.choice(_CLINICS), "place_name"),
        when=when, time=_appt_time(rng), old=letter_date(rng, appt - timedelta(days=rng.randint(5, 30)), dstyle),
        reason=rng.choice(_GENERIC_REASONS), weeks=str(rng.randint(4, 30)), practice=practice,
        test=pick(rng, "blood test", "scan", "X-ray", "ECG", "urine test"), screen=rng.choice(_SCREENING),
        ward=K(rng.choice(_WARDS), "place_name"), dpa=K("Data Protection Act 2018", "statute"),
        adm=letter_date(rng, ldate - timedelta(days=rng.randint(3, 12)), dstyle), dis=letter_date(rng, ldate - timedelta(days=rng.randint(0, 2)), dstyle),
        pron="her" if pt.female else "him", poss="her" if pt.female else "his", subj="she" if pt.female else "he",
        pron_cap="She" if pt.female else "He", poss_cap="Her" if pt.female else "His",
        mob=pt.mobile(), canc=pick(rng, "the clinician is unavailable", "of staff sickness", "the clinic has been rearranged",
                                   "of essential equipment maintenance", "the clinic has been moved to another day"),
    )
    # letterhead
    if use_gp:
        org = rng.choice(world.ORGS_BY_KIND["gp"])
        d.ln(org.name)
        if rng.random() < 0.8:
            d.ln(world.make_address(rng, flat_rate=0, building_rate=0.5).block(rng, None))
        d.ln(pick(rng, "Tel: ", "Telephone: ", "Reception: "), org_phone(rng))
        if rng.random() < 0.4:
            d.ln(pick(rng, "Practice manager: ", "Senior partner: Dr "), c.new().full())
        _, pid = org.custom(rng)
    else:
        org = None
        d.ln(trust)
        d.ln(pick(rng, f"{spec} Outpatients", f"Department of {spec}", f"{spec} Service", "Central Booking Office", "Patient Access Team",
                  f"{spec} Secretaries"))
        d.ln(hospital)
        if rng.random() < 0.6:
            d.ln(world.make_address(rng, flat_rate=0).block(rng, None))
        d.ln(pick(rng, "Appointments: ", "Booking office: ", "Tel: ", "Patient Access Centre: "), org_phone(rng))
        if rng.random() < 0.3:
            d.ln("Email: ", E(f"{rng.choice(['appointments', 'outpatients', 'booking', 'patientaccess'])}.{spec.lower().split()[0]}@nhs.net", "EMAIL"))
        pid = None
    d.blank()
    d.ln(pick(rng, "Date: ", "Date dictated: ", "Letter date: ", ""), letter_date(rng, ldate, dstyle))
    d.blank()
    if variant in ("clinic_letter", "discharge"):
        # letters to the GP about the patient
        d.ln(gp.title_full() if rng.random() < 0.5 else ["Dr ", gp.initial_last()])
        d.ln(practice)
        d.blank()
        title = "Discharge summary" if variant == "discharge" else pick(rng, "Clinic letter", "Outpatient clinic letter", "")
        if title:
            d.ln(title)
        d.ln(pick(rng, "Dear Dr ", "Dear Dr "), gp.last_name("greeting_name"), ",")
        d.blank()
        rows = [(["Patient", "Re", "Name"], pt.full() if rng.random() < 0.5 else pt.caps()),
                (["DOB", "Date of birth", "D.O.B."], pt.dob().with_hard("dob_near_dates")),
                (["NHS No", "NHS number"], pt.nhs())]
        if rng.random() < 0.75:
            rows.append((["Hosp No", "Hospital number", "MRN", "Unit number"], hosp_no))
        if rng.random() < 0.7:
            rows.append((["Address"], addr.inline(rng, pt.ref)))
        if variant == "discharge":
            rows += [(["Admitted", "Date of admission"], slots["adm"]), (["Discharged", "Date of discharge"], slots["dis"]),
                     (["Ward"], slots["ward"])]
        else:
            rows.append((["Clinic date", "Seen on"], letter_date(rng, ldate - timedelta(days=rng.randint(1, 10)), dstyle)))
        labelled(d, rng, rows, style=rng.choice([0, 1]))
        if variant == "discharge":
            para(d, rng, slots, ["{name} was admitted for {reason} and the stay was uncomplicated.",
                                 "Thank you for referring {name}, who was admitted to {ward} for a planned procedure.",
                                 "{name} was admitted to {ward} for a planned procedure."],
                 ["{pron_cap} recovered well and was discharged home.", "Observations remained stable throughout.",
                  "There were no complications and {subj} was discharged home as planned."])
        else:
            para(d, rng, slots, ["I saw {name} today in the {specl} clinic for {reason}.", "Thank you for referring {name}, whom I saw in clinic today.",
                                 "{name} attended the {specl} follow-up clinic today."],
                 ["Observations were stable and I have reassured {pron}.", "There were no new concerns today.",
                  "We discussed the plan and I have given {pron} written information.", "{poss_cap} symptoms have settled."])
        d.ln(pick(rng, "Plan:", "Actions:", "Follow-up:", "Recommendations:"))
        for it in rng.sample(["repeat blood tests in 3 months", "continue current medication", "review in clinic in 6 months",
                              "physiotherapy referral made", "discharge to GP care if stable", "GP to review medication in 4 weeks",
                              "no follow-up needed", "patient to contact the ward if any concerns", "results to be sent to the patient"], rng.randint(2, 4)):
            d.ln("- ", it)
        d.blank()
        d.ln(signoff(rng, doc_, True, None, pick(rng, f"Consultant in {spec}", "Specialty Registrar", "Consultant", f"{spec} Clinical Fellow")))
        if rng.random() < 0.5:
            d.ln(pick(rng, "Dictated but not checked", "Electronically signed", "Typed by: medical secretary"))
        d.ln("cc: ", pt.title_last() if rng.random() < 0.5 else "Patient")
        return d
    if rng.random() < 0.6:
        d.ln(pick(rng, "PRIVATE AND CONFIDENTIAL", "Private & Confidential", "To be opened by the addressee only"))
    d.add(recipient_block(rng, pt, addr))
    d.blank()
    rows = [(["NHS number", "NHS No", "NHS no."], pt.nhs()), (["Date of birth", "DOB", "Born"], pt.dob().with_hard("dob_near_dates"))]
    if pid is not None:
        rows.append((["Patient ID", "Practice ID", "Patient number"], pid))
    else:
        rows.append((["Hospital number", "Hospital no", "MRN", "Hosp No", "Unit no"], hosp_no))
    if rng.random() < 0.3:
        rows.append((["Referrer", "Referred by", "GP"], ["Dr ", gp.full()]))
    rng.shuffle(rows)
    labelled(d, rng, rows)
    d.ln(greeting(rng, pt))
    d.blank()
    if variant == "appointment":
        para(d, rng, slots, ["An appointment has been made for you to see Dr {doc} in the {spec} clinic for {reason}.",
                             "We have booked {reason} for you with Dr {docl}'s team in {spec}.",
                             "Your appointment with the {spec} service is shown below.",
                             "You have been given an appointment in the {specl} clinic."])
        for lab, v in [(pick(rng, "Date", "Day and date", "When"), slots["when"]), (pick(rng, "Time", "Appointment time"), slots["time"]),
                       (pick(rng, "Location", "Where", "Place"), [slots["clinic"], ", ", slots["hosp"]])]:
            d.ln(lab, ": ", v)
        d.blank()
        para(d, rng, slots, ["Please arrive 15 minutes early.", "Please report to the main outpatient reception.", "Please check in at the self check-in kiosk."],
             opt("We will send a text reminder to {mob} three days before.", "A reminder will be sent to {mob}."),
             opt("If you cannot attend, please call the number above.", "If this time is not convenient, please contact us to rearrange."))
    elif variant == "referral_ack":
        para(d, rng, slots, ["We have received a referral from your GP, Dr {gp}, to the {spec} service.",
                             "Your GP, Dr {gpl}, has referred you to {spec} at {hosp}.",
                             "Thank you for choosing {hosp} for your {specl} care. We have received your referral."],
             ["The current waiting time for a first appointment is about {weeks} weeks.", "Most patients are seen within {weeks} weeks.",
              "We expect to offer you an appointment within {weeks} weeks."])
        para(d, rng, slots, ["We will contact you to book a date and time.", "You will receive a letter or text with your appointment.",
                             "Please make sure we have your up-to-date phone number."],
             opt("If your symptoms change, contact your GP.", "You do not need to do anything now."))
    elif variant == "cancelled":
        para(d, rng, slots, ["We are sorry to tell you that your appointment on {old} has been cancelled because {canc}.",
                             "Unfortunately we have had to cancel your {specl} appointment on {old}, because {canc}.",
                             "Your appointment on {old} cannot go ahead. We apologise for this."],
             ["A new appointment has been made for {when} at {time}.", "We have rebooked you for {when} at {time}.",
              "Your new appointment is on {when} at {time} in {clinic}."])
        para(d, rng, slots, ["We are sorry for any inconvenience.", "We apologise for the disruption to your plans."],
             opt("If the new time does not suit you, please call us.", "Please let us know if you can no longer attend."))
    elif variant == "results":
        para(d, rng, slots, ["Your recent {test} results have been reviewed by Dr {docl}.", "Dr {docl} has looked at the results of your {test}.",
                             "We have now received the results of your {test}."],
             ["No further action is needed.", "Please book a routine appointment to discuss them.", "The results are within the normal range.",
              "Dr {docl} would like to see you in clinic to talk about them."])
        para(d, rng, slots, opt("You do not need to contact us unless you have questions.", "A copy has been sent to your GP.",
                                "You can also see your results in the NHS App."), p_opt=0.8)
    elif variant == "preop":
        para(d, rng, slots, ["Before your operation you need a pre-operative assessment.", "You have been booked for a pre-assessment appointment.",
                             "As part of your planned procedure, we need to check that you are ready for surgery."],
             ["This will take place on {when} at {time} in {clinic}.", "Please come to {clinic} on {when} at {time}."])
        para(d, rng, slots, ["A nurse will check your blood pressure and may take blood tests and swabs.", "The assessment can take up to three hours.",
                             "Please bring all your medicines in their original boxes."],
             opt("Tell us if you have had problems with an anaesthetic before.", "Bring a urine sample if you can."),
             opt("Your operation date will be confirmed after the assessment.", "You will be told when to stop eating and drinking."))
    elif variant == "screening":
        para(d, rng, slots, ["You are invited for {screen}.", "We are writing to invite you to take part in {screen}.",
                             "It is time for your {screen}."],
             ["Screening checks for early signs of problems, before you have symptoms.", "Screening is offered to everyone in your age group.",
              "This is a routine invitation and does not mean we think anything is wrong."])
        if rng.random() < 0.7:
            d.ln(pick(rng, "Your appointment: ", "Appointment: "), slots["when"], " at ", slots["time"], ", ", slots["clinic"])
            d.blank()
        para(d, rng, slots, ["It is your choice whether to take part.", "Please read the enclosed leaflet before you decide."],
             opt("If you have symptoms, see your GP rather than waiting.", "Results are usually sent within two weeks."))
    else:  # gp_invite
        para(d, rng, slots, [pick(rng, "You are due for a routine health check.", "You are due for your annual review.",
                                  "It is time for your flu vaccination.", "You are due for a review of your medication.",
                                  "You are due for a blood test.")],
             ["Please book an appointment with the practice nurse before {when}.", "Please contact the surgery to book before {when}.",
              "Appointments are available from now until {when}."])
        para(d, rng, slots, ["You can book online, through the NHS App or by calling the surgery.",
                             "Our reception team can book you in on the phone or at the front desk."],
             ["Please quote your NHS number when you book.", "You may need to fast before a blood test. We will tell you when you book."],
             opt("We may text you a reminder at {mob}.", "Evening and Saturday appointments are available."))
    extras(d, rng, slots, _MED_EXTRAS, 3, 6)
    if use_gp:
        d.ln(pick(rng, "Yours sincerely,", "Kind regards,", "With best wishes,"))
        d.ln("Dr ", doc_.full("signature_name") if rng.random() < 0.6 else doc_.initial_last("signature_name"))
        d.ln(org.name)
    else:
        d.ln(pick(rng, "Yours sincerely,", "Yours faithfully,", "Kind regards,"))
        d.ln(pick(rng, "Outpatient Appointments Team", "Booking Centre", f"{spec} Secretaries", "Appointments Office", "Patient Access Team",
                  f"{spec} Administration Team"))
        if rng.random() < 0.4:
            d.ln("cc: Dr ", gp.full(), ", ", practice)
    return d
