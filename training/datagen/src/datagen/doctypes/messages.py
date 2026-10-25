"""Email threads, chat/SMS/WhatsApp messages, support tickets and meeting notes."""
from __future__ import annotations

import random
from datetime import datetime, timedelta

from .. import ids, noise, world
from ..core import Doc, E, HC, HCEnd, HCStart, K, flatten
from ..core import fmt as _f
from ..names import Cast, Person
from . import register
from .common import amount, date_text, greeting, pick, recent_date

WD = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
WDF = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]


# =========================================================================== helpers
def _when(rng: random.Random, back: int = 400) -> datetime:
    d = recent_date(rng, back)
    return datetime(d.year, d.month, d.day, rng.randint(7, 22), rng.randint(0, 59), rng.randint(0, 59))


def _email_dt(dt: datetime, st: int) -> str:
    wd, wdf, m = WD[dt.weekday()], WDF[dt.weekday()], ids.MONTHS[dt.month - 1]
    hm = f"{dt.hour:02d}:{dt.minute:02d}"
    if st == 0:
        return f"{wd}, {dt.day} {m[:3]} {dt.year} {hm}"
    if st == 1:
        return f"{wdf}, {dt.day} {m} {dt.year} {hm}"
    if st == 2:
        return f"{dt.day:02d}/{dt.month:02d}/{dt.year} {hm}"
    if st == 3:
        return f"{dt.day} {m} {dt.year} at {hm}"
    if st == 4:
        return f"{wd}, {dt.day:02d} {m[:3]} {dt.year} {hm}:{dt.second:02d} {'+0100' if 4 <= dt.month <= 10 else '+0000'}"
    return f"{wd} {dt.day:02d}/{dt.month:02d}/{dt.year} {hm}"


def _rstrip(atoms: list) -> list:
    """Strip trailing whitespace from the last plain-text atoms."""
    atoms = list(atoms)
    i = len(atoms) - 1
    while i >= 0:
        a = atoms[i]
        if isinstance(a, (HCStart, HCEnd)):
            i -= 1
            continue
        if isinstance(a, str):
            s = a.rstrip()
            atoms[i] = s
            if s:
                break
            i -= 1
            continue
        break
    return [a for a in atoms if not (isinstance(a, str) and a == "")]


def _split_lines(text: str, make) -> list:
    """Split a multi-line value into one atom per line, keeping padding outside the spans."""
    out = []
    for j, ln in enumerate(text.split("\n")):
        if j:
            out.append("\n")
        core = ln.strip()
        if not core:
            out.append(ln)
            continue
        lead = len(ln) - len(ln.lstrip())
        if lead:
            out.append(ln[:lead])
        out.append(make(core))
        tail = ln[lead + len(core):]
        if tail:
            out.append(tail)
    return out


def quote(segs, prefix: str = "> ") -> list:
    """Prefix every line with '> '. Entities containing newlines become one span per line,
    so no span ever contains the quote marker."""
    atoms = _rstrip(flatten(segs))
    pieces: list = []
    for a in atoms:
        if isinstance(a, E) and "\n" in a.text:
            pieces += _split_lines(a.text, lambda t, a=a: E(t, a.type, a.ref, a.hard))
        elif isinstance(a, K) and "\n" in a.text:
            pieces += _split_lines(a.text, lambda t, a=a: K(t, a.kind))
        else:
            pieces.append(a)
    out: list = [prefix]
    for a in pieces:
        if isinstance(a, str):
            out.append(a.replace("\n", "\n" + prefix))
        else:
            out.append(a)
    return [HC("quoted_reply", out)]


def _join(items: list, sep: str) -> list:
    out = []
    for i, x in enumerate(items):
        if i:
            out.append(sep)
        out.append(x)
    return out


def _street(addr, ref=None) -> E:
    """Street line as one ADDRESS span (world.Address.street_only can be padded when a building has no number)."""
    return E(addr.street_line().strip(), "ADDRESS", ref, ("flat_number",) if addr.flat else ())


def _org_addr(rng: random.Random):
    return world.make_address(rng, flat_rate=0.0, building_rate=0.3)


class Party:
    """One email participant with a fixed address for the whole thread."""

    def __init__(self, rng: random.Random, p: Person, org: world.Org | None = None, role: str | None = None,
                 work: bool = False):
        self.p, self.org, self.role = p, org, role
        self.email_text = p.work_email(org.domain).text if (work and org) else p.email_raw
        self.hs = rng.choice([0, 0, 0, 0, 1, 2])
        self.addr = _org_addr(rng) if org else None
        self.phone_e = p.landline() if (org and rng.random() < 0.6) else p.mobile()

    def email(self) -> E:
        return E(self.email_text, "EMAIL", self.p.ref, ("name_in_email",))

    def header(self, rng: random.Random, outlook: bool = False) -> list:
        if outlook and rng.random() < 0.5:
            return [self.p.full(), " [mailto:", self.email(), "]"]
        if self.hs == 1:
            return ['"', self.p.last_comma_first(), '" <', self.email(), ">"]
        if self.hs == 2:
            return [self.email()]
        return [self.p.full(), " <", self.email(), ">"]


def _signature(rng: random.Random, s: Party, formal: bool) -> list:
    p = s.p
    out = [rng.choice(["Kind regards,", "Best regards,", "Many thanks,", "Regards,", "Best wishes,", "Thanks,"]
                      if formal else ["Thanks,", "Cheers,", "Best,", "Thanks!", "Speak soon,", "Ta,", "x", "Thanks again,"]), "\n"]
    if not formal:
        r = rng.random()
        out.append(p.first_name("signature_name") if r < 0.6 else p.nickname("signature_name") if r < 0.85 else p.full("signature_name"))
        return out
    short_first = rng.random() < 0.45
    if short_first:  # "Kind regards,\nJo\n--\nJo Bloggs | Associate"
        out += [p.first_name("signature_name"), "\n\n", pick(rng, "--\n", "", "__\n")]
    out.append(p.full("signature_name"))
    if s.role:
        out += [pick(rng, " | ", "\n", ", "), s.role]
    if s.org:
        out += ["\n", s.org.name]
        if rng.random() < 0.6:
            out += ["\n", pick(rng, "T: ", "Tel: ", "Direct line: ", "DDI: "), s.phone_e]
        if rng.random() < 0.4:
            out += [pick(rng, " | E: ", "\nE: ", "\nEmail: "), s.email()]
        if rng.random() < 0.5:
            out += ["\n", s.addr.inline(rng, None)]
        if s.org.kind in ("law", "accountant") and rng.random() < 0.5:
            out += ["\n\n", pick(rng, "This email and any attachments are confidential and intended solely for the addressee. ",
                                 "CONFIDENTIALITY: this message may contain privileged information. "),
                    s.org.name, " is ", pick(rng, "authorised and regulated by the Solicitors Regulation Authority (SRA number ",
                                               "registered in England and Wales (company number "),
                    K(ids.from_pattern(rng, pick(rng, "######", "OC######", "0#######")), "company_number"), ")."]
    elif rng.random() < 0.5:
        out += ["\n", pick(rng, "Mob: ", "", "Tel: "), s.phone_e]
    if rng.random() < 0.2:
        out += ["\n", pick(rng, "Sent from my iPhone", "Sent from Outlook for Android", "Get Outlook for iOS")]
    return out


def _body(rng: random.Random, s: Party, r: Party, paras: list, formal: bool) -> list:
    out: list = []
    if rng.random() < 0.9:
        out += [greeting(rng, r.p, formal), "\n\n"]
    for para in paras:
        out += [para, "\n\n"]
    out += _signature(rng, s, formal)
    return out


_KEEP_CAPS = {"April", "June", "Victor", "Art"}


def _cwp(rng: random.Random, name: str) -> list | None:
    """world.common_word_phrase, keeping capitals where the ordinary word is still capitalised
    (months, 'Rose Garden')."""
    ph = world.common_word_phrase(rng, name)
    if ph and isinstance(ph[1], K) and ph[1].text != name and (name in _KEEP_CAPS or ph[2].startswith(" Garden")):
        ph = [ph[0], K(name, ph[1].kind), ph[2]]
    return ph


def _cw_trap(rng: random.Random, c: Cast) -> list:
    for p in c.people:
        if p.common_word:
            ph = _cwp(rng, p.first)
            if ph:
                return [" ", ph]
    return []


# =========================================================================== email topics
# each returns (subject segments, [(sender, recipient, paragraphs, formal)])
def _t_tenancy(rng, c):
    org = rng.choice(world.ORGS_BY_KIND["letting"])
    agent = Party(rng, c.new(), org, pick(rng, "Property Manager", "Lettings Negotiator", "Deposit Team",
                                         "Senior Property Manager", "Block Manager"), work=True)
    ten = Party(rng, c.new())
    addr = world.make_address(rng, flat_rate=0.5)
    lab, cid = org.custom(rng)
    moved = recent_date(rng, 120)
    dep = amount(rng, 600, 3200, step=5)
    subj = [pick(rng, "Deposit return - ", "Check-out at ", "Repairs: ", "Renewal for "), _street(addr, ten.p.ref)]
    m = [
        (ten, agent, [[pick(rng, "I moved out of ", "I handed the keys back for "), addr.inline(rng, ten.p.ref), " on ",
                       date_text(rng, moved), pick(rng, ". Could you confirm when my deposit of ", ". When will the deposit of "),
                       dep, " be returned? ", pick(rng, "My tenancy reference is ", "The ref on my paperwork is "), cid, "."],
                      [pick(rng, "The deposit was protected with ", "My deposit is held by "),
                       world.public_company(rng, "deposit"), ". ", pick(rng, "I left the flat clean and photographed every room.",
                                                                        "Everything was in the same condition as the inventory.")]
                      + _cw_trap(rng, c)], False),
        (agent, ten, [[pick(rng, "Thank you for your email. ", "Thanks for getting in touch. "),
                       "The check-out report notes ", pick(rng, "a stain on the lounge carpet", "a missing set of window keys",
                                                           "limescale in the shower", "a damaged blind in bedroom 2"),
                       ". The landlord has proposed a deduction of ", amount(rng, 40, 350), "."],
                      ["Please confirm the bank account the balance should be paid to, quoting ", lab.lower(), " ", cid, "."]], True),
        (ten, agent, [[pick(rng, "That's fine. ", "OK, I accept that. "), "Please pay it to sort code ", ten.p.sort_code(),
                       ", account ", ten.p.account(), pick(rng, ", name ", ", account name "),
                       ten.p.full() if rng.random() < 0.6 else ten.p.initial_last(), "."]], False),
        (agent, ten, [["Thank you, ", ten.p.first_name(), ". The payment of ", amount(rng, 300, 3000), " has been requested and should reach ",
                       "your account within 10 working days of ", date_text(rng, recent_date(rng, 30)), "."]], True),
    ]
    return subj, m


