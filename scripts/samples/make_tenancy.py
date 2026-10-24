"""A long synthetic assured periodic tenancy agreement with an e-signature log, in the layout of a
lettings agency contract. Every name, address, number, IP address and reference is invented; IP
addresses come from the documentation ranges (RFC 5737, RFC 3849). The clause text is original.

Writes the app sample data/synthetic/pdfs/31_assured_periodic_tenancy.pdf and its answer key
(.gold.json, in the format of the other samples: the text as the app extracts it, every occurrence of
every personal value with its offsets and type). Run from backend/ so the app and evalkit import:

    cd backend && uv run python ../scripts/samples/make_tenancy.py ../data/synthetic/pdfs
"""

import html
import json
import sys
from pathlib import Path

import pymupdf

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "backend"))
from app.extract import extract_pdf  # noqa: E402
from evalkit.spans import locate  # noqa: E402

OUT = Path(sys.argv[1])
NAME = "31_assured_periodic_tenancy"

# ---------- The people and places (all invented) ----------
T1 = {"title": "Mr", "name": "Tomasz Wierzbicki", "initials": "TW", "email": "t.wierzbicki@mailbox.example",
      "phone": "07700 900481", "ip": "198.51.100.23", "ref": "08F242F3-AAAD-4631-915F-D28E74946264",
      "agreed": "18-08-2026 09:41:27", "signed": "18 Aug 26", "passport": "548213976", "dob": "02/11/1994"}
T2 = {"title": "Ms", "name": "Leila Haddad-Noor", "initials": "LH", "email": "leila.haddadnoor@post.example",
      "phone": "+44 7700 900736", "ip": "2001:db8:4f2a:91::17", "ref": "C07CE384-73CB-4249-98F8-264565F56702",
      "agreed": "19-08-2026 22:05:58", "signed": "19 Aug 26", "passport": "P7731046", "dob": "27/06/1996"}
LL = {"title": "Mr", "name": "Kenji Morioka-Grant", "initials": "KM", "email": "kmg.property@inbox.example",
      "phone": "+852 5550 2194", "ip": "203.0.113.47", "ref": "932DE688-0761-49E5-BBD0-5355D48AFBFE",
      "agreed": "17-08-2026 15:12:03", "signed": "17 Aug 26"}
GUARANTOR = {"name": "Margarethe Lindqvist", "dob": "14/03/1961", "ni": "QQ 12 34 56 C",
             "address": "4 Thornbury Rise, Harrogate", "postcode": "HG2 9LB", "phone": "01423 960 514",
             "email": "m.lindqvist@post.example"}
EMERGENCY = {"name": "Piotr Wierzbicki", "phone": "+48 600 555 213", "email": "piotr.w@mailbox.example"}

PROPERTY_LINE1 = "Flat 2714, Halcyon Tower, 88 Larkspur Quay, London"
PROPERTY_PC = "E14 6XQ"
T1_ADDR = ("Flat 5, Wexford House, 31 Cobalt Street, London", "E1 7QT")
T2_ADDR = "Fliederhofgasse 23/7, 1150 Wien, Austria"
LL_ADDR = "Unit 18C, Block 3, Silverstrand Court, 22 Harbour Crescent, Kowloon, Hong Kong"
AGENT = "Harbourline Residential Lettings Ltd"
AGENT_ADDR = ("Suite 4, Marlowe Chambers, 17 Tanner Row, London", "SE1 3PD")
AGENT_CONTACT = {"name": "Aisha Okonkwo-Reid", "phone": "020 7946 0381", "email": "a.okonkwo-reid@harbourline.example"}
BANK = {"account": "41758209", "sort": "40-12-76", "iban": "GB30NWBK40127641758209", "holder": "Kenji Morioka-Grant"}
REFS = {"tenancy": "HRL/TEN/2026/0841", "deposit_cert": "DPC-7739-1820-55", "landlord_ref": "LL-KMG-0093",
        "parking": "B2-114", "vehicle": "LK71 XFD", "fob": "FOB-58830-27"}
RENT, DEPOSIT, HOLDING = "£2,875.00", "£3,317.30", "£663.46"
START = "1 September 2026"

GOLD: list[tuple[str, str]] = []


def pii(value: str, etype: str) -> str:
    """Record a value for the answer key and return it escaped for HTML."""
    GOLD.append((value, etype))
    return html.escape(value)


def person(p: dict, with_title: bool = True) -> str:
    return (html.escape(p["title"]) + " " if with_title else "") + pii(p["name"], "PERSON")


def addr(line: str, postcode: str | None = None) -> str:
    out = pii(line, "ADDRESS")
    return out + (", " + pii(postcode, "POSTCODE") if postcode else "")


E = html.escape

# ---------- Cover: the e-signature log ----------
def log_entry(p: dict, role: str) -> str:
    return f"""
<p class="log"><b>{person(p)}, {role}</b><br/>
Date Agreed: {p['agreed']}<br/>
Logged IP Address: {pii(p['ip'], 'IP_ADDRESS')}<br/>
Signature Reference: {pii(p['ref'], 'CUSTOM')}</p>"""


cover = f"""
<h1>Assured Periodic Tenancy - APT</h1>
<p class="note">This document has been signed electronically.</p>
<p>This document has been signed electronically using InkProof, the online document signing service.
A record of each signature applied to this document can be found in the "Signature Log" below.</p>
<h2>Signature Log</h2>
<p>The following parties have read and confirmed their agreement to the contents of this document.</p>
{log_entry(T1, 'Tenant')}
{log_entry(T2, 'Tenant')}
{log_entry(LL, 'Landlord')}
<h2>Document Execution</h2>
<p>InkProof bears witness to the execution of this document.</p>
<p>A secure version of this document is stored with InkProof under envelope ID {pii('74CCE790-6E8C-4F8C-ACE5-5F31B0EA99B9', 'CUSTOM')}.</p>
<p>Access to this document has been provided to all parties above.</p>
<p>www.inkproof.example</p>
"""

