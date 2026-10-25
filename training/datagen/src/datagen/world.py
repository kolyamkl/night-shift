"""Places, addresses, organisations and keep-trap helpers."""
from __future__ import annotations

import random
from dataclasses import dataclass, field
from datetime import date

from faker.providers.person.en_GB import Provider as _FakerPerson

_LAST = list(_FakerPerson.last_names)

from . import ids
from .core import E, HC, K

# --------------------------------------------------------------------------- towns
# town | county | outward codes (ranges "LS1-29" expand to LS1..LS29)
_TOWNS = """Leeds|West Yorkshire|LS1-29
Manchester|Greater Manchester|M1-35,M40,M50
Birmingham|West Midlands|B1-38,B42,B44
Liverpool|Merseyside|L1-38
Bristol|Avon|BS1-16
Sheffield|South Yorkshire|S1-36
Nottingham|Nottinghamshire|NG1-17
Leicester|Leicestershire|LE1-9
Cardiff|South Glamorgan|CF10-24
Edinburgh|Midlothian|EH1-17
Glasgow|Lanarkshire|G1-53
Newcastle upon Tyne|Tyne and Wear|NE1-15
Brighton|East Sussex|BN1-3
Oxford|Oxfordshire|OX1-4
Cambridge|Cambridgeshire|CB1-5
York|North Yorkshire|YO1,YO10,YO23-32
Bath|Somerset|BA1-2
Exeter|Devon|EX1-4
Plymouth|Devon|PL1-9
Southampton|Hampshire|SO14-19
Portsmouth|Hampshire|PO1-6
Reading|Berkshire|RG1-6
Norwich|Norfolk|NR1-7
Coventry|West Midlands|CV1-6
Derby|Derbyshire|DE1-24
Stoke-on-Trent|Staffordshire|ST1-6
Hull|East Yorkshire|HU1-9
Bradford|West Yorkshire|BD1-10
Belfast|County Antrim|BT1-17
Aberdeen|Aberdeenshire|AB10-25
Dundee|Angus|DD1-5
Swansea|West Glamorgan|SA1-6
Milton Keynes|Buckinghamshire|MK1-15
Luton|Bedfordshire|LU1-4
Watford|Hertfordshire|WD17-25
Croydon|Surrey|CR0-9
Bournemouth|Dorset|BH1-11
Preston|Lancashire|PR1-5
Bolton|Greater Manchester|BL1-7
Wolverhampton|West Midlands|WV1-14
Sunderland|Tyne and Wear|SR1-6
Middlesbrough|North Yorkshire|TS1-8
Ipswich|Suffolk|IP1-4
Colchester|Essex|CO1-4
Chelmsford|Essex|CM1-3
Canterbury|Kent|CT1-2
Guildford|Surrey|GU1-4
Harrogate|North Yorkshire|HG1-3
Carlisle|Cumbria|CA1-3
Inverness|Inverness-shire|IV1-3
Lincoln|Lincolnshire|LN1-6
Peterborough|Cambridgeshire|PE1-7
Northampton|Northamptonshire|NN1-5
Gloucester|Gloucestershire|GL1-4
Cheltenham|Gloucestershire|GL50-53
Worcester|Worcestershire|WR1-5
Chester|Cheshire|CH1-4
Warrington|Cheshire|WA1-5
Stockport|Greater Manchester|SK1-7
Huddersfield|West Yorkshire|HD1-9
Wakefield|West Yorkshire|WF1-4
Doncaster|South Yorkshire|DN1-5
Blackpool|Lancashire|FY1-4
Truro|Cornwall|TR1
Swindon|Wiltshire|SN1-5
Durham|County Durham|DH1
Newport|Gwent|NP19-20
Wrexham|Clwyd|LL11-13
Salford|Greater Manchester|M5-7
Slough|Berkshire|SL1-3"""

_LONDON = ("E1-18,E1W,N1-22,N1C,NW1-11,SE1-28,SW1-20,SW1A,SW1P,SW1V,W1-14,W1T,W1F,W1U,WC1H,WC1N,WC2H,"
           "EC1V,EC2A,EC1M")