def _t_accounts(rng, c):
    org = rng.choice(world.ORGS_BY_KIND["accountant"])
    acc = Party(rng, c.new(), org, pick(rng, "Tax Senior", "Client Manager", "Partner", "Bookkeeper", "Tax Assistant"), work=True)
    cl = Party(rng, c.new())
    lab, cid = org.custom(rng)
    utr = E(ids.utr(rng, rng.random() < 0.5), "CUSTOM", cl.p.ref, ("custom_org_id",))
    emp = world.public_company(rng, "employer") if rng.random() < 0.5 else world.company_name(rng)
    subj = [pick(rng, "Self assessment 2025/26", "Your tax return - documents needed", "Re: P60 and UTR",
                 "Client "), cid if rng.random() < 0.3 else ""]
    m = [
        (acc, cl, [[pick(rng, "We are preparing your self assessment return for the 2025/26 tax year. ",
                         "Just a reminder that the online filing deadline is 31 January. "),
                    "Could you send us your UTR and the P60 from ", emp, "?"],
                   ["For our records your ", lab.lower(), " is ", cid, ". Our fee for this year is ",
                    amount(rng, 250, 950, step=5), " plus VAT."]], True),
        (cl, acc, [["Hi, my UTR is ", utr, " and my NI number is ", cl.p.ni(), ". P60 attached."]
                   + ([" I also had rental income from ", world.make_address(rng).inline(rng, cl.p.ref), "."] if rng.random() < 0.5 else [])
                   + _cw_trap(rng, c)], False),
        (acc, cl, [["Thank you, ", cl.p.title + " ", cl.p.last_name(), ". We will send the draft return for approval by ",
                    date_text(rng, recent_date(rng, 5, 40)), "."]], True),
    ]
    return subj, m


def _t_hr(rng, c):
    org = rng.choice(world.ORGS_BY_KIND["employer"])
    hr = Party(rng, c.new(), org, pick(rng, "HR Advisor", "People Partner", "Payroll Officer", "HR Administrator"), work=True)
    emp = Party(rng, c.new(), org, pick(rng, "Warehouse Operative", "Account Manager", "Care Assistant", "Developer"),
                work=rng.random() < 0.5)
    lab, eid = org.custom(rng)
    new_addr = world.make_address(rng)
    subj = [pick(rng, "Change of bank details", "Payroll - change of address", "Re: new address and bank details",
                 "Updated details for payroll")]
    m = [
        (emp, hr, [[pick(rng, "Please can you update my details for payroll. ", "I've moved house and changed banks. "),
                    "My ", lab.lower(), " is ", eid, "."],
                   ["New address:\n", new_addr.block(rng, emp.p.ref)],
                   ["New bank: ", emp.p.bank_name, ", sort code ", emp.p.sort_code(), ", account number ", emp.p.account(rng.random() < 0.2), "."]],
         rng.random() < 0.5),
        (hr, emp, [["Thanks ", emp.p.first_name(), ". For security we need to confirm this by phone. ",
                    "Can you confirm your date of birth and the last four digits of your old account?"]], True),
        (emp, hr, [["Sure, DOB is ", emp.p.dob(), ". Old account ended ", E(ids.account_number(rng)[-4:], "BANK_ACCOUNT", emp.p.ref,
                                                                              ("partial_number",)), ". Best number is ", emp.p.mobile(), "."]], False),
        (hr, emp, [["All updated. The change will apply from the ", K(pick(rng, "November", "December", "March", "April"), "date"),
                    " payroll, paid on ", date_text(rng, recent_date(rng, 0, 40)), "."]], True),
    ]
    return subj, m


def _t_legal(rng, c):
    org = rng.choice(world.ORGS_BY_KIND["law"])
    sol = Party(rng, c.new(), org, pick(rng, "Associate Solicitor", "Partner", "Conveyancing Executive", "Paralegal",
                                       "Trainee Solicitor"), work=True)
    cl = Party(rng, c.new())
    lab1 = next(iter(org.ids))
    lab2 = list(org.ids)[-1]
    _, ccode = org.custom(rng, lab1)
    _, matter = org.custom(rng, lab2)
    prop = world.make_address(rng)
    subj = [pick(rng, "Your purchase of ", "Sale of ", "Completion - ", "ID documents - "), _street(prop, None),
            pick(rng, "", " (", " - our ref ")]
    if subj[-1]:
        subj += [matter, ")" if subj[-1] == " (" else ""]
    m = [
        (sol, cl, [["Thank you for instructing us on the ", pick(rng, "purchase", "sale", "remortgage"), " of ",
                    prop.inline(rng, None), ". Your ", lab1.lower(), " is ", ccode, " and the ", lab2.lower(), " is ", matter, "."],
                   [pick(rng, "Before we can proceed we need to verify your identity under the ",
                         "As required by the "), K("Money Laundering Regulations 2017", "statute"),
                    pick(rng, ". Please send a certified copy of your passport or driving licence.",
                         ". Please bring your passport to our office.")]], True),
        (cl, sol, [[pick(rng, "Thanks. My passport number is ", "As requested, my passport number is ", "Passport no. "),
                    cl.p.passport(), pick(rng, " and my driving licence is ", " and licence number "), cl.p.licence(), "."],
                   ["The deposit of ", amount(rng, 5000, 60000, step=500), " will come from my account (sort code ", cl.p.sort_code(),
                    ", account ", cl.p.account(), ")."]], False),
        (sol, cl, [["Thank you. Completion is now agreed for ", date_text(rng, recent_date(rng, 0, 60)), ". Please do not send money ",
                    "to any account other than the one on our letterhead; we will never change our bank details by email."]], True),
    ]
    return subj, m


def _t_insurance(rng, c):
    org = rng.choice(world.ORGS_BY_KIND["insurer"])
    h = Party(rng, c.new(), org, pick(rng, "Claims Handler", "Senior Claims Adviser", "Customer Service"), work=True)
    ph = Party(rng, c.new())
    labs = list(org.ids)
    _, pol = org.custom(rng, labs[0])
    _, clm = org.custom(rng, labs[-1])
    tp = c.new()
    inc = recent_date(rng, 90)
    subj = [pick(rng, "Claim ", "Your claim ", "Re: claim "), clm]
    what = rng.randrange(3)
    if what == 0:
        incident = ["water leaked from the flat above and damaged my kitchen ceiling"]
    else:
        incident = [pick(rng, "my bike was stolen from outside ", "a delivery van reversed into my garden wall at ") if what == 1 else
                    "a tree from next door fell onto my shed at ",
                    world.make_address(rng).inline(rng, ph.p.ref) if rng.random() < 0.6 else "my home"]
    m = [
        (ph, h, [["I'd like to make a claim on policy ", pol, ". On ", date_text(rng, inc), " "] + incident + ["."],
                 ["The other party is ", tp.full(), pick(rng, ", phone ", ", contact number "), tp.phone(), "."]], rng.random() < 0.5),
        (h, ph, [["Thank you, ", ph.p.title + " ", ph.p.last_name(), ". Your claim reference is ", clm,
                  ". Please quote it in all correspondence. The excess on your policy is ", amount(rng, 100, 500, step=50), "."]], True),
        (ph, h, [["Thanks. Photos attached. The repair quote is ", amount(rng, 300, 4800), ". You can reach me on ",
                  ph.p.mobile(), "."]], False),
    ]
    return subj, m


def _t_personal(rng, c):
    a = Party(rng, c.new())
    b = Party(rng, c.new())
    addr = world.make_address(rng, flat_rate=0.4)
    when = recent_date(rng, 0, 60)
    subj = [pick(rng, "Saturday plans", "Party at ours!", "re: the weekend", "Address for the card", "Booking details", "hi")]
    m = [
        (a, b, [[pick(rng, "Hope you're well! ", "Long time no speak. ", ""), "We're having a ",
                 pick(rng, "housewarming", "birthday do", "barbecue", "leaving drinks"), " on ", date_text(rng, when),
                 ". The new place is ", addr.inline(rng, a.p.ref), "."],
                [pick(rng, "Bring ", "Can you bring "), pick(rng, "a bottle", "some snacks", "a chair", "the speaker"),
                 " if you can. My new number is ", a.p.mobile(), "."] + _cw_trap(rng, c)], False),
        (b, a, [[pick(rng, "Sounds great, ", "Count us in! ", "Yes please, "), pick(rng, "we'll be there. ", "see you then. "),
                 pick(rng, "Is it OK if ", "Can "), c.new().first_name(), pick(rng, " comes too?", " tag along?")]], False),
        (a, b, [[pick(rng, "Of course! ", "Course! ", "Yes! "), "For the booking I need everyone's dates of birth, mine's ",
                 a.p.dob(), ", what's yours?"]], False),
        (b, a, [["It's ", b.p.dob(), ". See you on the ", K(ids.ordinal(when.day), "date"), "!"]], False),
    ]
    return subj, m


def _t_recruit(rng, c):
    rec = Party(rng, c.new(), world.Org(world.company_name(rng).text, "recruiter", "talentbridge.co.uk"),
                pick(rng, "Recruitment Consultant", "Talent Partner", "Senior Recruiter"), work=True)
    cand = Party(rng, c.new())
    ref1 = c.new()
    co = world.public_company(rng, "employer") if rng.random() < 0.5 else world.company_name(rng)
    subj = [pick(rng, "Interview confirmation", "Your application - next steps", "References", "Re: role at "), co if rng.random() < 0.3 else ""]
    m = [
        (rec, cand, [["Thanks for sending your CV. ", co, " would like to interview you on ",
                      date_text(rng, recent_date(rng, 0, 30)), " at ", K(f"{rng.randint(9, 16)}:{pick(rng, '00', '30')}", "date"), "."],
                     ["The salary range is ", amount(rng, 26000, 70000, style=1, step=1000), " to ",
                      amount(rng, 70000, 95000, style=1, step=1000), ". Could you send two referees?"]], True),
        (cand, rec, [["Thanks! My referees are ", ref1.full(), " (", pick(rng, "my line manager", "former manager", "team lead"),
                      ", ", ref1.phone(), ", ", ref1.email(), ")"] + [" and ", c.new().full(), "."] if rng.random() < 0.6 else
                     ["Thanks! My referee is ", ref1.full(), ", ", ref1.phone(), "."]], False),
        (rec, cand, [["Great, I'll contact ", ref1.title_last(), " this week."]], True),
    ]
    return subj, m


def _t_billing(rng, c):
    org = rng.choice(world.ORGS_BY_KIND[pick(rng, "energy", "telecom", "water")])
    agent = Party(rng, c.new(), org, pick(rng, "Customer Care Team", "Billing Specialist", "Customer Support"), work=True)
    cust = Party(rng, c.new())
    lab, acc = org.custom(rng)
    addr = world.make_address(rng)
    subj = [pick(rng, "Wrong bill", "Complaint about my bill", "Final bill - moving out", "Meter reading"), " - ",
            lab, " ", acc]
    m = [
        (cust, agent, [[pick(rng, "My latest bill is ", "I was charged "), amount(rng, 80, 640), pick(rng, " which is far too high. ", ". That can't be right. "),
                        "My ", lab.lower(), " is ", acc, " and the supply address is ", addr.inline(rng, cust.p.ref), "."],
                       ["I paid by card ending ", cust.p.card_last4(), " on ", date_text(rng, recent_date(rng, 30)), "."]], rng.random() < 0.4),
        (agent, cust, [["Thanks for contacting ", org.name, ". I've checked ", lab.lower(), " ", acc,
                        " and the bill used an estimated reading. Could you send a photo of your meter?"]], True),
        (cust, agent, [["Reading today is ", str(rng.randint(10000, 99999)), ". Please call me on ", cust.p.phone(), " if you need anything else."]], False),
    ]
    return subj, m


TOPICS = [(_t_tenancy, 14), (_t_accounts, 10), (_t_hr, 12), (_t_legal, 12), (_t_insurance, 10), (_t_personal, 12),
          (_t_recruit, 8), (_t_billing, 12)]

