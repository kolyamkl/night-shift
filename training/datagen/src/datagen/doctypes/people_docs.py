"""CVs and HR new-starter forms."""
from __future__ import annotations

import random
from datetime import date

from .. import ids, world
from ..core import Doc, E, HC, K
from ..core import fmt as _f
from ..names import Cast, Person
from . import register
from .common import TODAY, amount, date_text, kv_block, pick, recent_date

# =========================================================================== CV
FAMILIES = {
    "finance": dict(
        titles=["Assistant Accountant", "Management Accountant", "Credit Controller", "Finance Manager", "Payroll Administrator",
                "Accounts Payable Clerk"],
        profile=["Qualified ACCA accountant with a strong record in month-end close and reporting.",
                 "Detail-focused finance professional experienced in Sage and Xero.",
                 "Commercially minded accountant who enjoys turning numbers into decisions."],
        products=["Xero", "Sage 200", "QuickBooks Online", "Power BI"],
        bullets=["Prepared monthly management accounts for a business turning over {amt}.",
                 "Reduced aged debt by {pct}% in six months.",
                 "Ran weekly and monthly payroll for {n} staff.",
                 "Led the move from spreadsheets to {prod}.",
                 "Prepared VAT returns and supported the year-end audit.",
                 "Managed a budget of {amt} across three cost centres."]),
    "care": dict(
        titles=["Healthcare Assistant", "Senior Care Assistant", "Staff Nurse", "Support Worker", "Deputy Care Manager"],
        profile=["Compassionate carer with experience in residential and domiciliary settings.",
                 "NMC registered nurse with experience on busy medical wards.",
                 "Reliable support worker who puts dignity and choice first."],
        products=["the eMAR system", "PCS care planning"],
        bullets=["Supported up to {n} residents with personal care and medication.",
                 "Completed care plans and risk assessments on the electronic system.",
                 "Mentored new starters through the Care Certificate.",
                 "Worked closely with district nurses and GP practices.",
                 "Took part in CQC inspection rated Good."]),
    "tech": dict(
        titles=["Software Engineer", "Senior Developer", "Data Analyst", "IT Support Technician", "DevOps Engineer", "QA Tester"],
        profile=["Backend engineer who likes simple, well-tested systems.",
                 "Data analyst comfortable with SQL, Python and Power BI.",
                 "Friendly IT support technician with strong troubleshooting skills."],
        products=["Microsoft 365", "Google Workspace", "Azure", "AWS"],
        bullets=["Built REST APIs in Python and PostgreSQL serving {n}k requests a day.",
                 "Cut cloud costs by {amt} a year by right-sizing services.",
                 "Introduced automated tests, raising coverage to {pct}%.",
                 "Supported {n} users across two offices.",
                 "Migrated email to {prod} with no downtime."]),
    "retail": dict(
        titles=["Store Manager", "Warehouse Supervisor", "Team Leader", "Customer Service Advisor", "Shift Manager", "Picker Packer"],
        profile=["Hard-working team leader with experience in fast-paced retail.",
                 "Warehouse supervisor with forklift (counterbalance) licence.",
                 "Customer-focused advisor who keeps calm under pressure."],
        products=["the new till system"],
        bullets=["Managed a team of {n} across early and late shifts.",
                 "Increased weekly sales by {pct}% through better merchandising.",
                 "Handled cash and card reconciliations of up to {amt} a day.",
                 "Trained new colleagues on health and safety and manual handling.",
                 "Resolved customer complaints by phone, email and chat."]),
    "teaching": dict(
        titles=["Teaching Assistant", "Primary Teacher", "Secondary Maths Teacher", "SENCO", "Learning Support Assistant"],
        profile=["Enthusiastic teacher with QTS and five years in primary schools.",
                 "Patient teaching assistant experienced in supporting pupils with SEND.",
                 "Maths specialist who makes lessons practical and engaging."],
        products=["Google Classroom"],
        bullets=["Taught classes of up to {n} pupils across Key Stages 2 and 3.",
                 "Raised the share of pupils meeting expected standard by {pct}%.",
                 "Led after-school clubs and the school trip to {place}.",
                 "Wrote EHCP reviews with parents and specialists."]),
    "legal": dict(
        titles=["Paralegal", "Legal Secretary", "Conveyancing Assistant", "Office Manager", "Compliance Officer"],
        profile=["Organised paralegal with experience in residential conveyancing.",
                 "Experienced legal secretary with fast, accurate typing.",
                 "Compliance officer familiar with AML checks and file audits."],
        products=["LEAP", "Clio"],
        bullets=["Handled a caseload of {n} conveyancing files from instruction to completion.",
                 "Ran ID and AML checks under the {statute}.",
                 "Prepared completion statements and SDLT returns.",
                 "Managed diaries and billing for three partners."]),
    "trades": dict(
        titles=["Electrician", "Plumber", "Site Manager", "Joiner", "Maintenance Technician", "Gas Engineer"],
        profile=["Qualified electrician (18th Edition) with domestic and commercial experience.",
                 "Gas Safe registered engineer with a clean driving licence.",
                 "Site manager with SMSTS and a strong safety record."],
        products=["Worcester Bosch boiler", "air source heat pump", "Hive thermostat", "solar PV"],
        bullets=["Completed rewires and EICRs on {n} rental properties.",
                 "Installed and serviced {prod} systems.",
                 "Delivered a {amt} refurbishment on time and on budget.",
                 "Supervised subcontractors and ran daily toolbox talks."]),
}
UNIS = ["University of Leeds", "Manchester Metropolitan University", "University of Bristol", "Cardiff University",
        "University of Glasgow", "The Open University", "University of Birmingham", "Sheffield Hallam University",
        "University of Nottingham", "Leeds Beckett University", "University of Warsaw", "Taras Shevchenko National University of Kyiv",
        "University of Lagos", "University of Mumbai", "Trinity College Dublin", "University College Cork", "Northumbria University",
        "University of the West of England", "Coventry University", "Ulster University"]
