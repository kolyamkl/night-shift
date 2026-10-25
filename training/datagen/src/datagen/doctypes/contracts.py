"""Contracts: tenancy agreement, employment contract, NDA, service agreement, letter of engagement."""
from __future__ import annotations

import random
import re
from datetime import date, timedelta

from .. import ids, noise, world
from ..core import Doc, E, HC, HCEnd, HCStart, K
from ..names import Cast, Person
from . import register
from .common import TODAY, amount, date_text, greeting, kv_block, pick, recent_date, signoff


# --------------------------------------------------------------------------- local helpers
def _cl(*parts: int) -> K:
    return K(".".join(str(p) for p in parts), "clause_number")


def _heading(rng_style: int, n: int, title: str) -> list:
    if rng_style == 0:
        return [_cl(n), ". " + title.upper()]
    if rng_style == 1:
        return [_cl(n), " " + title]
    if rng_style == 2:
        return ["## ", _cl(n), ". " + title]
    return ["SECTION ", _cl(n), " - " + title.upper()]


def _dspaces(atoms: list, rng: random.Random, rate: float = 0.03) -> list:
    """Double spaces in plain text, with the changed atoms marked as a hard case region."""
    out = []
    for a in atoms:
        if isinstance(a, str) and " " in a and len(a) > 40:
            b = re.sub(r"(?<=\S) (?=\S)", lambda m: "  " if rng.random() < rate else " ", a)
            if b != a:
                out.extend([HCStart("pdf_double_space"), b, HCEnd()])
                continue
        out.append(a)
    return out


def _pdfify(d: Doc, rng: random.Random, header_fn, footer_fn, sidebar=None, every: int | None = None) -> None:
    d.v("pdf")
    d.atoms = noise.page_breaks(d.atoms, rng, header_fn, footer_fn, every or rng.randint(2300, 3400))
    if rng.random() < 0.7:
        d.atoms = noise.hyphenate(d.atoms, rng, rng.choice([0.03, 0.06, 0.1]))
    if rng.random() < 0.5:
        d.atoms = _dspaces(d.atoms, rng)
    if sidebar is not None and rng.random() < 0.4:
        d.atoms = noise.column_break(d.atoms, rng, sidebar)


def _street(addr, ref=None) -> E:
    """Workaround: world.Address.street_line() keeps a leading space when there is no house number."""
    return E(addr.street_line().strip(), "ADDRESS", ref, ("flat_number",) if addr.flat else ())


def _org_phone(rng: random.Random) -> E:
    return E(ids.landline_number(rng, rng.choice([0, 0, 1, 2])), "PHONE")


def _org_email(rng: random.Random, domain: str, box: str | None = None) -> E:
    return E(f"{box or pick(rng, 'info', 'hello', 'enquiries', 'lettings', 'office', 'accounts')}@{domain}", "EMAIL")


def _company_number(rng: random.Random) -> K:
    if rng.random() < 0.12:
        return K(f"SC{rng.randint(100000, 799999)}", "company_number")
    return K(f"{rng.randint(1000000, 15999999):08d}", "company_number")


def _vat(rng: random.Random) -> K:
    return K(ids.format_vat(ids.vat_number(rng), rng.randrange(3)), "vat_number")


def _sig_line(rng: random.Random) -> str:
    return pick(rng, "..............................", "______________________", "____________________________", "[signature]", "")


def _months_later(d: date, months: int) -> date:
    y, m = divmod(d.month - 1 + months, 12)
    y += d.year
    day = min(d.day, 28)
    return date(y, m + 1, day) - timedelta(days=1)


def _sections(rng: random.Random, d: Doc, library: list, ctx: dict, hstyle: int, min_k: float = 0.55,
              start_n: int = 1, numbered_sub: bool = True, both_prob: float = 0.0) -> int:
    """Render a clause library: list of (title, [clause variants lists]) with random subsets."""
    n = start_n
    for title, clauses in library:
        k = max(1, round(len(clauses) * rng.uniform(min_k, 1.0)))
        chosen = rng.sample(range(len(clauses)), k)
        if rng.random() < 0.6:
            chosen.sort()
        d.ln(*_heading(hstyle, n, title))
        for m, ci in enumerate(chosen, 1):
            variants = clauses[ci]
            if isinstance(variants, list) and len(variants) > 1 and rng.random() < both_prob:
                t = " ".join(rng.sample(variants, 2))
            else:
                t = rng.choice(variants) if isinstance(variants, list) else variants
            if numbered_sub:
                d.add(_cl(n, m), pick(rng, " ", "  ", "\t") if hstyle != 2 else " ")
            else:
                d.add("- " if hstyle == 2 else "")
            d.f(t, **ctx)
            d.add("\n\n")
        n += 1
    return n


# =========================================================================== tenancy
_T_LIB = [
    ("Rent", [
        ["{Tc} will pay the Rent of {rent} per calendar month in advance on the {day} day of each month by standing order to the account set out in {cl_bank}.",
         "The Rent is {rent} per month. It is payable in advance, the first payment being due on or before {start}, and thereafter on the {day} of each month.",
         "{Tc} agrees to pay the Rent monthly in advance without any deduction or set-off, whether or not formally demanded."],
        ["If any Rent is unpaid for 14 days after it falls due, {T} will pay interest at 3% above the Bank of England base rate from the date it was due until the date it is paid, as permitted by the {statute_fees}.",
         "Late rent: where rent remains outstanding for more than 14 days, interest may be charged at no more than 3% above base rate, in line with the {statute_fees}."],
        ["There is no {grace} period for the payment of Rent beyond the 14 days referred to in clause {cl_late}.",
         "{Lc} may, acting in good {faith}, allow a short {grace} period where {T} has notified {L} in advance of a delay."],
        ["{Tc} is responsible for paying council tax, water and sewerage charges, gas, electricity, telephone, broadband and the television licence for the Property during the Term.",
         "Utilities: {T} must register with the suppliers for gas, electricity and water from {start} and pay all charges until the end of the tenancy, including any standing charges."],
        ["{Lc} may increase the Rent once a year by giving at least two months' written notice in the prescribed form under section 13 of the {statute_ha}.",
         "The Rent will be reviewed annually. Any increase will be notified in writing and will not take effect earlier than twelve months after the start of the tenancy."],
    ]),
    ("Deposit", [
        ["{Tc} has paid a Deposit of {deposit}. {Lc} will protect the Deposit with {scheme} within 30 days of receipt and give {T} the prescribed information.",
         "A deposit of {deposit} is payable on signing. It will be registered with {scheme}, an authorised tenancy deposit scheme, within 30 days."],
        ["At the end of the tenancy {L} may deduct from the Deposit reasonable costs for damage beyond fair wear and tear, unpaid Rent and unpaid utility bills, and will return the balance within 10 days of agreement.",
         "Deductions from the Deposit must be itemised. Any dispute about deductions may be referred to the free dispute resolution service of {scheme}."],
        ["The Deposit does not exceed five weeks' rent and complies with the {statute_fees}.",
         "No holding deposit is held. Where a holding deposit of {holding} was paid it has been credited against the first month's Rent."],
    ]),
    ("Tenant's obligations", [
        ["To keep the interior of the Property, including the fixtures, fittings and items listed in the Inventory, in the same condition as at the start of the tenancy, fair wear and tear excepted.",
         "{Tc} must keep the inside of the Property clean and in good condition and must not damage it or the contents."],
        ["Not to assign, sublet, take in lodgers or part with possession of the whole or any part of the Property.",
         "{Tc} must not sublet the Property or allow anyone other than the persons named in this agreement to live there."],
        ["Not to keep any animal at the Property without {possL} prior written consent, which will not be unreasonably withheld.",
         "Pets: no pets are permitted other than {pet} which {L} has agreed to in writing."],
        ["Not to smoke or vape inside the Property and to ensure that visitors do not do so.",
         "Smoking is not permitted anywhere inside the Property, including the communal hallways."],
        ["Not to cause a nuisance or annoyance to neighbours, including excessive noise between 11pm and 7am.",
         "{Tc} must be considerate to neighbours and must not play music or hold gatherings that can be heard outside the Property late at night."],
        ["To keep the garden tidy and the lawns cut, and not to remove any trees or shrubs. The communal areas, including {place2}, are shared with other residents and must be kept clear.",
         "To keep any garden in a neat condition. Residents may use {place2} but must not leave bicycles or rubbish there."],
        ["To put refuse and recycling out for collection on the correct days and not to leave rubbish in the communal areas.",
         "Bins: {T} must use the bins provided and follow the council's collection schedule."],
        ["To report any disrepair or defect to {L} or the Agent promptly, and in any event within 7 days of becoming aware of it.",
         "{Tc} must tell the Agent as soon as possible about any repair that is needed, damp or mould, or any leak."],
        ["To ventilate the Property adequately and to take reasonable steps to prevent condensation.",
         "To heat and air the Property properly so that condensation does not build up, particularly in the bathroom and bedrooms."],
        ["Not to change the locks or have additional keys cut without consent, and to return all keys at the end of the tenancy.",
         "{Tc} has received {keys} sets of keys and will return the same number on leaving. Lost keys will be replaced at {possT} cost."],
        ["Not to redecorate, put up shelves or make alterations without the written consent of {L}.",
         "No alterations: {T} must not paint, drill or alter the Property without permission."],
        ["To insure their own possessions; {possL} insurance does not cover {possT} contents.",
         "{Tc} is advised to take out contents insurance. {Lc} is not liable for loss of {possT} belongings."],
    ]),
    ("Landlord's obligations", [
        ["To allow {T} quiet enjoyment of the Property without interruption by {L} or anyone acting on {possL} behalf, provided {T} complies with this agreement.",
         "{Lc} will not interfere with {possT} right to live in the Property peacefully."],
        ["To keep in repair the structure and exterior of the Property and the installations for the supply of water, gas, electricity, sanitation and heating, as required by section 11 of the {statute_lta}.",
         "Repairs: {L} is responsible for repairing the structure, exterior, drains, boiler, radiators, wiring and plumbing, in line with the {statute_lta}."],
        ["To ensure that all gas appliances are checked annually by a Gas Safe registered engineer and to give {T} a copy of the gas safety record.",
         "{Lc} will arrange an annual gas safety check and provide the certificate within 28 days, as required by the {statute_gas}."],
        ["To ensure that a smoke alarm is fitted on every storey and a carbon monoxide alarm in any room with a fixed combustion appliance.",
         "Smoke and carbon monoxide alarms have been tested on the first day of the tenancy and {T} will test them monthly."],
        ["To provide an electrical installation condition report dated no more than five years before the start of the tenancy.",
         "An EICR has been carried out and a copy has been given to {T} with the Energy Performance Certificate and the How to Rent guide."],
        ["{Lc} acknowledges that {place} may cause temporary noise or restricted access and will not hold {T} responsible for any resulting delay to inspections.",
         "{Tc} notes that {place} are scheduled during the Term; {L} will pass on any notices from the council."],
    ]),
    ("Access", [
        ["{Tc} will allow {L} or the Agent access to the Property at reasonable times on at least 24 hours' written notice to inspect its condition or carry out repairs.",
         "Access: on 24 hours' notice, except in an emergency, {L} may enter to inspect, repair or show the Property to prospective tenants in the last two months of the tenancy."],
        ["In an emergency {L} may enter the Property without notice.",
         "Where there is an emergency such as a flood or fire, access may be taken immediately."],
        ["Inspections will normally take place every {insp} months.",
         "The Agent will carry out a routine visit around every {insp} months and send a short report to {L}."],
    ]),
    ("Ending the tenancy", [
        ["{Lc} may seek possession on the grounds in {sched} of the {statute_ha} by serving the required notice.",
         "If {T} breaks the terms of this agreement, {L} may apply to the court for possession under the {statute_ha}."],
        ["After the end of the fixed term the tenancy will continue as a periodic tenancy from month to month on the same terms.",
         "If neither party ends the tenancy at the end of the Term it will become a statutory periodic tenancy."],
        ["{Tc} may end the tenancy after the fixed term by giving at least one month's written notice ending on the last day of a rental period.",
         "Break clause: either party may end this agreement on or after the {brk} month of the Term by giving two months' notice in writing."],
        ["At the end of the tenancy {T} must leave the Property clean, remove all belongings and return the keys to the Agent.",
         "On leaving, {T} will arrange a professional clean if the Property was professionally cleaned at the start, as recorded in the check-in report."],
    ]),
    ("Notices", [
        ["For the purposes of sections 47 and 48 of the Landlord and Tenant Act 1987, notices may be served on {L} at: {service_addr}.",
         "{possLc} address for service of notices in England and Wales is {service_addr}."],
        ["Notices to {T} may be served by leaving them at the Property or by email to the address given in Schedule 1.",
         "Any notice may be served by email, provided a copy is also sent by first class post."],
    ]),
    ("Data protection", [
        ["{Lc} and the Agent will process {possT} personal data in accordance with the {statute_dp} and may share it with the deposit scheme, utility suppliers and the local authority.",
         "Personal data will be handled under the {statute_dp}. The Agent's privacy notice is available on request."],
    ]),
    ("General", [
        ["Where there is more than one tenant, their obligations are joint and several.",
         "If two or more people are the Tenant, each is responsible for all the obligations, not just a share."],
        ["This agreement is governed by the law of England and Wales.",
         "The courts of England and Wales have jurisdiction over any dispute."],
        ["Nothing in this agreement is intended to give any third party rights under the {statute_3p}.",
         "No one other than the parties may enforce this agreement."],
        ["{Lc} and {T} agree to act in good {faith} when dealing with any dispute.",
         "The parties will try to resolve any disagreement informally before taking any further step."],
    ]),
]


