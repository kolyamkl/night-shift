"""Short user prompts to an AI assistant that paste in personal data (largest share)."""
from __future__ import annotations

import random

from .. import ids, noise, world
from ..core import Doc, E, HC, K
from ..names import Cast
from . import register
from .common import TODAY, amount, date_text, pick, recent_date

OPENERS = ["", "", "", "", "Hi, ", "Hey, ", "hello! ", "Quick one: ", "Please help. ", "ok so ", "Morning! ",
           "Hi Claude, ", "Can you help? ", "Hiya, ", "Urgent: ", "Good evening. ", "So, ", "Help pls. ",
           "I need a hand with something. ", "Right, ", "Sorry, another one: ", "Hello there, ", "hey can you help ",
           "Task for you: ", "Bit stuck here. ", "Could you do me a favour? ", "Evening, ", "Hi again, ",
           "Not sure how to word this. ", "First time using this, ", "Need this today: "]
CLOSERS = ["", "", "", "", " Thanks!", " Thank you.", " Keep it short.", " Make it polite but firm.",
           " UK English please.", " Don't change any of the facts.", " Under 150 words.", " ty", " thanks x",
           " Make it sound less angry.", " Bullet points are fine.", " Formal tone please.", " Cheers.",
           " Keep my details exactly as written.", " Plain English, no jargon.", " Two short paragraphs max.",
           " Can you also give it a subject line?", " Make it sound confident.", " Nothing too legal-sounding.",
           " I'll paste it into an email.", " Thanks in advance!!", " Please be quick, it's due tomorrow.",
           " Use a friendly tone.", " Avoid exclamation marks.", " Write it as if from me.", " Much appreciated.",
           " Keep the dates and amounts the same.", " Add a line asking them to confirm by email."]
CONTEXT = ["I've been with them for years and never had a problem before.", "This is the third time I'm asking.",
           "I work nights so email is better than calls.", "I'm not great at formal writing.",
           "English is my second language so please check it.", "My manager says it needs to go out today.",
           "They already ignored my first email.", "I've attached nothing yet, just want the wording.",
           "It's for a new flat so first impressions matter.", "I'm quite stressed about this tbh.",
           "The last person I spoke to was really helpful.", "I need to keep a copy for my records.",
           "My solicitor said to put everything in writing.", "I'm on a tight budget this month.",
           "This is for my elderly parent who doesn't use email.", "We're moving at the end of the month.",
           "I've already checked the FAQ on their website.", "It doesn't need to be perfect.",
           "I want to sound polite but not weak.", "I'll print it and post it.", "The deadline is Friday.",
           "Citizens Advice told me to write this down.", "My partner thinks I'm overreacting.",
           "I'm writing from my phone so sorry for typos.", "They said it would take 5 working days.",
           "I don't want to lose the deposit over this.", "Can you keep all the numbers exactly as they are?",
           "I tried their chatbot and got nowhere.", "I've screenshotted everything just in case."]


def _context(rng, d: Doc, lead: bool = True):
    k = rng.choices([0, 1, 2], [0.45, 0.4, 0.15])[0]
    for i, t in enumerate(rng.sample(CONTEXT, k)):
        d.add(" " if (lead or i) else "", t)
    return k


def _complaint(rng, d: Doc, c: Cast):
    me = c.new()
    co = world.public_company(rng, pick(rng, "energy", "telecom", "retail", "bank", "transport"))
    org = rng.choice(world.ORGS_BY_KIND[pick(rng, "energy", "telecom", "saas")])
    lab, cid = org.custom(rng)
    addr = world.make_address(rng)
    when = recent_date(rng, 120)
    d.v("complaint")
    d.f(pick(rng, "Can you rewrite this complaint so it sounds more professional:\n\n",
             "Rewrite this complaint for me:\n\"", "Make this complaint clearer, it's going to {co}:\n\n",
             "pls fix the grammar in this complaint\n\n"), co=co)
    d.f(pick(rng, "My name is {name} and I have been a customer for {yrs} years. ",
             "I am writing as {name}, {lab} {cid}. ", "This is {name} from {addr}. "),
        name=me.full(), yrs=str(rng.randint(2, 15)), lab=lab.lower(), cid=cid, addr=addr.inline(rng, me.ref))
    d.f(pick(rng, "On {when} you charged me {amt} for a service I cancelled. ",
             "Since {when} nobody has fixed my {thing} and I have called {n} times. ",
             "My bill went up to {amt} without any warning on {when}. "),
        when=date_text(rng, when), amt=amount(rng, 20, 900), thing=pick(rng, "broadband", "boiler", "meter", "router", "account"),
        n=str(rng.randint(3, 9)))
    if rng.random() < 0.6:
        d.f(pick(rng, "My {lab} is {cid} and my phone is {ph}. ", "Account: {cid}. Call me on {ph}. ",
                 "You can reach me at {em} or {ph}. "), lab=lab.lower(), cid=cid, ph=me.phone(), em=me.email())
    if rng.random() < 0.5:
        d.f("I want a refund of {amt} and an apology. ", amt=amount(rng, 15, 400))
    if rng.random() < 0.35:
        d.add(HC("signature_only", "\nRegards, ", me.first_name("signature_name")))
    d.add("\"" if rng.random() < 0.3 else "")