# ---------- Parties and particulars ----------
parties = f"""
<h1 class="newpage">Assured Periodic Tenancy Agreement</h1>
<p><b>Relating to:</b></p>
<p>{addr(PROPERTY_LINE1, PROPERTY_PC)}</p>
<p><b>Commencement Date:</b> {START}</p>
<p><b>Tenancy reference:</b> {pii(REFS['tenancy'], 'CUSTOM')}</p>
<p><b>Between</b></p>
<p>(1) {person(LL)}<br/>{pii(LL_ADDR, 'ADDRESS')}<br/>(the "Landlord")</p>
<p><b>And</b></p>
<p>(2) {person(T1, False)} &amp; {person(T2, False)}<br/>
{addr(*T1_ADDR)}<br/>{pii(T2_ADDR, 'ADDRESS')}<br/>(the "Tenant")</p>
<p><b>Managing agent:</b> {E(AGENT)}, {addr(*AGENT_ADDR)}. Your property manager is
{pii(AGENT_CONTACT['name'], 'PERSON')} (telephone {pii(AGENT_CONTACT['phone'], 'PHONE')},
email {pii(AGENT_CONTACT['email'], 'EMAIL')}).</p>
<h2>Particulars</h2>
<table>
<tr><td>Rent</td><td>{RENT} per calendar month, payable in advance on the 1st day of each month</td></tr>
<tr><td>Security Deposit</td><td>{DEPOSIT}</td></tr>
<tr><td>Holding deposit already paid</td><td>{HOLDING}, credited against the first month's Rent</td></tr>
<tr><td>Deposit Scheme Type</td><td>Insured</td></tr>
<tr><td>Deposit protection certificate</td><td>{pii(REFS['deposit_cert'], 'CUSTOM')}</td></tr>
<tr><td>Tenancy Commencement Date</td><td>{START}</td></tr>
<tr><td>Permitted Occupiers</td><td>The Tenant only, being no more than two adults</td></tr>
<tr><td>Rent account</td><td>Account name {pii(BANK['holder'], 'PERSON')}, account number {pii(BANK['account'], 'BANK_ACCOUNT')},
sort code {pii(BANK['sort'], 'SORT_CODE')}, IBAN {pii(BANK['iban'], 'IBAN')}. Please quote the reference {pii(REFS['landlord_ref'], 'CUSTOM')}.</td></tr>
<tr><td>Tenant contact details</td><td>{person(T1, False)}: {pii(T1['phone'], 'PHONE')}, {pii(T1['email'], 'EMAIL')}<br/>
{person(T2, False)}: {pii(T2['phone'], 'PHONE')}, {pii(T2['email'], 'EMAIL')}</td></tr>
<tr><td>Landlord contact details</td><td>{pii(LL['phone'], 'PHONE')}, {pii(LL['email'], 'EMAIL')}</td></tr>
<tr><td>Are bills included in the Rent?</td><td>No</td></tr>
<tr><td>Bills not included in the Rent</td><td>N/A</td></tr>
</table>
"""