_T_EXTRA = [
    ("Use of the Property", [
        ["To use the Property as a private residence for the occupation of {T} only and not for any business, trade or profession.",
         "{Tc} must live at the Property as their only or main home and must not run a business from it."],
        ["Not to allow more than {guests} overnight guests to stay for more than 14 nights in any six-month period without consent.",
         "Visitors may stay occasionally, but no other person may move in without the written agreement of {L}."],
        ["Not to keep any petrol, gas cylinders or other hazardous substances at the Property, other than ordinary household products.",
         "Barbecues, chimeneas and patio heaters must not be used on balconies or in communal areas."],
        ["Parking is permitted only in the space allocated to the Property. Residents must not park in {place3} overnight.",
         "{Tc} has no right to park at the Property. Permits for on-street parking are the responsibility of {T}."],
    ]),
    ("Inventory and check-in", [
        ["An inventory and schedule of condition has been prepared and {T} must return a signed copy within 7 days of the start of the tenancy, noting any discrepancies.",
         "The check-in report, including dated photographs, forms part of this agreement. If {T} does not comment on it within seven days it will be treated as accurate."],
        ["At the end of the tenancy a check-out inspection will be carried out against the inventory, and {T} is invited to attend.",
         "{Tc} may attend the check-out appointment. Differences from the check-in report, allowing for fair wear and tear, may be deducted from the Deposit."],
    ]),
    ("Insurance", [
        ["{Lc} will insure the building against the usual risks. {Tc} must not do anything that would make the insurance void or increase the premium.",
         "The buildings insurance is arranged by {L}. {Tc} must report any damage that could lead to an insurance claim as soon as possible."],
        ["If the Property is made uninhabitable by an insured risk, the Rent will stop being payable until it is fit to live in again, unless the damage was caused by {T}.",
         "Rent suspension applies where the Property cannot be lived in because of fire or flood, except where {T} is at fault."],
    ]),
    ("Furniture and appliances", [
        ["Not to remove any furniture or effects belonging to {L} from the Property or store them outside.",
         "The furniture listed in the inventory must remain at the Property throughout the tenancy."],
        ["{Lc} will repair or replace appliances supplied with the Property, such as the washing machine, fridge freezer and oven, unless the fault is caused by misuse.",
         "Repairs to appliances provided by {L} will be arranged by the Agent within a reasonable time after they are reported."],
    ]),
    ("Keys and security", [
        ["To keep the Property secure, locking all doors and windows when it is empty, and to set the alarm if one is fitted.",
         "{Tc} must keep the Property locked when unoccupied and must not give keys to anyone not named in this agreement."],
        ["To tell {L} if the Property will be empty for more than 14 consecutive days, and in winter to keep the heating on at a low setting to prevent frozen pipes.",
         "If {T} goes away for more than two weeks they must let the Agent know and take reasonable steps to protect the Property from frost."],
    ]),
    ("Moving out", [
        ["Before leaving, {T} must give the Agent a forwarding address and take final meter readings.",
         "{Tc} must provide a forwarding address in writing so that the Deposit can be returned and any post redirected."],
        ["Any items left at the Property after the end of the tenancy may be disposed of after 14 days' written notice to {T}.",
         "Belongings left behind will be stored for 14 days and then disposed of, and the reasonable cost may be deducted from the Deposit."],
    ]),
]

_INVENTORY = [("Entrance hall", ["Carpet", "Coat hooks", "Smoke alarm", "Front door and locks", "Ceiling light"]),
              ("Living room", ["Three-seater sofa", "Coffee table", "Curtains and rail", "Radiator", "TV unit", "Laminate flooring"]),
              ("Kitchen", ["Oven and hob", "Fridge freezer", "Washing machine", "Extractor hood", "Worktops", "Sink and taps", "Kettle"]),
              ("Bedroom 1", ["Double bed and mattress", "Wardrobe", "Chest of drawers", "Blinds", "Carpet"]),
              ("Bedroom 2", ["Single bed", "Desk and chair", "Built-in wardrobe", "Window restrictor"]),
              ("Bathroom", ["Bath with shower over", "WC", "Wash basin", "Extractor fan", "Mirror cabinet", "Tiling"]),
              ("Garden", ["Lawn", "Shed", "Fence panels", "Patio slabs", "Rotary washing line"])]
_COND = ["Good", "Good, minor scuffs", "Fair", "Clean", "New", "Fair, worn in places", "Good, light marks", "Excellent", "Working"]

_PETS = ["one small dog", "one cat", "a pair of guinea pigs", "one indoor cat", "a small caged bird"]


def _tenancy_kind(rng: random.Random) -> tuple[str, str, str, str]:
    """(variant, title, role word, statute)"""
    r = rng.random()
    if r < 0.55:
        return ("ast_england", pick(rng, "ASSURED SHORTHOLD TENANCY AGREEMENT", "Assured Shorthold Tenancy Agreement",
                                    "TENANCY AGREEMENT (Assured Shorthold Tenancy)"), "Tenant", "Housing Act 1988")
    if r < 0.72:
        return ("periodic", pick(rng, "ASSURED PERIODIC TENANCY AGREEMENT", "Assured Periodic Tenancy Agreement",
                                 "Periodic Tenancy Agreement (Assured Tenancy)"), "Tenant", "Housing Act 1988")
    if r < 0.86:
        return ("wales_occupation", pick(rng, "STANDARD OCCUPATION CONTRACT", "Periodic Standard Occupation Contract",
                                         "Fixed Term Standard Occupation Contract"), "Contract-Holder", "Renting Homes (Wales) Act 2016")
    return ("scotland_prt", pick(rng, "PRIVATE RESIDENTIAL TENANCY AGREEMENT", "Scottish Government Model Private Residential Tenancy Agreement"),
            "Tenant", "Private Housing (Tenancies) (Scotland) Act 2016")


def _tenancy_ctx(rng, role, statute_main, ll_word, start, rent, deposit, scheme, service_addr):
    T = f"the {role}"
    L = f"the {ll_word}"
    return dict(
        T=T, Tc=T[0].upper() + T[1:], L=L, Lc=L[0].upper() + L[1:],
        possT=f"the {role}'s", possL=f"the {ll_word}'s", possLc=f"The {ll_word}'s",
        rent=rent, deposit=deposit, scheme=scheme, start=start,
        day=pick(rng, "1st", "1st", "15th", "28th", "5th", "first"),
        holding=amount(rng, 100, 450, step=10),
        statute_ha=K(statute_main, "statute"), statute_fees=K(pick(rng, "Tenant Fees Act 2019", "Tenant Fees Act 2019", "Renters' Rights Act 2025"), "statute"),
        statute_lta=K("Landlord and Tenant Act 1985", "statute"),
        statute_gas=K("Gas Safety (Installation and Use) Regulations 1998", "statute"),
        statute_dp=K(pick(rng, "Data Protection Act 2018", "UK GDPR"), "statute"),
        statute_3p=K("Contracts (Rights of Third Parties) Act 1999", "statute"),
        cl_bank=_cl(rng.randint(1, 3), rng.randint(1, 9)) if rng.random() < 0.5 else K("Schedule 2", "clause_number"),
        cl_late=_cl(2, 2), grace=K("grace", "common_word"), faith=K("faith", "common_word"),
        place=K(pick(rng, "the Oak Road works", "the Station Road resurfacing works", "the Mill Lane roadworks",
                     "the High Street gas main works", "the Victoria Park drainage works"), "place_name"),
        place2=K(pick(rng, "the Rose Garden", "the communal Rose Garden", "the courtyard known as Grace Court",
                      "the Elm Grove allotments", "the residents' garden"), "place_name"),
        pet=rng.choice(_PETS), keys=str(rng.randint(1, 3)), insp=str(rng.choice([3, 4, 6])),
        brk=pick(rng, "sixth", "fourth", "eighth"), service_addr=service_addr,
        guests=str(rng.choice([1, 2, 2, 3])), place3=K(pick(rng, "the Station Road car park", "the visitor bays", "Market Street car park", "the Rose Garden turning circle"), "place_name"),
        sched="Schedule 3" if "Scotland" in statute_main else ("Schedule 2" if "Wales" not in statute_main else "the possession provisions"),
    )