def _landlord_email(rng, d: Doc, c: Cast):
    me = c.new()
    ll = c.new()
    org = rng.choice(world.ORGS_BY_KIND["letting"])
    lab, cid = org.custom(rng)
    addr = world.make_address(rng, flat_rate=0.5)
    issue = pick(rng, "the boiler has stopped working", "there is black mould in the bedroom",
                 "the front door lock is broken", "the deposit has not been returned",
                 "the rent increase notice", "a leak from the flat upstairs", "the oven does not work")
    d.v("landlord")
    d.f(pick(rng, "Draft an email to my landlord {ll} about {issue}. ",
             "Write a short message to {ll} (my landlord) because {issue}. ",
             "can u write to my landlord {ll}? {issue} "), ll=ll.full() if rng.random() < 0.6 else ll.title_last(), issue=issue)
    d.f(pick(rng, "I live at {addr}. ", "The property is {addr}. ", "Address: {addr}. "),
        addr=addr.inline(rng, me.ref))
    if rng.random() < 0.6:
        d.f(pick(rng, "The {lab} with {org} is {cid}. ", "Agent is {org}, ref {cid}. "), lab=lab.lower(),
            org=org.name, cid=cid)
    if rng.random() < 0.5:
        d.f(pick(rng, "Rent is {amt} a month and I paid on {when}. ", "I've paid {amt} so far."),
            amt=amount(rng, 550, 2400, step=5), when=date_text(rng, recent_date(rng, 60)))
    d.f(pick(rng, "Sign it from {me}.", "My name is {me}.", "Sign off as {me}, {ph}.", ""), me=me.full(), ph=me.mobile())


def _bank_check(rng, d: Doc, c: Cast):
    p = c.new()
    d.v("bank")
    t = rng.random()
    if t < 0.4:
        d.f(pick(rng, "Is this a valid UK sort code and account? {sc} {acct}. It's for {name}.",
                 "My friend {name} sent me sort code {sc} and account {acct} for the {amt} I owe her, does that look right?",
                 "check these bank details before I pay {amt}: name {name}, sort {sc}, acc no {acct}"),
            sc=p.sort_code(), acct=p.account(), name=p.full(), amt=amount(rng, 20, 2500))
    elif t < 0.7:
        d.f(pick(rng, "What bank is this IBAN from? {iban}", "Convert this IBAN to sort code and account number: {iban}",
                 "Someone gave me IBAN {iban} for {name}, is it UK?"), iban=p.iban(), name=p.full())
    else:
        d.f(pick(rng, "I set up a standing order of {amt} to {name} ({sc}, {acct}) but it bounced. Why?",
                 "Write a payment reference for paying {name} {amt}. Their account is {acct}, sort code {sc}."),
            amt=amount(rng, 50, 1500), name=p.full(), sc=p.sort_code(), acct=p.account())


def _hmrc_letter(rng, d: Doc, c: Cast):
    me = c.new()
    addr = world.make_address(rng)
    d.v("hmrc")
    d.f(pick(rng, "Write a letter to HMRC asking why my tax code changed. ",
             "Help me write to HMRC about an underpayment of {amt}. ",
             "I need to tell HMRC I moved house. "), amt=amount(rng, 90, 3000))
    rows = [("My name is {v}. ", me.full())]
    if rng.random() < 0.8:
        rows.append(("NI number {v}. ", me.ni()))
    if rng.random() < 0.5:
        rows.append(("UTR {v}. ", E(ids.utr(rng, rng.random() < 0.5), "CUSTOM", me.ref, ("custom_org_id",))))
    if rng.random() < 0.7:
        rows.append(("New address: {v}. ", addr.inline(rng, me.ref)))
    if rng.random() < 0.4:
        rows.append(("Date of birth {v}. ", me.dob()))
    rng.shuffle(rows)
    for t, v in rows:
        d.f(t, v=v)
    d.add(K(pick(rng, "", "Tax year 2025 to 2026. ", "This is for the 2024/25 tax year. "), "date"))


def _form_fill(rng, d: Doc, c: Cast):
    me = c.new()
    addr = world.make_address(rng)
    d.v("form")
    d.add(pick(rng, "Turn this into a neat table:\n", "Fill in the form fields using these details:\n",
               "format these details for a job application form\n", "Put this into JSON please:\n"))
    rows = [("name", me.full()), ("dob", me.dob()), ("address", addr.inline(rng, me.ref)),
            ("phone", me.phone()), ("email", me.email()), ("NI", me.ni())]
    if rng.random() < 0.3:
        rows.append(("passport", me.passport()))
    if rng.random() < 0.2:
        rows.append(("licence", me.licence()))
    rng.shuffle(rows)
    sep = pick(rng, ", ", "\n", "; ", " / ")
    for i, (lab, val) in enumerate(rows):
        if i:
            d.add(sep)
        d.add(pick(rng, lab + ": ", lab.upper() + " ", lab + " - ", "") if lab not in ("name",) or rng.random() < 0.7 else "", val)


def _translate(rng, d: Doc, c: Cast):
    p = c.new(origin=pick(rng, "ua", "pl", "in", "ng", "uk", "pk"))
    gp = rng.choice(world.ORGS_BY_KIND["gp"])
    lang = pick(rng, "Ukrainian", "Polish", "Romanian", "Urdu", "Spanish", "Arabic", "Yoruba")
    d.v("translate")
    d.f("Translate this into {lang} for my mum:\n\n", lang=lang)
    when = recent_date(rng, 10, 60)
    d.f(pick(rng, "\"Dear {t}, your appointment at {gp} is on {when} at {hh}:{mm}. Please bring photo ID. "
                  "If you cannot attend call {ph}.\"",
             "\"Hello {first}, this is a reminder that your rent of {amt} is due on {when}. Ref: {cid}.\"",
             "\"{t}, your parcel could not be delivered to {street}. Rebook online.\""),
        t=p.title_last(), gp=gp.name, when=date_text(rng, when), hh=str(rng.randint(8, 17)), mm=pick(rng, "00", "15", "30", "45"),
        ph=E(ids.landline_number(rng, 0), "PHONE"), first=p.first_name(), amt=amount(rng, 500, 1800),
        cid=rng.choice(world.ORGS_BY_KIND["letting"]).custom(rng)[1], street=world.make_address(rng).street_only(p.ref))