NEG_EMAILS = [
    ("Office closed for the bank holiday", "Facilities Team", "All Staff",
     ["The office will be closed on {date}. Normal hours resume the following day.",
      "If you need to collect anything, the {place} entrance will be open until 4pm on the Friday before.",
      "We will run the fire alarm test at 10am on {date2} as usual."]),
    ("IT maintenance this weekend", "IT Service Desk", "All Users",
     ["Planned maintenance on the {prod} systems will take place from 8pm on {date}.",
      "You may need to restart your laptop on Monday. Saved work will not be affected.",
      "Please do not raise tickets for slow VPN during the window."]),
    ("Your {month} update from {co}", "{co}", "Customers",
     ["Prices change on {date}. The standing charge will be {amt} per day and the unit rate {amt2} per kWh.",
      "Read more about the {statute} and your rights on our website.",
      "You don't need to do anything if you pay by Direct Debit."]),
    ("Team lunch - menu choices", "Social Committee", "Team",
     ["Lunch is booked at {place} on {date}. The budget is {amt} per head.",
      "Please choose from the menu by Wednesday. Vegetarian and vegan options are available.",
      "We hope to see everyone there."]),
    ("Policy update: expenses", "Finance", "All Staff",
     ["From {date} the mileage rate for business travel is 45p per mile for the first 10,000 miles.",
      "Hotel bookings above {amt} a night need approval in advance.",
      "Receipts must be uploaded within 30 days."]),
    ("New tenancy guidance", "Compliance", "Lettings Team",
     ["The {tstatute} changes how notices are served from {date}.",
      "Section 21 notices will no longer be valid once the new rules apply. Use the updated templates on the shared drive.",
      "Training sessions will run at {place} next month."]),
    ("Quarterly results summary", "Leadership Team", "All Colleagues",
     ["Revenue for the quarter was {amt}, up 8% on last year.",
      "Our partnership with {co} goes live on {date}.",
      "Thank you all for your hard work. May the next quarter be just as good."]),
]


def _neg_email(rng, d: Doc):
    subj, frm, to, paras = rng.choice(NEG_EMAILS)
    d.v("neg" + str(NEG_EMAILS.index((subj, frm, to, paras))))
    co = world.public_company(rng, pick(rng, "energy", "telecom", "retail", "bank", "water"))
    kw = dict(date=date_text(rng, recent_date(rng, 0, 60)), date2=date_text(rng, recent_date(rng, 0, 90)),
              place=world.place_trap(rng), prod=world.product(rng), co=co,
              month=K(pick(rng, "January", "April", "October", "November"), "date"),
              amt=amount(rng, 0.2, 180000), amt2=amount(rng, 0.1, 0.4), statute=world.statute(rng),
              tstatute=K(pick(rng, "Renters' Rights Act 2025", "Housing Act 1988", "Renting Homes (Wales) Act 2016"), "statute"))
    st = rng.randrange(6)
    d.f("From: " + frm + "\nTo: " + to + "\nDate: {dt}\nSubject: " + subj + "\n\n", dt=K(_email_dt(_when(rng), st), "date"), **kw)
    d.add(pick(rng, "Dear customer,\n\n", "Hello,\n\n", "") if "{co}" in frm else pick(rng, "Hi all,\n\n", "Dear colleagues,\n\n", "Hello,\n\n", "All,\n\n", ""))
    ps = list(paras)
    if rng.random() < 0.5:
        rng.shuffle(ps)
    for p in ps[: rng.randint(2, len(ps))]:
        d.f(p + "\n\n", **kw)
    d.add(pick(rng, "Thanks,\n", "Kind regards,\n", "Best wishes,\n", ""))
    if "{co}" in frm:
        d.f("The {co} team", co=co)
    else:
        d.add(pick(rng, "The ", "") + frm)


@register("email_thread", weight=9, neg_weight=10)
def email_thread(rng: random.Random, neg: bool) -> Doc:
    d = Doc("email_thread", "email_thread/v1")
    if neg:
        _neg_email(rng, d)
        return d
    c = Cast(rng, common_word_rate=0.1)
    fn = rng.choices([t for t, _ in TOPICS], [w for _, w in TOPICS])[0]
    subj, msgs = fn(rng, c)
    n = rng.choices([1, 2, 3, 4], [25, 35, 25, 15])[0]
    msgs = msgs[:n]
    d.v(fn.__name__)
    dt = _when(rng)
    times = []
    for _ in msgs:
        times.append(dt)
        dt = dt + timedelta(hours=rng.randint(1, 60), minutes=rng.randint(0, 59))
    st = rng.randrange(6)
    style = rng.choices(["gmail", "outlook", "export"], [45, 30, 25])[0]
    d.v(style)
    bodies = [_body(rng, s, r, paras, formal) for (s, r, paras, formal) in msgs]
    cc = None
    if rng.random() < 0.2:
        s0 = msgs[0][0]
        cc = Party(rng, c.new(), s0.org, None, work=s0.org is not None)

    def headers(i: int, outlook: bool, full: bool = True) -> list:
        s, r, _, _ = msgs[i]
        out = ["From: ", s.header(rng, outlook), "\n"]
        date_lab = "Sent: " if outlook else "Date: "
        if not outlook:
            out += ["To: ", r.header(rng), "\n"]
            if cc is not None and i == len(msgs) - 1:
                out += ["Cc: ", cc.header(rng), "\n"]
        out += [date_lab, K(_email_dt(times[i], st), "date"), "\n"]
        if outlook:
            out += ["To: ", r.header(rng, outlook), "\n"]
            if cc is not None and full:
                out += ["Cc: ", cc.header(rng, outlook), "\n"]
        out += ["Subject: ", "Re: " if i > 0 else "", subj, "\n"]
        return out

    if style == "export":
        for i in range(len(msgs)):
            if i:
                d.add(pick(rng, "\n\n---\n\n", "\n\n________________________________\n\n", "\n\n"))
            d.add(headers(i, False), "\n", bodies[i])
        return d
    last = len(msgs) - 1
    if style == "gmail":  # nested quoting: each reply quotes the whole previous block
        block = bodies[0]
        for i in range(1, len(msgs)):
            s = msgs[i - 1][0]
            block = [bodies[i], "\n\n", "On ", K(_email_dt(times[i - 1], 3 if rng.random() < 0.6 else 0), "date"), ", ",
                     s.header(rng), " wrote:\n", quote(block)]
        d.add(headers(last, False), "\n", block)
        return d
    # outlook: newest first, older messages appended below their own header blocks
    d.add(headers(last, True), "\n", bodies[last])
    for i in range(last - 1, -1, -1):
        d.add("\n\n", pick(rng, "-----Original Message-----\n", "________________________________\n"),
              headers(i, True), "\n", bodies[i])
    return d


# =========================================================================== chats
FILLERS = ["ok", "thanks!", "np", "lol", "on my way", "can't talk, in a meeting", "sounds good x", "ta", "haha",
           "yeah", "cheers", "nice one", "omg", "brb", "ok cool", "perfect, thank you", "yep", "no worries",
           "will do", "hang on", "sorry only just seen this", "👍", "😂", "great stuff", "ok thx", "speak later",
           "ah ok", "fab", "kk", "brilliant"]


def _ex_address(rng, a, b, ctx):
    addr = world.make_address(rng, flat_rate=0.4)
    need = pick(rng, "for the delivery", "for the christmas card", "for the taxi", "so I can post the keys", "")
    out = [(a, [pick(rng, "what's your address again? ", "can you send me your address ", "whats ur address "), need])]
    if rng.random() < 0.5:
        out.append((b, [addr.inline(rng, b.ref, postcode=False)]))
        out.append((b, [pick(rng, "postcode ", "pc is ", ""), addr.postcode(b.ref, lower=rng.random() < 0.5)]))
    else:
        out.append((b, [addr.inline(rng, b.ref)]))
    return out


def _ex_bank(rng, a, b, ctx):
    thing = pick(rng, "the tickets", "the deposit", "your half of the bill", "the takeaway", "the hen do", "petrol")
    out = [(a, [pick(rng, "can you send me your bank details? ", "send me ur bank details "), "I'll transfer ", amount(rng, 8, 900), " for ", thing])]
    r = rng.random()
    if r < 0.5:
        out.append((b, [b.full() if rng.random() < 0.5 else b.initial_last(), " ", b.sort_code(), " ", b.account()]))
    elif r < 0.8:
        out.append((b, ["sort code ", b.sort_code(), "\nacc ", b.account()]))
    else:
        out.append((b, ["IBAN is ", b.iban()]))
    out.append((a, [pick(rng, "sent 👍", "done, sent", "transferred", "paid!")]))
    return out


def _ex_card(rng, a, b, ctx):
    return [(a, [pick(rng, "my card ending ", "card ending in "), a.card_last4(), pick(rng, " keeps getting declined at ", " got declined at "),
                 world.public_company(rng, "retail")]),
            (b, [pick(rng, "ring ", "call "), world.public_company(rng, "bank"), pick(rng, ", it's probably a fraud block", " they'll sort it")])]


def _ex_ni(rng, a, b, ctx):
    return [(a, [pick(rng, "HR need your NI number for the form", "what's your national insurance number? for the payroll form",
                     "need ur NI no for the agency", "the accountant wants your NI number", "can u send ur national insurance no",
                     "new job needs my NI number and I can't find it, is it on your copy of the P60?"), pick(rng, "", " pls", " asap", " x")]),
            (b, [b.ni()])]


def _ex_dob(rng, a, b, ctx):
    return [(a, [pick(rng, "what's your DOB for the booking?", "need your date of birth for the insurance quote",
                     "dob? doing the railcard", "what's your birthday again? filling in the GP form", "date of birth for the flight?",
                     "the vet form wants the owner's DOB lol, what's yours")]),
            (b, [b.dob().with_hard("dob_near_dates") if rng.random() < 0.2 else b.dob()])]


def _ex_phone(rng, a, b, ctx):
    p3 = ctx["cast"].new()
    r = rng.random()
    if r < 0.5:
        return [(a, [pick(rng, "new number btw, it's ", "save this number ", "this is my new number: "), a.mobile()]),
                (b, [pick(rng, "saved", "got it", "ok saved x")])]
    return [(a, [p3.first_name(), pick(rng, " the plumber", " from the garage", " (the electrician)"), " is coming ",
                 K(pick(rng, "tomorrow", "Thursday", "on the 14th", "Monday morning"), "date"), ", ", pick(rng, "his", "their"), " number is ", p3.phone()]),
            (b, [pick(rng, "great, thanks", "cool", "ok") if rng.random() < 0.6 else ["ok I'll text ", p3.first_name()]])]


def _ex_email(rng, a, b, ctx):
    return [(a, [pick(rng, "whats ur email? sending the photos", "can you send me your email for the invite", "email address?",
                     "what email do you use for the school stuff?", "send me your email and I'll forward the tickets",
                     "need your email for the ", ), pick(rng, "", "Airbnb", "group booking", "landlord")]),
            (b, [b.email()])]


def _ex_passport(rng, a, b, ctx):
    return [(a, [pick(rng, "need passport numbers for the ", "booking the "), world.public_company(rng, "transport"), " flights, what's yours?"]),
            (b, [b.passport(), pick(rng, ", expires ", " exp "), date_text(rng, recent_date(rng, 0, 3000))])]