# ---------- Clauses (original text) ----------
SECTIONS: list[tuple[str, list[str]]] = [
    ("Interpretation", [
        "The definitions and rules of interpretation in this clause apply throughout this Agreement.",
        "Agreement: this tenancy agreement, its particulars and every schedule attached to it.",
        "Building: the block known as Halcyon Tower, including its common parts, plant, lifts, car park and amenity spaces.",
        "Building Owner: the freeholder of the Building, or any person who manages the Building on the freeholder's behalf.",
        "Check-In Inventory and Schedule of Condition: the written and photographic record of the Property and its contents made at or before the start of the Tenancy and signed or accepted by the parties.",
        "Common Parts: the entrance halls, corridors, stairs, lifts, refuse stores, cycle stores and other areas of the Building that the Tenant may use in common with other occupiers.",
        "Deposit Scheme: the insured tenancy deposit protection scheme with which the Security Deposit is registered, as named in the particulars and in the prescribed information.",
        "Fixtures and Fittings: everything belonging to the Landlord in the Property, including the items listed in the Check-In Inventory and anything that replaces them.",
        "Insured Risks: fire, smoke, explosion, lightning, storm, flood, escape of water or oil, impact, theft, malicious damage and any other risk the Landlord insures against from time to time.",
        "Permitted Occupiers: the persons named as the Tenant and no one else, unless the Landlord agrees otherwise in writing.",
        "Rent: the sum set out in the particulars, or any other sum that becomes payable under clause 5 or by statute.",
        "Tenancy: the assured periodic tenancy created by this Agreement.",
        "Working Day: any day other than a Saturday, a Sunday or a bank holiday in England.",
        "Where there is more than one Tenant, their obligations are joint and several, so each of them can be held responsible for the whole Rent and for every other obligation.",
        "Headings are for convenience only and do not affect the meaning of any clause. Words in the singular include the plural and the other way round.",
        "A reference to a statute includes any amendment, extension or re-enactment of it in force from time to time and any subordinate legislation made under it.",
    ]),
    ("The Tenancy", [
        "The Landlord lets the Property to the Tenant on an assured periodic tenancy from the Commencement Date. The Tenancy runs from month to month and has no fixed end date.",
        "Each period of the Tenancy begins on the first day of a calendar month. Where the Commencement Date is not the first day of a month, the first period runs to the end of that month and Rent for it is apportioned by the day.",
        "The Tenancy may be brought to an end only in the ways allowed by law and set out in clause 18.",
        "Nothing in this Agreement is intended to create a tenancy of any part of the Common Parts or of any parking space other than the space described in Schedule 1.",
    ]),
    ("Special terms", [
        "The parties also agree to the special terms in Schedule 1. Where a special term conflicts with a clause in the body of this Agreement, the special term prevails.",
        "A special term that is found to be unfair or unenforceable does not affect the rest of this Agreement.",
    ]),
    ("Contents and keys", [
        "The Tenant shall keep the Fixtures and Fittings in good and clean condition and return them at the end of the Tenancy in the same condition, fair wear and tear excepted.",
        "The Tenant shall not remove any of the Fixtures and Fittings from the Property, and shall not store them in a loft, garage or shed without the Landlord's written consent.",
        f"At the start of the Tenancy the Tenant receives two sets of keys, one communal entrance fob numbered {pii(REFS['fob'], 'CUSTOM')} and one post box key. Further keys or fobs may be cut or programmed only through the managing agent.",
        "The Tenant shall return every key, fob and access card at the end of the Tenancy. The reasonable cost of replacing anything not returned may be deducted from the Security Deposit.",
        "Any item that is broken or lost through the act or neglect of the Tenant, a Permitted Occupier or a visitor shall be repaired or replaced by the Tenant with an item of similar quality and value.",
    ]),
    ("Rent and payments", [
        "The Tenant shall pay the Rent in advance by standing order to the rent account named in the particulars, so that cleared funds arrive on or before the 1st day of each month.",
        "The first payment of Rent, less the holding deposit, falls due before the Tenant receives the keys.",
        "If any Rent remains unpaid for 14 days after it falls due, the Tenant shall pay interest on it at 3% a year above the Bank of England base rate, calculated from the due date until the date of payment.",
        "The Landlord may propose an increase in the Rent no more than once in any twelve months, by serving notice in the prescribed form under section 13 of the Housing Act 1988.",
        "The Tenant consents to the Landlord and the managing agent discussing with the local housing authority any claim for housing benefit, council tax support or universal credit made in relation to the Property.",
        "No payment by the Tenant shall be treated as accepted in full settlement of any dispute unless the Landlord confirms so in writing.",
        "Where the Tenancy is ended lawfully part way through a rental period, any Rent paid in advance for the days after the end of the Tenancy shall be refunded within seven days, calculated by the day.",
        "The Tenant shall not withhold or set off any part of the Rent against any sum the Tenant believes is owed by the Landlord, except where the law permits it.",
    ]),
    ("Permitted payments", [
        "The Landlord and the managing agent shall not require any payment from the Tenant other than a payment permitted by the Tenant Fees Act 2019.",
        "Permitted payments include the Rent, the Security Deposit, the holding deposit, the reasonable cost of replacing a lost key or security device, a payment of £50 or the reasonable cost if higher for a variation requested by the Tenant, and the cost of utilities and council tax.",
        "Any default fee shall be limited to the reasonable cost actually incurred and shall be supported by written evidence.",
    ]),
    ("Security Deposit", [
        f"The Tenant shall pay the Security Deposit of {DEPOSIT} on or before signing this Agreement.",
        "The Security Deposit shall be protected with the Deposit Scheme within 30 days of receipt, and the prescribed information shall be given to the Tenant and to any relevant person within the same period.",
        "No interest is payable to the Tenant on the Security Deposit.",
        "The Security Deposit is held as security for the Tenant's obligations and may be used to meet any unpaid Rent, any unpaid utility charges for which the Landlord becomes liable, the cost of making good damage beyond fair wear and tear, the cost of cleaning to the standard in the Check-In Inventory, and the replacement of missing items.",
        "At the end of the Tenancy the Landlord shall tell the Tenant within ten Working Days if any deduction is proposed, with an itemised list of the amounts claimed and the evidence for them.",
        "If there is no dispute, the agreed balance of the Security Deposit shall be repaid within ten days of the parties agreeing it.",
        "If the amount of any deduction is disputed, either party may refer the dispute to the free alternative dispute resolution service of the Deposit Scheme, and the undisputed part shall be repaid in the meantime.",
        "The Tenant may not use the Security Deposit as a payment of the last month's Rent.",
    ]),
    ("Use and occupation", [
        "The Tenant shall use the Property as a private home for the Permitted Occupiers only and for no other purpose.",
        "The Tenant shall not run a business from the Property that involves visitors, deliveries of stock or any change to the insurance of the Building. Working from home with a computer and telephone is allowed.",
        "The Tenant shall not sublet the Property or any part of it, take in lodgers, or allow the Property to be used for short-term holiday lets.",
        "The Tenant shall not do anything at the Property that is a nuisance or annoyance to neighbours, the Landlord or other occupiers of the Building, including loud music or gatherings that can be heard outside the Property between 11pm and 7am.",
        "The Tenant shall comply with the regulations of the Building Owner as notified from time to time, including those on the use of balconies, lifts, refuse stores and the residents' gym.",
        "The Tenant acknowledges that access to on-site amenities is provided at the discretion of the Building Owner, and that no reduction in Rent is due for any period when they are closed for maintenance.",
        "The Tenant shall not hang washing, flags or signs from any balcony or window, and shall not fix any satellite dish or aerial to the outside of the Building.",
        "The Tenant shall keep all external doors and windows locked when the Property is empty, and shall not leave the Property unoccupied for more than 21 consecutive days without telling the managing agent.",
    ]),
    ("Fire safety and prohibited items", [
        "The Tenant shall not obstruct any corridor, stairway or fire escape in the Building, and shall not wedge open any fire door.",
        "The Tenant shall not keep at the Property any paraffin heater, gas bottle, barbecue or other appliance that burns fuel, or any substance that is dangerous or highly flammable.",
        "The Tenant shall not charge an electric bike, scooter or similar vehicle inside the Property or in the Common Parts, except in a charging area provided by the Building Owner for that purpose.",
        "The Tenant shall not tamper with, cover or disconnect any smoke alarm, heat detector, sprinkler head or carbon monoxide alarm, and shall test each alarm at least once a month.",
        "The Tenant shall follow the fire strategy for the Building as published in the entrance lobby, including the stay put or evacuate instructions that apply.",
    ]),
    ("Insurance", [
        "The Landlord shall insure the Fixtures and Fittings against the Insured Risks. The Tenant's own belongings are not covered by the Landlord's insurance.",
        "The Tenant is strongly advised to take out contents and personal liability insurance for the duration of the Tenancy.",
        "The Tenant shall not do anything that would make the Landlord's insurance void or increase the premium, and shall pay any increase in premium caused by a breach of this clause.",
    ]),
    ("Repairs, alterations and condition", [
        "The Tenant shall keep the interior of the Property clean and tidy and in the same condition as at the start of the Tenancy, fair wear and tear excepted.",
        "The Tenant shall report to the managing agent promptly any disrepair, defect, leak or damage in the Property or the Building, including any damp or mould, so that it can be put right before it gets worse.",
        "The Tenant shall heat and ventilate the Property properly, use extractor fans when cooking and bathing, and wipe away condensation, to reduce the risk of damp and mould.",
        "The Tenant shall replace light bulbs, fuses and batteries in smoke alarms as needed, and keep sinks, baths, toilets and drains free from blockages caused by the Tenant's use.",
        "The Tenant shall not paint, wallpaper, drill, fix shelves or make any alteration or addition to the Property without the Landlord's prior written consent, which shall not be unreasonably withheld for minor works.",
        "The Tenant shall not install an electric vehicle charger, air conditioning unit or any equipment that would change the energy performance of the Property.",
        "At the end of the Tenancy the Tenant shall leave the Property clean to the standard recorded in the Check-In Inventory. Where the Property was professionally cleaned before the Tenancy, the Tenant shall either arrange a professional clean or clean it to an equivalent standard.",
        "The Tenant shall allow a check-out inspection to be made at the end of the Tenancy and is encouraged to attend it.",
    ]),
    ("Utilities and outgoings", [
        "The Tenant shall pay for all gas, electricity, water, sewerage, telephone, broadband and television services used at the Property during the Tenancy, and the television licence.",
        "The Tenant shall pay the council tax for the Property for the duration of the Tenancy and shall register with the local authority in the Tenant's own name.",
        "The Tenant shall tell the suppliers of every utility the date the Tenancy begins and ends, with meter readings, and shall not change supplier in a way that leaves the Landlord liable for any debt.",
        "The Tenant shall pay any service charge for the heating and hot water network of the Building where it is billed to the occupier rather than to the Landlord.",
    ]),
    ("Locks and security", [
        "The Tenant shall not change or add any lock to the Property without the Landlord's written consent.",
        "Where it becomes reasonable for the Landlord to change the locks because of the Tenant's act or default, the Tenant shall pay the reasonable cost of doing so.",
        "The Tenant shall not give a key or fob to any person who is not a Permitted Occupier, except a contractor waiting to carry out authorised works.",
    ]),
    ("Pets", [
        "The Tenant shall not keep any pet at the Property without the prior written consent of the Landlord, which shall not be unreasonably withheld.",
        "A request to keep a pet shall be made in writing with a description of the animal, and the Landlord shall answer within 28 days.",
        "Where consent is given, the Tenant shall keep the pet under control, shall make good any damage it causes, and shall have the Property professionally cleaned and treated for fleas at the end of the Tenancy.",
    ]),
    ("The Landlord's obligations", [
        "The Landlord shall allow the Tenant to live in the Property quietly and without interruption by the Landlord or anyone acting for the Landlord.",
        "The Landlord shall keep in repair the structure and exterior of the Property, and keep in repair and working order the installations for the supply of water, gas, electricity, sanitation, space heating and hot water, as required by section 11 of the Landlord and Tenant Act 1985.",
        "The Landlord shall arrange an annual gas safety check by a Gas Safe registered engineer and give the Tenant a copy of the record within 28 days of each check.",
        "The Landlord shall ensure that the electrical installations are inspected and tested by a qualified person at least every five years, and give the Tenant a copy of the latest report.",
        "The Landlord shall ensure that a working smoke alarm is fitted on each storey used as living accommodation and a carbon monoxide alarm in any room with a fixed combustion appliance.",
        "The Landlord shall not be required to repair anything the Tenant is liable to repair under this Agreement, or anything the Tenant is entitled to remove from the Property.",
        "The Landlord acknowledges that the Tenant may request a disability-related improvement to the Property and shall not unreasonably refuse consent to it.",
    ]),
    ("Breach and recovery of costs", [
        "If the Tenant breaks any obligation in this Agreement, the Landlord may give the Tenant written notice describing the breach and asking for it to be put right within a reasonable time.",
        "The Tenant shall pay the reasonable costs that the Landlord incurs in court proceedings against the Tenant for unpaid Rent or other sums, subject to the Tenant's right to have those costs assessed by the court.",
        "Should the total amount legally due from the Tenant at the end of the Tenancy exceed the Security Deposit, the Tenant shall pay the excess within 14 days of a written demand with evidence.",
    ]),
    ("Access and viewings", [
        "The Tenant shall allow the Landlord, the managing agent and their contractors to enter the Property at reasonable times on at least 24 hours' written notice to inspect it, carry out repairs or safety checks, or read meters.",
        "In an emergency the Landlord or the managing agent may enter without notice, and shall tell the Tenant as soon as possible afterwards.",
        "After either party has given notice to end the Tenancy, the Tenant shall allow the Property to be viewed by prospective tenants or buyers at reasonable times on 24 hours' notice.",
        "The managing agent may display a sign advertising the Property to let or for sale, where the Building Owner allows it.",
    ]),
    ("Ending the Tenancy", [
        "This is a periodic tenancy which continues from month to month until it is ended in one of the ways set out in this clause.",
        "The Tenant may end the Tenancy by giving the Landlord at least two months' written notice, ending on the last day of a rental period. Notice from one joint Tenant ends the Tenancy for all of them.",
        "The Landlord may end the Tenancy only by serving the notice required by law on one of the statutory grounds for possession and, if the Tenant does not leave, by obtaining an order of the court.",
        "On leaving, the Tenant shall remove all personal belongings and rubbish, return every key and fob, and give the managing agent a forwarding address for the return of the Security Deposit.",
        "Any belongings left in the Property after the Tenancy ends may be stored for 14 days, after which the Landlord may dispose of them and deduct the reasonable cost of doing so.",
    ]),
    ("Interruptions to the Tenancy", [
        "If the Property becomes uninhabitable because of an Insured Risk that was not caused by the Tenant, the Rent shall stop being payable until the Property is fit to live in again.",
        "If the Property is not made fit to live in again within three months, either party may end the Tenancy by giving one month's written notice.",
        "The suspension of Rent does not apply where the Landlord's insurance has been made void by the act or default of the Tenant or a visitor.",
    ]),
    ("Data protection", [
        "The Landlord and the managing agent will process the Tenant's personal data to manage the Tenancy, collect the Rent, protect the Security Deposit and meet their legal duties, as explained in the managing agent's privacy notice.",
        f"Questions about personal data may be sent to the managing agent's data protection lead, {pii('Daniel Ferreira-Holt', 'PERSON')}, at {pii('privacy@harbourline.example', 'EMAIL')}.",
        "The Tenant agrees that the managing agent may give the Tenant's contact details to utility suppliers, the local authority and the Deposit Scheme for the purposes of this Agreement.",
    ]),
    ("Notices", [
        f"The Landlord gives the following address in England and Wales at which notices, including notices in proceedings, may be served on the Landlord under section 48 of the Landlord and Tenant Act 1987: care of {E(AGENT)}, {addr(*AGENT_ADDR)}.",
        f"Notices to the Tenant may be served at the Property or by email to {pii(T1['email'], 'EMAIL')} and {pii(T2['email'], 'EMAIL')}.",
        "A notice sent by first class post is treated as received on the second Working Day after posting. A notice sent by email before 4pm on a Working Day is treated as received that day.",
    ]),
    ("Right to rent", [
        f"Before the Tenancy began the managing agent checked the right to rent of each adult occupier. {person(T1)} produced passport number {pii(T1['passport'], 'ID_DOC')} and {person(T2)} produced passport number {pii(T2['passport'], 'ID_DOC')}.",
        "Where a Permitted Occupier has a time-limited right to rent, the Tenant shall provide evidence of any extension before the expiry date, so that a follow-up check can be made.",
    ]),
    ("Changes of sharer and assignment", [
        "The Tenant shall not assign, transfer or part with possession of the Property or any part of it.",
        "Where one joint Tenant wishes to leave and a replacement sharer is proposed, the Landlord shall consider the request in good faith. Any change requires a deed of variation signed by all parties and fresh reference and right to rent checks on the incoming sharer.",
        "The outgoing sharer remains liable for the Tenant's obligations until the deed of variation takes effect, and the Security Deposit shall be re-registered in the names of the new Tenant within 30 days.",
        "The Landlord may charge the permitted fee for a variation requested by the Tenant, which shall not exceed £50 unless the Landlord shows that a higher cost was reasonably incurred.",
    ]),
    ("Smoking, balconies and outside space", [
        "The Tenant shall not smoke tobacco, use a vaporiser or burn incense inside the Property or in the Common Parts.",
        "Smoking on the balcony is permitted only where the Building regulations allow it, and the Tenant shall make sure that no smoke, ash or cigarette ends reach other balconies or windows.",
        "The Tenant shall keep the balcony clean and free of rubbish, shall not overload it, and shall not use it to store bicycles, furniture other than garden furniture, or flammable items.",
        "Plants on the balcony must be kept in trays so that water does not run onto the balconies below, and nothing may be fixed to the balcony glass or railings.",
    ]),
    ("Refuse, deliveries and the concierge", [
        "The Tenant shall separate rubbish and recycling as directed by the Building Owner and place it only in the bins provided in the refuse store on the ground floor.",
        "Bulky items such as furniture or appliances must not be left in the refuse store; the Tenant shall arrange their collection with the local authority or a licensed carrier.",
        "The concierge may accept parcels on the Tenant's behalf but neither the Landlord nor the Building Owner accepts liability for parcels lost or damaged while held by the concierge.",
        "The Tenant shall book the service lift through the concierge at least 48 hours in advance for moving in or out, and shall pay for any damage caused to the Common Parts during a move.",
    ]),
    ("Complaints and redress", [
        "If the Tenant is unhappy with the service of the managing agent, the Tenant should first follow the managing agent's written complaints procedure, which is available on request.",
        "If the complaint is not resolved within eight weeks, the Tenant may refer it to the property redress scheme of which the managing agent is a member.",
        "Nothing in this clause affects the Tenant's right to contact the local housing authority about the condition of the Property.",
    ]),
    ("General", [
        "This Agreement contains the whole agreement between the parties about the Tenancy. No promise made before it was signed forms part of it unless it is written into this Agreement.",
        "Any delay by the Landlord in enforcing a term of this Agreement does not prevent the Landlord from enforcing it later.",
        "This Agreement is governed by the law of England and Wales and the courts of England and Wales have jurisdiction over any dispute arising from it.",
        "The Tenant agrees to comply with all laws, regulations and local authority requirements relating to the occupation of the Property, and shall not allow the Property to become overcrowded.",
    ]),
]