def _expand(spec: str) -> list[str]:
    out = []
    for part in spec.split(","):
        if "-" in part:
            a, b = part.split("-")
            pre = "".join(c for c in a if c.isalpha())
            lo = int(a[len(pre):])
            out += [f"{pre}{i}" for i in range(lo, int(b) + 1)]
        else:
            out.append(part)
    return out


TOWNS: list[tuple[str, str, list[str]]] = []
for _line in _TOWNS.splitlines():
    _t, _c, _o = _line.split("|")
    TOWNS.append((_t, _c, _expand(_o)))
TOWNS.append(("London", "", _expand(_LONDON)))
TOWN_NAMES = [t[0] for t in TOWNS]

LOCALITIES = {
    "Leeds": ["Headingley", "Chapel Allerton", "Roundhay", "Armley", "Horsforth", "Meanwood", "Kirkstall"],
    "Manchester": ["Didsbury", "Chorlton", "Ancoats", "Fallowfield", "Levenshulme", "Withington"],
    "London": ["Hackney", "Brixton", "Islington", "Peckham", "Stoke Newington", "Walthamstow", "Clapham",
               "Ealing", "Tooting", "Camden", "Greenwich", "Hammersmith"],
    "Birmingham": ["Edgbaston", "Moseley", "Harborne", "Kings Heath", "Selly Oak"],
    "Bristol": ["Clifton", "Redland", "Bedminster", "Bishopston", "Easton"],
    "Glasgow": ["Partick", "Dennistoun", "Shawlands", "Hyndland"],
    "Edinburgh": ["Leith", "Morningside", "Stockbridge", "Portobello"],
    "Cardiff": ["Canton", "Roath", "Cathays", "Pontcanna"],
    "Sheffield": ["Crookes", "Ecclesall", "Hillsborough", "Walkley"],
    "Liverpool": ["Wavertree", "Allerton", "Toxteth", "Aigburth"],
}
_STREET_STEMS = ["Oak", "Elm", "Church", "Station", "Victoria", "Mill", "Park", "Queen's", "King's", "Albert",
                 "Manor", "Grove", "Chapel", "School", "Springfield", "Windsor", "York", "Cedar", "Beech",
                 "Willow", "Ash", "Holly", "Meadow", "Orchard", "Hawthorn", "Primrose", "Clarence", "Stanley",
                 "Cromwell", "Nelson", "Wellington", "Marlborough", "Belmont", "Highfield", "Fairfield",
                 "Brookside", "Riverside", "Hillside", "Lancaster", "Gladstone", "Thornton", "Moorland",
                 "Heathfield", "Linden", "Lime", "Sycamore", "Rowan", "Laburnum", "Bramble", "Foxglove",
                 "Kestrel", "Heron", "Sandringham", "Balmoral", "Osborne", "Cavendish", "Devonshire",
                 "Grosvenor", "St Mary's", "St John's", "St Peter's", "Coronation", "Jubilee", "Alexandra",
                 "Railway", "Canal", "Bridge", "Water", "North", "South", "West", "Back", "Low", "Granby",
                 "Beechwood", "Ashgrove", "Woodland", "Greenhill", "Mount Pleasant", "Cherry Tree", "Rose"]
_SUFFIXES = ["Road", "Road", "Street", "Street", "Lane", "Avenue", "Close", "Crescent", "Drive", "Grove",
             "Way", "Terrace", "Gardens", "Place", "Mews", "Rise", "Walk", "Court", "Square", "Hill", "Row",
             "Parade", "View", "Green"]
_BUILDINGS = ["Rosewood House", "Albion Court", "Wharf Mill", "The Old Rectory", "Kingfisher Lodge",
              "Victoria Quays", "Mercury House", "Weavers Yard", "Holbeck Mill", "Cedar Point", "The Maltings",
              "Ashton Lofts", "Prospect Place", "Sovereign Court", "Granary Wharf", "Brunswick House",
              "Hollybank", "Ivy Cottage", "Lark Rise", "Station House", "Copper Works", "Navigation Point"]
_FLATS = ["Flat {n}", "Flat {n}", "Flat {n}{l}", "Apartment {n}", "Flat {n}", "Unit {n}", "Room {n}"]