def _reference(rng, d: Doc, c: Cast):
    emp = c.new()
    me = c.new()
    co = world.company_name(rng)
    d.v("reference")
    d.f(pick(rng, "Write a job reference for {e}, who worked for me at {co} from {s} to {t}. ",
             "Can you write a reference letter for my former employee {e}? Dates: {s} - {t}. "),
        e=emp.full(), co=co, s=date_text(rng, recent_date(rng, 2500, 0)), t=date_text(rng, recent_date(rng, 300)))
    d.f(pick(rng, "{pos} was reliable and great with customers. ", "{pos} never missed a shift. ",
             "Mention {pos} attention to detail. "), pos=emp.possessive(use_first=True) if rng.random() < 0.6 else emp.first_name())
    if rng.random() < 0.5:
        d.f("Sign it from me, {me}, {role}, and add my number {ph}.", me=me.full(), role=pick(rng, "Store Manager", "Director", "Head of Operations"), ph=me.phone())


def _card_fraud(rng, d: Doc, c: Cast):
    me = c.new()
    bank = world.public_company(rng, "bank")
    d.v("card")
    full = rng.random() < 0.45
    d.f(pick(rng, "Someone used my card {card} at {shop} for {amt} on {when}. Write a dispute letter to {bank}. ",
             "help me dispute a payment of {amt} to {shop}, card {card}, bank is {bank}. ",
             "My {bank} card {card} was charged twice by {shop} ({amt}). "),
        card=me.card() if full else ["ending ", me.card_last4()], shop=world.public_company(rng, "retail"),
        amt=amount(rng, 9, 650), when=date_text(rng, recent_date(rng, 40)), bank=bank)
    if rng.random() < 0.6:
        d.f(pick(rng, "My name is {n}, account {acct}, sort code {sc}.", "Name on card: {n}.", "I'm {n}, call me on {ph}."),
            n=me.full() if rng.random() < 0.7 else me.caps(), acct=me.account(), sc=me.sort_code(), ph=me.mobile())


def _gp_request(rng, d: Doc, c: Cast):
    me = c.new()
    gp = rng.choice(world.ORGS_BY_KIND["gp"])
    d.v("gp")
    d.f(pick(rng, "Write a polite message to {gp} asking for a repeat prescription. ",
             "Help me email my GP surgery ({gp}) to ask for a copy of my records. ",
             "I need to change my address with {gp}. "), gp=gp.name)
    rows = [("I'm {v}", me.full()), ("DOB {v}", me.dob()), ("NHS number {v}", me.nhs())]
    if rng.random() < 0.5:
        rows.append(("my address is {v}", world.make_address(rng).inline(rng, me.ref)))
    if rng.random() < 0.4:
        rows.append(("mobile {v}", me.mobile()))
    rng.shuffle(rows)
    for i, (t, v) in enumerate(rows):
        d.f(("" if i == 0 else ", ") + t, v=v)
    d.add(".")


def _flatmates(rng, d: Doc, c: Cast):
    names = [c.new(common_word=rng.random() < 0.45) for _ in range(rng.randint(2, 4))]
    d.v("flatmates")
    d.add(pick(rng, "Split this bill fairly between us: ", "Make a table of who owes what. ",
               "work out what each of us owes for the {m} bills: ".replace("{m}", pick(rng, "March", "June", "winter"))))
    for i, p in enumerate(names):
        if i:
            d.add(pick(rng, ", ", "; ", " and "))
        d.f("{n} paid {a}", n=p.first_name(), a=amount(rng, 15, 600))
    d.f(". Total {t}.", t=amount(rng, 200, 1500))
    cw = next((p for p in names if p.common_word), None)
    if cw is not None:
        ph = world.common_word_phrase(rng, cw.first)
        if ph:
            d.add(" ", ph)


def _address_fix(rng, d: Doc, c: Cast):
    me = c.new()
    addr = world.make_address(rng, flat_rate=0.5)
    d.v("addressfix")
    d.add(pick(rng, "Format this address properly for a letter: ", "is this address written right? ",
               "Put this address in Royal Mail format: "))
    seg = addr.inline(rng, me.ref)
    if rng.random() < 0.6:
        seg = noise.lower_all(world_flat(seg))
    if rng.random() < 0.5:
        d.add(me.full(), ", ")
    d.add(seg)


def world_flat(x):
    from ..core import flatten
    return flatten(x)


def _sar(rng, d: Doc, c: Cast):
    me = c.new()
    org = rng.choice(world.SYNTH_ORGS)
    lab, cid = org.custom(rng)
    d.v("sar")
    d.f(pick(rng, "Write a subject access request to {org}. ", "Draft a GDPR data request to {org} for everything they hold on me. "),
        org=org.name)
    d.f(pick(rng, "Details: {n}, {em}, {lab} {cid}.", "I'm {n} ({em}) and my {lab} is {cid}.",
             "Use my name {n}, email {em}, and {lab} {cid}. My old address was {addr}."),
        n=me.full(), em=me.email(), lab=lab.lower(), cid=cid, addr=world.make_address(rng).inline(rng, me.ref))