def clauses_html() -> str:
    out = ["<h2>Agreed terms</h2>"]
    for n, (title, items) in enumerate(SECTIONS, 1):
        out.append(f"<h3>{n}. {E(title)}</h3>")
        for k, text in enumerate(items, 1):
            # Items that already hold markup (pii values) are trusted; plain ones are escaped.
            body = text if ("<" in text or "&amp;" in text) else E(text)
            out.append(f'<p class="clause"><span class="num">{n}.{k}.</span> {body}</p>')
    return "\n".join(out)


ROOMS = {
    "Entrance hall": ["Front door, solid core fire door with self-closer, spy hole and two locks",
                      "Walls, painted white, two small scuffs beside the light switch",
                      "Ceiling, painted white, smoke alarm fitted and tested",
                      "Flooring, engineered oak, light wear at the threshold",
                      "Storage cupboard, with consumer unit, washing machine and two shelves",
                      "Video entry handset, working, cleaned"],
    "Living and dining room": ["Walls, painted pale grey, picture hooks removed and filled",
                               "Windows, floor to ceiling glazing with restrictors, cleaned inside",
                               "Curtains, two pairs of blackout curtains in charcoal, cleaned",
                               "Sofa, three seat in grey fabric, no stains noted",
                               "Dining table, oak veneer, six chairs, one chair with a loose back leg",
                               "Television unit, white gloss, two drawers, light scratch on the top",
                               "Rug, cream wool, 200 by 290 cm, professionally cleaned",
                               "Balcony door, sliding, lock working, two keys"],
    "Kitchen": ["Worktops, quartz, small chip near the hob",
                "Oven, single electric, cleaned, grill pan and two shelves present",
                "Induction hob, four zones, no marks",
                "Extractor hood, filters cleaned",
                "Fridge freezer, integrated, clean, no ice build up",
                "Dishwasher, integrated, filter cleaned",
                "Cupboards, eight wall and base units, soft close, all present",
                "Sink, stainless steel with mixer tap, no limescale"],
    "Bedroom one": ["Walls, painted white, small mark above the bed head",
                    "Double bed frame with mattress and mattress protector, no stains",
                    "Wardrobe, built in, mirrored sliding doors, ten hangers",
                    "Bedside tables, two, white gloss",
                    "Window blinds, roller, working"],
    "Bedroom two": ["Walls, painted white, no marks",
                    "Single bed with mattress protector",
                    "Desk and chair, white, light scratch on the desk surface",
                    "Wardrobe, freestanding, two doors, one shelf",
                    "Window blinds, roller, cord tidy missing"],
    "Bathroom": ["Bath with shower over and glass screen, sealant in good order",
                 "Toilet, wall hung, cleaned",
                 "Basin with vanity unit, two drawers",
                 "Heated towel rail, working",
                 "Mirror cabinet with light, one bulb not working",
                 "Extractor fan, working, cleaned"],
}