@register("tenancy_agreement", weight=4, neg_weight=4)
def tenancy_agreement(rng: random.Random, neg: bool) -> Doc:
    variant, title, role, statute_main = _tenancy_kind(rng)
    d = Doc("tenancy_agreement", f"tenancy_agreement/{variant}")
    d.v(variant)
    ll_word = "Landlord"
    hstyle = rng.randrange(4)
    start = recent_date(rng, 700, 60)
    term = rng.choice([6, 12, 12, 12, 18, 24])
    rent_v = round(rng.uniform(475, 3200) / 5) * 5
    rent = amount(rng, rent_v, rent_v, style=rng.choice([0, 1]))
    deposit = K(world.money_text(round(rent_v * 12 / 52 * 5, 2), 0), "amount")
    scheme = K(pick(rng, "the Deposit Protection Service", "the Tenancy Deposit Scheme", "mydeposits",
                    "SafeDeposits Scotland", "Letting Protection Service Scotland")
               if variant == "scotland_prt" else rng.choice(world.PUBLIC["deposit"]), "public_company")
    if neg:
        return _tenancy_negative(rng, d, title, role, statute_main, ll_word, hstyle, rent, deposit, scheme, start)

    c = Cast(rng, common_word_rate=0.1)
    tenants = [c.new() for _ in range(rng.choices([1, 2, 3], [55, 35, 10])[0])]
    agent = rng.choice(world.ORGS_BY_KIND["letting"]) if rng.random() < 0.75 else None
    prop = world.make_address(rng, flat_rate=0.45)
    tref = tenants[0].ref

    # landlord: individual, company or sole trader
    lr = rng.random()
    landlord_p: Person | None = None
    if lr < 0.55:
        landlord_p = c.new(min_age=30)
        ll_name: list = [landlord_p.full()]
        d.v("ll_person")
    elif lr < 0.8:
        donor = Person(rng, ref="surname_donor").last if rng.random() < 0.4 else None  # never emitted as PERSON
        ll_name = [world.company_name(rng, with_person_surname=donor)]
        d.v("ll_company")
    else:
        landlord_p = c.new(min_age=30)
        ll_name = world.sole_trader(rng, landlord_p)
        d.v("ll_sole_trader")
    ll_addr = world.make_address(rng, flat_rate=0.1)
    agent_addr = world.make_address(rng, flat_rate=0.0, building_rate=0.3) if agent else None

    # address for service (maybe c/o agent)
    if agent and rng.random() < 0.6:
        service_addr = HC("care_of_address", "c/o ", agent.name, ", ", agent_addr.inline(rng))
    elif landlord_p and rng.random() < 0.3:
        cop = c.new()
        service_addr = HC("care_of_address", "c/o ", cop.full(), ", ", ll_addr.inline(rng, cop.ref))
    else:
        service_addr = ll_addr.inline(rng, landlord_p.ref if landlord_p else None)
    start_k = date_text(rng, start, rng.choice([1, 2, 0]))
    ctx = _tenancy_ctx(rng, role, statute_main, ll_word, start_k, rent, deposit, scheme, service_addr)

    # ---------------- title block
    d.ln(title)
    if rng.random() < 0.6:
        d.ln(pick(rng, "Dated: ", "Date of agreement: ", "This agreement is made on "),
             date_text(rng, start - timedelta(days=rng.randint(3, 30))))
    lab = cid = None
    if agent:
        lab, cid = agent.custom(rng, next((k for k in agent.ids if "enan" in k or "Tenancy" in k), None))
        d.ln(lab, ": ", cid, pick(rng, "", "   ", "  |  "), pick(rng, "", "Prepared by " + agent.name))
    d.blank()
    if variant == "ast_england":
        d.f("This agreement is intended to create an assured shorthold tenancy as defined in section 19A of the {s} "
            "and the provisions for the recovery of possession by the Landlord in section 21 of that Act may apply"
            "{x}.\n\n", s=K(statute_main, "statute"),
            x=pick(rng, "", " (subject to any changes made by the Renters' Rights Act 2025)"))
    elif variant == "periodic":
        d.f("This is an assured periodic tenancy under the {s} as amended by the {r}. It runs from month to month and there is no fixed term.\n\n",
            s=K(statute_main, "statute"), r=K("Renters' Rights Act 2025", "statute"))
    elif variant == "wales_occupation":
        d.f("This is a standard occupation contract under the {s}. In this contract the tenant is called the "
            "contract-holder.\n\n", s=K(statute_main, "statute"))
    else:
        d.f("This tenancy is a private residential tenancy under the {s}.\n\n", s=K(statute_main, "statute"))

    # ---------------- particulars (plain or table)
    table = rng.random() < 0.35
    d.ln(pick(rng, "PARTICULARS", "1. Particulars", "The parties", "KEY TERMS"))
    d.blank()
    if table:
        d.v("table")
        rows: list = []
        rows.append(("Landlord", ll_name))
        for i, t in enumerate(tenants, 1):
            rows.append((f"{role} {i}" if len(tenants) > 1 else role, t.full()))
        rows.append(("Property", HC("address_in_table", prop.inline(rng, tref))))
        rows.append(("Start date", start_k))
        if variant not in ("periodic", "scotland_prt"):
            rows.append(("Term", f"{term} months"))
        rows.append(("Rent", [rent, " per month"]))
        rows.append(("Deposit", deposit))
        rows.append(("Deposit scheme", scheme))
        if agent:
            rows.append(("Agent", agent.name))
        d.add(kv_block(rng, rows, style=1))
        d.blank()
    else:
        d.f("{L}: ", L=ll_word)
        d.add(ll_name)
        if rng.random() < 0.6:
            d.add(pick(rng, " of ", ", whose address is ", "\n"), ll_addr.inline(rng, landlord_p.ref if landlord_p else None))
        d.add("\n\n")
        for i, t in enumerate(tenants, 1):
            d.add(f"{role}{' ' + str(i) if len(tenants) > 1 else ''}: ", t.full_middle() if rng.random() < 0.3 else t.full())
            if rng.random() < 0.3:
                d.add(" (date of birth ", t.dob(), ")")
            d.add("\n")
        d.add("\n", pick(rng, "The Property:\n", "Property address:\n", "The premises known as\n"))
        d.add(prop.block(rng, tref), "\n")
        if prop.flat:
            d.ln("together with the use in common with others of the entrance hall, stairs and communal areas.")
        d.blank()
        if variant in ("periodic", "scotland_prt"):
            d.add("Start date: ", start_k, "\n")
        else:
            d.f("Term: {n} months from and including {s} to and including {e}\n", n=str(term), s=start_k,
                e=date_text(rng, _months_later(start, term)))
        d.add("Rent: ", rent, pick(rng, " per calendar month", " pcm", " per month"), "\n")
        d.add("Deposit: ", deposit, " protected with ", scheme, "\n")
        if agent:
            d.add("Agent: ", agent.name, " of ", agent_addr.inline(rng), "\n")
        d.blank()

    # guarantor
    if rng.random() < 0.25:
        g = c.new(min_age=40)
        d.v("guarantor")
        d.ln(pick(rng, "Guarantor: ", "GUARANTOR: "), g.full(), pick(rng, " of ", ", "), world.make_address(rng).inline(rng, g.ref),
             pick(rng, " (date of birth ", " DOB: "), g.dob(), pick(rng, ")", ""))
        d.f("The Guarantor guarantees the payment of the Rent and the performance of {T}'s obligations and agrees to pay on demand "
            "any sum that {T} fails to pay.\n\n", T=f"the {role}")

    # bank details for rent
    if rng.random() < 0.6:
        payee = landlord_p if landlord_p and rng.random() < 0.6 else None
        bp = payee or Person(rng, ref="acct_holder")
        d.ln(pick(rng, "Rent payment details", "Bank details for rent", "Payment of Rent"))
        rows = [("Account name", payee.full() if payee else (agent.name + " Client Account" if agent else ll_name)),
                ("Sort code", bp.sort_code()), ("Account number", bp.account())]
        if rng.random() < 0.3:
            rows.append(("IBAN", bp.iban()))
        rows.append(("Reference", cid if cid is not None and rng.random() < 0.7 else
                     (tenants[0].last_name() if rng.random() < 0.5 else _street(prop, tref))))
        d.add(kv_block(rng, rows, style=rng.choice([0, 2])))
        d.blank()

    # ---------------- definitions (another mention of every party)
    long_mode = rng.random() < 0.35
    if long_mode:
        d.v("long")
    if rng.random() < (0.85 if long_mode else 0.4):
        d.ln(pick(rng, "DEFINITIONS", "1A. Definitions and interpretation", "Interpretation"))
        d.blank()
        defs = [["\"", ll_word, "\" means ", ll_name, " and includes any person who later becomes entitled to the reversion of the Property."],
                ["\"", role, "\" means "] + sum(([t.full() if rng.random() < 0.7 else t.full_middle(), " and "] for t in tenants), [])[:-1]
                + [". Where there is more than one, the obligations are joint and several."],
                ["\"Property\" means ", prop.inline(rng, tref), " and includes the Fixtures and Fittings."],
                ["\"Rent\" means ", rent, " per month or such other sum as may be agreed or determined."],
                ["\"Deposit\" means the sum of ", deposit, " held under clause ", _cl(3, 1), "."],
                ["\"Fixtures and Fittings\" means the items listed in the Inventory."],
                ["\"Communal Areas\" means the entrance, stairs, bin store and ", ctx["place2"], "."],
                ["\"Utilities\" means gas, electricity, water, sewerage, telecommunications and broadband."]]
        if agent:
            defs.append(["\"Agent\" means ", agent.name, " or any other agent appointed by the ", ll_word, "."])
        if rng.random() < 0.5:
            rng.shuffle(defs)
        lettered = rng.random() < 0.5
        for i, df in enumerate(defs, 1):
            d.add(f"({chr(96 + i)}) " if lettered else "", df, "\n")
        d.blank()

    # ---------------- clauses
    d.ln(pick(rng, "TERMS AND CONDITIONS", "THE AGREEMENT", "Terms of the tenancy", "IT IS AGREED AS FOLLOWS:"))
    d.blank()
    lib = list(_T_LIB)
    head, mid, tail = lib[:2], lib[2:6], lib[6:]
    extra = rng.sample(_T_EXTRA, rng.randint(1, len(_T_EXTRA)))
    mid = mid + extra
    if rng.random() < 0.5:
        rng.shuffle(mid)
    _sections(rng, d, head + mid + tail, ctx, hstyle, min_k=1.0 if long_mode else rng.uniform(0.55, 0.95), start_n=2,
              both_prob=0.65 if long_mode else 0.1)

    # ---------------- prescribed information about the deposit (repeats the parties)
    if variant != "scotland_prt" and rng.random() < 0.45:
        d.v("prescribed_info")
        d.ln(pick(rng, "DEPOSIT PRESCRIBED INFORMATION", "Prescribed information (Housing Act 2004)", "Deposit protection: prescribed information"))
        d.blank()
        rows = [("Scheme", scheme), ("Deposit amount", deposit), ("Property", prop.inline(rng, tref)),
                ("Landlord", landlord_p.title_full() if landlord_p else ll_name)]
        for t in tenants:
            rows.append(("Tenant", [t.title_last() if rng.random() < 0.5 else t.full()]))
        rows.append(("Tenant contact after the tenancy ends", tenants[0].email()))
        if agent:
            rows.append(("Agent", [agent.name, ", ", _org_phone(rng)]))
        d.add(kv_block(rng, rows, style=rng.choice([0, 2])))
        d.f("\nThe deposit will be repaid in accordance with the rules of {s}. Deductions may be made for unpaid rent, damage "
            "and cleaning. {T} confirms that {L} has given the information above within 30 days of receiving the deposit.\n\n",
            s=scheme, T=ctx["Tc"], L=ctx["L"])

    # ---------------- inventory schedule (no personal data)
    if rng.random() < 0.5:
        d.v("inventory")
        d.ln(pick(rng, "SCHEDULE 2 - INVENTORY (SUMMARY)", "Inventory summary", "Schedule of condition"))
        d.blank()
        d.add("| Room | Item | Condition |\n|---|---|---|\n")
        for room, items in rng.sample(_INVENTORY, rng.randint(3, len(_INVENTORY))):
            for it in rng.sample(items, rng.randint(2, len(items))):
                d.add(f"| {room} | {it} | {rng.choice(_COND)} |\n")
        d.blank()

    # ---------------- schedule 1: tenant details (same person 3 ways)
    if rng.random() < 0.7:
        d.ln(pick(rng, "SCHEDULE 1 - TENANT DETAILS", "Schedule 1: Contact details", "SCHEDULE 1"))
        d.blank()
        for t in tenants:
            rows = [("Name", t.last_comma_first()), ("Mobile", t.mobile()), ("Email", t.email())]
            if rng.random() < 0.5:
                rows.append(("Date of birth", t.dob()))
            if rng.random() < 0.35:
                rows.append(("Previous address", world.make_address(rng).inline(rng, t.ref)))
            if rng.random() < 0.25:
                rows.append(("Emergency contact", [c.new().full(), " ", c.people[-1].mobile()]))
            d.add(kv_block(rng, rows, style=rng.choice([0, 1, 2])))
            d.blank()
    if rng.random() < 0.5:
        t = tenants[0]
        d.f(pick(rng, "Note: {n} has asked that all correspondence be sent by email.\n\n",
                 "Inventory signed by {n} at check-in.\n\n",
                 "{n} confirmed receipt of the How to Rent guide, the EPC and the gas safety record.\n\n"),
            n=pick(rng, t.title_last(), [t.first_name()], [t.initial_last()]))

    if long_mode and rng.random() < 0.6:
        d.ln(pick(rng, "NOTES FOR TENANTS", "Guidance notes (not part of the agreement)", "Important information"))
        notes = ["Read this agreement carefully before signing. If you do not understand it, take independent advice, for example from {ca} or a solicitor.",
                 "Keep a copy of this agreement, the inventory and the deposit certificate in a safe place.",
                 "Report repairs in writing and keep a note of the date. Urgent repairs, such as no heating or hot water, should be reported by phone as well.",
                 "If the landlord wants you to leave, they must follow the legal process and obtain a court order. It is a criminal offence to evict a tenant without one under the {pfe}.",
                 "Council tax is payable by the tenant. Students may be exempt and should contact {council}.",
                 "Free advice on deposits is available from {scheme}.", "You can check whether a property has a valid gas safety record and EPC before you move in."]
        for nt in rng.sample(notes, rng.randint(3, len(notes))):
            d.add("- ")
            d.f(nt, ca=K("Citizens Advice", "public_company"), pfe=K("Protection from Eviction Act 1977", "statute"),
                council=K(rng.choice(world.COUNCILS), "public_company"), scheme=scheme)
            d.add("\n")
        d.blank()

    # ---------------- signatures
    d.ln(pick(rng, "SIGNATURES", "Signed as an agreement", "EXECUTION"))
    d.blank()
    sig_date = date_text(rng, start - timedelta(days=rng.randint(1, 20)))
    d.add("Signed by the ", ll_word, " ", _sig_line(rng), "\n", "Name: ")
    d.add(landlord_p.full() if landlord_p else [c.new().full(), " (Director, for and on behalf of the Landlord)"])
    d.add("\nDate: ", sig_date if rng.random() < 0.7 else "________", "\n\n")
    for t in tenants:
        d.add("Signed by the ", role, " ", _sig_line(rng), "\n", "Name: ",
              pick(rng, t.full(), t.caps(), t.full()), "\n")
        d.add("Date: ", sig_date if rng.random() < 0.7 else "________", "\n\n")
    if rng.random() < 0.3:
        w = c.new()
        d.add("Witnessed by: ", w.full(), ", ", world.make_address(rng).inline(rng, w.ref), "\n")

    # ---------------- PDF artefacts
    if rng.random() < 0.4:
        t0 = tenants[0]

        def header(page, total):
            r = rng.random()
            if r < 0.35:
                return [title.title()[:40], " - ", _street(prop, tref)]
            if r < 0.65:
                return ["Tenancy agreement: ", t0.full("name_in_page_header")]
            return [agent.name if agent else "Tenancy Agreement", "  ", cid if cid is not None else ""]

        def footer(page, total):
            if rng.random() < 0.4:
                return [f"Page {page} of {total}    Tenant initials: ", t0.initials()]
            return [f"Page {page} of {total}"]

        sidebar = None
        if agent:
            sidebar = [agent.name, "\n", agent_addr.block(rng), "\n", "Tel ", _org_phone(rng), "\n", _org_email(rng, agent.domain)]
        _pdfify(d, rng, header, footer, sidebar)
    return d