def _birthday(rng, d: Doc, c: Cast):
    p = c.new()
    rel = pick(rng, "sister", "mum", "nan", "colleague", "friend", "partner", "daughter") if p.female else \
        pick(rng, "brother", "dad", "grandad", "colleague", "friend", "partner", "son")
    d.v("birthday")
    dob = p.dob_date
    d.f(pick(rng, "Write a birthday card message for my {rel} {n}, born {dob}. ",
             "My {rel} {n} turns {age} on {pdob}. Give me gift ideas under {amt}.",
             "Plan a surprise party for {n} ({rel}), DOB {dob}. Budget {amt}."),
        rel=rel, n=p.first_name() if rng.random() < 0.6 else p.full(), dob=p.dob(),
        age=str(TODAY.year - dob.year), amt=amount(rng, 20, 300, style=1, step=5),
        pdob=E(f"{dob.day} {ids.MONTHS[dob.month - 1]}", "DOB", p.ref, ("partial_dob",)))


def _parking(rng, d: Doc, c: Cast):
    me = c.new()
    council = K(rng.choice(world.COUNCILS), "public_company")
    pcn = E(ids.from_pattern(rng, pick(rng, "@@########", "PCN@#######", "LS#######@")), "CUSTOM", None, ("custom_org_id",))
    d.v("parking")
    d.f(pick(rng, "Help me appeal a parking fine from {c}. PCN {pcn}, issued {when} on {place}. ",
             "Write an appeal for penalty charge notice {pcn} ({amt}). I was parked at {place}. "),
        c=council, pcn=pcn, when=date_text(rng, recent_date(rng, 30)), place=world.place_trap(rng), amt=amount(rng, 35, 130, style=1, step=5))
    d.f(pick(rng, "My name is {n} and I live at {addr}.", "{n}, {addr}.", "Name: {n}"), n=me.full(),
        addr=world.make_address(rng).inline(rng, me.ref))


def _cv_help(rng, d: Doc, c: Cast):
    me = c.new()
    d.v("cvhelp")
    d.f(pick(rng, "Improve this CV summary: \"{n}, {job} with {y} years at {co}. Contact {em} / {ph}.\"",
             "Rewrite the top of my CV:\n{N}\n{town} | {ph} | {em}\n{job}",
             "can you make my linkedin about section better, im {n}, {job}, {y} yrs at {co}"),
        n=me.full(), N=me.caps(), job=pick(rng, "a project manager", "an accountant", "a nurse", "a software engineer",
                                                "a warehouse supervisor", "a paralegal", "a teaching assistant"),
        y=str(rng.randint(2, 20)), co=world.public_company(rng, "employer") if rng.random() < 0.5 else world.company_name(rng),
        em=me.email(), ph=me.mobile(), town=rng.choice(world.TOWN_NAMES))


def _payslip_q(rng, d: Doc, c: Cast):
    me = c.new()
    org = rng.choice(world.ORGS_BY_KIND["employer"])
    lab, cid = org.custom(rng)
    d.v("payslipq")
    d.f(pick(rng, "My payslip from {org} says tax code {tc}, NI number {ni}, {lab} {cid}. Why was {amt} deducted?",
             "Explain my payslip: gross {g}, net {n}, NI {ni}, tax code {tc}.",
             "I think my employer {org} got my NI number wrong, it shows {ni}. How do I fix it?"),
        org=org.name, tc=K(pick(rng, "1257L", "BR", "K475", "1257L M1", "S1257L", "C1257L", "0T"), "tax_code"),
        ni=me.ni(), lab=lab.lower(), cid=cid, amt=amount(rng, 40, 900), g=amount(rng, 1800, 6000), n=amount(rng, 1400, 4200))


def _summarise_chat(rng, d: Doc, c: Cast):
    a, b = c.new(), c.new()
    d.v("summarise")
    d.add(pick(rng, "Summarise this message thread for me:\n\n", "What is this person asking for?\n\n",
               "tl;dr this pls\n\n"))
    when = recent_date(rng, 20)
    d.f("{a}: hi it's {af}, can you send the {amt} to my new account? sort code {sc}, acc {acct}\n",
        a=a.first_name(), af=a.first_name(), amt=amount(rng, 20, 800), sc=a.sort_code(), acct=a.account())
    d.f("{b}: sure, is that still in the name {an}?\n", b=b.first_name(), an=a.full())
    d.f("{a}: yes. also I moved, new address {addr}\n", a=a.first_name(), addr=world.make_address(rng).inline(rng, a.ref))
    if rng.random() < 0.5:
        d.f("{b}: ok will do by {when}\n", b=b.first_name(), when=date_text(rng, when))


def _tenancy_application(rng, d: Doc, c: Cast):
    me = c.new()
    emp = rng.choice(world.ORGS_BY_KIND["employer"])
    lab, cid = emp.custom(rng)
    prev = world.make_address(rng)
    d.v("tenancyapp")
    d.add(pick(rng, "Help me answer a tenancy application. ", "Fill this referencing form in a tidy way. ",
               "The letting agent wants these details, can you lay them out nicely? ",
               "I'm applying for a flat, make this look professional: "))
    facts = [["Name ", me.full()], ["previous address ", prev.inline(rng, me.ref)],
             ["employer ", emp.name, " (", lab.lower(), " ", cid, ")"],
             ["salary ", amount(rng, 18000, 65000, style=1, step=500), " a year"],
             ["mobile ", me.mobile()], ["date of birth ", me.dob()]]
    if rng.random() < 0.5:
        facts.append(["I've been at my current job since ", date_text(rng, recent_date(rng, 3000, 0))])
    rng.shuffle(facts)
    sep = pick(rng, ". ", "; ", "\n", ", ")
    for i, f in enumerate(facts[: rng.randint(3, len(facts))]):
        d.add(sep if i else "", f)
    d.add(".")