@dataclass
class Address:
    number: str
    street: str
    town: str
    county: str
    postcode_text: str
    flat: str = ""
    building: str = ""
    locality: str = ""

    def lines(self, county: bool = False, upper_town: bool = False, flat_sep_line: bool = False) -> list[str]:
        out = []
        street = f"{self.number} {self.street}".strip()
        if self.flat and self.building:
            out.append(f"{self.flat}, {self.building}" if not flat_sep_line else self.flat)
            if flat_sep_line:
                out.append(self.building)
        elif self.flat:
            if flat_sep_line:
                out.append(self.flat)
            else:
                street = f"{self.flat}, {street}"
        elif self.building:
            out.append(self.building)
        out.append(street)
        if self.locality:
            out.append(self.locality)
        out.append(self.town.upper() if upper_town else self.town)
        if county and self.county:
            out.append(self.county)
        return out

    def street_line(self) -> str:
        s = f"{self.number} {self.street}".strip()
        if self.flat and not self.building:
            return f"{self.flat}, {s}"
        if self.building and not self.number:
            return f"{self.building}, {s}"
        return s

    def _hard(self) -> tuple[str, ...]:
        return ("flat_number",) if self.flat else ()

    def block(self, rng: random.Random, ref: str | None = None, postcode_same_line: bool | None = None) -> list:
        """Multi-line address: ADDRESS span (with newlines) + POSTCODE span."""
        lines = self.lines(county=rng.random() < 0.25, upper_town=rng.random() < 0.3,
                           flat_sep_line=rng.random() < 0.5)
        same = rng.random() < 0.25 if postcode_same_line is None else postcode_same_line
        sep = "\n" if not same else rng.choice(["  ", " ", ", "])
        return HC("multiline_address", E("\n".join(lines), "ADDRESS", ref, self._hard()), sep,
                  E(self.postcode_text, "POSTCODE", ref))

    def inline(self, rng: random.Random, ref: str | None = None, postcode: bool = True) -> list:
        lines = self.lines(county=rng.random() < 0.1, upper_town=False, flat_sep_line=False)
        if not postcode:
            return [E(", ".join(lines), "ADDRESS", ref, self._hard())]
        sep = rng.choice([", ", " ", ", ", " "])
        return [E(", ".join(lines), "ADDRESS", ref, self._hard()), sep, E(self.postcode_text, "POSTCODE", ref)]

    def street_only(self, ref: str | None = None) -> E:
        return E(self.street_line(), "ADDRESS", ref, self._hard())

    def postcode(self, ref: str | None = None, lower: bool = False) -> E:
        t = self.postcode_text.lower() if lower else self.postcode_text
        return E(t, "POSTCODE", ref)


def street_name(rng: random.Random) -> str:
    if rng.random() < 0.08:
        return rng.choice(["High Street", "The Green", "The Crescent", "Market Place", "The Avenue",
                           "London Road", "Main Street", "The Drive"])
    stem = rng.choice(_STREET_STEMS) if rng.random() < 0.75 else rng.choice(_LAST)
    return f"{stem} {rng.choice(_SUFFIXES)}"


def make_address(rng: random.Random, town: str | None = None, flat_rate: float = 0.25,
                 building_rate: float = 0.1) -> Address:
    if town is None:
        t = rng.choice(TOWNS) if rng.random() < 0.8 else TOWNS[-1]  # London over-weighted
    else:
        t = next(x for x in TOWNS if x[0] == town)
    tname, county, outwards = t
    pc = ids.postcode(rng, rng.choice(outwards))
    if rng.random() < 0.04:
        pc = pc.replace(" ", "")
    num = str(rng.randint(1, 240)) if rng.random() < 0.9 else f"{rng.randint(1, 120)}{rng.choice('ABC')}"
    flat = ""
    building = ""
    if rng.random() < flat_rate:
        flat = rng.choice(_FLATS).format(n=rng.randint(1, 48), l=rng.choice("ABCD"))
        if rng.random() < 0.3:
            building = rng.choice(_BUILDINGS)
    elif rng.random() < building_rate:
        building = rng.choice(_BUILDINGS)
        if rng.random() < 0.5:
            num = ""
    loc = ""
    if tname in LOCALITIES and rng.random() < 0.35:
        loc = rng.choice(LOCALITIES[tname])
    return Address(num, street_name(rng), tname, county, pc, flat, building, loc)