def _tenancy_negative(rng, d, title, role, statute_main, ll_word, hstyle, rent, deposit, scheme, start):
    d.template_id += "_template"
    d.v("blank_template")
    ph = lambda s: K(s, "placeholder")  # noqa: E731
    d.ln(title)
    d.ln(pick(rng, "(Template - complete all fields in square brackets)", "MODEL AGREEMENT - FOR GUIDANCE ONLY",
              "Draft for discussion"))
    d.blank()
    d.add("Landlord: ", ph("[Landlord name]"), " of ", ph("[Landlord address]"), "\n")
    d.add(role, ": ", ph(pick(rng, "[Tenant name]", "[Full name of tenant]", "[NAME]")), "\n")
    d.add("Property: ", ph(pick(rng, "[Property address]", "[Address of the Property]", "[ADDRESS]")), "\n")
    d.add("Start date: ", ph("[dd/mm/yyyy]"), "\n")
    d.add("Rent: ", ph("£[amount]") if rng.random() < 0.5 else rent, " per month\n")
    d.add("Deposit: ", ph("£[amount]") if rng.random() < 0.5 else deposit, " (", scheme, ")\n\n")
    ctx = _tenancy_ctx(rng, role, statute_main, ll_word, ph("[start date]"), ph("£[rent]"), ph("£[deposit]"), scheme,
                       ph("[address for service]"))
    _sections(rng, d, _T_LIB, ctx, hstyle, min_k=rng.uniform(0.4, 0.7), start_n=2)
    d.add("Signed by the Landlord ", _sig_line(rng), "  Date ", ph("[date]"), "\n")
    d.add("Signed by the ", role, " ", _sig_line(rng), "  Date ", ph("[date]"), "\n")
    if rng.random() < 0.3:
        d.f("\nGuidance: from {d} landlords should check the latest rules on rent increases and possession under the {s}.\n",
            d=date_text(rng, date(2026, 5, 1)), s=K("Renters' Rights Act 2025", "statute"))
    return d


# =========================================================================== employment contract
_JOBS = ["Warehouse Operative", "Customer Service Adviser", "Software Engineer", "Senior Care Assistant",
         "Teaching Assistant", "Accounts Assistant", "Project Manager", "HGV Driver", "Marketing Executive",
         "Data Analyst", "Site Supervisor", "Receptionist", "Payroll Administrator", "Chef de Partie",
         "Office Manager", "Mechanical Engineer", "Sales Executive", "HR Adviser", "Graphic Designer", "Nurse"]

_E_LIB = [
    ("Commencement and probation", [
        ["Your employment will begin on {start}. No previous employment counts as part of your period of continuous employment.",
         "Your employment starts on {start}, and your period of continuous employment begins on that date."],
        ["The first {prob} months of your employment are a probationary period, during which either party may end the employment by giving one week's notice.",
         "You will be on probation for {prob} months. We may extend this period if we need more time to assess your performance."],
    ]),
    ("Job title and duties", [
        ["You are employed as {job}. You will report to the {mgr_role} and carry out any reasonable duties we ask of you.",
         "Your job title is {job}. A job description has been given to you but it does not form part of this contract."],
        ["Your normal place of work is {work_addr}. You may be required to work at other sites within a reasonable distance.",
         "You will work from our premises at {work_addr}, with hybrid working of up to {wfh} days a week subject to business needs."],
    ]),
    ("Hours of work", [
        ["Your normal hours are {hours} hours per week, Monday to Friday, between 9am and 5.30pm with an unpaid lunch break of 30 minutes.",
         "You will work {hours} hours a week on a rota. Shift patterns are published at least two weeks in advance."],
        ["You agree to opt out of the 48-hour average weekly limit under the {statute_wt}. You may withdraw this agreement by giving three months' written notice.",
         "Your working time will comply with the {statute_wt}. Overtime is paid at time and a half when authorised in advance."],
    ]),
    ("Pay", [
        ["Your salary is {salary} per year, paid monthly in arrears on or around the {payday} of each month by credit transfer.",
         "You will be paid {hourly} per hour, weekly in arrears every Friday, which is at least the rate required under the {statute_nmw}."],
        ["We may deduct from your pay any sums you owe us, including overpaid salary and the cost of unreturned equipment.",
         "Deductions will only be made where required by law or where you have agreed to them in writing."],
        ["Your salary will be reviewed each April. There is no obligation to increase it.",
         "Pay reviews take place annually and any increase is at the discretion of the Company."],
    ]),
    ("Holidays", [
        ["You are entitled to {hol} days' paid holiday each holiday year, plus the usual bank holidays in England and Wales. The holiday year runs from 1 January to 31 December.",
         "Your holiday entitlement is {hol} days per year including bank holidays, pro rata for part-time staff."],
        ["You may carry forward up to five days of unused holiday into the next holiday year with your manager's approval.",
         "Holiday not taken by the end of the year will be lost unless the law requires it to be carried forward."],
    ]),
    ("Sickness absence", [
        ["If you are absent through illness you must tell your manager by 9am on the first day. For absences of more than seven days you must provide a fit note.",
         "Statutory Sick Pay is payable in line with current rules. Company sick pay of {sickw} weeks at full pay applies after probation."],
    ]),
    ("Pension", [
        ["We will automatically enrol you in our workplace pension scheme with {pension} if you are eligible. We will contribute {pct}% of your qualifying earnings.",
         "You will be enrolled into the {pension} pension scheme. You may opt out within one month of enrolment."],
    ]),
    ("Notice", [
        ["After probation you must give us {notice_emp} written notice to end your employment. We will give you one week's notice for each complete year of service, with a minimum of {notice_er}.",
         "The notice period is {notice_emp} on either side, increasing in line with the {statute_era} where that is longer."],
        ["We may pay you in lieu of notice, or ask you not to attend work during your notice period (garden leave).",
         "During any notice period we may place you on garden leave and you must not contact clients."],
    ]),
    ("Confidentiality and data", [
        ["You must not, during or after your employment, disclose any confidential information about the Company, its clients or suppliers.",
         "Confidential information includes client lists, prices, plans and personal data. This obligation continues after you leave."],
        ["We will process your personal data in line with the {statute_dp} and our privacy notice for employees.",
         "Your data will be held securely and only for as long as necessary, as set out in our staff privacy notice."],
    ]),
    ("Discipline and grievance", [
        ["Our disciplinary and grievance procedures are in the Staff Handbook and do not form part of your contract. They follow the {acas} Code of Practice.",
         "If you have a grievance you should raise it with your manager in writing. Our procedures follow the {acas} Code."],
    ]),
]