def _cancel_membership(rng, d: Doc, c: Cast):
    me = c.new()
    org = rng.choice(world.ORGS_BY_KIND["saas"] + world.ORGS_BY_KIND["telecom"] + world.ORGS_BY_KIND["energy"])
    lab, cid = org.custom(rng)
    d.v("cancel")
    d.f(pick(rng, "Write an email cancelling my {o} account. ", "I want to leave {o}, draft the cancellation. ",
             "How do I word a cancellation to {o} so they can't keep charging me? ",
             "cancel my {o} subscription for me (wording only). "), o=org.name)
    d.f(pick(rng, "My {lab} is {cid}", "{lab}: {cid}", "they know me as {n}, {lab} {cid}", "ref {cid}"),
        lab=lab.lower(), cid=cid, n=me.full())
    d.f(pick(rng, " and the email on the account is {em}.", ", registered to {em}.", ". Phone on file {ph}.",
             ". Last payment was {amt} on {dt}."), em=me.email(), ph=me.phone(), amt=amount(rng, 5, 90),
        dt=date_text(rng, recent_date(rng, 40)))
    if rng.random() < 0.5:
        d.f(pick(rng, " Refunds should go to card ending {c4}.", " Sign it {n}.", " Mention I'm moving to {town}."),
            c4=me.card_last4(), n=me.full(), town=rng.choice(world.TOWN_NAMES))


def _sick_note(rng, d: Doc, c: Cast):
    me = c.new()
    boss = c.new()
    d.v("sick")
    d.f(pick(rng, "Write a short message to my manager {b} saying I'm off sick today. ",
             "Draft a sick day email to {b}, keep it professional. ",
             "tell {b} I can't come in, I've got a fever. ", "Message for my line manager {b}: I'm unwell. "),
        b=boss.first_name() if rng.random() < 0.6 else boss.full())
    d.f(pick(rng, "I should be back on {dt}. ", "My shift on {dt} might need cover. ", "GP appointment is on {dt}. ",
             ""), dt=date_text(rng, recent_date(rng, 0, 10)))
    d.f(pick(rng, "Sign it from {me}.", "I'm {me}, staff number {sid}.", "From {me} ({ph}).", "Name: {me}"),
        me=me.full() if rng.random() < 0.7 else me.first_name(), ph=me.mobile(),
        sid=rng.choice(world.ORGS_BY_KIND["employer"]).custom(rng)[1])


def _witness(rng, d: Doc, c: Cast):
    me = c.new()
    other = c.new()
    addr = world.make_address(rng)
    d.v("witness")
    d.add(pick(rng, "Turn my notes into a formal statement for the insurer: ", "Make this into a proper incident report: ",
               "Can you write this up neatly for the police report? ", "Rewrite as a clear timeline: "))
    when = recent_date(rng, 60)
    d.f(pick(rng, "on {dt} around {hh}pm I was outside {addr} when {o} reversed into my fence. ",
             "{dt}: water came through the ceiling at {addr}; the upstairs neighbour {o} wasn't in. ",
             "{o} from next door ({addr}) says the tree damage happened on {dt}. "),
        dt=date_text(rng, when), hh=str(rng.randint(1, 9)), addr=addr.inline(rng, me.ref), o=other.full())
    d.f(pick(rng, "{o} gave me their number {ph}. ", "Their insurer is {ins}. ", "Damage is about {amt}. ", ""),
        o=other.first_name(), ph=other.mobile(), ins=world.public_company(rng, "insurer"), amt=amount(rng, 150, 6000))
    d.f(pick(rng, "My policy number is {pol}.", "Statement by {me}.", "My details: {me}, {em}.", ""),
        pol=rng.choice(world.ORGS_BY_KIND["insurer"]).custom(rng)[1], me=me.full(), em=me.email())


def _dvla(rng, d: Doc, c: Cast):
    me = c.new()
    d.v("dvla")
    d.f(pick(rng, "I got a letter from the DVLA about renewing my licence. My licence number is {lic}. What do I do?",
             "Is this a real UK driving licence number format? {lic}",
             "Help me fill the change of address bit for the DVLA: licence {lic}, new address {addr}.",
             "Check my passport renewal details: passport number {pp}, name {n}, born {dob}."),
        lic=me.licence(), addr=world.make_address(rng).inline(rng, me.ref), pp=me.passport(), n=me.full(), dob=me.dob())


def _neighbour(rng, d: Doc, c: Cast):
    me = c.new()
    nb = c.new(common_word=rng.random() < 0.4)
    d.v("neighbour")
    d.f(pick(rng, "Write a friendly note to my neighbour {n} about the noise at night. ",
             "Draft a polite WhatsApp to {n} next door about the bins. ",
             "Help me ask {n} (number {num}) if their builders can stop blocking the drive. ",
             "Can you make this less passive aggressive: '{n}, your parcel was left at mine again'. "),
        n=nb.first_name(), num=nb.mobile())
    d.f(pick(rng, "We're at {street}. ", "I'm the one at {street}. ", "They live at {street2}. ", ""),
        street=world.make_address(rng).street_only(me.ref), street2=world.make_address(rng).street_only(nb.ref))
    if rng.random() < 0.5:
        d.f(pick(rng, "Sign it {me}.", "From {me} and family.", "- {me}"), me=me.first_name())
    if nb.common_word:
        ph = world.common_word_phrase(rng, nb.first)
        if ph:
            d.add(" ", ph)