def _ex_landlord(rng, a, b, ctx):
    ll = ctx["cast"].new()
    return [(a, [pick(rng, "landlord ", "my landlord "), ll.title_last() if rng.random() < 0.6 else ll.full(),
                 pick(rng, " says the boiler man is coming ", " wants to do an inspection ", " finally replied, coming round "),
                 K(pick(rng, "Friday", "next week", "tomorrow at 10"), "date")]),
            (b, [pick(rng, "about time", "finally", "ugh ok"), " lol"])]


def _ex_meet(rng, a, b, ctx):
    return [(a, [pick(rng, "meet at ", "shall we say ", "see you at "), world.place_trap(rng), " at ", str(rng.randint(5, 9)), pick(rng, "?", "pm?", "")]),
            (b, [pick(rng, "yes!", "perfect", "might be late, train's delayed", "ok")])]


def _ex_rent(rng, a, b, ctx):
    return [(a, ["rent's going up to ", amount(rng, 500, 2200, step=5), " from ", date_text(rng, recent_date(rng, 0, 90))]),
            (b, [pick(rng, "seriously?", "that's mad", "can they do that?"), " ", pick(rng, "we'll have to", "I'll check the contract", "")])]


def _ex_work(rng, a, b, ctx):
    org = rng.choice(world.ORGS_BY_KIND[pick(rng, "law", "accountant", "letting", "insurer")])
    lab, cid = org.custom(rng)
    cl = ctx["cast"].new()
    return [(a, [pick(rng, "can you pull up ", "have you got the file for ", "quick q about "), cl.full() if rng.random() < 0.5 else cl.title_last(),
                 pick(rng, "? ", " - "), lab.lower(), " ", cid]),
            (b, [pick(rng, "yep, ", "on it, ", "found it, "), cl.possessive() if rng.random() < 0.5 else "the",
                 pick(rng, " file is on the shared drive", " docs are with compliance", " bundle is ready to send")])]


EXCHANGES = [(_ex_address, 14), (_ex_bank, 12), (_ex_card, 6), (_ex_ni, 5), (_ex_dob, 6), (_ex_phone, 10), (_ex_email, 6),
             (_ex_passport, 4), (_ex_landlord, 6), (_ex_meet, 5), (_ex_rent, 4), (_ex_work, 6)]

NEG_EXCHANGES = [
    ["did you see {co} has the {prod} for {amt}?", "no way, that's cheap", "deal ends {date} apparently"],
    ["meet at {place} at {time}?", "yep see you there", "running {n} mins late sorry"],
    ["the {bill} was {amt} this month", "ouch", "we should switch to {co}"],
    ["train's cancelled again", "typical", "get the bus from {place}"],
    ["are we still on for {date}?", "yes! I'll bring snacks", "great"],
    ["I hope the interview goes well {day}", "thank you! so nervous", "you'll smash it"],
    ["how much was the deposit in the end?", "{amt}", "not bad for {place}"],
    ["parcel says delivered but nothing here", "check with the neighbours", "found it, behind the bin lol"],
    ["{co} app is down again", "mine too", "they said it'll be back by {time}"],
    ["what time is the match {day}?", "{time} I think", "pub after?"],
    ["got the quote for the boiler: {amt}", "that's steep", "get another one from {co}"],
    ["rent's going up {n}% from {date}", "seriously", "may be worth asking for a longer fixed term"],
    ["can you grab milk from {co} on the way back?", "will do", "and bread pls"],
    ["did the {prod} arrive?", "yes, box was soaked though", "send it back, {co} will refund"],
    ["bin day moved to {day}", "since when", "council letter came {date}"],
    ["is the {place} open on bank holidays?", "think so, til {time}", "ok"],
    ["electric is {amt} a month now", "we need to stop using the dryer", "or switch to {co}"],
    ["booked the table for {n} at {time}", "amazing", "I'll let the others know"],
]


def _label(rng, p: Person, fmt: str):
    r = rng.random()
    if fmt in ("slack", "teams"):
        return p.full() if r < 0.8 else p.first_name()
    if r < 0.55:
        return p.first_name()
    if r < 0.7:
        return p.full()
    if r < 0.82:
        return p.nickname()
    if r < 0.9:
        return [p.first_name(), " ", pick(rng, "Plumber", "Work", "Gym", "Uni", "(landlord)", "Neighbour")]
    return K(pick(rng, "Mum", "Dad", "Nan", "Landlord", "Babe", "Bro"), "relationship_word")


def _chat_lines(rng, d: Doc, fmt: str, lines: list, labels: dict, start: datetime, title: list):
    t = start
    if title:
        d.add(title, "\n\n" if fmt in ("slack", "teams") else "\n")
    prev_day = None
    for who, segs in lines:
        t = t + timedelta(minutes=rng.choice([0, 1, 1, 2, 3, 5, 8, 15, 40, 90]), seconds=rng.randint(0, 59))
        lab = labels[who]
        day = K(f"{t.day:02d}/{t.month:02d}/{t.year}", "date")
        if fmt == "wa_ios":
            d.add("[", day, f", {t.hour:02d}:{t.minute:02d}:{t.second:02d}] ", lab, ": ", segs, "\n")
        elif fmt == "wa_android":
            d.add(day, f", {t.hour:02d}:{t.minute:02d} - ", lab, ": ", segs, "\n")
        elif fmt == "slack":
            h12 = (t.hour - 1) % 12 + 1
            d.add(lab, f"  {h12}:{t.minute:02d} {'AM' if t.hour < 12 else 'PM'}\n", segs, "\n\n")
        elif fmt == "teams":
            d.add(f"[{t.hour:02d}:{t.minute:02d}] ", lab, "\n", segs, "\n\n")
        elif fmt == "sms":
            if prev_day != t.date():
                d.add(K(f"{WD[t.weekday()]} {t.day} {ids.MONTHS[t.month - 1][:3]}", "date"), f" {t.hour:02d}:{t.minute:02d}\n")
                prev_day = t.date()
            d.add(lab, ": ", segs, "\n")
        else:
            d.add(lab, ": ", segs, "\n")


@register("chat_messages", weight=12, neg_weight=15, short=True)
def chat_messages(rng: random.Random, neg: bool) -> Doc:
    d = Doc("chat_messages", "chat_messages/v1")
    fmt = rng.choices(["wa_ios", "wa_android", "sms", "slack", "teams", "plain"], [25, 15, 20, 12, 8, 20])[0]
    d.v(fmt)
    start = _when(rng, 300)
    if neg:
        conv = rng.choice(NEG_EXCHANGES)
        d.v("neg" + str(NEG_EXCHANGES.index(conv)))
        kw = dict(co=world.public_company(rng, pick(rng, "retail", "energy", "telecom", "bank")), prod=world.product(rng),
                  amt=amount(rng, 5, 1500), date=date_text(rng, recent_date(rng, 20, 30)), place=world.place_trap(rng),
                  bill=pick(rng, "gas bill", "electric", "water bill", "council tax", "broadband"), n=str(rng.randint(2, 20)),
                  time=K(pick(rng, "7", "half 6", "8pm", "19:30", "noon", "6ish", "3"), "date"),
                  day=K(pick(rng, "tomorrow", "on Saturday", "Thursday", "next week", "tonight"), "date"))
        labels = {0: pick(rng, "Me", "You"), 1: "Them"}
        if rng.random() < 0.3:
            labels = {0: "Me", 1: K(pick(rng, "Mum", "Dad", "Landlord", "Work"), "relationship_word")}
        lines = []
        convs = [conv] + ([rng.choice(NEG_EXCHANGES)] if rng.random() < 0.45 else [])
        for cv_ in convs:
            first = rng.randrange(2)
            for i, m in enumerate(cv_[: rng.randint(2, 3)]):
                lines.append(((first + i) % 2, _f(m, **kw)))
            for _ in range(rng.choice([0, 1, 1, 2])):
                lines.append((rng.randrange(2), [rng.choice(FILLERS)]))
        _chat_lines(rng, d, fmt if fmt not in ("slack", "teams") else "plain", lines, labels, start, [])
    else:
        c = Cast(rng, common_word_rate=0.14)
        n_people = 2 if rng.random() < 0.8 else 3
        people = [c.new() for _ in range(n_people)]
        ctx = {"cast": c}
        labels = {}
        for i, p in enumerate(people):
            if i == 0 and fmt in ("plain", "sms") and rng.random() < 0.4:
                labels[i] = pick(rng, "Me", "You")
            else:
                labels[i] = _label(rng, p, fmt)
        lines = []
        k = rng.choices([1, 2, 3], [50, 35, 15])[0]
        for _ in range(k):
            fn = rng.choices([e for e, _ in EXCHANGES], [w for _, w in EXCHANGES])[0]
            ai, bi = rng.sample(range(n_people), 2)
            for who, segs in fn(rng, people[ai], people[bi], ctx):
                idx = people.index(who) if who in people else ai
                lines.append((idx, segs))
            for _ in range(rng.choice([0, 0, 1, 1, 2, 3])):
                lines.append((rng.randrange(n_people), [rng.choice(FILLERS)]))
        # mention a common-word person by name and plant the ordinary word nearby
        for i, p in enumerate(people):
            if p.common_word:
                ph = _cwp(rng, p.first)
                other = (i + 1) % n_people
                a_, b_ = rng.choice([("is ", " coming?"), ("has ", " paid yet?"), ("did ", " see it?"), ("tell ", " I said hi"),
                                     ("ask ", " if that's ok")])
                lines.insert(rng.randrange(len(lines) + 1), (other, [a_, p.first_name(), b_] + ([" ", ph] if ph else [])))
                break
        if rng.random() < 0.3:
            if rng.random() < 0.25:
                lines.insert(0, (0, ["hi it's ", people[0].first_name(), pick(rng, "", " x", ", new number")]))
            else:
                lines.insert(0, (rng.randrange(n_people), [pick(rng, "hiya", "hey", "morning!", "you about?")]))
        while len(lines) < 3:
            lines.insert(rng.randrange(len(lines) + 1), (rng.randrange(n_people), [rng.choice(FILLERS)]))
        lines = lines[:15]
        title = []
        if fmt == "sms" and rng.random() < 0.6:
            p = people[1]
            title = [pick(rng, "Messages with ", "Conversation with ", ""), p.first_name() if rng.random() < 0.6 else p.full(),
                     " (", p.mobile(), ")"]
        elif fmt == "slack":
            title = [pick(rng, "#general", "#client-queries", "#lettings", "#payroll", "#ops"), pick(rng, "", " | Today")]
        elif fmt == "wa_ios" and rng.random() < 0.2:
            title = [K("Messages and calls are end-to-end encrypted.", "system_text")]
        _chat_lines(rng, d, fmt, lines, labels, start, title)
    if rng.random() < 0.22:
        d.atoms = noise.lower_all(d.atoms)
        d.v("lower")
    if rng.random() < 0.3:
        d.atoms = noise.typos(d.atoms, rng, 0.05)
        d.v("typos")
    return d


# =========================================================================== support tickets
# Sentence pools: every slot has several wordings so tickets about the same issue still differ.
_C_GREET = ["", "", "Hi,\n\n", "Hello,\n\n", "Hi there,\n\n", "Hi team,\n\n", "Dear Sir/Madam,\n\n", "To whom it may concern,\n\n",
            "Good morning,\n\n", "Hiya,\n\n", "Hello support,\n\n", "Evening,\n\n"]