def inventory_html() -> str:
    out = ['<h2 class="newpage">Schedule 5: Check-In Inventory and Schedule of Condition (summary)</h2>',
           f"<p>Prepared on 28 August 2026 by the inventory clerk {pii('Rhiannon Castellanos', 'PERSON')} of Clearview Inventories for {E(AGENT)}. "
           "The full report, with photographs, has been sent to the Tenant by email. The Tenant has seven days from the start "
           "of the Tenancy to comment on it; any comments will be attached to the report.</p>",
           "<h3>Meters and keys</h3>",
           f"<p>Electricity meter serial {pii('E17Z045321', 'CUSTOM')}, reading 018442. Heat meter serial {pii('HM-2209-7718', 'CUSTOM')}, reading 3,120 kWh. "
           "Water is billed through the Building service charge. Keys: two sets of flat keys, two balcony keys, one post box key, one entrance fob.</p>"]
    for room, items in ROOMS.items():
        out.append(f"<h3>{E(room)}</h3>")
        for k, item in enumerate(items, 1):
            out.append(f'<p class="clause"><span class="num">{k}.</span> {E(item)}. Cleanliness: professionally cleaned. Condition: good unless noted.</p>')
    out.append("<p>General notes: all light fittings were working at check-in except where noted. Windows were cleaned internally. "
               "External window cleaning is arranged by the Building Owner. The Property was professionally cleaned before the Tenancy "
               "and should be returned to the same standard, fair wear and tear excepted.</p>")
    return "\n".join(out)