_E_EXTRA = [
    ("Expenses", [
        ["We will reimburse expenses you reasonably incur in performing your duties, provided you submit receipts within 30 days.",
         "Business mileage in your own car is paid at {mile} per mile for the first 10,000 miles in a tax year."],
    ]),
    ("Company property", [
        ["All equipment we provide, including laptops, phones, keys and ID badges, remains our property and must be returned when your employment ends.",
         "You are responsible for looking after company equipment. We may deduct the cost of unreturned items from your final pay."],
    ]),
    ("Changes to your terms", [
        ["We may make reasonable changes to these terms. We will give you at least one month's written notice of any significant change.",
         "Minor changes may be made to our policies from time to time and will be notified to you in writing."],
    ]),
    ("Restrictions after employment", [
        ["For {restr} months after your employment ends you must not solicit or deal with any client with whom you had material dealings in the last 12 months.",
         "You must not, for {restr} months after leaving, try to entice away any employee of the Company with whom you worked closely."],
    ]),
    ("Outside interests", [
        ["You must not take up any other employment or business interest that conflicts with your duties without our written consent.",
         "You must tell us about any other job you have so that we can check compliance with the {statute_wt}."],
    ]),
    ("Training", [
        ["You must complete all mandatory training, including health and safety, data protection and safeguarding where relevant.",
         "We will pay for training required for your role. If you leave within 12 months of completing an external course costing more than {train}, you may be asked to repay part of the cost."],
    ]),
    ("Health and safety", [
        ["You must follow our health and safety policy and report any accident or near miss to your manager immediately.",
         "You must take reasonable care of your own health and safety and that of others affected by your work."],
    ]),
    ("Collective agreements", [
        ["There are no collective agreements which directly affect your terms and conditions of employment.",
         "Your terms are not affected by any collective agreement."],
    ]),
    ("Family leave", [
        ["You may be entitled to maternity, paternity, adoption, shared parental and parental bereavement leave and pay in line with current legislation.",
         "Details of family-friendly leave, including time off for dependants, are set out in the Staff Handbook."],
    ]),
]


@register("employment_contract", weight=3, neg_weight=4)
def employment_contract(rng: random.Random, neg: bool) -> Doc:
    style = rng.choice(["contract", "statement", "offer"])
    d = Doc("employment_contract", f"employment_contract/{style}")
    d.v(style)
    hstyle = rng.randrange(4)
    if neg:
        return _employment_negative(rng, d, hstyle)
    c = Cast(rng, common_word_rate=0.08)
    emp = c.new(min_age=18, max_age=64)
    signer = c.new(min_age=28)
    org = rng.choice(world.ORGS_BY_KIND["employer"]) if rng.random() < 0.7 else None
    co_name = org.name if org else world.company_name(rng)
    if org:
        lab, eid = org.custom(rng)
    else:
        lab, eid = pick(rng, "Employee number", "Staff ID", "Payroll number"), \
            E(ids.from_pattern(rng, pick(rng, "EMP-#####", "E######", "######", "P/####")), "CUSTOM", None, ("custom_org_id",))
    reg_addr = world.make_address(rng, flat_rate=0.0, building_rate=0.5)
    work_addr = reg_addr if rng.random() < 0.6 else world.make_address(rng, flat_rate=0.0, building_rate=0.5)
    home = world.make_address(rng)
    start = recent_date(rng, 400, 90)
    job = rng.choice(_JOBS)
    salaried = rng.random() < 0.75
    ctx = dict(
        start=date_text(rng, start), prob=str(rng.choice([3, 3, 6])), job=job,
        mgr_role=pick(rng, "Operations Manager", "Head of Finance", "Team Leader", "Managing Director", "Registered Manager"),
        work_addr=work_addr.inline(rng), wfh=pick(rng, "2", "3", "two", "three"), hours=str(rng.choice([37.5, 40, 35, 37, 16, 24])),
        statute_wt=K("Working Time Regulations 1998", "statute"), statute_nmw=K("National Minimum Wage Act 1998", "statute"),
        statute_era=K("Employment Rights Act 1996", "statute"), statute_dp=K(pick(rng, "Data Protection Act 2018", "UK GDPR"), "statute"),
        salary=amount(rng, 21000, 78000, step=250, style=rng.choice([0, 1])), hourly=amount(rng, 12.21, 19.5),
        payday=pick(rng, "25th", "last working day", "28th", "20th"), hol=str(rng.choice([20, 25, 28, 30, 33])),
        sickw=str(rng.randint(2, 12)), pension=K(pick(rng, "NEST", "The People's Pension", "Aviva", "Scottish Widows", "Smart Pension"), "public_company"),
        pct=str(rng.choice([3, 4, 5, 6])), notice_emp=pick(rng, "one month's", "four weeks'", "three months'", "one week's"),
        notice_er=pick(rng, "one week", "one month", "four weeks"), acas=K("ACAS", "public_company"),
        mile=K(pick(rng, "45p", "40p", "35p"), "amount"), restr=str(rng.choice([3, 6, 6, 9, 12])), train=amount(rng, 500, 3000, step=100, style=1),
    )
    if style == "offer":
        d.ln(co_name)
        d.ln(reg_addr.block(rng))
        d.blank()
        d.ln(pick(rng, "Private and confidential", "PRIVATE & CONFIDENTIAL", "Strictly private"))
        d.ln(emp.full())
        d.ln(home.block(rng, emp.ref))
        d.blank()
        d.ln(date_text(rng, start - timedelta(days=rng.randint(10, 40))))
        d.blank()
        d.ln(*greeting(rng, emp, formal=True))
        d.blank()
        d.f("Offer of employment: {job}\n\nI am delighted to offer you the position of {job} with {co}. "
            "This letter, together with the enclosed terms, forms your contract of employment.\n\n", job=job, co=co_name)
    else:
        d.ln(pick(rng, "CONTRACT OF EMPLOYMENT", "Contract of Employment", "STATEMENT OF MAIN TERMS OF EMPLOYMENT",
                  "Written statement of employment particulars"))
        if style == "statement":
            d.f("This written statement is given under section 1 of the {s}.\n", s=K("Employment Rights Act 1996", "statute"))
        d.blank()
        d.ln("BETWEEN:")
        d.f("(1) {co} (company number {cn}) whose registered office is at ", co=co_name, cn=_company_number(rng))
        d.add(reg_addr.inline(rng), " (\"the Company\"); and\n")
        d.add("(2) ", emp.full_middle() if rng.random() < 0.4 else emp.full(), " of ")
        d.add(home.inline(rng, emp.ref) if rng.random() < 0.6 else ["\n", home.block(rng, emp.ref)], " (\"you\" or \"the Employee\").\n\n")
    rows = [(lab, eid)]
    if rng.random() < 0.8:
        rows.append(("National Insurance number", emp.ni()))
    if rng.random() < 0.45:
        rows.append(("Date of birth", emp.dob()))
    if rng.random() < 0.5:
        rows.append(("Personal email", emp.email()))
    if rng.random() < 0.4:
        rows.append(("Mobile", emp.mobile()))
    rows.append(("Start date", date_text(rng, start)))
    d.ln(pick(rng, "Employee details", "Your details", "PARTICULARS"))
    d.add(kv_block(rng, rows))
    d.blank()
    if rng.random() < 0.45:
        d.ln(pick(rng, "Payroll bank details", "Bank details for salary"))
        brow = [("Account holder", emp.full() if rng.random() < 0.7 else emp.caps()), ("Bank", emp.bank_name),
                ("Sort code", emp.sort_code()), ("Account number", emp.account())]
        d.add(kv_block(rng, brow, style=rng.choice([0, 2])))
        d.blank()
    lib = list(_E_LIB)
    extra = rng.sample(_E_EXTRA, rng.randint(2, len(_E_EXTRA)))
    lib = lib[:-2] + extra + lib[-2:]
    if rng.random() < 0.3:
        mid = lib[2:-2]
        rng.shuffle(mid)
        lib = lib[:2] + mid + lib[-2:]
    nxt = _sections(rng, d, lib, ctx, hstyle, min_k=rng.uniform(0.5, 0.95))
    if rng.random() < 0.4:
        d.v("right_to_work")
        d.ln(*_heading(hstyle, nxt, "Right to work"))
        d.f("This offer is conditional on you proving your right to work in the UK. ", )
        if rng.random() < 0.6:
            d.add(pick(rng, "We have checked and copied your passport (number ", "We have seen your passport, number "),
                  emp.passport(), pick(rng, ").", ", and kept a copy on file."))
        else:
            d.add("Please bring your passport or share code to your first day.")
        d.add("\n\n")
    if style == "offer" and rng.random() < 0.8:
        d.add(pick(rng, "Please sign and return a copy of this letter to confirm your acceptance.\n\n",
                   "We look forward to welcoming you to the team.\n\n"))
        d.add(signoff(rng, signer, formal=True, role=ctx["mgr_role"], contact=rng.random() < 0.5,
                      domain=org.domain if org else world.domain_for(co_name.text)))
        d.add("\n\n")
    d.ln(pick(rng, "Signed for and on behalf of the Company", "SIGNED by the Employer", "For the Company"))
    d.add(_sig_line(rng), "\n", "Name: ", signer.full(), "\n", "Position: ", ctx["mgr_role"], "\n",
          "Date: ", date_text(rng, start - timedelta(days=rng.randint(5, 30))), "\n\n")
    d.ln(pick(rng, "Signed by the Employee", "I accept the terms set out above", "EMPLOYEE ACCEPTANCE"))
    d.add(_sig_line(rng), "\n", "Name: ", pick(rng, emp.full(), emp.caps(), emp.full_middle()), "\n", "Date: ",
          date_text(rng, start - timedelta(days=rng.randint(1, 10))) if rng.random() < 0.6 else "________", "\n")
    if rng.random() < 0.3:
        d.f("\nInitials: {i}  {s}\n", i=emp.initials(), s=pick(rng, "", "Ref: " + lab))
    if d.length() > 3500 and rng.random() < 0.35:
        def header(page, total):
            return [co_name, " - ", pick(rng, "Contract of Employment", "Private and confidential"),
                    " - " if rng.random() < 0.5 else "", emp.full("name_in_page_header") if rng.random() < 0.5 else ""]

        def footer(page, total):
            return [f"Page {page} of {total}"] if rng.random() < 0.6 else [f"{page}/{total}    ", eid]
        _pdfify(d, rng, header, footer, None)
    return d