DEGREES = ["BA (Hons) Business Management", "BSc (Hons) Computer Science", "BSc Nursing (Adult)", "LLB Law", "BA (Hons) English",
           "BSc (Hons) Accounting and Finance", "BA Primary Education with QTS", "BSc Mathematics", "HND Construction",
           "MSc Data Science", "BA (Hons) Marketing"]
SKILLS = ["Microsoft Excel (advanced)", "Xero", "Sage 50", "Python", "SQL", "Customer service", "First Aid at Work", "Forklift licence",
          "Fluent Ukrainian", "Polish (native)", "Punjabi and Hindi", "Full UK driving licence", "CSCS card", "Safeguarding Level 2",
          "Power BI", "Salesforce", "Team leadership", "Report writing", "Yoruba (fluent)", "Irish (conversational)"]


def _mon(d: date) -> str:
    return f"{ids.MONTHS[d.month - 1][:3]} {d.year}"


def _cv_contact(rng, d: Doc, p: Person, md: bool):
    r = rng.random()
    addr = world.make_address(rng)
    if r < 0.4:  # one line, town only
        parts = [p.email(), p.mobile()]
        if rng.random() < 0.7:
            parts.append(rng.choice(world.TOWN_NAMES))
        rng.shuffle(parts)
        sep = pick(rng, " | ", " · ", " • ", "  |  ", ", ")
        for i, x in enumerate(parts):
            if i:
                d.add(sep)
            d.add(x)
        d.add("\n")
    elif r < 0.75:  # labelled lines
        d.add(pick(rng, "Address: ", "Home: ", ""), addr.inline(rng, p.ref), "\n")
        d.add(pick(rng, "Mobile: ", "Tel: ", "Phone: ", "M: "), p.mobile(), "\n")
        d.add(pick(rng, "Email: ", "E-mail: ", "E: "), p.email(), "\n")
    else:  # address block (older style)
        d.add(addr.block(rng, p.ref), "\n", p.phone(), "\n", p.email(), "\n")
    if rng.random() < 0.25:  # older UK CVs still carry personal details
        d.v("personal")
        d.add("\n", "**Personal details**\n" if md else "PERSONAL DETAILS\n")
        d.add("Date of birth: ", p.dob().with_hard("dob_near_dates"), "\n")
        d.add("Nationality: ", pick(rng, "British", "Irish", "Ukrainian", "Polish", "British/Nigerian", "Indian"), "\n")
        if rng.random() < 0.4:
            d.add("Driving licence: ", pick(rng, "Full UK, clean", "Full UK manual", "Provisional"), "\n")
        if rng.random() < 0.15:
            d.add("NI number: ", p.ni(), "\n")