HANDBOOK = [
    ("Welcome", "Halcyon Tower has a 24 hour concierge in the main lobby. The concierge can help with deliveries, lift bookings, visitor access and reporting problems in the Common Parts."),
    ("Building management", f"The building manager is {pii('Callum Ashdown-Pryce', 'PERSON')}. Repairs inside your flat should be reported to your managing agent, not to the building manager."),
    ("Fire safety", "The Building has a stay put policy unless the fire is in your flat or you are told to leave by the fire service or the concierge. Learn where the nearest protected stair is. Never use the lifts in a fire."),
    ("Residents' gym and lounge", "The gym on the second floor is open from 6am to 10pm. Children under 16 must be supervised. The residents' lounge can be booked for private events through the concierge, subject to a refundable deposit."),
    ("Noise", "Please keep noise to a minimum between 11pm and 7am. Hard floors carry sound; rugs and felt pads under furniture legs are recommended."),
    ("Moving in and out", "Moves must be booked at least 48 hours in advance and take place between 9am and 5pm on weekdays. The service lift will be fitted with protective covers for your booking."),
    ("Cycle store", "Bicycles must be kept in the cycle store on the lower ground floor, not in the corridors or on balconies. E-bike batteries must not be charged in the cycle store."),
    ("Refuse", "General waste, mixed recycling and food waste each have their own chute or bin. Glass must be taken down to the refuse store and not put down the chute."),
    ("Parking", "Parking spaces are allocated with each lease. Visitors must not park in the basement car park. Electric vehicle charging points are available by arrangement with the concierge."),
    ("Your data", "CCTV operates in the Common Parts for the safety of residents. Footage is kept for 30 days and is viewed only when an incident is reported."),
]