def _employment_negative(rng, d, hstyle):
    d.template_id = "employment_contract/handbook_excerpt"
    d.v("handbook")
    co = world.public_company(rng, "employer") if rng.random() < 0.4 else world.company_name(rng)
    d.ln(pick(rng, "STAFF HANDBOOK", "Employee Handbook", "People Policies"), " - ", co)
    d.ln(pick(rng, "Version ", "Issue "), f"{rng.randint(1, 9)}.{rng.randint(0, 9)}", ", effective ",
         date_text(rng, recent_date(rng, 500)))
    d.blank()
    ctx = dict(
        start=K("[start date]", "placeholder"), prob=str(rng.choice([3, 6])), job=K("[job title]", "placeholder"),
        mgr_role="line manager", work_addr=K("[place of work]", "placeholder"), wfh=str(rng.randint(1, 3)),
        hours=str(rng.choice([37.5, 40, 35])), statute_wt=K("Working Time Regulations 1998", "statute"),
        statute_nmw=K("National Minimum Wage Act 1998", "statute"), statute_era=K("Employment Rights Act 1996", "statute"),
        statute_dp=K("UK GDPR", "statute"), salary=K("[salary]", "placeholder"), hourly=amount(rng, 12.21, 15),
        payday=pick(rng, "25th", "last working day"), hol=str(rng.choice([25, 28, 30])), sickw=str(rng.randint(2, 8)),
        pension=K(pick(rng, "NEST", "The People's Pension"), "public_company"), pct=str(rng.choice([3, 5])),
        notice_emp=pick(rng, "one month's", "four weeks'"), notice_er="one week", acas=K("ACAS", "public_company"),
        mile=K("45p", "amount"), restr=str(rng.choice([3, 6])), train=amount(rng, 500, 3000, step=100, style=1),
    )
    lib = rng.sample(_E_LIB + _E_EXTRA, rng.randint(5, 12))
    _sections(rng, d, lib, ctx, hstyle, min_k=0.6)
    d.f("Questions about this policy should be raised with your line manager or the HR team. "
        "This handbook is reviewed every {n} months.\n", n=str(rng.choice([12, 18, 24])))
    return d


# =========================================================================== NDA
_NDA_LIB = [
    ("Definitions", [
        ["\"Confidential Information\" means all information of a confidential nature disclosed by {disc} to {recv}, whether in writing, orally or by any other means, including business plans, customer lists, pricing, software, designs and know-how.",
         "In this Agreement, Confidential Information means any information disclosed in connection with the Purpose that is marked as confidential or would reasonably be regarded as confidential."],
        ["\"Purpose\" means {purpose}.",
         "The Purpose is {purpose}."],
        ["\"Representatives\" means a party's employees, officers, professional advisers and subcontractors who need to know the Confidential Information for the Purpose.",
         "References to a party include its Representatives."],
    ]),
    ("Obligations", [
        ["{recvc} shall keep the Confidential Information secret and shall not use it for any purpose other than the Purpose.",
         "The Recipient will use the Confidential Information only for the Purpose and will protect it with at least the same degree of care it uses for its own information."],
        ["{recvc} shall not disclose the Confidential Information to any third party except to its Representatives who are bound by obligations no less strict than those in this Agreement.",
         "Disclosure is permitted only to Representatives on a need-to-know basis."],
        ["{recvc} shall not copy or reproduce the Confidential Information except as reasonably required for the Purpose.",
         "No copies may be made other than as strictly necessary."],
    ]),
    ("Exceptions", [
        ["The obligations in clause {cl_ob} do not apply to information that is or becomes public other than through a breach of this Agreement, was lawfully in the Recipient's possession before disclosure, or is independently developed.",
         "This Agreement does not restrict the use of information which is already public, or which must be disclosed by law or by order of a court or regulator, provided notice is given where lawful."],
    ]),
    ("Return of information", [
        ["On request, {recv} shall return or destroy all documents containing Confidential Information and confirm in writing that it has done so.",
         "Within 10 business days of a written request the Recipient will delete or return all Confidential Information."],
    ]),
    ("Term", [
        ["This Agreement starts on the Effective Date and the obligations of confidentiality continue for {yrs} years from the date of the last disclosure.",
         "The confidentiality obligations survive termination for a period of {yrs} years."],
    ]),
    ("General", [
        ["Damages alone may not be an adequate remedy for breach and the Discloser is entitled to seek injunctive relief.",
         "Each party acknowledges that a breach may cause irreparable harm."],
        ["No licence or other right is granted in respect of any intellectual property.",
         "All Confidential Information remains the property of the Discloser."],
        ["The parties will negotiate in good {faith} in relation to any dispute arising under this Agreement.",
         "Nothing in this Agreement obliges either party to enter into any further agreement."],
        ["This Agreement is governed by the law of England and Wales and the parties submit to the exclusive jurisdiction of its courts.",
         "This Agreement is governed by {law}."],
        ["A person who is not a party has no right under the {statute_3p} to enforce any term of this Agreement.",
         "This Agreement may only be varied in writing signed by both parties."],
    ]),
]
_PURPOSES = ["evaluating a possible software development partnership", "discussing the potential acquisition of shares in the Company",
             "assessing a proposed supply of packaging materials", "exploring a joint marketing campaign",
             "the evaluation of a property investment opportunity", "discussions about a consultancy engagement",
             "reviewing a pilot of the Discloser's analytics platform", "negotiating a franchise agreement"]


def _party_company(rng: random.Random) -> tuple[list, Person | None]:
    name = world.company_name(rng)
    addr = world.make_address(rng, flat_rate=0.0, building_rate=0.5)
    seg = [name, pick(rng, ", a company incorporated in England and Wales with company number ",
                      " (registered number ", " (company no. "), _company_number(rng),
           pick(rng, ", whose registered office is at ", ") of ", ") whose registered office is "), addr.inline(rng)]
    return seg, None


@register("nda", weight=2, neg_weight=3)
def nda(rng: random.Random, neg: bool) -> Doc:
    mutual = rng.random() < 0.55
    d = Doc("nda", "nda/" + ("mutual" if mutual else "one_way"))
    d.v("mutual" if mutual else "one_way")
    hstyle = rng.randrange(4)
    ctx = dict(disc="the Discloser" if not mutual else "either party", recv="the Recipient" if not mutual else "the other party",
               recvc="The Recipient" if not mutual else "Each party", purpose=rng.choice(_PURPOSES),
               cl_ob=_cl(3), yrs=str(rng.choice([2, 3, 5])), faith=K("faith", "common_word"),
               law=pick(rng, "the law of England and Wales", "Scots law", "the law of Northern Ireland"),
               statute_3p=K("Contracts (Rights of Third Parties) Act 1999", "statute"))
    d.ln(pick(rng, "MUTUAL NON-DISCLOSURE AGREEMENT" if mutual else "NON-DISCLOSURE AGREEMENT",
              "CONFIDENTIALITY AGREEMENT", "Non-Disclosure Agreement" if not mutual else "Mutual Confidentiality Agreement"))
    d.blank()
    if neg:
        d.template_id += "_template"
        d.v("template")
        ph = lambda s: K(s, "placeholder")  # noqa: E731
        d.add("This Agreement is dated ", ph("[date]"), "\n\nPARTIES\n")
        d.add("(1) ", ph("[COMPANY NAME]"), " incorporated and registered in England and Wales with company number ",
              ph("[NUMBER]"), " whose registered office is at ", ph("[REGISTERED OFFICE ADDRESS]"), "\n")
        d.add("(2) ", ph("[NAME OF OTHER PARTY]"), " of ", ph("[ADDRESS]"), "\n\n")
        _sections(rng, d, _NDA_LIB, ctx, hstyle, min_k=0.6)
        d.add("Signed by ", ph("[NAME OF DIRECTOR]"), " for and on behalf of ", ph("[COMPANY NAME]"), "  ", _sig_line(rng), "\n")
        return d
    c = Cast(rng, common_word_rate=0.08)
    eff = recent_date(rng, 500)
    d.add(pick(rng, "This Agreement is dated ", "Dated: ", "Effective Date: "), date_text(rng, eff), "\n\n")
    d.ln(pick(rng, "PARTIES", "BETWEEN", "Parties"))
    p1, _ = _party_company(rng)
    d.add("(1) ", p1, " (\"", "Party A" if mutual else "the Discloser", "\"); and\n")
    signers = [c.new(min_age=28)]
    if rng.random() < 0.45:
        ind = c.new(min_age=21)
        d.v("individual")
        d.add("(2) ", ind.full_middle() if rng.random() < 0.4 else ind.full(), " of ")
        d.add(world.make_address(rng).inline(rng, ind.ref), " (\"", "Party B" if mutual else "the Recipient", "\").\n\n")
        signers.append(ind)
        ind_party = True
    else:
        p2, _ = _party_company(rng)
        d.add("(2) ", p2, " (\"", "Party B" if mutual else "the Recipient", "\").\n\n")
        signers.append(c.new(min_age=28))
        ind_party = False
    d.ln(pick(rng, "BACKGROUND", "Recitals"))
    d.f("(A) The parties wish to exchange information for the purpose of {p}.\n(B) Each party has agreed to keep that information confidential on the terms of this Agreement.\n\n",
        p=ctx["purpose"])
    if rng.random() < 0.4:
        ct = signers[0]
        d.f("Contact for notices: {n}, {e}, {ph}\n\n", n=ct.full(), e=ct.work_email(world.domain_for(p1[0].text)), ph=ct.landline())
    _sections(rng, d, _NDA_LIB, ctx, hstyle, min_k=rng.uniform(0.5, 0.9))
    if rng.random() < 0.35:
        ct = signers[0]
        d.f("Notices under this Agreement must be in writing and marked for the attention of {a} (or {i}, if {p} has left the business).\n\n",
            a=ct.title_last(), i=ct.initial_last(), p=ct.first_name())
    d.ln(pick(rng, "SIGNED by the parties on the date stated above.", "Executed as an agreement.", "AGREED"))
    d.blank()
    for i, s in enumerate(signers):
        if i == 1 and ind_party:
            d.add("Signed by ", s.full(), " ", _sig_line(rng), "\n")
        else:
            d.add("Signed by ", s.full(), ", ", pick(rng, "Director", "Authorised signatory", "Chief Executive Officer", "Managing Director"),
                  ", for and on behalf of Party ", "A" if i == 0 else "B", " ", _sig_line(rng), "\n")
        d.add("Date: ", date_text(rng, eff) if rng.random() < 0.6 else "____________", "\n\n")
    if rng.random() < 0.3:
        def header(page, total):
            return [p1[0], " / ", pick(rng, "NDA", "Confidentiality Agreement", "Strictly confidential")]

        def footer(page, total):
            return [f"Page {page} of {total}"] if rng.random() < 0.6 else [f"{page} | Initials: ", signers[0].initials()]
        _pdfify(d, rng, header, footer, None, every=rng.randint(1200, 1800))
    return d