# --------------------------------------------------------------------------- organisations
PUBLIC = {
    "bank": ["Barclays", "Lloyds Bank", "NatWest", "HSBC", "Santander", "Nationwide", "Halifax", "Monzo",
             "Starling Bank", "TSB", "Metro Bank", "first direct", "Revolut", "Chase UK"],
    "energy": ["British Gas", "Octopus Energy", "EDF", "E.ON Next", "OVO Energy", "Scottish Power", "So Energy",
               "Utility Warehouse"],
    "water": ["Thames Water", "Yorkshire Water", "Severn Trent", "United Utilities", "Anglian Water",
              "Welsh Water", "Southern Water", "Northumbrian Water"],
    "telecom": ["EE", "Vodafone", "O2", "Three", "BT", "Sky", "Virgin Media", "giffgaff", "Tesco Mobile",
                "Plusnet", "TalkTalk", "iD Mobile", "Lebara", "Hyperoptic"],
    "retail": ["Tesco", "Sainsbury's", "Asda", "Morrisons", "Aldi", "Lidl", "Argos", "Currys", "John Lewis",
               "Marks & Spencer", "Boots", "IKEA", "Amazon", "ASOS", "Screwfix", "B&Q", "Greggs",
               "Pret A Manger", "Costa Coffee", "Waitrose", "Next", "Primark", "Wickes", "Dunelm"],
    "insurer": ["Aviva", "Direct Line", "Admiral", "LV=", "Churchill", "AXA", "Hastings Direct", "NFU Mutual"],
    "transport": ["TfL", "Trainline", "National Rail", "Uber", "Deliveroo", "Royal Mail", "DPD", "Evri",
                  "Ryanair", "easyJet", "British Airways", "Avanti West Coast", "Northern"],
    "public_body": ["HMRC", "DVLA", "DWP", "the NHS", "Ofgem", "Ofcom", "the Financial Ombudsman Service",
                    "Citizens Advice", "Companies House", "HM Land Registry", "the Legal Ombudsman", "ACAS",
                    "the ICO", "the Valuation Office Agency"],
    "deposit": ["the Deposit Protection Service", "the Tenancy Deposit Scheme", "mydeposits"],
    "tech": ["Microsoft", "Google", "Apple", "Zoom", "Slack", "Xero", "QuickBooks", "Sage", "HubSpot",
             "Stripe", "PayPal", "WhatsApp", "Dropbox", "DocuSign", "Rightmove", "Zoopla", "OpenRent"],
    "employer": ["Deloitte", "PwC", "Unilever", "the BBC", "Network Rail", "Rolls-Royce", "AstraZeneca",
                 "GSK", "Jaguar Land Rover", "BAE Systems", "Sky", "Capita"],
}
ALL_PUBLIC = sorted({n for v in PUBLIC.values() for n in v})


@dataclass
class Org:
    name: str
    kind: str
    domain: str
    ids: dict[str, str] = field(default_factory=dict)  # label -> pattern for CUSTOM ids
    public: bool = False

    def custom(self, rng: random.Random, label: str | None = None, year: int | None = None) -> tuple[str, E]:
        """Return (label, CUSTOM entity) for one of this org's identifier formats."""
        if label is None:
            label = rng.choice(list(self.ids))
        val = ids.from_pattern(rng, self.ids[label], year)
        return label, E(val, "CUSTOM", None, ("custom_org_id",))

    def name_k(self) -> K | str:
        return K(self.name, "public_company") if self.public else self.name