def handbook_html() -> str:
    return "\n".join(f"<h3>{E(title)}</h3><p>{body}</p>" for title, body in HANDBOOK)


def signature_block(p: dict, role: str) -> str:
    return f"""<p class="sig">Name: {person(p)}<br/>Signature: <i>{pii(p['name'], 'PERSON')}, {p['signed']}</i><br/>
Capacity: {role}</p>"""


signatures = f"""
<h2 class="newpage">Signatures</h2>
<p>SIGNED BY THE LANDLORD:</p>
{signature_block(LL, 'Landlord')}
<p>SIGNED BY THE TENANT(S):</p>
{signature_block(T1, 'Tenant')}
{signature_block(T2, 'Tenant')}
<p>SIGNED BY THE GUARANTOR:</p>
<p class="sig">Name: Mrs {pii(GUARANTOR['name'], 'PERSON')}<br/>Signature: <i>{pii(GUARANTOR['name'], 'PERSON')}, 20 Aug 26</i></p>
<p class="initials">{pii(T1['initials'], 'PERSON')} {pii(LL['initials'], 'PERSON')} {pii(T2['initials'], 'PERSON')}</p>
"""

schedules = f"""
<h2 class="newpage">Schedule 1: Special Terms and Conditions</h2>
<p>The parties agree that the following terms apply for the duration of the Tenancy. Where an equivalent clause exists in the Agreement, these terms supersede it.</p>
<p class="clause"><span class="num">1.</span> The Tenant may use parking space {pii(REFS['parking'], 'CUSTOM')} in the basement car park of the Building for one private car only. The registered vehicle is {pii(REFS['vehicle'], 'CUSTOM')}. Any change of vehicle must be notified to the concierge before use.</p>
<p class="clause"><span class="num">2.</span> The Landlord consents to the Tenant keeping one indoor cat at the Property. Clause 14.3 applies.</p>
<p class="clause"><span class="num">3.</span> The Landlord will have the oven and extractor professionally serviced before the Commencement Date.</p>
<p class="clause"><span class="num">4.</span> The Tenant's emergency contact is {pii(EMERGENCY['name'], 'PERSON')}, telephone {pii(EMERGENCY['phone'], 'PHONE')}, email {pii(EMERGENCY['email'], 'EMAIL')}.</p>
<p class="clause"><span class="num">5.</span> Rent reviews under clause 5.4 will not take effect before 1 September 2027.</p>

<h2>Schedule 2: Guarantor</h2>
<p>In consideration of the Landlord granting the Tenancy, the guarantor named below guarantees the payment of the Rent and the performance of the Tenant's obligations for the first twelve months of the Tenancy.</p>
<table>
<tr><td>Guarantor</td><td>Mrs {pii(GUARANTOR['name'], 'PERSON')}</td></tr>
<tr><td>Date of birth</td><td>{pii(GUARANTOR['dob'], 'DOB')}</td></tr>
<tr><td>National Insurance number</td><td>{pii(GUARANTOR['ni'], 'NI_NUMBER')}</td></tr>
<tr><td>Address</td><td>{addr(GUARANTOR['address'], GUARANTOR['postcode'])}</td></tr>
<tr><td>Telephone</td><td>{pii(GUARANTOR['phone'], 'PHONE')}</td></tr>
<tr><td>Email</td><td>{pii(GUARANTOR['email'], 'EMAIL')}</td></tr>
</table>

<h2>Schedule 3: Checklist</h2>
<p>In addition to this Agreement, the Tenant has been given copies of the following documents:</p>
<p class="clause"><span class="num">1.</span> Energy Performance Certificate ("EPC").</p>
<p class="clause"><span class="num">2.</span> Gas Safety Record, where there is a gas supply to the Property.</p>
<p class="clause"><span class="num">3.</span> Electrical Installation Condition Report ("EICR").</p>
<p class="clause"><span class="num">4.</span> The prescribed information for the Security Deposit, including certificate {pii(REFS['deposit_cert'], 'CUSTOM')}.</p>
<p class="clause"><span class="num">5.</span> The Building fire strategy and the residents' handbook.</p>
<p class="clause"><span class="num">6.</span> The government guide "How to rent: the checklist for renting in England".</p>

<h2 class="newpage">Schedule 4: Prescribed information for the Security Deposit</h2>
<p>This information is given under the Housing (Tenancy Deposits) (Prescribed Information) Order 2007.</p>
<table>
<tr><td>Property</td><td>{addr(PROPERTY_LINE1, PROPERTY_PC)}</td></tr>
<tr><td>Amount of the deposit</td><td>{DEPOSIT}</td></tr>
<tr><td>Scheme</td><td>Insured scheme, certificate {pii(REFS['deposit_cert'], 'CUSTOM')}</td></tr>
<tr><td>Landlord</td><td>{person(LL)}, {pii(LL_ADDR, 'ADDRESS')}, telephone {pii(LL['phone'], 'PHONE')}, email {pii(LL['email'], 'EMAIL')}</td></tr>
<tr><td>Person who paid the deposit</td><td>{person(T1)} on behalf of both tenants</td></tr>
<tr><td>Tenant 1</td><td>{person(T1)}, date of birth {pii(T1['dob'], 'DOB')}, telephone {pii(T1['phone'], 'PHONE')}, forwarding address {addr(*T1_ADDR)}</td></tr>
<tr><td>Tenant 2</td><td>{person(T2)}, date of birth {pii(T2['dob'], 'DOB')}, telephone {pii(T2['phone'], 'PHONE')}, forwarding address {pii(T2_ADDR, 'ADDRESS')}</td></tr>
<tr><td>Relevant person</td><td>Mrs {pii(GUARANTOR['name'], 'PERSON')}, guarantor</td></tr>
</table>
<p>The deposit may be retained at the end of the Tenancy in the circumstances set out in clause 7 of the Agreement. If the amount to be repaid is in dispute, the Tenant may apply to the scheme's free dispute resolution service within three months of the end of the Tenancy.</p>
<p>The Landlord confirms that the information above is accurate to the best of the Landlord's knowledge and belief, and that the Tenant has had the opportunity to sign it to confirm the same.</p>
<p class="sig">Signed for the Landlord: <i>{pii(AGENT_CONTACT['name'], 'PERSON')}</i>, property manager, {E(AGENT)}, 21 Aug 26</p>

{inventory_html()}

<h2 class="newpage">Schedule 6: Residents' handbook (extract)</h2>
{handbook_html()}
"""