_C_CONTEXT = [
    "I've been a customer for {n} years and this has never happened before.",
    "This is the {nth} time I've contacted you about this.",
    "Your chat bot kept sending me round in circles.",
    "I tried ringing but gave up after an hour on hold.",
    "I'm away from {date} so a quick reply would be appreciated.",
    "Screenshot attached.",
    "Not impressed, to be honest.",
    "Any help would be appreciated.",
    "My partner set the account up originally, if that matters.",
    "I've already read the FAQ and it doesn't cover this.",
    "Please don't close this ticket until it's actually sorted.",
    "Happy to give more details if needed.",
    "I'm writing from my phone so apologies for typos.",
    "I need this fixed before the end of the month.",
    "A friend had the same problem last week.",
    "I'd rather not have to escalate this.",
]
_C_SIGN = ["", "Thanks,\n", "Regards,\n", "Cheers\n", "Many thanks,\n", "Kind regards,\n", "Thanks in advance,\n", "Best,\n", "Ta\n"]
_NTH = ["second", "third", "fourth", "fifth"]


def _ctx_sentence(rng) -> list:
    return _f(rng.choice(_C_CONTEXT), n=str(rng.randint(2, 14)), nth=rng.choice(_NTH),
              date=date_text(rng, recent_date(rng, 0, 40)))


def _iss_refund(rng, cust, lab, cid):
    order = world.doc_ref(rng, "order")
    subj = pick(rng, "Refund not received", "Where is my refund?", "Refund still pending", "Chasing a refund", "Refund for returned item")
    p1 = [pick(rng, "I returned ", "I sent back ", "Your courier collected "), pick(rng, "my order ", "order ", "the items from order "), order,
          pick(rng, " on ", " back on ", " on "), date_text(rng, recent_date(rng, 40)), pick(rng, " and I still haven't had my money back. ",
                                                                                      " but the refund hasn't arrived. ",
                                                                                      ". The tracking shows it was received. ")]
    p2 = [pick(rng, "The amount was ", "I'm owed ", "It should be "), amount(rng, 6, 450), pick(rng, " to my card ending ", " back to the card ending in ",
                                                                                             " on the Mastercard ending "),
          cust.card_last4(), "."]
    if rng.random() < 0.5:
        p2 += [" ", pick(rng, "My ", "For reference, my ", "The "), lab.lower(), " is ", cid, "."]
    acts = ["I can see the return was received and I've pushed the refund through manually.",
            "The refund was approved today; banks usually take 3 to 5 working days to show it.",
            "Our returns team has confirmed the item and released the refund.",
            "I've asked the finance team to trace the payment."]
    return subj, [p1, p2], acts, "refund"


def _iss_delivery(rng, cust, lab, cid):
    addr = world.make_address(rng, flat_rate=0.6)
    order = world.doc_ref(rng, "order")
    subj = pick(rng, "Parcel not delivered", "Order marked delivered but not here", "Missing delivery", "Where is my parcel?",
                "Delivery failed again")
    p1 = [pick(rng, "My order ", "Order ", "Parcel for order "), order, pick(rng, " says delivered on ", " was marked as delivered on ",
                                                                            " should have arrived on "),
          date_text(rng, recent_date(rng, 12)), pick(rng, " but nothing arrived.", ", nothing here.", " but I've checked with neighbours and it isn't there.",
                                                     ". The photo shows someone else's door.")]
    p2 = [pick(rng, "Please redeliver to:\n", "Can you resend it to:\n", "The correct address is:\n", "Address for delivery:\n"),
          addr.block(rng, cust.ref)]
    if addr.flat:
        p2 += ["\n\n", pick(rng, "The flat number is often missed by drivers.", "Leave it with the concierge if I'm out.",
                            "Use the side entrance, the buzzer for my flat is broken.")]
    elif rng.random() < 0.6:
        p2 += ["\n\n", pick(rng, "Please leave it in the porch if I'm out.", "Don't leave it with next door again.",
                            "There's a safe place by the back gate.", "I work from home on Tuesdays and Thursdays.")]
    acts = ["I've opened an investigation with the courier.", "I've arranged a replacement to be sent by tracked delivery.",
            "The courier has 48 hours to respond to our claim.", "I've updated the delivery notes on your order."]
    return subj, [p1, p2], acts, "delivery"


def _iss_locked(rng, cust, lab, cid):
    subj = pick(rng, "Can't log in", "Account locked", "Locked out of my account", "Login not working", "Too many attempts - locked")
    p1 = [pick(rng, "I'm locked out of my account", "My account has been locked", "I can't get into my account"), " (", lab, ": ", cid, "). ",
          pick(rng, "The reset email goes to my old address ", "Reset links go to an email I no longer use: ", "I no longer have access to "),
          cust.email(), "."]
    p2 = [pick(rng, "My date of birth is ", "For verification, DOB ", "To prove it's me: date of birth "), cust.dob(),
          pick(rng, " and my postcode is ", ", postcode ", " and I live at postcode "), world.make_address(rng).postcode(cust.ref), "."]
    acts = ["I've unlocked the account and sent a reset link to the email on file.",
            "For security I can't change the login email by email; I've sent you a verification code instead.",
            "I've removed the lock; please reset your password within 24 hours.",
            "Your identity check passed and the account is now active again."]
    return subj, [p1, p2], acts, "account"


def _iss_gdpr(rng, cust, lab, cid):
    subj = pick(rng, "Delete my data", "Subject access request", "GDPR request", "Please erase my account", "Data request")
    sar = rng.random() < 0.5
    p1 = [pick(rng, "Under ", "In line with ", "As is my right under "), K(pick(rng, "UK GDPR", "Data Protection Act 2018"), "statute"),
          pick(rng, " I am asking for a copy of all personal data you hold about me. ", " please send me everything you hold on me. ") if sar else
          pick(rng, " I am asking you to delete all data you hold about me. ", " please erase my account and personal data. ")]
    rows = [("Name", cust.full()), ("Email", cust.email()), (lab, cid), ("Phone", cust.phone())]
    if rng.random() < 0.4:
        rows.append(("Previous address", world.make_address(rng).inline(rng, cust.ref)))
    rng.shuffle(rows)
    p2 = []
    for i, (k, v) in enumerate(rows[: rng.randint(2, len(rows))]):
        p2 += (["\n"] if i else []) + [k, pick(rng, ": ", " - ", ": "), v]
    acts = ["We'll respond within one calendar month as required.", "I've logged your request with our data protection team.",
            "Your account is scheduled for deletion; some records must be kept for 6 years for tax reasons.",
            "We'll send the data as an encrypted download link."]
    return subj, [p1, p2], acts, "gdpr"


def _iss_billing(rng, cust, lab, cid):
    order = world.doc_ref(rng, "order")
    subj = pick(rng, "Charged twice", "Billing dispute", "Wrong amount taken", "Overcharged on my bill", "Duplicate payment")
    p1 = [pick(rng, "I was charged ", "You took ", "My statement shows "), amount(rng, 5, 300),
          pick(rng, " twice on ", " two times on ", " more than agreed on "), date_text(rng, recent_date(rng, 25)),
          pick(rng, " for order ", " for invoice ", " against order "), order, ". "]
    p2 = [pick(rng, "The card used was the one ending ", "Card ending in ", "It went on my Visa ending ", "Payment card: ending "),
          cust.card_last4(), pick(rng, ". Please refund the duplicate payment.", ". I want the extra charge reversed.",
                                  ". Can you explain the second payment?")]
    acts = ["I can see the duplicate authorisation and have voided it.", "The second payment has been refunded.",
            "One of the payments is a pending authorisation and will drop off within 7 days.",
            "I've raised a billing adjustment for the difference."]
    return subj, [p1, p2], acts, "billing"


def _iss_ddbank(rng, cust, lab, cid):
    subj = pick(rng, "Change Direct Debit bank details", "New bank for Direct Debit", "Update payment details", "Switching banks")
    p1 = [pick(rng, "Please change my Direct Debit to my new account: ", "I've switched banks. New details: ", "Update my bank details to "),
          "sort code ", cust.sort_code(), pick(rng, ", account number ", ", acc ", " / account "), cust.account(), ". "]
    p2 = [pick(rng, "The account holder is ", "Name on the account: ", "Account name "), cust.full() if rng.random() < 0.6 else cust.caps(),
          ". ", pick(rng, "My ", "Our "), lab.lower(), " is ", cid, "."]
    acts = ["The new mandate is set up and will be used from your next payment.",
            "I've sent a confirmation letter for the new Direct Debit.",
            "Your next collection on the 1st will come from the new account."]
    return subj, [p1, p2], acts, "payment"


def _iss_moving(rng, cust, lab, cid):
    old, new = world.make_address(rng), world.make_address(rng, flat_rate=0.4)
    subj = pick(rng, "Moving home", "Change of address", "New address", "Moving out - update account", "Home move")
    p1 = [pick(rng, "I'm moving on ", "We move on ", "From "), date_text(rng, recent_date(rng, 0, 40)),
          pick(rng, ". Old address: ", ", so please update my address. Current address: ", ". Leaving "), old.inline(rng, cust.ref), "."]
    if rng.random() < 0.5:
        p2 = [pick(rng, "New address:\n", "Moving to:\n", "Please send everything to:\n"), new.block(rng, cust.ref), "\n\n",
              pick(rng, "My ", "Our "), lab.lower(), " is ", cid, "."]
    else:
        p2 = [pick(rng, "The new address is ", "We're going to ", "New place: "), new.inline(rng, cust.ref), ". ", lab, ": ", cid, "."]
    acts = ["I've updated your address from the move date.", "Your final bill for the old address will follow within 6 weeks.",
            "Everything is now set up at the new address.", "Please send meter readings on the day you move."]
    return subj, [p1, p2], acts, "moving"


def _iss_cancel(rng, cust, lab, cid):
    addr = world.make_address(rng)
    subj = pick(rng, "Cancel my account", "Cancellation request", "Please cancel", "End my contract", "Close account")
    p1 = [pick(rng, "I'd like to cancel from ", "Please cancel my plan from ", "I want to close my account on "),
          date_text(rng, recent_date(rng, 0, 30)), ". ", lab, " ", cid, ". ",
          pick(rng, "", "I've found a cheaper deal.", "I'm moving abroad.", "I no longer need the service.")]
    p2 = [pick(rng, "Send the final bill to my new address: ", "Final bill to: ", "Please post anything else to "), addr.inline(rng, cust.ref),
          ". ", pick(rng, "Refund any credit (", "There should be a credit of about ", "Return the balance ("), amount(rng, 2, 140),
          pick(rng, ") to the card on file.", " to my card.", ")."),]
    acts = ["Your cancellation is booked and you'll get a confirmation email.", "There's no early exit fee as you're out of contract.",
            "Your final bill will include any credit owed.", "I've stopped future payments."]
    return subj, [p1, p2], acts, "cancel"