def _customer_script(rng, d: Doc, c: Cast):
    cust = c.new()
    agent = c.new()
    org = rng.choice(world.SYNTH_ORGS)
    lab, cid = org.custom(rng)
    d.v("callnotes")
    d.add(pick(rng, "Summarise this call note for the CRM:\n", "Clean up these call notes:\n",
               "Turn this into a case summary:\n", "make these notes readable pls\n"))
    d.f(pick(rng, "Caller {n} verified with DOB {dob} and postcode {pc}. {lab} {cid}. ",
             "spoke to {n} ({ph}), passed security (dob {dob}, pc {pc}). acct {cid}. ",
             "{lab} {cid} - customer {n} rang re missing payment of {amt}. Verified DOB {dob}. "),
        n=cust.full(), dob=cust.dob(), pc=world.make_address(rng).postcode(cust.ref, lower=rng.random() < 0.3),
        lab=lab, cid=cid, ph=cust.phone(), amt=amount(rng, 10, 900))
    d.f(pick(rng, "Agreed callback {dt}. Agent {a}.", "Refund of {amt} raised. Handled by {a}.",
             "Customer unhappy, escalated to {a}.", "Sent email to {em}. {a}"),
        dt=date_text(rng, recent_date(rng, 0, 7)), a=agent.first_name(), amt=amount(rng, 5, 400), em=cust.email())


def _wedding_list(rng, d: Doc, c: Cast):
    people = [c.new(common_word=rng.random() < 0.25) for _ in range(rng.randint(3, 6))]
    d.v("guestlist")
    d.add(pick(rng, "Sort this guest list alphabetically by surname:\n", "Make labels for these invitations:\n",
               "Put this list into a table with name and address:\n", "Who's missing a postcode here?\n"))
    for p in people:
        a = world.make_address(rng)
        if rng.random() < 0.7:
            d.add(p.full(), pick(rng, ", ", " - ", ": "), a.inline(rng, p.ref), "\n")
        else:
            d.add(p.full(), pick(rng, ", ", " - "), a.inline(rng, p.ref, postcode=False), "\n")


def _email_signature(rng, d: Doc, c: Cast):
    me = c.new()
    org = rng.choice(world.SYNTH_ORGS)
    d.v("signature")
    d.add(pick(rng, "Design a clean email signature with these details: ", "Make my email signature look professional: ",
               "Format this as an email footer: "))
    parts = [me.full(), pick(rng, "Senior Associate", "Office Manager", "Lettings Negotiator", "Payroll Officer",
                             "Customer Success Lead", "Trainee Solicitor"), org.name,
             me.work_email(org.domain), me.mobile(), E(ids.landline_number(rng, 0), "PHONE")]
    if rng.random() < 0.4:
        parts.append(world.make_address(rng).inline(rng))
    sep = pick(rng, " | ", ", ", "\n", " / ")
    for i, p in enumerate(parts):
        d.add(sep if i else "", p)


def _loan_letter(rng, d: Doc, c: Cast):
    me = c.new()
    bank = world.public_company(rng, "bank")
    d.v("hardship")
    d.f(pick(rng, "Write a financial hardship letter to {b}. ", "Help me ask {b} for a payment holiday. ",
             "Draft a letter to {b} explaining I lost my job and can't pay {amt} this month. "),
        b=bank, amt=amount(rng, 80, 1200))
    facts = [["My account number is ", me.account(), " and sort code ", me.sort_code(), "."],
             ["The card is ", me.card(), "."], ["I'm ", me.full(), ", born ", me.dob(), "."],
             ["Address: ", world.make_address(rng).inline(rng, me.ref), "."],
             ["I can afford ", amount(rng, 10, 150, step=5), " a month from ", date_text(rng, recent_date(rng, 0, 40)), "."]]
    rng.shuffle(facts)
    for f in facts[: rng.randint(2, 4)]:
        d.add(" ", f)


TASKS_EXTRA = [(_tenancy_application, 5), (_cancel_membership, 6), (_sick_note, 5), (_witness, 4), (_dvla, 3),
               (_neighbour, 5), (_customer_script, 5), (_wedding_list, 3), (_email_signature, 3), (_loan_letter, 4)]


TASKS = [(_complaint, 12), (_landlord_email, 10), (_bank_check, 8), (_hmrc_letter, 6), (_form_fill, 8),
         (_translate, 5), (_reference, 5), (_card_fraud, 7), (_gp_request, 5), (_flatmates, 5), (_address_fix, 5),
         (_sar, 4), (_birthday, 4), (_parking, 4), (_cv_help, 5), (_payslip_q, 5), (_summarise_chat, 5)] + TASKS_EXTRA