# =========================================================================== service agreement
_SVC = [("Website design and build", 1200, 6500, 1), ("Monthly SEO retainer", 250, 1500, 12), ("Bookkeeping (monthly)", 120, 650, 12),
        ("Office cleaning (per visit)", 45, 180, 24), ("Garden maintenance (fortnightly)", 35, 140, 26), ("Photography (half day)", 250, 600, 3),
        ("IT support retainer", 150, 900, 12), ("Social media management", 300, 1800, 6), ("Boiler service", 70, 140, 2),
        ("Copywriting (per 1,000 words)", 90, 300, 10), ("Consultancy day rate", 400, 1200, 15), ("Window cleaning", 15, 60, 12),
        ("Payroll processing (per employee)", 4, 12, 40), ("Annual software licence", 500, 4000, 1), ("Training workshop", 600, 2500, 2)]

_S_LIB = [
    ("Services", [
        ["The Supplier shall provide the Services described in the Schedule with reasonable skill and care and in accordance with good industry practice.",
         "The Supplier will carry out the Services set out in Schedule 1 using appropriately qualified staff."],
        ["The Customer shall provide the Supplier with access, information and instructions reasonably required to perform the Services.",
         "The Customer will co-operate with the Supplier and provide timely feedback."],
    ]),
    ("Fees and payment", [
        ["The Customer shall pay the fees in the Schedule within {days} days of the date of each invoice.",
         "Invoices are payable within {days} days. Payment is to be made by bank transfer to the account below."],
        ["All fees are exclusive of VAT, which will be added at the prevailing rate where applicable.",
         "The Supplier is not VAT registered and no VAT is charged."],
        ["Interest on late payments may be charged under the {statute_late}.",
         "If payment is late the Supplier may suspend the Services and charge statutory interest under the {statute_late}."],
    ]),
    ("Term and termination", [
        ["This Agreement begins on {start} and continues until terminated by either party giving {notice} written notice.",
         "The Agreement runs for an initial period of {months} months from {start} and then continues month to month."],
        ["Either party may terminate immediately if the other commits a material breach which is not remedied within 14 days of notice.",
         "Termination does not affect any rights that have accrued before the date of termination."],
    ]),
    ("Liability", [
        ["The Supplier's total liability under this Agreement shall not exceed the fees paid in the 12 months before the claim.",
         "Neither party excludes liability for death or personal injury caused by negligence, or for fraud."],
    ]),
    ("Intellectual property", [
        ["On payment in full, the Supplier assigns to the Customer all intellectual property rights in the deliverables.",
         "The Supplier retains ownership of its pre-existing materials and grants the Customer a non-exclusive licence to use them."],
    ]),
    ("Data protection and confidentiality", [
        ["Each party shall comply with the {statute_dp} in relation to any personal data processed under this Agreement.",
         "Where the Supplier processes personal data on the Customer's behalf it shall do so only on documented instructions."],
        ["Each party shall keep the other's confidential information secret.",
         "This clause survives termination for two years."],
    ]),
    ("General", [
        ["This Agreement is governed by the law of England and Wales.",
         "Any dispute will first be referred to the parties' named contacts, who will meet in good {faith} to resolve it."],
        ["Neither party may assign this Agreement without the other's consent.",
         "This Agreement is the entire agreement between the parties."],
    ]),
]


@register("service_agreement", weight=2, neg_weight=3)
def service_agreement(rng: random.Random, neg: bool) -> Doc:
    d = Doc("service_agreement", "service_agreement/v1")
    hstyle = rng.randrange(4)
    start = recent_date(rng, 400, 60)
    ctx = dict(days=str(rng.choice([7, 14, 30, 30, 60])), statute_late=K("Late Payment of Commercial Debts (Interest) Act 1998", "statute"),
               start=date_text(rng, start), notice=pick(rng, "one month's", "30 days'", "three months'"),
               months=str(rng.choice([3, 6, 12])), statute_dp=K(pick(rng, "UK GDPR", "Data Protection Act 2018"), "statute"),
               faith=K("faith", "common_word"))
    d.ln(pick(rng, "SERVICE AGREEMENT", "Agreement for the Supply of Services", "SERVICES AGREEMENT", "Terms of Service Agreement"))
    d.blank()
    if neg:
        d.template_id = "service_agreement/standard_terms"
        d.v("standard_terms")
        d.ln(pick(rng, "Standard terms and conditions", "General terms (version ", "Standard Terms"),
             f"{rng.randint(1, 5)}.{rng.randint(0, 9)})" if rng.random() < 0.3 else "")
        d.blank()
        _sections(rng, d, _S_LIB, ctx, hstyle, min_k=0.7)
        if rng.random() < 0.6:
            d.f("Fees are as quoted. Typical rates: {a} per hour; minimum charge {b}.\n", a=amount(rng, 25, 120), b=amount(rng, 50, 300, step=5))
        return d
    c = Cast(rng, common_word_rate=0.08)
    sole = rng.random() < 0.55
    sup_p = c.new(min_age=24)
    sup_addr = world.make_address(rng, flat_rate=0.2 if sole else 0.0, building_rate=0.3)
    if sole:
        d.v("sole_trader")
        sup_name = world.sole_trader(rng, sup_p)
        sup_dom = None
    else:
        sup_name = [world.company_name(rng)]
        sup_dom = world.domain_for(sup_name[0].text)
    cust_ind = rng.random() < 0.35
    cust_p = c.new()
    cust_addr = world.make_address(rng, flat_rate=0.2 if cust_ind else 0.0, building_rate=0.3)
    cust_name = [cust_p.full()] if cust_ind else [world.company_name(rng)]
    if cust_ind:
        d.v("customer_individual")
    d.add(pick(rng, "This Agreement is made on ", "Date: "), date_text(rng, start - timedelta(days=rng.randint(1, 20))), "\n\n")
    d.add("(1) ", sup_name, pick(rng, " of ", ", trading from ", ", "), sup_addr.inline(rng, sup_p.ref if sole else None), " (\"the Supplier\")")
    if sole and rng.random() < 0.5:
        d.add(", a sole trader")
    d.add("\n(2) ", cust_name, pick(rng, " of ", ", "), cust_addr.inline(rng, cust_p.ref if cust_ind else None), " (\"the Customer\")\n\n")
    # contacts
    d.ln(pick(rng, "Contacts", "Key contacts", "Named contacts"))
    d.add("Supplier: ", sup_p.full() if not sole or rng.random() < 0.5 else sup_p.first_name(), ", ",
          sup_p.mobile(), ", ", sup_p.email() if sup_dom is None else sup_p.work_email(sup_dom), "\n")
    if cust_ind:
        d.add("Customer: ", cust_p.title_last(), ", ", cust_p.phone(), ", ", cust_p.email(), "\n\n")
    else:
        cc = c.new()
        d.add("Customer: ", cc.full(), " (", pick(rng, "Office Manager", "Finance Director", "Operations Lead"), "), ",
              cc.landline(), ", ", cc.work_email(world.domain_for(cust_name[0].text)), "\n\n")
    _sections(rng, d, _S_LIB, ctx, hstyle, min_k=rng.uniform(0.5, 0.9))
    # schedule of fees
    d.ln(pick(rng, "SCHEDULE 1 - SERVICES AND FEES", "Schedule: Fees", "Schedule 1"))
    d.blank()
    items = rng.sample(_SVC, rng.randint(2, 5))
    d.add("| Service | Rate | Quantity | Total |\n|---|---|---|---|\n")
    for name, lo, hi, qmax in items:
        q = rng.randint(1, qmax)
        r = round(rng.uniform(lo, hi), 2)
        d.add("| ", name, " | ", K(world.money_text(r), "amount"), " | ", str(q), " | ", K(world.money_text(round(r * q, 2)), "amount"), " |\n")
    d.blank()
    # bank details
    d.ln(pick(rng, "Payment details", "Bank details", "Please pay to:"))
    rows = [("Account name", sup_p.full() if sole and rng.random() < 0.7 else sup_name),
            ("Sort code", sup_p.sort_code()), ("Account number", sup_p.account())]
    if rng.random() < 0.4:
        rows.append(("IBAN", sup_p.iban()))
        rows.append(("BIC", K(sup_p.bank[1] + "GB2" + str(rng.randint(1, 9)), "bic")))
    d.add(kv_block(rng, rows, style=rng.choice([0, 2])))
    d.blank()
    d.ln("Signed for the Supplier ", _sig_line(rng))
    d.add("Name: ", sup_p.full(), "\n\n")
    d.ln("Signed for the Customer ", _sig_line(rng))
    d.add("Name: ", cust_p.full() if cust_ind else c.new().full(), "\n")
    if rng.random() < 0.25:  # covering note pasted above the agreement
        d.v("cover_note")
        note = [greeting(rng, cust_p, formal=False) if cust_ind else "Hi,", "\n",
                pick(rng, "Please find our service agreement below. Let me know if anything needs changing.",
                     "As discussed, here is the agreement for signature.", "Agreement below - any questions just call."),
                "\n", signoff(rng, sup_p, formal=False), "\n\n"]
        d.atoms = [*__import__("datagen.core", fromlist=["flatten"]).flatten(note), *d.atoms]
    return d


# =========================================================================== letter of engagement
_ENG_SCOPE_LAW = [
    "acting for you in the purchase of {prop}",
    "acting for you in the sale of {prop}",
    "advising you on your employment dispute with your former employer",
    "preparing your will and lasting powers of attorney",
    "acting for you in the administration of the estate of the late {dec}",
    "advising you on the tenancy deposit dispute concerning {prop}",
    "acting for you in your remortgage of {prop}",
]
_ENG_SCOPE_ACC = [
    "preparing your self assessment tax return for the {ty} tax year",
    "preparing the annual accounts and corporation tax return for your company",
    "dealing with HMRC's enquiry into your {ty} return",
    "acting as your agent for Making Tax Digital for income tax",
    "providing bookkeeping and VAT return services each quarter",
    "preparing rental income schedules for your property at {prop}",
]