def _cv_refs(rng, d: Doc, c: Cast, md: bool):
    d.add("\n", "## References\n" if md else "REFERENCES\n")
    if rng.random() < 0.45:
        d.add(pick(rng, "Available on request.", "References available on request.", "Available upon request"), "\n")
        return
    for _ in range(rng.randint(1, 2)):
        r = c.new()
        co = world.company_name(rng) if rng.random() < 0.6 else world.public_company(rng, "employer")
        if rng.random() < 0.5:
            d.add(r.full(), pick(rng, ", ", " - "), pick(rng, "Line Manager", "Operations Director", "Head of Department", "Team Leader"),
                  ", ", co, "\n", pick(rng, "Tel: ", "", "Phone: "), r.phone(), pick(rng, " | ", "\n"), r.email(), "\n")
        else:
            d.add(r.title_full(), "\n", pick(rng, "Former manager at ", "Supervisor, "), co, "\n", r.work_email(world.domain_for(co.text)), "\n")


@register("cv", weight=3, neg_weight=0)
def cv(rng: random.Random, neg: bool) -> Doc:
    d = Doc("cv", "cv/v1")
    c = Cast(rng, common_word_rate=0.07)
    p = c.new(min_age=19, max_age=64)
    md = rng.random() < 0.5
    fam = rng.choice(list(FAMILIES))
    F = FAMILIES[fam]
    d.v("md" if md else "plain").v(fam)
    if rng.random() < 0.15:
        d.add(pick(rng, "CURRICULUM VITAE", "Curriculum Vitae", "CV"), "\n\n")
    r = rng.random()
    name = p.caps() if r < 0.3 else p.full_middle() if r < 0.45 else p.full()
    d.add("# " if md else "", name, "\n")
    roles = [rng.choice(F["titles"]) for _ in range(4)]
    if rng.random() < 0.5:
        d.add(roles[0], "\n")
    _cv_contact(rng, d, p, md)
    H = (lambda t: f"\n## {t}\n") if md else (lambda t: f"\n{t.upper()}\n")
    d.add(H(pick(rng, "Profile", "Personal statement", "Summary", "About me")), rng.choice(F["profile"]), " ",
          pick(rng, "Looking for a new challenge.", "Available immediately.", "Happy to relocate.", "Seeking a permanent role.", ""), "\n")
    d.add(H(pick(rng, "Experience", "Employment history", "Work experience", "Career history")))
    end = TODAY
    earliest = max(1985, p.dob_date.year + 17)
    for i in range(rng.randint(2, 4)):
        if end.year < earliest:
            break
        start = date(max(earliest, end.year - rng.randint(1, 6)), rng.randint(1, 12), 1)
        if start > end:
            start = date(end.year, 1, 1)
        co = world.public_company(rng, pick(rng, "employer", "retail", "bank", "telecom")) if rng.random() < 0.45 else world.company_name(rng)
        dates = [K(_mon(start), "date"), pick(rng, " - ", " – ", " to "), K("Present", "date") if i == 0 and rng.random() < 0.6 else K(_mon(end), "date")]
        title = roles[i]
        town = rng.choice(world.TOWN_NAMES)
        if md:
            d.add("### ", title, " - ", co, ", ", town, "\n*", dates, "*\n")
        else:
            o, cl = rng.choice([("  ", ""), (" (", ")"), ("\n", ""), (" | ", "")])
            d.add(title, pick(rng, ", ", " | ", " at "), co, pick(rng, ", " + town, ""), o, dates, cl, "\n")
        for b in rng.sample(F["bullets"], rng.randint(2, min(4, len(F["bullets"])))):
            d.add("- " if md or rng.random() < 0.7 else "• ",
                  _f(b, amt=amount(rng, 20000, 4000000, style=1, step=1000), pct=str(rng.randint(5, 45)), n=str(rng.randint(3, 120)),
                     prod=K(rng.choice(F["products"]), "product"), place=world.place_trap(rng),
                     statute=K(pick(rng, "Money Laundering Regulations 2017", "Proceeds of Crime Act 2002"), "statute")), "\n")
        end = date(start.year - 1, 12, 1) if start.month == 1 else date(start.year, start.month - 1, 1)
    d.add(H("Education"))
    grad = rng.randint(max(1985, p.dob_date.year + 21), 2024) if p.dob_date.year + 21 <= 2024 else 2024
    d.add(pick(rng, *DEGREES), ", ", rng.choice(UNIS), ", ", K(str(grad - 3), "date"), pick(rng, "-", " - ", "–"), K(str(grad), "date"), "\n")
    if rng.random() < 0.5:
        d.add(pick(rng, "A-levels: ", "A Levels - "), pick(rng, "Maths (A), Economics (B), English (B)", "Biology, Chemistry, Psychology",
                                                         "BTEC Business (Distinction*)"), "\n")
    d.add(H("Skills"), ", ".join(rng.sample(SKILLS, rng.randint(3, 6))), "\n")
    if rng.random() < 0.3:
        d.add(H("Interests"), pick(rng, "Running, cooking and volunteering at ", "Football, reading and "), world.place_trap(rng), ".\n")
    _cv_refs(rng, d, c, md)
    return d