SYNTH_ORGS = [
    # solicitors
    Org("Ashcombe Legal LLP", "law", "ashcombelegal.co.uk", {"Client code": "CL-#####", "Matter number": "M/{yyyy}/###"}),
    Org("Harrow & Finch LLP", "law", "harrowfinch.co.uk", {"Client code": "HF-#####", "Matter number": "HF/M/{yy}/####", "Our ref": "HF/@@/####"}),
    Org("Kestrel Lane Solicitors", "law", "kestrellane.co.uk", {"Client number": "KL#####", "Matter": "KL-{yy}-####"}),
    Org("Bramwell Oakes Solicitors", "law", "bramwelloakes.com", {"Client ID": "BO/C/####", "Matter no.": "BO/M/{yy}/####"}),
    Org("Ferncliffe Law", "law", "ferncliffelaw.co.uk", {"Client ref": "FCL-@@-####", "File ref": "FCL/{yyyy}/#####"}),
    # accountants
    Org("Brook & Partners Accountants", "accountant", "brookpartners.co.uk", {"Client code": "BPA####", "Engagement ref": "ENG-{yyyy}-###"}),
    Org("Larkfield Tax & Accounts Ltd", "accountant", "larkfieldtax.co.uk", {"Client ref": "LTA-@@####"}),
    Org("Penrose Hale Chartered Accountants", "accountant", "penrosehale.co.uk", {"Client no.": "PH#####", "Job ref": "PH/{yy}/####"}),
    # letting agents
    Org("Cavendish Row Lettings", "letting", "cavendishrow.co.uk", {"Tenancy ref": "CRL/T/#####", "Landlord ref": "CRL/L/####"}),
    Org("Northgate Property Management", "letting", "northgatepm.co.uk", {"Tenant ID": "NPM-######", "Property ref": "NPM-P-####"}),
    Org("Riverside Homes Lettings", "letting", "riversidehomes.co.uk", {"Tenancy reference": "RHL######"}),
    Org("Halden & Moor Estates", "letting", "haldenmoor.co.uk", {"Tenancy ref": "HME/{yy}/####", "Applicant ID": "HME-A-#####"}),
    # insurers
    Org("Meridian Mutual Insurance", "insurer", "meridianmutual.co.uk", {"Policy number": "MMH-########", "Claim reference": "CLM-{yy}-######"}),
    Org("Harbourside General", "insurer", "harboursidegeneral.co.uk", {"Policy no.": "HG/@@/#######", "Claim no.": "HGC#######"}),
    Org("Thistle Cover Ltd", "insurer", "thistlecover.co.uk", {"Policy number": "TC#######@", "Claim number": "TCC-{yyyy}-#####"}),
    # utilities / telecom (synthetic)
    Org("Northstar Energy", "energy", "northstarenergy.co.uk", {"Account number": "NSE ### ### ####"}),
    Org("Brightwave Broadband", "telecom", "brightwave.co.uk", {"Account number": "BW-########"}),
    Org("Pennant Water", "water", "pennantwater.co.uk", {"Customer reference": "#### #### ####"}),
    Org("Lumen Mobile", "telecom", "lumenmobile.co.uk", {"Account number": "LM########"}),
    Org("Greenleaf Power", "energy", "greenleafpower.co.uk", {"Account no.": "GLP-#######"}),
    # employers
    Org("Brightwater Logistics Ltd", "employer", "brightwaterlogistics.co.uk", {"Employee number": "BWL#####", "Payroll ID": "PR-######"}),
    Org("Fenwick Hale Engineering Ltd", "employer", "fenwickhale.com", {"Employee ID": "FH-####"}),
    Org("Copperleaf Digital Ltd", "employer", "copperleaf.io", {"Staff no.": "CD####"}),
    Org("Saltmarsh Foods plc", "employer", "saltmarshfoods.co.uk", {"Employee no.": "SF######"}),
    Org("Greyfriars Care Homes Ltd", "employer", "greyfriarscare.co.uk", {"Staff ID": "GCH-#####"}),
    Org("Oakhurst Academy Trust", "employer", "oakhurstacademy.org.uk", {"Employee number": "OAT####"}),
    Org("Tamberly Studio Ltd", "employer", "tamberly.studio", {"Employee ID": "TS-###"}),
    # SaaS / consumer services (support tickets)
    Org("Parcelly", "saas", "parcelly.co.uk", {"Customer ID": "PCY-#######"}),
    Org("Tidyhome", "saas", "tidyhome.co.uk", {"Account ID": "TH-@@@-####"}),
    Org("Quillpad", "saas", "quillpad.app", {"Workspace ID": "qp-########"}),
    Org("Fetchly Pets", "saas", "fetchly.co.uk", {"Member no.": "FP######"}),
    Org("Roamwell Travel", "saas", "roamwell.travel", {"Booking customer ref": "RW-@@####"}),
    # healthcare (synthetic GP practices)
    Org("Oakwood Medical Centre", "gp", "oakwoodmedical.nhs.uk", {"Patient ID": "OMC######"}),
    Org("Riverbank Surgery", "gp", "riverbanksurgery.nhs.uk", {"Practice patient no.": "RBS-#####"}),
    Org("Elmtree Health Centre", "gp", "elmtreehealth.nhs.uk", {"Patient ref": "ETH#######"}),
]
ORGS_BY_KIND: dict[str, list[Org]] = {}
for _o in SYNTH_ORGS:
    ORGS_BY_KIND.setdefault(_o.kind, []).append(_o)