def _iss_damaged(rng, cust, lab, cid):
    order = world.doc_ref(rng, "order")
    prod = world.product(rng)
    subj = pick(rng, "Item arrived damaged", "Broken on arrival", "Damaged parcel", "Faulty item", "Smashed in transit")
    p1 = [pick(rng, "The ", "My "), prod, pick(rng, " from order ", " (order ", " in order "), order,
          pick(rng, " arrived with a cracked screen.", ") arrived broken.", " was dented and won't switch on.", " came with the box crushed.")]
    p2 = [pick(rng, "Photos attached. ", "I've kept the packaging. ", ""), pick(rng, "I'd like a replacement", "Please send a new one",
                                                                              "I want a full refund"),
          pick(rng, ". You can call me on ", " - best number ", ". Reach me on "), cust.phone(), "."]
    acts = ["I've arranged a free collection and a replacement.", "A replacement is on its way and the courier will collect the damaged item.",
            "I've issued a full refund, no need to return it.", "Please keep the item until the courier collects it."]
    return subj, [p1, p2], acts, "damaged"


def _iss_upgrade(rng, cust, lab, cid):
    subj = pick(rng, "Upgrade my subscription", "Change of plan", "Want to upgrade", "Plan upgrade question", "Downgrade please")
    p1 = [pick(rng, "I'd like to move to the ", "Can I switch to the ", "Please upgrade me to the "), world.product(rng),
          pick(rng, " plan", " tier", " bundle"), pick(rng, " from next month. ", " today. ", ". "),
          pick(rng, "My ", "The "), lab.lower(), pick(rng, " is ", ": "), cid, "."]
    p2 = [pick(rng, "Is it still ", "Will it be ", "You advertised it at "), amount(rng, 4, 80), pick(rng, " a month?", " per month?", "/month.")]
    if rng.random() < 0.4:
        p2 += [" ", pick(rng, "Please use the card ending ", "Bill the card ending "), cust.card_last4(), "."]
    acts = ["Your plan has been changed and the new price applies from your next bill.",
            "I've applied the upgrade; any difference is charged pro rata.", "The offer price is valid for 12 months."]
    return subj, [p1, p2], acts, "plan"


def _iss_password(rng, cust, lab, cid):
    subj = pick(rng, "Password reset not arriving", "Reset link expired", "Can't reset password", "Forgot password", "2FA codes not arriving")
    p1 = [pick(rng, "The password reset email never arrives", "The reset link says it has expired", "I'm not getting the SMS code"),
          pick(rng, ". My login is ", ". I sign in with ", ". Account email: "), cust.email(), "."]
    p2 = [pick(rng, "Codes should go to ", "My mobile is ", "The number on the account is "), cust.mobile(),
          pick(rng, ". Checked spam already.", ". I've tried three times.", ".")]
    acts = ["I've resent the link; it's valid for one hour.", "Our email provider had a delay this morning, it should work now.",
            "I've reset two-factor on your account; set it up again after logging in."]
    return subj, [p1, p2], acts, "password"


def _iss_fraud(rng, cust, lab, cid):
    subj = pick(rng, "Fraud alert", "Payment I didn't make", "Suspicious transaction", "Someone used my account", "Unauthorised order")
    p1 = [pick(rng, "There is an order on my account I didn't place, for ", "Someone spent ", "I got an alert for a payment of "),
          amount(rng, 15, 900), pick(rng, " on ", " dated ", " at about 3am on "), date_text(rng, recent_date(rng, 10)), ". "]
    p2 = [pick(rng, "It was charged to my card ending ", "Card used: ending ", "My card ending "), cust.card_last4(), ". ",
          pick(rng, "I've already called ", "I've reported it to ", "I've frozen the card with "), world.public_company(rng, "bank"), ". ",
          pick(rng, "My ", "The "), lab.lower(), " is ", cid, "."]
    acts = ["I've cancelled the order and secured your account.", "We've blocked further orders until you reset your password.",
            "Our fraud team will contact you within 24 hours.", "Please also change your password on any site where you used it."]
    return subj, [p1, p2], acts, "fraud"


def _iss_broadband(rng, cust, lab, cid):
    subj = pick(rng, "Broadband keeps dropping", "No internet", "Slow speeds", "Router keeps restarting", "Line fault")
    p1 = [pick(rng, "My connection drops every evening since ", "Speeds have been awful since ", "The internet has been down since "),
          date_text(rng, recent_date(rng, 30)), ". ", pick(rng, "Landline number ", "The line is ", "Phone line: "), cust.landline(), "."]
    p2 = [pick(rng, "I've restarted the ", "I've reset the ", "I've swapped the cable on the "), world.product(rng),
          pick(rng, " router", " hub", ""), pick(rng, " several times. ", " twice. ", " already. "),
          pick(rng, "Best contact is ", "Call me on ", "Mobile: "), cust.mobile(), "."]
    acts = ["I've run a line test and booked an engineer.", "There's a known fault in your area, expected fix within 48 hours.",
            "I've reset the line from our side; please restart the router."]
    return subj, [p1, p2], acts, "fault"


_ISSUES = [_iss_refund, _iss_delivery, _iss_locked, _iss_gdpr, _iss_billing, _iss_ddbank, _iss_moving, _iss_cancel, _iss_damaged,
           _iss_upgrade, _iss_password, _iss_fraud, _iss_broadband]

_A_ACK = ["Thanks for getting in touch.", "Sorry to hear about this.", "Thank you for your patience while we looked into this.",
          "I'm sorry for the trouble this has caused.", "Thanks for the details, that really helps.",
          "Apologies for the delay in coming back to you.", "I understand how frustrating this must be.",
          "Thanks for letting us know.", "I've had a look at your account.", "Thanks for bearing with us."]
_A_TIME = ["You should see this within 3 to 5 working days.", "I'll update you within 48 hours.",
           "This usually takes up to 10 working days.", "We'll email you as soon as it's done.",
           "I'll check back on this tomorrow.", "Nothing else is needed from you for now."]
_A_EXTRA = ["If there's anything else, just reply to this email.", "You can track progress in the app under Help.",
            "For security, we'll never ask for your full card number.",
            "I've added a note so you won't need to explain this again.",
            "As a goodwill gesture I've added a credit of {amt} to your account.",
            "Please keep this reference handy if you get back in touch.",
            "Our opening hours are 8am to 8pm, Monday to Saturday."]
_A_CLOSE = ["Kind regards,", "Best wishes,", "Thanks,", "Many thanks,", "All the best,", "Speak soon,", "Regards,"]
_MACROS = ["Refund - duplicate charge", "Delivery - investigation opened", "Account - unlock steps", "GDPR - acknowledgement",
           "Billing - adjustment", "Cancellation - confirmation", "Damaged item - replacement", "General - holding reply",
           "Fraud - account secured", "Plan change - confirmation"]
_NOTES = ["Customer verified via DOB and postcode.", "ID&V passed (security questions).", "Second contact about this.",
          "Escalated to tier 2.", "Checked with the warehouse, parcel scanned at the depot.", "Refund of {amt} approved.",
          "Possible duplicate of {tid}.", "Customer may be vulnerable, flag for a callback.", "Do not offer further credit.",
          "Waiting on the payments team.", "Courier claim raised.", "Linked to the outage on {date}.", "Goodwill of {amt} applied."]
_TAGS = ["billing", "refund", "delivery", "vip", "complaint", "gdpr", "fraud", "account", "escalated", "repeat-contact", "courier",
         "outage", "retention", "card-payment", "address-change"]
_SURVEY = [["Satisfaction survey sent ", "{date}", "."], ["CSAT: ", "{n}", "/5 - \"", "{c}", "\""],
           ["Customer rating: ", "{good}"], ["How did we do? Reply with a number from 1 to 5."]]
_SURVEY_C = ["quick and helpful", "took far too long", "agent was lovely", "still not fixed", "sorted in one go", "had to chase twice"]


def _agent_reply(rng, cust: Person, agent: Person, org: world.Org, acts: list, length: int) -> list:
    out = []
    r = rng.random()
    if r < 0.45:
        out += [pick(rng, "Hi ", "Hello ", "Hey "), cust.first_name("greeting_name"), ",\n\n"]
    elif r < 0.75:
        out += ["Dear ", cust.title + " ", cust.last_name("greeting_name"), ",\n\n"]
    elif r < 0.85:
        out += [pick(rng, "Hi there,\n\n", "Hello,\n\n")]
    sents = [rng.choice(_A_ACK).replace("{org}", org.name), rng.choice(acts)]
    if length >= 1:
        sents.append(rng.choice(_A_TIME))
    if length >= 2:
        sents += [_f(x, amt=amount(rng, 5, 50)) for x in rng.sample(_A_EXTRA, 2)]
    for i, s in enumerate(sents):
        if i:
            out.append(" " if rng.random() < 0.6 else "\n\n")
        out.append(s)
    if length >= 2 and rng.random() < 0.5:
        out += ["\n\n", pick(rng, "Next steps:\n", "What happens now:\n"), "1. ", pick(rng, "We confirm by email", "The team reviews the case"),
                "\n2. ", pick(rng, "You get an update within 2 days", "We close the ticket once you confirm")]
    out += ["\n\n", rng.choice(_A_CLOSE), "\n"]
    s = rng.random()
    if s < 0.5:
        out += [agent.first_name("signature_name"), pick(rng, "\n", " | ", " - "), org.name, pick(rng, " Support", " Customer Care", " Help Team", "")]
    elif s < 0.8:
        out += [agent.full("signature_name"), "\n", pick(rng, "Customer Support Advisor", "Team Lead", "Customer Care", "Specialist, Billing")]
    else:
        out += [agent.first_name("signature_name")]
    return out


def _follow_up(rng, cust: Person, prev_reply: list) -> list:
    out = [pick(rng, "Thanks, but ", "Hi, ", "Thanks for the reply. ", "", "Still waiting - "),
           pick(rng, "it still hasn't come through.", "that worked, thank you!", "nothing has changed since.",
                "can you confirm the date?", "I've checked and the money is there now.", "the courier says they never had it.",
                "why does this take so long?")]
    if rng.random() < 0.5:
        out += ["\n\n", pick(rng, "Thanks,\n", "Cheers,\n", ""), cust.first_name("signature_name")]
    if rng.random() < 0.45:  # quoted previous agent reply
        out += ["\n\n", pick(rng, "", "", "Your reply:\n", "Previously:\n"), quote(prev_reply)]
    return out


def _fields_block(rng, fields: list) -> list:
    """Header fields in random order, label wording and arrangement."""
    fields = list(fields)
    rng.shuffle(fields)
    fields = fields[: rng.randint(max(2, len(fields) - 3), len(fields))]
    sep = pick(rng, ": ", ": ", ": ", " - ", ":  ")
    joiner = pick(rng, "\n", "\n", "   ", " | ")
    out = []
    for i, (lab, val) in enumerate(fields):
        if i:
            out.append(joiner)
        out += [lab, sep, val]
    return out + ["\n"]


def _lab(rng, *opts):
    return rng.choice(opts)