# =========================================================================== HR new starter form
JOBS = [("Warehouse Operative", "Operations"), ("Customer Service Advisor", "Customer Services"), ("Care Assistant", "Care"),
        ("Junior Developer", "Technology"), ("Finance Assistant", "Finance"), ("Teaching Assistant", "Learning Support"),
        ("Delivery Driver", "Logistics"), ("Marketing Executive", "Marketing"), ("Payroll Administrator", "Finance"),
        ("Night Care Worker", "Care"), ("Site Supervisor", "Operations"), ("Receptionist", "Front of House")]
RELATIONSHIPS = ["Partner", "Wife", "Husband", "Mother", "Father", "Sister", "Brother", "Friend", "Son", "Daughter", "Flatmate"]


def _label_case(rows, upper: bool):
    return [(lab.upper() if upper else lab, v) for lab, v in rows]


def _section(rng, d: Doc, title: str, rows, style: int, upper: bool, md: bool):
    if md:
        d.add("### ", title, "\n")
    else:
        d.add(title.upper() if rng.random() < 0.5 else title, "\n", pick(rng, "", "-" * len(title) + "\n"))
    d.add(kv_block(rng, _label_case(rows, upper), style), "\n")


@register("hr_form", weight=3, neg_weight=0)
def hr_form(rng: random.Random, neg: bool) -> Doc:
    d = Doc("hr_form", "hr_form/v1")
    c = Cast(rng, common_word_rate=0.07)
    org = rng.choice(world.ORGS_BY_KIND["employer"])
    emp = c.new(min_age=17, max_age=66)
    mgr = c.new()
    style = rng.choice([0, 0, 1, 2])
    upper = style != 1 and rng.random() < 0.2
    md = style == 1 or rng.random() < 0.3
    d.v(f"s{style}")
    title = pick(rng, "New Starter Form", "New Employee Details", "Starter Checklist and Personal Details", "Employee Information Form",
                 "Onboarding form - personal details")
    d.add("# " if md else "", org.name, " - " if rng.random() < 0.6 else "\n", title, "\n")
    d.add(pick(rng, "Please complete all sections in BLOCK CAPITALS and return to HR before your first day.\n\n",
               "Confidential once completed.\n\n", "\n"))
    addr = world.make_address(rng, flat_rate=0.35)
    # personal details
    rows: list = [("Title", emp.title)]
    if rng.random() < 0.5:
        rows += [("Surname", emp.last_name()),
                 ("Forename(s)", emp.e(f"{emp.first} {emp.middle}" if emp.middle else emp.first))]
    else:
        rows += [("Full name", emp.full_middle())]
    if rng.random() < 0.5:
        rows.append(("Preferred name", emp.nickname()))
    rows += [("Date of birth", emp.dob().with_hard("dob_near_dates")), ("National Insurance number", emp.ni())]
    addr_style = rng.random()
    if style == 1:
        rows.append(("Home address", HC("address_in_table", addr.inline(rng, emp.ref, postcode=False))))
        rows.append(("Postcode", addr.postcode(emp.ref)))
    elif addr_style < 0.4:
        rows.append(("Home address", addr.inline(rng, emp.ref, postcode=False)))
        rows.append(("Postcode", addr.postcode(emp.ref, lower=rng.random() < 0.1)))
    elif addr_style < 0.7 and style == 0:
        rows.append(("Home address", ["\n", addr.block(rng, emp.ref)]))
    else:
        rows.append(("Home address", addr.inline(rng, emp.ref)))
    rows.append(("Mobile", emp.mobile()))
    if rng.random() < 0.3:
        rows.append(("Home phone", emp.landline()))
    rows.append(("Personal email", emp.email()))
    _section(rng, d, pick(rng, "Section 1: Personal details", "Personal details", "1. About you"), rows, style, upper, md)
    # emergency contact
    if rng.random() < 0.85:
        ec = c.new()
        rel = rng.choice(["Partner", "Wife", "Mother", "Sister", "Friend", "Daughter", "Flatmate"] if ec.female
                         else ["Partner", "Husband", "Father", "Brother", "Friend", "Son", "Flatmate"])
        rows = [("Name", ec.full()), ("Relationship", rel), ("Phone", ec.mobile())]
        if rng.random() < 0.3:
            rows.append(("Alternative phone", ec.landline()))
        if rng.random() < 0.2:
            rows.append(("Address", pick(rng, "Same as above", "As above") if rng.random() < 0.5 else world.make_address(rng).inline(rng, ec.ref)))
        _section(rng, d, pick(rng, "Section 2: Emergency contact", "Emergency contact", "2. Next of kin"), rows, style, upper, md)
    # bank details
    rows = [("Account holder name", emp.caps() if rng.random() < 0.4 else emp.full()),
            ("Bank / building society", K(emp.bank_name, "public_company")),
            ("Sort code", emp.sort_code()), ("Account number", emp.account(rng.random() < 0.15))]
    if rng.random() < 0.2:
        rows.append(("Building society roll number", pick(rng, "N/A", "n/a", "-")))
    _section(rng, d, pick(rng, "Section 3: Bank details for salary", "Bank details", "3. Payment details"), rows, style, upper, md)
    # right to work
    doc_kind = rng.random()
    if doc_kind < 0.55:
        rows = [("Document seen", pick(rng, "UK passport", "Irish passport", "Passport")), ("Passport number", emp.passport()),
                ("Expiry date", date_text(rng, recent_date(rng, 0, 2500)))]
    elif doc_kind < 0.85:
        rows = [("Document seen", "UK photocard driving licence"), ("Licence number", emp.licence()),
                ("Valid to", date_text(rng, recent_date(rng, 0, 3000)))]
    else:
        rows = [("Document seen", "Share code (online check)"), ("Share code", K(ids.from_pattern(rng, "@## ### ###"), "doc_reference")),
                ("Checked on", date_text(rng, recent_date(rng, 60)))]
    _section(rng, d, pick(rng, "Section 4: Right to work", "Right to work check (HR use)", "4. Identity documents"), rows, style, upper, md)
    # employment details
    lab, eid = org.custom(rng)
    start = recent_date(rng, 60, 45)
    job, dept = rng.choice(JOBS)
    rows = [(lab, eid), ("Job title", job), ("Department", dept),
            ("Line manager", mgr.full() if rng.random() < 0.7 else mgr.title_last()),
            ("Start date", date_text(rng, start)),
            ("Salary", [amount(rng, 18000, 52000, style=1, step=250), pick(rng, " per annum", " p.a.", "", " pro rata")]),
            ("Contracted hours", pick(rng, "37.5 per week", "40 per week", "22.5 per week", "Zero hours"))]
    if rng.random() < 0.5:
        rows.insert(rng.randint(1, len(rows)), ("Pay frequency", pick(rng, "Monthly", "Weekly", "4-weekly")))
    _section(rng, d, pick(rng, "Section 5: Employment details (office use only)", "For HR use", "5. Job details"), rows, style, upper, md)
    # starter declaration
    box = lambda on: pick(rng, "[x]", "[X]", "☑") if on else pick(rng, "[ ]", "☐")
    d.add(pick(rng, "Starter declaration\n", "### Starter checklist\n" if md else "STARTER CHECKLIST\n", "Tax information\n"))
    st = rng.choice("ABC")
    for letter, text in (("A", "This is my first job since 6 April and I have not had taxable benefits"),
                         ("B", "This is now my only job"), ("C", "I have another job or receive a pension")):
        d.add(box(letter == st), " Statement ", letter, ": ", text, "\n")
    d.add(box(rng.random() < 0.5), " P45 provided\n", box(rng.random() < 0.4), " Student loan (", pick(rng, "Plan 1", "Plan 2", "Plan 4", "Postgraduate"), ")\n")
    if rng.random() < 0.4:
        d.add(box(rng.random() < 0.5), " I agree to the ", K(pick(rng, "Data Protection Act 2018", "UK GDPR"), "statute"),
              " privacy notice\n")
    d.add("\n")
    # signatures
    d.add(pick(rng, "Employee signature: ", "Signed (employee): "), pick(rng, "____________", "[signed]", ""), "   ",
          "Print name: " if rng.random() < 0.6 else "", emp.full() if rng.random() < 0.5 else emp.caps(), "   Date: ",
          date_text(rng, start), "\n")
    if rng.random() < 0.8:
        d.add(pick(rng, "Manager signature: ", "Authorised by: ", "Checked by: "), mgr.full("signature_name"),
              pick(rng, "", ", Line Manager", ", HR Advisor", " (Manager)"), "   Date: ", date_text(rng, recent_date(rng, 30, 30)), "\n")
    if rng.random() < 0.3:
        d.add("\nHR use: entered on ", K(pick(rng, "Sage HR", "BrightHR", "Xero Payroll", "iTrent"), "product"), " by ",
              c.new().first_name(), " on ", date_text(rng, recent_date(rng, 30)), ".\n")
    return d