HOSPITAL_TRUSTS = ["Leeds Teaching Hospitals NHS Trust", "Manchester University NHS Foundation Trust",
                   "Guy's and St Thomas' NHS Foundation Trust", "University Hospitals Bristol and Weston NHS Foundation Trust",
                   "Sheffield Teaching Hospitals NHS Foundation Trust", "Barts Health NHS Trust",
                   "Newcastle upon Tyne Hospitals NHS Foundation Trust", "Cardiff and Vale University Health Board",
                   "NHS Greater Glasgow and Clyde", "Nottingham University Hospitals NHS Trust",
                   "Oxford University Hospitals NHS Foundation Trust", "University Hospitals Birmingham NHS Foundation Trust"]
COUNCILS = [f"{t} City Council" for t in ["Leeds", "Manchester", "Birmingham", "Bristol", "Sheffield",
                                           "Nottingham", "Leicester", "Coventry", "Bradford", "York"]] + \
    ["Cardiff Council", "Glasgow City Council", "City of Edinburgh Council", "London Borough of Hackney",
     "London Borough of Lambeth", "Royal Borough of Greenwich", "Brighton & Hove City Council",
     "Oxford City Council", "Cambridge City Council", "Kirklees Council", "Wakefield Council"]

_CO_WORDS = ["Apex", "Northern", "Summit", "Crown", "Anchor", "Beacon", "Harbour", "Pinnacle", "Evergreen",
             "Ironbridge", "Bluebell", "Silverline", "Redbrick", "Fairway", "Lighthouse", "Meadowbank",
             "Stonegate", "Whitecross", "Kingfisher", "Oakridge", "Riverstone", "Westmoor", "Cobalt", "Juniper"]
_CO_TRADES = ["Plumbing", "Electrical", "Roofing", "Joinery", "Cleaning Services", "Consulting", "Design",
              "Logistics", "Lettings", "Accountancy", "Builders", "Landscaping", "IT Services", "Catering",
              "Photography", "Decorating", "Locksmiths", "Removals", "Tutoring", "Bookkeeping", "Web Design"]
_CO_SUFFIX = ["Ltd", "Ltd", "Limited", "LLP", "plc", "Ltd", "& Co Ltd"]


def company_name(rng: random.Random, with_person_surname: str | None = None) -> K:
    """A private limited company. If ``with_person_surname`` is given the name contains a surname
    (e.g. 'Patel & Sons Ltd'), which we deliberately do NOT label (registered company)."""
    if with_person_surname:
        pat = rng.choice(["{s} & Sons Ltd", "{s} & Co Ltd", "{s} Brothers Ltd", "{s} {t} Ltd", "{s} and {s2} LLP",
                          "{s} Family Holdings Ltd", "{s} & Daughters Ltd"])
        s2 = rng.choice(_LAST)
        return K(pat.format(s=with_person_surname, s2=s2, t=rng.choice(_CO_TRADES)), "company_with_person_name")
    pat = rng.choice(["{w} {t} {x}", "{w} {x}", "{w} {w2} {x}", "{w} {t} {x}"])
    return K(pat.format(w=rng.choice(_CO_WORDS), w2=rng.choice(_CO_WORDS), t=rng.choice(_CO_TRADES),
                        x=rng.choice(_CO_SUFFIX)), "company_name")


def sole_trader(rng: random.Random, person) -> list:
    """Trading name that is a person's own name: label the name part as PERSON."""
    pat = rng.choice(["{n} {t}", "{n} {t}", "{t} by {n}", "{n} T/A {w} {t}"])
    parts = []
    for chunk in pat.replace("{n}", "\x00").split("\x00"):
        if parts:
            parts.append(person.full("sole_trader_name"))
        parts.append(chunk.format(t=rng.choice(_CO_TRADES), w=rng.choice(_CO_WORDS)))
    return parts