CSS = """
* { font-family: sans-serif; }
body { font-size: 11pt; line-height: 1.55; color: #222; }
h1 { font-size: 17pt; margin: 0 0 10pt 0; }
h2 { font-size: 13pt; margin: 14pt 0 6pt 0; }
h3 { font-size: 11pt; margin: 12pt 0 4pt 0; }
p { margin: 0 0 6pt 0; }
p.note { font-style: italic; }
p.log { margin: 8pt 0 8pt 0; padding-left: 8pt; }
p.clause { margin: 0 0 7pt 0; }
span.num { font-weight: bold; }
p.sig { margin: 10pt 0 14pt 0; }
p.initials { margin-top: 20pt; font-style: italic; }
td { padding: 3pt 8pt 3pt 0; vertical-align: top; }
"""

# Each part that should start on a new page is rendered as its own Story.
parts = [cover, parties, clauses_html(), signatures, schedules]
MEDIABOX = pymupdf.paper_rect("a4")
WHERE = MEDIABOX + (64, 64, -64, -70)
tmp = OUT / f"_{NAME}_body.pdf"
OUT.mkdir(parents=True, exist_ok=True)
writer = pymupdf.DocumentWriter(str(tmp))
for part in parts:
    story = pymupdf.Story(html=f"<html><body>{part}</body></html>", user_css=CSS)
    more = True
    while more:
        device = writer.begin_page(MEDIABOX)
        more, _ = story.place(WHERE)
        story.draw(device)
        writer.end_page()
writer.close()

doc = pymupdf.open(tmp)
initials = f"{T1['initials']}  {T2['initials']}  {LL['initials']}"
for i, page in enumerate(doc):
    if i:
        page.insert_text((56, 40), str(i), fontsize=9, fontname="helv")
    page.insert_text((56, page.rect.height - 34), f"Initials: {initials}", fontsize=8, fontname="helv", color=(0.35, 0.35, 0.35))
    page.insert_text((page.rect.width - 210, page.rect.height - 34), "InkProof secure document", fontsize=8,
                     fontname="helv", color=(0.35, 0.35, 0.35))
doc.set_metadata({"title": "Assured Periodic Tenancy - APT (synthetic)", "producer": "make_tenancy.py"})
pdf_path = OUT / f"{NAME}.pdf"
doc.save(pdf_path, garbage=3, deflate=True)
doc.close()
tmp.unlink()

values: dict[str, str] = {}
for value, etype in GOLD + [(p["initials"], "PERSON") for p in (T1, T2, LL)]:  # initials are also in every footer
    values.setdefault(value, etype)
text = extract_pdf(pdf_path.read_bytes(), pdf_path.name).text
spans = locate(text, [{"text": v, "type": t} for v, t in values.items()])
missing = [v for v in values if not any(sp.text.split() == v.split() or v in sp.text for sp in spans)]
if missing:
    raise SystemExit(f"values not found in the extracted text: {missing}")
entities = [{"start": sp.start, "end": sp.end, "text": sp.text, "type": sp.type} for sp in spans]
gold = {
    "doc_id": "pdf-031",
    "doc_type": "tenancy_agreement",
    "pdf": pdf_path.name,
    "text": text,
    "entities": entities,
    "meta": {"template_id": "tenancy_agreement/e_signed_periodic", "generator": "scripts/samples/make_tenancy.py",
             "note": "Every value is invented. IP addresses are from the documentation ranges (RFC 5737, RFC 3849)."},
    "extracted_text": text,
    "extracted_entities": [{**e, "gold_text": e["text"], "exact": True} for e in entities],
    "missing_in_extracted": [],
    "text_similarity": 1.0,
}
(OUT / f"{NAME}.gold.json").write_text(json.dumps(gold, indent=2, ensure_ascii=False))
print(pdf_path, "pages", len(pymupdf.open(pdf_path)), "values", len(values), "occurrences", len(entities))