# --------------------------------------------------------------------------- negatives
NEG_TEMPLATES = [
    "What notice does a landlord have to give under the {statute}?",
    "Explain the difference between a sort code, an account number and an IBAN in simple words.",
    "How do I read my {co} bill? The standing charge is {amt} a day and the unit rate went up on {date}.",
    "Is {amt} a fair deposit for a flat that rents at {amt2} a month?",
    "Rewrite this clause in plain English: \"The Tenant shall not assign, sublet or part with possession of the Property or any part of it without the prior written consent of the Landlord, such consent not to be unreasonably withheld.\"",
    "Write a template letter to a landlord about damp, with placeholders like {ph1} and {ph2}.",
    "Draft an email to the whole team about the office move to {place} on {date}.",
    "What's a P60 and when should I get it?",
    "My energy bill went from {amt} to {amt2} in {month}, is that normal for a 2 bed flat?",
    "Summarise the main rights a tenant has under the {statute}.",
    "Give me a checklist for moving house in the UK: utilities, council tax, TV licence, GP, DVLA.",
    "What is the difference between {prod} and {prod2}?",
    "How long do I have to return something bought online under the {statute}?",
    "Order {ref} from {co} arrived damaged. What should I say in a complaint? Don't include my details yet.",
    "Write a polite chaser for invoice {ref} which was due on {date} for {amt}.",
    "Can you explain what clause {cl} of a standard NDA usually covers?",
    "Make a weekly budget: rent {amt}, food {amt2}, travel {amt3}.",
    "How do I find my NI number if I've lost it? Don't need mine, just the general steps.",
    "What does {co} mean by a 'final notice' and what happens after it?",
    "Is it legal for an employer to deduct {amt} from wages for a uniform under the {statute}?",
    "Write a short LinkedIn post celebrating our team hitting {amt} in sales this quarter.",
    "Translate 'please call the surgery to rebook your appointment' into Polish.",
    "What should a good tenancy inventory include? Mention {place} style communal areas.",
    "List the documents a solicitor usually asks for in an ID check for buying a house.",
    "Draft a reply to a customer who says their {prod} stopped working after {n} days.",
    "I hope you can help: May I pay council tax in 12 instalments instead of 10?",
    "We will be closing the office for the bank holiday. Write a short notice.",
    "What's the best way to complain to {co} about a delayed refund of {amt}?",
    "Explain how a direct debit guarantee works in the UK.",
    "Write a short guide for new tenants on how to report repairs.",
    "What happens if I miss a council tax payment of {amt}?",
    "Is it normal for a letting agent to charge {amt} for a reference check after the {statute}?",
    "Compare {prod} and {prod2} for a family of four.",
    "Draft a generic out-of-office reply for the week of {date}.",
    "What should be in a good complaint letter? Give me a structure with headings.",
    "How do I calculate pro-rata holiday if I start on {date}?",
    "Summarise what a letter of engagement from a solicitor normally contains.",
    "Can a landlord keep a deposit for normal wear and tear?",
    "Create a checklist for an end of tenancy clean.",
    "Explain tax codes like 1257L and BR in plain English.",
    "How long should I keep bank statements and payslips?",
    "Write a polite reminder template for unpaid invoices, with placeholders {ph1} and {ph2}.",
    "What does 'jointly and severally liable' mean in a tenancy agreement?",
    "Give me five subject lines for an email chasing a refund from {co}.",
    "How do energy price caps work? Our unit rate is now {amt} per kWh.",
    "My phone contract with {co} ends on {date}. Should I switch to SIM only?",
    "Explain what a section 21 notice was and what replaced it under the {statute}.",
    "Turn this into a friendly team message: the office kitchen will be closed on {date} for deep cleaning.",
    "What is a reasonable notice period for a part-time job?",
    "Write a short FAQ about how we handle customer data, no names needed.",
    "How do I read an itemised phone bill? There's a charge of {amt} I don't recognise.",
    "Rewrite this job advert to be more inclusive: 'We need a young, energetic sales guy to join our {place} team.'",
    "What documents prove right to work in the UK?",
    "Give me a template to request a copy of my data under the {statute}, using {ph1} for my name.",
    "How do I dispute a parking charge from a private car park at {place}?",
    "Is {amt} too much for a boiler service?",
    "Explain the difference between a P45 and a P60.",
    "Draft meeting minutes headings for a residents' association meeting about {place}.",
    "Our team spent {amt} on travel last quarter. Write a one-paragraph summary for the budget report.",
    "Make a packing list for a weekend in the Lake District.",
    "What should I check before signing an NDA for a freelance job?",
    "How does the {statute} affect deposits?",
    "Rewrite this more politely: '{r1} will collect the keys from {r2} on {date}. Call {r3} if late.'",
    "Summarise: {r1} emailed {r4} about invoice {ref} for {amt}; {r4} says it was paid on {date}.",
    "Translate into Polish: 'Dear {r1}, your appointment is confirmed. Please bring {r5}.'",
    "Is this redacted text still readable? '{r1} ({r6}) lives at {r2}, {r7}, and banks with {co}.'",
]

NEG_TOPICS = ["tenancy deposits", "council tax bands", "energy bills", "payslip deductions", "National Insurance contributions",
              "phone contracts", "online refunds", "data subject access requests", "job interviews", "writing a CV",
              "international bank transfers", "cash ISAs", "remortgaging", "workplace pensions", "statutory sick pay",
              "holiday entitlement", "private parking charges", "home insurance claims", "boiler repairs",
              "moving house", "switching broadband", "the TV licence", "student loan repayments",
              "Self Assessment tax returns", "VAT registration for sole traders", "invoicing clients",
              "NDAs for freelancers", "employment contracts", "notice periods", "redundancy pay", "flexible working requests",
              "rent increases", "mould and damp in rented homes", "credit scores", "direct debits", "standing orders",
              "chargebacks on card payments", "GP registration", "hospital appointment letters", "jury service",
              "electoral registration", "right to work checks", "probation reviews", "expense claims", "maternity pay"]