def _neg_ticket(rng, d: Doc, tid: K, when: datetime, st: int):
    comps = ["Export to CSV", "Invoice PDF", "Password reset email", "Search", "Mobile app login", "Push notifications", "Dark mode",
             "Calendar sync", "File upload", "Two-factor codes", "Checkout page", "Dashboard charts", "API rate limiting", "Webhooks",
             "SSO login", "Billing page", "Address autocomplete", "Order history", "Shipping labels", "Audit log", "Bulk import",
             "Email templates", "Report scheduler", "Saved filters"]
    symps = ["does nothing when clicked", "times out after 30 seconds", "shows a blank page", "returns a 500 error",
             "is very slow (over {n} seconds)", "shows the wrong totals", "creates duplicate entries", "crashes the app",
             "loses unsaved changes", "shows times in the wrong time zone", "ignores the selected filter", "fails silently",
             "spins forever", "sends twice", "renders off-screen on small screens", "rounds VAT per line instead of per invoice"]
    envs = ["Safari 17", "Chrome 129", "Firefox 131", "Edge", "iOS 18", "Android 14", "Windows 11", "macOS 14", "iPadOS 17"]
    comp, symp = rng.choice(comps), rng.choice(symps)
    title = f"{comp} {symp}".replace("{n}", str(rng.randint(5, 90)))
    d.v("neg")
    head = rng.random()
    if head < 0.4:
        d.add(_lab(rng, "Ticket ", "Issue ", "Bug "), tid, " - ", title, "\n")
    elif head < 0.7:
        d.add(K(ids.from_pattern(rng, pick(rng, "BUG-####", "ENG-#####", "QA-###")), "doc_reference"), ": ", title, "\n")
    else:
        d.add(_lab(rng, "Summary: ", "Title: ", "Subject: "), title, "\n", _lab(rng, "Ref: ", "ID: ", "Ticket: "), tid, "\n")
    fields = [(_lab(rng, "Type", "Category", "Kind"), pick(rng, "Bug", "Defect", "Incident", "Problem")),
              (_lab(rng, "Priority", "Severity", "Urgency"), pick(rng, "High", "P2", "P3", "Medium", "Critical", "Low")),
              (_lab(rng, "Status", "State"), pick(rng, "Open", "In progress", "Triage", "Waiting for release", "New")),
              (_lab(rng, "Reporter", "Raised by", "Source"), pick(rng, "Tier 1 Support", "QA team", "Customer Success", "Monitoring alert",
                                                                   "Sales engineering", "Internal user")),
              (_lab(rng, "Created", "Opened", "Logged"), K(_email_dt(when, st), "date")),
              (_lab(rng, "Component", "Area", "Module"), pick(rng, "Web app", "Mobile", "Billing", "Integrations", "Reporting", "Auth")),
              (_lab(rng, "Environment", "Platform"), ", ".join(rng.sample(envs, rng.randint(1, 3))))]
    d.add(_fields_block(rng, fields), "\n")
    desc = [pick(rng, "Users report that ", "Several customers say ", "Since ", "We've confirmed that ", "Monitoring shows that "),
            comp.lower() if rng.random() < 0.7 else comp, " ", symp.replace("{n}", str(rng.randint(5, 90)))]
    if desc[0] == "Since ":
        desc = ["Since ", pick(rng, "release ", "version "), K(ids.from_pattern(rng, "#.#.#"), "product"), ", ", comp.lower(), " ",
                symp.replace("{n}", str(rng.randint(5, 90)))]
    desc += [pick(rng, ". ", " for some users. ", " intermittently. ", " on the first attempt only. ")]
    if rng.random() < 0.5:
        desc += [pick(rng, "First seen on ", "Started around ", "Reports began "), date_text(rng, recent_date(rng, 30)), "."]
    d.add(pick(rng, "Description:\n", "Details:\n", "What happened:\n", ""), desc, "\n\n")
    if rng.random() < 0.6:
        steps = rng.sample(["Log in as any user", "Open the {c} screen", "Apply any filter", "Click the main action button",
                            "Switch to a mobile viewport", "Wait 30 seconds", "Refresh the page", "Repeat with a second account",
                            "Upload a file larger than 10 MB", "Change the language to Welsh"], rng.randint(2, 5))
        d.add(pick(rng, "Steps to reproduce:\n", "Repro:\n", "How to reproduce:\n"))
        numbered = rng.random() < 0.75
        for i, s in enumerate(steps):
            d.add(f"{i + 1}. " if numbered else "- ", s.replace("{c}", comp.lower()), "\n")
        d.add("\n")
    if rng.random() < 0.5:
        d.add("Expected: ", pick(rng, "the action completes", "correct totals", "a confirmation message", "the file downloads"),
              pick(rng, "\n", " | "), "Actual: ", symp.replace("{n}", "40"), "\n\n")
    d.add(pick(rng, "Impact: about ", "Affected: roughly ", "Scope: "), str(rng.randint(2, 900)),
          pick(rng, " accounts. ", " users today. ", " reports this week. "), pick(rng, "No customer data involved.", "Workaround exists.",
                                                                                    "Blocking month-end for finance teams.", ""), "\n")
    if rng.random() < 0.6:
        d.add("\n", pick(rng, "Internal note: ", "Engineering: ", "Triage note: "),
              pick(rng, "linked to release ", "workaround documented in KB article ", "regression from build "),
              K(ids.from_pattern(rng, pick(rng, "#.#.#", "####")), "product"),
              pick(rng, ". Escalated to engineering.", ". Monitoring.", ". Fix scheduled for next sprint.", ". Needs a product decision."))
    if rng.random() < 0.3:
        d.add("\n", "Tags: ", ", ".join(rng.sample(["bug", "regression", "frontend", "backend", "p2", "mobile", "billing", "needs-repro"], 3)))


@register("support_ticket", weight=6, neg_weight=6)
def support_ticket(rng: random.Random, neg: bool) -> Doc:
    d = Doc("support_ticket", "support_ticket/v2")
    layout = rng.choice(["zendesk", "jira", "form", "freshdesk", "livechat"])
    d.v(layout)
    tid = world.doc_ref(rng, "ticket")
    when = _when(rng, 200)
    st = rng.randrange(6)
    if neg:
        _neg_ticket(rng, d, tid, when, st)
        return d
    c = Cast(rng, common_word_rate=0.08)
    cust = c.new()
    agent = c.new()
    org = rng.choice(world.ORGS_BY_KIND[pick(rng, "saas", "saas", "telecom", "energy")])
    lab, cid = org.custom(rng)
    iss = rng.choice(_ISSUES)
    subj, paras, acts, cat = iss(rng, cust, lab, cid)
    d.v(cat)
    # customer message
    body: list = [rng.choice(_C_GREET)]
    ctx = [_ctx_sentence(rng) for _ in range(rng.choice([0, 0, 1, 1, 2]))]
    pos = rng.randrange(len(paras) + 1)
    blocks = paras[:pos] + ([ctx] if ctx else []) + paras[pos:]
    for b in blocks:
        if b is ctx:
            for i, s in enumerate(ctx):
                body += ([" "] if i else []) + [s]
        else:
            body += [b]
        body += ["\n\n"]
    if rng.random() < 0.7:
        body += [rng.choice(_C_SIGN), cust.first_name("signature_name") if rng.random() < 0.6 else cust.full("signature_name")]
    body = _rstrip(flatten(body))
    length = rng.choices([0, 1, 2], [30, 45, 25])[0]
    reply = _rstrip(flatten(_agent_reply(rng, cust, agent, org, acts, length)))
    turns = [("cust", body, when)]
    t = when
    if rng.random() < 0.85:
        t = t + timedelta(hours=rng.randint(1, 50), minutes=rng.randint(0, 59))
        turns.append(("agent", reply, t))
        if rng.random() < 0.45:
            t = t + timedelta(hours=rng.randint(1, 72))
            turns.append(("cust", _rstrip(flatten(_follow_up(rng, cust, reply))), t))
            if rng.random() < 0.5:
                t = t + timedelta(hours=rng.randint(1, 30))
                rest = [a for a in acts if a not in [x for x in reply if isinstance(x, str)]] or acts
                short = _rstrip(flatten(_agent_reply(rng, cust, agent, org, rest, 0)))
                turns.append(("agent", short, t))
    who = {"cust": lambda: cust.full() if rng.random() < 0.5 else cust.first_name(),
           "agent": lambda: agent.full() if rng.random() < 0.4 else agent.first_name()}
    # optional extra blocks
    extras = []
    if rng.random() < 0.6:
        note = rng.sample(_NOTES, rng.randint(1, 3))
        extras.append([pick(rng, "Internal note", "Private note", "Agent note", "Note"), " (",
                       agent.initials() if rng.random() < 0.5 else agent.first_name(), "): ",
                       _join([_f(n, amt=amount(rng, 5, 60), tid=world.doc_ref(rng, "ticket"), date=date_text(rng, recent_date(rng, 20)))
                              for n in note], " ")])
    if rng.random() < 0.35:
        extras.append([pick(rng, "Macro applied: ", "Macro: ", "Applied template: "), rng.choice(_MACROS)])
    if rng.random() < 0.35:
        sv = rng.choice(_SURVEY)
        extras.append([x if not x.startswith("{") else
                       {"{date}": date_text(rng, recent_date(rng, 10)), "{n}": str(rng.randint(1, 5)), "{c}": rng.choice(_SURVEY_C),
                        "{good}": pick(rng, "Good", "Bad", "Great", "Okay")}[x] for x in sv])
    if rng.random() < 0.3:
        extras.append(["Tags: ", ", ".join(rng.sample(_TAGS, rng.randint(2, 4)))])
    if rng.random() < 0.2:
        extras.append([pick(rng, "First response: ", "FRT: "), f"{rng.randint(0, 30)}h {rng.randint(0, 59)}m", " | ",
                       pick(rng, "Resolution target: ", "SLA due: "), date_text(rng, recent_date(rng, 0, 7))])
    rng.shuffle(extras)
    status = pick(rng, "Open", "Pending", "Solved", "On hold", "Awaiting customer", "Closed", "New")
    prio = pick(rng, "Normal", "High", "Low", "Urgent", "P2", "P3")
    chan = pick(rng, "Email", "Web form", "Chat", "Phone", "App", "Twitter DM")
    if layout in ("zendesk", "freshdesk"):
        if layout == "zendesk":
            d.add(_lab(rng, "Ticket ", "#", "Request "), tid, pick(rng, ": ", " - ", " | "), subj, "\n")
        else:
            d.add(subj, pick(rng, " (", " - #", " ["), tid, pick(rng, ")", "", "]"), "\n")
        fields = [(_lab(rng, "Status", "State"), status), (_lab(rng, "Priority", "Urgency"), prio),
                  (_lab(rng, "Channel", "Source", "Via"), chan),
                  (_lab(rng, "Requester", "Customer", "Contact", "From"), [cust.full(), " <", cust.email(), ">"]),
                  (_lab(rng, "Organisation", "Brand", "Company"), org.name),
                  (lab, cid), (_lab(rng, "Created", "Opened", "Received"), K(_email_dt(when, st), "date")),
                  (_lab(rng, "Assignee", "Agent", "Owner"), agent.full() if rng.random() < 0.5 else agent.first_name()),
                  (_lab(rng, "Group", "Team", "Queue"), pick(rng, "Billing", "Deliveries", "Tier 1", "Accounts", "Escalations"))]
        if rng.random() < 0.4:
            fields.append((_lab(rng, "Phone", "Mobile", "Tel"), cust.phone()))
        d.add(_fields_block(rng, fields), "\n")
        for role, text, tm in turns:
            hdr = rng.random()
            if hdr < 0.5:
                d.add("--- ", who[role](), " (", K(_email_dt(tm, st), "date"), ") ---\n")
            elif hdr < 0.8:
                d.add(who[role](), pick(rng, " replied ", " wrote on ", ", "), K(_email_dt(tm, st), "date"), ":\n")
            else:
                d.add("[", "Customer" if role == "cust" else "Agent", "] ", K(_email_dt(tm, st), "date"), "\n")
            d.add(text, "\n\n")
    elif layout == "jira":
        key = K(ids.from_pattern(rng, pick(rng, "SUP-####", "CS-#####", "HELP-###", "SD-####")), "doc_reference")
        d.add(key, ": ", subj, "\n")
        fields = [(_lab(rng, "Issue type", "Request type"), pick(rng, "Customer request", "Service request", "Incident", "Question")),
                  (_lab(rng, "Priority", "Impact"), prio), (_lab(rng, "Reporter", "Raised by"), agent.full()),
                  (_lab(rng, "Customer", "Requester"), cust.full()), (_lab(rng, "Phone", "Contact number"), cust.phone()),
                  (lab, cid), ("Linked ticket", tid), (_lab(rng, "Status", "Workflow"), status)]
        d.add(_fields_block(rng, fields), "\n", pick(rng, "Description:\n", "Summary of request:\n", "Customer says:\n"), body, "\n\n")
        if len(turns) > 1:
            d.add(pick(rng, "Comments:\n", "Activity:\n"))
            for role, text, tm in turns[1:]:
                d.add("[", K(_email_dt(tm, st), "date"), "] ", who[role](), ": ", text, "\n\n")
    elif layout == "form":
        d.add(pick(rng, "New contact form submission", "Web enquiry", "Contact us form", "Online help request", "Form: Get in touch"), "\n\n")
        fields = [("Name", cust.full()), (_lab(rng, "Email", "Email address"), cust.email()), (lab, cid),
                  (_lab(rng, "Topic", "Subject", "Reason for contact"), subj), (_lab(rng, "Submitted", "Sent", "Date"), K(_email_dt(when, st), "date")),
                  (_lab(rng, "Reference", "Case number", "Ticket"), tid)]
        if rng.random() < 0.7:
            fields.append((_lab(rng, "Phone", "Phone number", "Mobile"), cust.phone()))
        if rng.random() < 0.3:
            fields.append(("Preferred contact", pick(rng, "Email", "Phone", "Either")))
        d.add(_fields_block(rng, fields), "\n", pick(rng, "Message:\n", "Your message:\n", "Details:\n", "How can we help?\n"), body)
        if len(turns) > 1:
            d.add("\n\n", pick(rng, "Reply sent:\n", "Our response:\n", "Response:\n"), turns[1][1])
            for role, text, tm in turns[2:]:
                d.add("\n\n", pick(rng, "Customer replied:\n", "Follow-up:\n") if role == "cust" else "Further reply:\n", text)
        d.add("\n\n")
    else:  # live chat transcript
        d.add(pick(rng, "Chat transcript", "Live chat", "Webchat log") if rng.random() < 0.6 else ["Conversation with ", cust.first_name()],
              "\n", pick(rng, "Started: ", "Date: "), K(_email_dt(when, st), "date"), "\n")
        d.add(_fields_block(rng, [(_lab(rng, "Visitor", "Customer"), cust.full()), ("Email", cust.email()), (lab, cid),
                                  (_lab(rng, "Agent", "Advisor"), agent.first_name()), ("Topic", subj)]), "\n")
        tm = when
        cust_lab = cust.first_name() if rng.random() < 0.6 else "Visitor"
        ag_lab = agent.first_name()
        for role, text, _ in turns:
            for chunk in [text]:
                tm = tm + timedelta(minutes=rng.randint(0, 4), seconds=rng.randint(0, 59))
                d.add("[", f"{tm.hour:02d}:{tm.minute:02d}", "] ", cust_lab if role == "cust" else ag_lab, ": ", chunk, "\n")
        d.add(pick(rng, "Chat ended by ", "Chat closed by "), pick(rng, "visitor", "agent"), ".\n\n")
    if extras:
        for x in extras:
            d.add(x, "\n")
    if rng.random() < 0.12:
        d.atoms = noise.typos(d.atoms, rng, 0.03)
        d.v("typos")
    return d