def public_company(rng: random.Random, kind: str | None = None) -> K:
    if kind is None:
        kind = rng.choice(list(PUBLIC))
    return K(rng.choice(PUBLIC[kind]), "public_company")


def domain_for(name: str) -> str:
    base = "".join(c for c in name.lower().replace("&", "and") if c.isalnum())
    return base[:22] + ".co.uk"


# --------------------------------------------------------------------------- keep-trap helpers
def money_text(x: float, style: int = 0) -> str:
    if style == 1 and x == int(x):
        return f"£{int(x):,}"
    if style == 2:
        return f"{x:,.2f} GBP"
    if style == 3:
        return f"GBP {x:,.2f}"
    return f"£{x:,.2f}"


def money(rng: random.Random, lo: float, hi: float, style: int | None = None, round_to: float | None = None) -> K:
    x = rng.uniform(lo, hi)
    if round_to:
        x = round(x / round_to) * round_to
    x = round(x, 2)
    st = rng.choice([0, 0, 0, 1, 2]) if style is None else style
    return K(money_text(x, st), "amount")


def amount_k(x: float, style: int = 0) -> K:
    return K(money_text(x, style), "amount")


def date_k(d: date, style: int | None = None, rng: random.Random | None = None) -> K:
    if style is None:
        style = (rng or random).choice([0, 0, 1, 1, 2, 3, 5])
    return K(ids.format_date(d, style), "date")


STATUTES = ["Housing Act 1988", "Housing Act 2004", "Landlord and Tenant Act 1985", "Deregulation Act 2015",
            "Tenant Fees Act 2019", "Renters' Rights Act 2025", "Protection from Eviction Act 1977",
            "Employment Rights Act 1996", "Working Time Regulations 1998", "Equality Act 2010",
            "Data Protection Act 2018", "UK GDPR", "Consumer Rights Act 2015",
            "Late Payment of Commercial Debts (Interest) Act 1998", "Money Laundering Regulations 2017",
            "Limitation Act 1980", "Insurance Act 2015", "Contracts (Rights of Third Parties) Act 1999",
            "Companies Act 2006", "Unfair Contract Terms Act 1977", "Gas Safety (Installation and Use) Regulations 1998",
            "Smoke and Carbon Monoxide Alarm (England) Regulations 2015", "Renting Homes (Wales) Act 2016",
            "Private Housing (Tenancies) (Scotland) Act 2016", "Electrical Safety Standards in the Private Rented Sector (England) Regulations 2020",
            "Agency Workers Regulations 2010", "National Minimum Wage Act 1998", "Proceeds of Crime Act 2002"]


def statute(rng: random.Random) -> K:
    return K(rng.choice(STATUTES), "statute")


PLACE_TRAPS = ["the Rose Garden", "the Oak Road works", "Victoria Park", "the Station Road car park",
               "Kings Cross station", "Manchester Piccadilly", "the Lake District", "Hyde Park", "the M62",
               "Leeds city centre", "Heathrow Terminal 5", "the Royal Infirmary", "Market Street car park",
               "the Mill Lane recycling centre", "Hope Street", "the High Street branch", "Grace Hall",
               "Millennium Square", "the Elm Grove allotments", "Birmingham New Street", "the A64",
               "Canary Wharf", "the Trafford Centre", "Meadowhall", "Bristol Temple Meads"]


def place_trap(rng: random.Random) -> K:
    return K(rng.choice(PLACE_TRAPS), "place_name")