NEG_FORMS = ["Explain {t} in simple terms.", "What are the most common mistakes people make with {t}?",
             "Give me a checklist for {t}.", "Write a short blog intro about {t}.", "What should I ask an adviser about {t}?",
             "Summarise the rules on {t} in five bullet points.", "Make a one-page cheat sheet on {t}.",
             "What are my rights when it comes to {t}?", "Write a template email about {t} with placeholders like {ph1}.",
             "Create a quiz with 5 questions about {t}.", "How do {t} work for someone on a zero-hours contract?",
             "What changed recently with {t}?", "Explain {t} to a 16 year old starting their first job.",
             "Draft an internal FAQ on {t} for our HR team.", "List the pros and cons of {t}.",
             "Give me a step-by-step plan for sorting out {t}.", "Write a LinkedIn post about {t}, no names.",
             "Compare how {t} work in England and Scotland.", "What paperwork do I need for {t}?",
             "Rewrite this to be clearer: 'Please note {t} must be reviewed annually.'"]
NEG_DETAILS = [" For context, it's with {co}.", " The amount involved is {amt}.", " It starts on {date}.",
               " We're based near {place}.", " I read something about the {statute}.", " Our budget is {amt}.",
               " The deadline was {date}.", " The product is {prod}.", " Reference {ref} if it matters.",
               " Keep it under {n} words.", " I'm in {town}.", ""]


def _negative_comp(rng, d: Doc):
    t = rng.choice(NEG_TOPICS)
    form = rng.choice(NEG_FORMS)
    d.v("negc")
    if rng.random() < 0.3 and _context(rng, d, lead=False):
        d.add(" ")
    d.f(form, t=t, ph1=K(pick(rng, "[Name]", "[Your name]", "<customer name>", "{{first_name}}", "[Address]"), "placeholder"))
    for det in rng.sample(NEG_DETAILS, rng.randint(0, 2)):
        d.f(det, co=world.public_company(rng), amt=amount(rng, 5, 3000), date=date_text(rng, recent_date(rng, 300, 90)),
            place=world.place_trap(rng), statute=world.statute(rng), prod=world.product(rng),
            ref=world.doc_ref(rng, pick(rng, "order", "invoice", "ticket")), n=str(rng.choice([100, 150, 200, 250, 300])),
            town=rng.choice(world.TOWN_NAMES))



def _negative(rng, d: Doc):
    t = rng.choice(NEG_TEMPLATES)
    d.v("neg" + str(NEG_TEMPLATES.index(t)))
    if rng.random() < 0.35 and _context(rng, d, lead=False):
        d.add(" ")
    d.f(t, statute=world.statute(rng), co=world.public_company(rng, pick(rng, "energy", "telecom", "retail", "bank", "water")),
        amt=amount(rng, 0.2, 1500), amt2=amount(rng, 40, 2500), amt3=amount(rng, 20, 200),
        date=date_text(rng, recent_date(rng, 200, 60)), place=world.place_trap(rng),
        month=K(pick(rng, "January", "February", "November", "December"), "date"),
        prod=world.product(rng), prod2=world.product(rng), ref=world.doc_ref(rng, pick(rng, "order", "invoice")),
        cl=K(f"{rng.randint(1, 14)}.{rng.randint(1, 9)}", "clause_number"), n=str(rng.randint(2, 40)),
        ph1=K(pick(rng, "[Your Name]", "[Landlord's name]", "<NAME>"), "placeholder"),
        ph2=K(pick(rng, "[Your Address]", "[Property address]", "<ADDRESS>"), "placeholder"),
        r1=K("[PERSON_1]", "placeholder"), r2=K("[ADDRESS_1]", "placeholder"), r3=K("[PHONE_1]", "placeholder"),
        r4=K("[PERSON_2]", "placeholder"), r5=K("[ID_DOC_1]", "placeholder"), r6=K("[DOB_1]", "placeholder"),
        r7=K("[POSTCODE_1]", "placeholder"))


@register("ai_prompt", weight=20, neg_weight=40, short=True)
def ai_prompt(rng: random.Random, neg: bool) -> Doc:
    d = Doc("ai_prompt", "ai_prompt/v1")
    d.add(rng.choice(OPENERS))
    if neg:
        (_negative_comp if rng.random() < 0.6 else _negative)(rng, d)
    else:
        c = Cast(rng, common_word_rate=0.12)
        fn = rng.choices([t for t, _ in TASKS], [w for _, w in TASKS])[0]
        if rng.random() < 0.3 and _context(rng, d, lead=False):
            d.add(" ")
        fn(rng, d, c)
        if rng.random() < 0.4:
            _context(rng, d)
        if rng.random() < 0.15:  # a second request in the same prompt
            fn2 = rng.choices([t for t, _ in TASKS], [w for _, w in TASKS])[0]
            d.add(pick(rng, "\n\nAlso, ", "\n\nAnd one more thing: ", " Also "))
            fn2(rng, d, c)
        for p in c.people:
            if p.common_word and rng.random() < 0.5:
                ph = world.common_word_phrase(rng, p.first)
                if ph:
                    d.add(" ", ph)
                    break
    d.add(rng.choice(CLOSERS))
    r = rng.random()
    if r < 0.12:
        d.atoms = noise.lower_all(d.atoms)
        d.v("lower")
    if rng.random() < 0.25:
        d.atoms = noise.typos(d.atoms, rng, 0.05)
        d.v("typos")
    return d