# =========================================================================== meeting notes
_MEET_TITLES = {
    "law": ["Weekly matter review", "Conveyancing team meeting", "Client intake meeting", "Case conference"],
    "accountant": ["Tax season planning", "Client portfolio review", "Weekly bookkeeping catch-up"],
    "letting": ["Lettings team stand-up", "Tenant arrears review", "Maintenance planning meeting"],
    "employer": ["HR and payroll review", "Team leads meeting", "Absence and wellbeing review"],
    "insurer": ["Claims triage meeting", "Complex claims review"],
}


def _client_line(rng, p: Person, org: world.Org, kind: str) -> list:
    lab, cid = org.custom(rng)
    r = rng.randrange(6)
    if r == 0:
        return [p.full(), " (", cid, "): ", pick(rng, "completion moved to ", "documents due ", "review booked for "),
                date_text(rng, recent_date(rng, 0, 45)), "."]
    if r == 1:
        return [p.title_last(), " called about ", pick(rng, "the fee estimate of ", "arrears of ", "the claim excess of "),
                amount(rng, 100, 4000), ". ", lab, " ", cid, "."]
    if r == 2:
        return [p.possessive(), " file (", cid, ") still missing ", pick(rng, "proof of address", "ID", "the signed engagement letter"), "."]
    if r == 3:
        return ["New client: ", p.full(), ", ", p.mobile(), ", ", p.email(), ". ", lab, " ", cid, " opened."]
    if r == 4:
        return ["Complaint from ", p.full(), " at ", world.make_address(rng).inline(rng, p.ref), "; ", lab, " ", cid, "."]
    return [p.initial_last(), " - ", lab.lower(), " ", cid, ": ", pick(rng, "no change.", "chase next week.", "closed.")]


@register("meeting_notes", weight=4, neg_weight=8)
def meeting_notes(rng: random.Random, neg: bool) -> Doc:
    d = Doc("meeting_notes", "meeting_notes/v1")
    md = rng.random() < 0.7
    d.v("md" if md else "plain")
    when = recent_date(rng, 300)
    H1, H2 = ("# ", "## ") if md else ("", "")
    B = "**" if md else ""
    if neg:
        title = pick(rng, "Budget planning", "Office move working group", "Quarterly operations review", "Health and safety committee",
                     "Product launch sync")
        d.v("neg")
        d.add(H1, title, "\n", B, "Date:", B, " ", date_text(rng, when), " | ", B, "Location:", B, " ",
              pick(rng, "Teams", "Meeting room 2", world.place_trap(rng)), "\n")
        roles = rng.sample(["Chair", "Finance lead", "Ops manager", "HR business partner", "Facilities", "IT lead", "Compliance officer",
                            "Head of Sales", "Minute taker"], rng.randint(3, 6))
        d.add(B, "Attendees:", B, " ", ", ".join(roles), "\n\n", H2, "Notes\n")
        items = [["- Budget for next year set at ", amount(rng, 20000, 900000, style=1, step=1000), ", ", pick(rng, "up", "down"), " ",
                  str(rng.randint(2, 12)), "%.\n"],
                 ["- Contract with ", world.public_company(rng), " renews on ", date_text(rng, recent_date(rng, 0, 200)), ".\n"],
                 ["- Move to ", world.place_trap(rng), " site planned for ", K(pick(rng, "spring", "Q3", "next March"), "date"), ".\n"],
                 ["- Compliance: review against the ", world.statute(rng), " due by ", date_text(rng, recent_date(rng, 0, 60)), ".\n"],
                 ["- Pilot of ", world.product(rng), " for the team; cost ", amount(rng, 5, 60), " per user per month.\n"],
                 ["- We will circulate the risk register before the next meeting.\n"]]
        rng.shuffle(items)
        for it in items[: rng.randint(3, 6)]:
            d.add(it)
        d.add("\n", H2, "Actions\n", "- Finance lead to update the forecast by ", date_text(rng, recent_date(rng, 0, 14)), "\n",
              "- Chair to confirm the next meeting date\n")
        return d
    c = Cast(rng, common_word_rate=0.1)
    kind = rng.choice(list(_MEET_TITLES))
    org = rng.choice(world.ORGS_BY_KIND[kind])
    d.v(kind)
    staff = []
    seen = set()
    for _ in range(rng.randint(3, 6)):
        for _try in range(4):
            p = c.new()
            ini = p.initials().text
            if ini not in seen:
                break
        seen.add(ini)
        staff.append((p, ini))
    d.add(H1, pick(rng, *_MEET_TITLES[kind]), [pick(rng, " - ", " | ", ": "), org.name] if rng.random() < 0.5 else "", "\n")
    d.add(B, "Date:", B, " ", date_text(rng, when), pick(rng, "  ", " | ", "\n"), B, "Time:", B, " ",
          K(f"{rng.randint(8, 16)}:{pick(rng, '00', '30')}", "date"), "\n")
    att = staff[:-1] if rng.random() < 0.5 else staff
    d.add(B, "Attendees:", B, " ")
    for i, (p, ini) in enumerate(att):
        if i:
            d.add(", ")
        d.add(p.full(), " (", p.e(ini, "initials"), ")") if rng.random() < 0.8 else d.add(p.full())
    d.add("\n")
    if len(att) < len(staff):
        p, ini = staff[-1]
        d.add(B, "Apologies:", B, " ", p.full() if rng.random() < 0.5 else p.first_name(), "\n")
    d.add("\n", H2, "Agenda\n", "1. Actions from last meeting\n2. ", pick(rng, "Client updates", "Open matters", "Arrears", "Claims"),
          "\n3. ", pick(rng, "Resourcing", "AOB", "Training"), "\n\n", H2, "Discussion\n")
    clients = [c.new() for _ in range(rng.randint(1, 4))]
    for cl in clients:
        d.add("- ", _client_line(rng, cl, org, kind), "\n")
    p0, ini0 = rng.choice(staff)
    d.add("- ", p0.e(ini0, "initials"), pick(rng, " noted ", " raised ", " flagged ", " asked about "),
          pick(rng, "the training due on the ", "the guidance on the ", "the update to the "), world.statute(rng), ".\n")
    for p in c.people:
        if p.common_word:
            ph = _cwp(rng, p.first)
            if ph:
                d.add("- ", ph, "\n")
            break
    d.add("\n", H2, "Actions\n")
    use_table = md and rng.random() < 0.5
    if use_table:
        d.add("| Owner | Action | Due |\n|---|---|---|\n")
    for cl in clients[: rng.randint(1, len(clients))]:
        p, ini = rng.choice(staff)
        lab, cid = org.custom(rng)
        due = date_text(rng, recent_date(rng, 0, 21)) if rng.random() < 0.6 else K(pick(rng, "Friday", "next week", "EOD", "Monday"), "date")
        act = [pick(rng, "Send engagement letter to ", "Chase ", "Call ", "Update file for "),
               cl.title_last() if rng.random() < 0.5 else [cl.full()], " (", cid, ")"]
        if use_table:
            d.add("| ", p.e(ini, "initials"), " | ", act, " | ", due, " |\n")
        else:
            d.add("- ", "[ ] " if md else "", p.e(ini, "initials"), " to ", [act[0].lower() if isinstance(act[0], str) else act[0]] + act[1:],
                  " by ", due, "\n")
    if rng.random() < 0.6:
        p, ini = staff[0]
        d.add("\n", pick(rng, "Next meeting: ", "Next review: "), date_text(rng, recent_date(rng, 0, 30)), ". Minutes: ",
              p.first_name() if rng.random() < 0.5 else p.e(ini, "initials"), "\n")
    return d