# phrases where a first name appears as an ordinary word ({w} is the trap word)
COMMON_WORD_PHRASES = {
    "Will": ["We {w} confirm in writing.", "It {w} be ready on Monday.", "{w} that be OK?"],
    "Rose": ["Prices {w} by 4% this year.", "We met by {w} Garden.", "The rent {w} again in April."],
    "Mark": ["Please {w} the parcel as fragile.", "Did you {w} it as paid?", "The {w}-up was 10%."],
    "Grace": ["There is a {w} period of 14 days.", "A {w} period applies."],
    "Hope": ["I {w} this helps.", "We {w} to hear from you soon.", "Fingers crossed and {w} for the best."],
    "May": ["You {w} need to provide ID.", "The inspection {w} take an hour.", "{w} I ask for an update?"],
    "Bill": ["The {w} is due on the 1st.", "Your {w} has gone up.", "Can you split the {w}?"],
    "Joy": ["No {w} with the courier yet.", "Still no {w} from the council."],
    "Faith": ["Both parties act in good {w}.", "This is offered in good {w}."],
    "Frank": ["To be {w}, it is late.", "Thanks for the {w} feedback."],
    "Holly": ["The {w} bushes need cutting back.", "There is {w} by the front gate."],
    "Ivy": ["The {w} on the rear wall is the landlord's job.", "Remove the {w} from the fence."],
    "Dawn": ["The van left at {w}.", "Works start at {w} on Saturday."],
    "Miles": ["It is about 12 {w} away.", "Business {w} are paid at 45p."],
    "Guy": ["The {w} from the courier never came.", "A delivery {w} left it outside."],
    "Ray": ["A {w} of light came through the leak.", "Get an X-{w} if it still hurts."],
    "Rich": ["The report is {w} in detail.", "That is a {w} source of data."],
    "Drew": ["We {w} up the contract last week.", "The landlord {w} up a new inventory."],
    "Penny": ["Every {w} counts.", "Not a {w} was refunded."],
    "Summer": ["We will be away this {w}.", "The {w} rota is attached."],
    "Amber": ["There is an {w} weather warning.", "The light was {w}."],
    "Sue": ["They threatened to {w} the agency.", "I do not want to {w} anyone."],
    "Pat": ["{w} the screen dry.", "Give the dog a {w}."],
    "Jack": ["Use the {w} in the boot.", "Plug it into the audio {w}."],
    "Robin": ["A {w} was nesting in the porch.", "We saw a {w} in the garden."],
    "June": ["The lease ends in {w}.", "Rent is reviewed every {w}."],
    "April": ["Prices change in {w}.", "The next review is in {w}."],
    "Ruby": ["It was a {w} wedding anniversary.", "The {w} red paint is chipped."],
    "Daisy": ["The {w} chain is in the drawer.", "Fresh as a {w}."],
    "Pearl": ["The {w} earrings were not insured.", "A {w} necklace was taken."],
    "Iris": ["The {w} scan is routine.", "{w} bulbs in the front bed."],
    "Heather": ["The {w} on the hill is out.", "{w} grows by the path."],
    "Victor": ["The {w} was announced.", "{w} was the word they used."],
    "Art": ["The {w} supplies are extra.", "It is more {w} than science."],
    "Sonny": ["\"All right, {w}\" was the greeting.", "Hey {w}, said the driver."],
}


def common_word_phrase(rng: random.Random, name: str) -> list | None:
    opts = COMMON_WORD_PHRASES.get(name)
    if not opts:
        return None
    t = rng.choice(opts)
    a, b = t.split("{w}", 1)
    keep_cap = (a == "" or a.endswith('"') or a.endswith("X-") or b.startswith(" Garden")
                or name in ("May", "June", "April") and a.rstrip().endswith(("in", "every")))
    w = name if keep_cap else name.lower()
    return [a, K(w, "common_word"), b]


PRODUCTS = ["iPhone 15", "Galaxy S24", "Octopus Flexible", "Fixed Saver June 2027", "Unlimited Max",
            "SIM Only 30GB", "Fibre 500", "Premium Saver", "Clubcard", "Nectar card", "Prime membership",
            "MacBook Air", "Dyson V11", "Hive thermostat", "Ring doorbell", "Nest Mini", "Kindle Paperwhite",
            "Flex Account", "Everyday Saver", "Cash ISA", "Microsoft 365 Family", "Spotify Premium",
            "Netflix Standard", "PlayStation 5", "Ninja air fryer", "Worcester Bosch boiler"]


def product(rng: random.Random) -> K:
    return K(rng.choice(PRODUCTS), "product")


def doc_ref(rng: random.Random, kind: str = "invoice") -> K:
    pats = {
        "invoice": ["INV-{yyyy}-####", "INV####", "#####", "SI-######", "{yy}/####"],
        "order": ["#######", "ORD-########", "A##-#######-#######", "W#########"],
        "ticket": ["#######", "TKT-######", "SR-#####", "CS-######"],
        "txn": ["##########", "FP@@##########", "TXN#########"],
        "bill": ["######", "B########", "#######"],
    }
    return K(ids.from_pattern(rng, rng.choice(pats[kind])), "doc_reference")