_ENG_SECTIONS_LAW = [
    ("What we will do", ["investigate title and raise enquiries with the other side's solicitors", "carry out local authority, drainage and environmental searches",
                          "report to you on the title and the contract", "deal with the exchange of contracts and completion",
                          "pay Stamp Duty Land Tax on your behalf and register the transaction at {lr}", "advise you on the terms of your mortgage offer"]),
    ("What is not included", ["advice on the value of the property or its physical condition", "tax planning advice",
                              "court proceedings, unless agreed separately in writing", "advice on any planning or building regulation issues",
                              "work for any other person, including your lender, beyond what is required"]),
]
_ENG_SECTIONS_LAW_GENERAL = [
    ("What we will do", ["review the documents you send us and advise on the merits", "prepare correspondence and attend calls with you",
                         "advise you on the options available and the likely costs of each", "draft the documents needed and explain them to you",
                         "correspond with the other party or their representatives on your behalf", "keep you updated at least once a month"]),
    ("What is not included", ["court proceedings, unless agreed separately in writing", "tax planning advice",
                              "advice on the law of any country other than England and Wales", "appeals against any decision"]),
]
_ENG_SECTIONS_ACC = [
    ("What we will do", ["prepare your tax return from the information and records you provide", "calculate your income tax and National Insurance liability",
                         "submit the return to {hmrc} after you have approved it", "advise you of payments on account and deadlines",
                         "deal with routine correspondence from {hmrc}", "prepare quarterly VAT returns and file them through Making Tax Digital software"]),
    ("Your responsibilities", ["provide complete and accurate records by {deadline}", "tell us about any change in your circumstances",
                               "keep your records for at least six years", "approve the return before it is submitted",
                               "pay any tax due by the deadlines set by {hmrc}"]),
]
_ENG_GENERAL = [
    ("Timescales", ["We aim to {x} within {n} weeks of receiving everything we need from you.",
                    "We will keep you informed of progress and let you know if anything is likely to cause a delay."]),
    ("Storage of documents", ["We will keep your file for at least {yrs} years after the matter ends, after which it may be destroyed without further notice.",
                              "We store documents electronically and may not keep paper originals."]),
    ("Professional indemnity insurance", ["We hold professional indemnity insurance with {ins}. Details of the cover are available on request.",
                                          "Our insurer is {ins} and the cover applies throughout the UK."]),
    ("Limitation of liability", ["Our liability to you for any loss arising from this engagement is limited to {cap}, unless the law does not allow such a limit.",
                                 "We will not be liable for losses caused by false or incomplete information given to us."]),
    ("Cancellation", ["If this contract was agreed away from our offices you have the right to cancel within 14 days without giving a reason.",
                      "If you ask us to start work during the cancellation period you will pay for the work done up to the date you cancel."]),
    ("Data protection", ["We will use your personal data only to provide our services and to meet our legal obligations under the {dp}.",
                         "Our privacy notice explains how we use and protect your information."]),
]


@register("engagement_letter", weight=3, neg_weight=0)
def engagement_letter(rng: random.Random, neg: bool) -> Doc:
    law = rng.random() < 0.55
    org = rng.choice(world.ORGS_BY_KIND["law" if law else "accountant"])
    d = Doc("engagement_letter", "engagement_letter/" + ("solicitor" if law else "accountant"))
    d.v("solicitor" if law else "accountant")
    c = Cast(rng, common_word_rate=0.08)
    client = c.new(min_age=22)
    partner = c.new(min_age=30)
    assoc = c.new(min_age=24) if rng.random() < 0.6 else None
    org_addr = world.make_address(rng, flat_rate=0.0, building_rate=0.4)
    caddr = world.make_address(rng)
    when = recent_date(rng, 500)
    # letterhead
    d.ln(org.name)
    if rng.random() < 0.7:
        d.ln(org_addr.block(rng))
    else:
        d.ln(org_addr.inline(rng))
    d.ln(pick(rng, "Tel: ", "T ", "Telephone: "), _org_phone(rng), pick(rng, "  |  ", "\n"), pick(rng, "", "www.") + org.domain)
    d.blank()
    # refs
    ref_rows = []
    labels = list(org.ids)
    rng.shuffle(labels)
    for lab in labels[: rng.randint(1, len(labels))]:
        _, v = org.custom(rng, lab, year=when.year if rng.random() < 0.7 else None)
        ref_rows.append((lab, v))
    if rng.random() < 0.4:
        ref_rows.append(("Your ref", pick(rng, "-", "N/A", "TBC")))
    for lab, v in ref_rows:
        d.add(lab, ": ", v, "\n")
    d.add(date_text(rng, when), "\n\n")
    if rng.random() < 0.25:
        d.ln(pick(rng, "By email only: ", "Sent by email to "), client.email())
    else:
        d.ln(pick(rng, "PRIVATE AND CONFIDENTIAL", "Private & Confidential", "Strictly private and confidential"))
    d.add(client.title_full() if rng.random() < 0.6 else [client.full()], "\n")
    d.add(caddr.block(rng, client.ref), "\n\n")
    d.ln(*greeting(rng, client, formal=True))
    d.blank()
    prop = world.make_address(rng)
    ty = K(pick(rng, "2024/25", "2025/26", "2023-24", "2025 to 2026"), "date")
    dec = c.new(min_age=60)
    scope_t = rng.choice(_ENG_SCOPE_LAW if law else _ENG_SCOPE_ACC)
    scope = []
    from ..core import fmt
    scope = fmt(scope_t, prop=prop.inline(rng, client.ref), ty=ty, dec=dec.full())
    if "{dec}" not in scope_t:
        c.people.remove(dec)
    d.add("Re: ", scope[0][:1].upper() + scope[0][1:], *scope[1:], "\n\n")
    d.add(pick(rng, "Thank you for instructing us. ", "Thank you for choosing ", "We are pleased to confirm our engagement. "))
    if "choosing" in d.atoms[-1]:
        d.add(org.name, ". ")
    d.add("This letter sets out the basis on which we will be ", *scope, ".\n\n")
    gctx = dict(lr=K("HM Land Registry", "public_company"), hmrc=K("HMRC", "public_company"),
                deadline=date_text(rng, when + timedelta(days=rng.randint(20, 90))), x=pick(rng, "complete the work", "report to you", "submit your return"),
                n=str(rng.randint(2, 12)), yrs=str(rng.choice([6, 7, 15])), ins=K(pick(rng, "Aviva", "AXA", "Hiscox", "QBE", "Travelers"), "public_company"),
                cap=amount(rng, 500000, 3000000, step=250000, style=1), dp=K(pick(rng, "UK GDPR", "Data Protection Act 2018"), "statute"))
    bullet = pick(rng, "- ", "* ", "• ", "(a) ")
    conveyancing = any(w in scope_t for w in ("purchase", "sale of", "remortgage"))
    for title, items in ((_ENG_SECTIONS_LAW if conveyancing else _ENG_SECTIONS_LAW_GENERAL) if law else _ENG_SECTIONS_ACC):
        if rng.random() < 0.8:
            d.ln(title)
            for i, it in enumerate(rng.sample(items, rng.randint(2, len(items)))):
                b_ = f"({chr(97 + i)}) " if bullet == "(a) " else bullet
                d.add(b_)
                d.f(it, **gctx)
                d.add("\n")
            d.blank()
    d.f("{p}, {role}, will have overall responsibility for your matter.", p=partner.full(), role=pick(rng, "Partner", "Director", "Senior Partner", "Principal"))
    if assoc:
        d.f(" Day-to-day work will be carried out by {a}, {r}, who you can contact on {ph} or {em}.",
            a=assoc.full(), r=pick(rng, "Associate", "Senior Associate", "Trainee Solicitor", "Tax Manager", "Paralegal"),
            ph=assoc.landline(), em=assoc.work_email(org.domain))
        if rng.random() < 0.5:
            d.f(" If {a} is unavailable, please ask for {p}.", a=assoc.first_name(), p=partner.title_last())
    d.add("\n\n")
    d.ln(pick(rng, "Our fees", "Fees and expenses", "Costs"))
    d.f("Our charges are based on the time spent. The current hourly rates are {a} for a partner and {b} for other fee earners, plus VAT. "
        "We estimate the total cost at {lo} to {hi} plus VAT and disbursements.\n", a=amount(rng, 220, 450, step=5), b=amount(rng, 120, 260, step=5),
        lo=amount(rng, 600, 2500, step=50, style=1), hi=amount(rng, 2600, 9000, step=50, style=1))
    if rng.random() < 0.6:
        d.f("Please pay {m} on account to our client account: sort code {sc}, account {acct}, quoting reference {ref}. "
            "We will never change our bank details by email.\n", m=amount(rng, 200, 1500, step=50),
            sc=E(ids.format_sort(ids.sort_code(rng, rng.choice(ids.BANKS)[2][0]), 0), "SORT_CODE"),
            acct=E(ids.account_number(rng), "BANK_ACCOUNT"), ref=ref_rows[0][1])
    d.blank()
    d.ln(pick(rng, "Identification", "Anti-money laundering checks", "Proof of identity"))
    d.f("Under the {s} we must verify your identity. ", s=K("Money Laundering Regulations 2017", "statute"))
    r = rng.random()
    if r < 0.45:
        d.v("aml_ids")
        d.add(pick(rng, "We have recorded the following documents: ", "Thank you for providing: "))
        docs = []
        if rng.random() < 0.8:
            docs.append(["passport number ", client.passport()])
        if rng.random() < 0.6 or not docs:
            docs.append(["UK driving licence ", client.licence()])
        for i, x in enumerate(docs):
            if i:
                d.add(" and ")
            d.add(x)
        if rng.random() < 0.5:
            d.add(", and we have confirmed your date of birth as ", client.dob())
        d.add(".\n\n")
    else:
        d.add("Please bring your passport or photocard driving licence and a utility bill dated within the last three months.\n\n")
    d.ln(pick(rng, "Complaints", "If you are unhappy"))
    if law:
        d.f("If you are unhappy with our service, please contact {p}. If we cannot resolve your complaint you may contact {lo} within six months of our final response.\n\n",
            p=partner.title_last(), lo=K("the Legal Ombudsman", "public_company"))
    else:
        d.f("If you are unhappy with our service, please contact {p}. You may also complain to {b}.\n\n",
            p=partner.full(), b=K(pick(rng, "the ICAEW", "ACCA", "the Chartered Institute of Taxation"), "public_company"))
    for title, paras in rng.sample(_ENG_GENERAL, rng.randint(2, len(_ENG_GENERAL))):
        d.ln(title)
        for ptxt in rng.sample(paras, rng.randint(1, len(paras))):
            d.f(ptxt + " ", **gctx)
        d.add("\n\n")
    d.f("Our terms of business are enclosed and form part of this letter. Please sign and return the enclosed copy{x}.\n\n",
        x=pick(rng, "", " within 14 days", " so that we can start work"))
    d.add(signoff(rng, partner, formal=True, org=org, role=pick(rng, "Partner", "Director", "Principal"), contact=rng.random() < 0.6, domain=org.domain))
    d.add("\n\n")
    if rng.random() < 0.7:
        d.ln("-" * rng.randint(10, 30))
        d.add(pick(rng, "I confirm that I have read and agree to the terms set out in this letter.\n",
                   "ACCEPTANCE: I agree to the terms of engagement.\n"))
        d.add("Signed: ", _sig_line(rng), "\nName: ", pick(rng, client.full(), client.caps(), client.full()), "\nDate: ________\n")
    if rng.random() < 0.2:
        d.f("\nAuthorised and regulated by the {r}. Registered in England and Wales, company number {cn}. VAT number {v}.\n",
            r=K(pick(rng, "Solicitors Regulation Authority", "ICAEW"), "public_company"), cn=_company_number(rng), v=_vat(rng))
    return d
