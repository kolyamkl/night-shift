"""Synthetic people: names by origin, name surface forms, personal identifiers.

All names are combined at random from common first-name and surname lists (Faker en_GB
plus hand-made lists for other origins), so no record describes a real person.
"""
from __future__ import annotations

import random
from datetime import date
from functools import cached_property

from faker.providers.person.en_GB import Provider as _FakerPerson

from . import ids
from .core import E

_EN_M = list(_FakerPerson.first_names_male)
_EN_F = list(_FakerPerson.first_names_female)
_EN_L = list(_FakerPerson.last_names)

# first names that are also ordinary English words (hard case)
COMMON_WORD_F = ["Rose", "Grace", "Hope", "May", "Joy", "Faith", "Holly", "Ivy", "Dawn", "Penny",
                 "Summer", "Amber", "Iris", "Heather", "Ruby", "June", "April", "Sue", "Pearl", "Daisy"]
COMMON_WORD_M = ["Will", "Mark", "Bill", "Frank", "Miles", "Guy", "Ray", "Rich", "Drew", "Jack",
                 "Robin", "Pat", "Sonny", "Victor", "Art"]
COMMON_WORD_SURNAMES = ["Baker", "Green", "White", "Wood", "Hill", "Bell", "King", "Young", "Hope",
                        "Moss", "Rice", "Hall", "Stone", "Cook", "Bishop", "Church", "Marsh", "Fox",
                        "Banks", "Brook", "Mills", "Lane", "Field", "Rose", "May", "Bird", "Sharp"]

ORIGINS = {
    "uk": dict(m=_EN_M, f=_EN_F, l=_EN_L),
    "ua": dict(
        m=["Oleksandr", "Dmytro", "Mykola", "Taras", "Andrii", "Bohdan", "Serhii", "Volodymyr", "Yaroslav",
           "Maksym", "Vasyl", "Danylo", "Ihor", "Yurii", "Oleh", "Vitalii", "Mykhailo", "Petro", "Roman"],
        f=["Oleksandra", "Olena", "Iryna", "Kateryna", "Yuliia", "Viktoriia", "Nataliia", "Oksana", "Halyna",
           "Liudmyla", "Hanna", "Sofiia", "Tetiana", "Svitlana", "Mariia", "Daryna", "Khrystyna", "Yevheniia"],
        l=["Kovalenko", "Shevchenko", "Bondarenko", "Tkachenko", "Kravchenko", "Melnyk", "Boiko", "Koval",
           "Oliinyk", "Shevchuk", "Polishchuk", "Lysenko", "Marchenko", "Rudenko", "Savchenko", "Petrenko",
           "Moroz", "Pavlenko", "Hrytsenko", "Zinchenko", "Kuzmenko", "Ostapchuk", "Tymoshchuk", "Yatsenko",
           "Burdeniuk", "Honcharenko", "Kostiuk", "Levchenko"],
    ),
    "pl": dict(
        m=["Łukasz", "Krzysztof", "Wojciech", "Paweł", "Grzegorz", "Michał", "Tomasz", "Piotr", "Jakub",
           "Mateusz", "Bartosz", "Kamil", "Marcin", "Rafał", "Lukasz", "Pawel", "Michal"],
        f=["Małgorzata", "Agnieszka", "Katarzyna", "Zofia", "Joanna", "Magdalena", "Aleksandra", "Ewa",
           "Dorota", "Beata", "Justyna", "Weronika", "Malgorzata", "Zuzanna"],
        l=["Kowalski", "Wiśniewski", "Wójcik", "Kamiński", "Lewandowski", "Zieliński", "Szymański",
           "Woźniak", "Dąbrowski", "Nowak", "Mazur", "Krawczyk", "Grabowski", "Wojcik", "Kaminski",
           "Jankowski", "Pawlak", "Michalski", "Król"],
    ),
    "in": dict(
        m=["Rahul", "Arjun", "Deepak", "Ravi", "Sanjay", "Vikram", "Amit", "Rohan", "Kiran", "Harpreet",
           "Gurpreet", "Manpreet", "Arun", "Nikhil", "Pranav", "Suresh", "Rajesh", "Anil"],
        f=["Priya", "Anjali", "Sunita", "Kavya", "Neha", "Pooja", "Divya", "Meera", "Lakshmi", "Simran",
           "Jaspreet", "Anika", "Shreya", "Deepa", "Asha", "Nisha"],
        l=["Patel", "Sharma", "Singh", "Kaur", "Gupta", "Shah", "Mehta", "Iyer", "Reddy", "Nair", "Chopra",
           "Desai", "Joshi", "Kapoor", "Malhotra", "Bhatt", "Chauhan", "Sandhu", "Gill", "Mistry", "Pillai"],
    ),
    "ng": dict(
        m=["Chinedu", "Oluwaseun", "Adebayo", "Emeka", "Tunde", "Obinna", "Babatunde", "Uchenna", "Chukwuemeka",
           "Olumide", "Ikenna", "Femi", "Segun", "Kelechi"],
        f=["Ngozi", "Chiamaka", "Folake", "Ifeoma", "Yetunde", "Funmilayo", "Nkechi", "Adaeze", "Temitope",
           "Oluwakemi", "Chidinma", "Bukola", "Amaka", "Titilayo"],
        l=["Okafor", "Adeyemi", "Okonkwo", "Balogun", "Eze", "Nwosu", "Adebayo", "Ogunleye", "Okoro",
           "Abiodun", "Chukwu", "Oyelaran", "Afolabi", "Nwachukwu", "Olawale", "Onyeka", "Adeleke", "Obi"],
    ),
    "ie": dict(
        m=["Seán", "Pádraig", "Ciarán", "Dónal", "Séamus", "Tadhg", "Eoin", "Cillian", "Oisín", "Darragh",
           "Colm", "Fionn", "Liam", "Cathal"],
        f=["Siobhán", "Niamh", "Aoife", "Caoimhe", "Róisín", "Clíodhna", "Órla", "Máire", "Sinéad", "Saoirse",
           "Aisling", "Gráinne", "Méabh", "Eimear"],
        l=["O'Sullivan", "O'Brien", "Ó Súilleabháin", "Ó Ceallaigh", "MacCarthy", "Ó Néill", "O'Connor",
           "Fitzgerald", "Ní Bhriain", "Mac Giolla Phádraig", "Ó Briain", "Murphy", "Byrne", "Kavanagh",
           "Ó Dónaill", "Ní Dhomhnaill", "Walsh", "McGrath"],
    ),
    "pk": dict(
        m=["Muhammad", "Ahmed", "Ali", "Hassan", "Bilal", "Imran", "Usman", "Zain", "Omar", "Tariq", "Yusuf"],
        f=["Fatima", "Ayesha", "Zainab", "Maryam", "Sana", "Hira", "Amina", "Noor", "Khadija", "Rabia"],
        l=["Khan", "Hussain", "Iqbal", "Malik", "Ahmed", "Rashid", "Akhtar", "Siddiqui", "Qureshi", "Butt",
           "Chaudhry", "Mahmood", "Shah", "Aziz"],
    ),
    "cn": dict(
        m=["Wei", "Jun", "Hao", "Yang", "Lei", "Jian", "Zhiwei", "Chen", "Ming"],
        f=["Li Na", "Xiaoling", "Mei", "Yan", "Jing", "Hui", "Xin", "Ying", "Lan"],
        l=["Zhang", "Wang", "Li", "Liu", "Chen", "Huang", "Zhao", "Wu", "Zhou", "Lin", "Ng", "Wong", "Chan"],
    ),
    "cy": dict(  # Welsh and Scottish
        m=["Rhys", "Gethin", "Dafydd", "Iwan", "Gareth", "Iain", "Hamish", "Callum", "Ewan", "Angus", "Euan"],
        f=["Cerys", "Siân", "Bethan", "Angharad", "Rhiannon", "Mhairi", "Morag", "Eilidh", "Catriona", "Ffion"],
        l=["Jones", "Williams", "Evans", "Davies", "Pritchard", "Llewellyn", "MacLeod", "Campbell", "Fraser",
           "MacDonald", "Stewart", "Morgan", "ap Rhys", "Robertson", "McKenzie"],
    ),
    "eu": dict(  # other European
        m=["João", "José", "Andrei", "Ionuț", "Luca", "Matteo", "Mehmet", "Nikos", "Tiago", "Javier", "Pierre"],
        f=["María", "Andreea", "Giulia", "Ana", "Elif", "Chloé", "Inês", "Lucía", "Eleni", "Ioana", "Sofía"],
        l=["Popescu", "Gonçalves", "Rossi", "Fernández", "Yılmaz", "Papadopoulos", "Silva", "García",
           "Ionescu", "Dubois", "de Souza", "van der Berg", "Moreau", "Esposito", "Costa"],
    ),
}
ORIGIN_WEIGHTS = [("uk", 46), ("ua", 8), ("pl", 7), ("in", 10), ("ng", 7), ("ie", 6), ("pk", 6),
                  ("cn", 3), ("cy", 4), ("eu", 3)]
_O_NAMES = [o for o, _ in ORIGIN_WEIGHTS]
_O_W = [w for _, w in ORIGIN_WEIGHTS]

NICKNAMES = {
    "William": "Will", "Robert": "Rob", "Elizabeth": "Liz", "Katherine": "Kate", "Catherine": "Cathy",
    "Margaret": "Maggie", "Jonathan": "Jon", "Christopher": "Chris", "Alexander": "Alex", "Samuel": "Sam",
    "Benjamin": "Ben", "Thomas": "Tom", "Daniel": "Dan", "Michael": "Mike", "Rebecca": "Becky",
    "Jennifer": "Jen", "Victoria": "Vicky", "Joanne": "Jo", "Josephine": "Jo", "Joseph": "Joe",
    "Richard": "Rich", "Patrick": "Pat", "Susan": "Sue", "Matthew": "Matt", "Nicholas": "Nick",
    "Oleksandra": "Sasha", "Oleksandr": "Sasha", "Dmytro": "Dima", "Kateryna": "Katia", "Volodymyr": "Volodia",
    "Małgorzata": "Gosia", "Malgorzata": "Gosia", "Katarzyna": "Kasia", "Aleksandra": "Ola",
    "Oluwaseun": "Seun", "Babatunde": "Tunde", "Chukwuemeka": "Emeka", "Oluwakemi": "Kemi",
    "Muhammad": "Mo", "Gareth": "Gaz", "Siobhán": "Shiv", "Pádraig": "Paddy", "Mark": "Marky",
    "Deborah": "Debbie", "Andrew": "Andy", "Anthony": "Tony", "Charlotte": "Charlie",
}
# transliteration variants of the same name (hard case)
TRANSLIT = {
    "Oleksandr": "Alexander", "Oleksandra": "Alexandra", "Serhii": "Sergey", "Andrii": "Andriy",
    "Yuliia": "Yulia", "Viktoriia": "Viktoria", "Nataliia": "Natalia", "Mykola": "Nikolai",
    "Dmytro": "Dmitry", "Hanna": "Anna", "Halyna": "Galina", "Yurii": "Yuri", "Ihor": "Igor",
    "Oleh": "Oleg", "Liudmyla": "Lyudmila", "Tetiana": "Tatiana", "Mykhailo": "Mikhail", "Sofiia": "Sofia",
    "Łukasz": "Lukasz", "Paweł": "Pawel", "Michał": "Michal", "Małgorzata": "Malgorzata",
    "Seán": "Sean", "Siobhán": "Siobhan", "Róisín": "Roisin", "Ciarán": "Ciaran", "Pádraig": "Padraig",
    "Muhammad": "Mohammed", "Kovalenko": "Kowalenko", "Shevchenko": "Schewtschenko",
    "Wiśniewski": "Wisniewski", "Wójcik": "Wojcik", "Ó Súilleabháin": "O'Sullivan", "Ó Briain": "O'Brien",
}
TITLES_M = ["Mr", "Mr", "Mr", "Dr", "Mr."]
TITLES_F = ["Mrs", "Ms", "Miss", "Ms", "Dr", "Mrs."]

EMAIL_DOMAINS = ["gmail.com", "gmail.com", "outlook.com", "hotmail.co.uk", "yahoo.co.uk", "btinternet.com",
                 "icloud.com", "sky.com", "live.co.uk", "protonmail.com", "aol.com", "virginmedia.com",
                 "outlook.co.uk", "me.com", "talktalk.net", "googlemail.com"]

_ASCII = str.maketrans({"á": "a", "é": "e", "í": "i", "ó": "o", "ú": "u", "Á": "A", "É": "E", "Í": "I",
                        "Ó": "O", "Ú": "U", "ł": "l", "Ł": "L", "ś": "s", "ż": "z", "ź": "z", "ą": "a",
                        "ę": "e", "ć": "c", "ń": "n", "ó": "o", "ç": "c", "ã": "a", "ț": "t", "ı": "i",
                        "ê": "e", "ô": "o", "ü": "u", "ö": "o", "ğ": "g", "ş": "s", "Ș": "S", "è": "e"})


def ascii_fold(s: str) -> str:
    return s.translate(_ASCII)


def _slug(s: str) -> str:
    return "".join(c for c in ascii_fold(s).lower() if c.isalnum())


_FEMALE_SURNAME = {"ski": "ska", "cki": "cka", "dzki": "dzka"}


class Person:
    """A synthetic person. Identifiers are created lazily from the person's own RNG."""

    _counter = 0

    def __init__(self, rng: random.Random, origin: str | None = None, female: bool | None = None,
                 common_word: bool = False, ref: str = "p0", min_age: int = 18, max_age: int = 85):
        self.rng = rng
        self.ref = ref
        self.origin = origin or rng.choices(_O_NAMES, _O_W)[0]
        self.female = rng.random() < 0.5 if female is None else female
        pool = ORIGINS[self.origin]
        if common_word:
            self.first = rng.choice(COMMON_WORD_F if self.female else COMMON_WORD_M)
            self.origin = "uk"
        else:
            self.first = rng.choice(pool["f"] if self.female else pool["m"])
        self.common_word = common_word
        last = rng.choice(pool["l"] if not common_word else (_EN_L + COMMON_WORD_SURNAMES))
        if self.female:
            for a, b in _FEMALE_SURNAME.items():
                if last.endswith(a):
                    last = last[: -len(a)] + b
            if last.startswith("Ó ") and rng.random() < 0.7:
                last = "Ní " + last[2:]
        elif last.startswith("Ní "):
            last = "Ó " + last[3:]
        if self.origin == "uk" and rng.random() < 0.05:
            last = f"{last}-{rng.choice(_EN_L)}"
        self.last = last
        self.middle = ""
        if rng.random() < 0.22:
            self.middle = rng.choice(pool["f"] if self.female else pool["m"])
            if self.middle == self.first:
                self.middle = ""
        self.title = rng.choice(TITLES_F if self.female else TITLES_M)
        self.min_age, self.max_age = min_age, max_age

    # ----------------------------------------------------------------- names
    @property
    def full_text(self) -> str:
        return f"{self.first} {self.last}"

    @property
    def is_non_english(self) -> bool:
        return self.origin not in ("uk",)

    def _hard(self) -> tuple[str, ...]:
        h = []
        if self.common_word:
            h.append("common_word_name")
        if self.origin in ("ua", "pl", "in", "ng", "ie", "pk", "cn", "eu"):
            h.append("non_english_name")
        return tuple(h)

    def e(self, text: str, *hard: str) -> E:
        return E(text, "PERSON", self.ref, self._hard() + hard)

    def full(self, *hard: str) -> E:
        return self.e(self.full_text, *hard)

    def full_middle(self, *hard: str) -> E:
        if self.middle:
            return self.e(f"{self.first} {self.middle} {self.last}", *hard)
        return self.full(*hard)

    def first_name(self, *hard: str) -> E:
        return self.e(self.first, *hard)

    def last_name(self, *hard: str) -> E:
        return self.e(self.last, *hard)

    def title_last(self, *hard: str) -> list:
        """'Mr Patel' -> title stays outside the span."""
        return [self.title + " ", self.e(self.last, *hard)]

    def title_full(self, *hard: str) -> list:
        return [self.title + " ", self.e(self.full_text, *hard)]

    def initial_last(self, *hard: str) -> E:
        sep = self.rng.choice([". ", " ", "."])
        return self.e(f"{self.first[0]}{sep}{self.last}".replace("..", "."), "initials", *hard)

    def initials(self, *hard: str) -> E:
        ini = self.first[0] + (self.middle[:1] if self.middle and self.rng.random() < 0.3 else "") + \
            ascii_fold(self.last.replace("Ó ", "O").replace("Ní ", "N").replace("Mac ", "M"))[0]
        return self.e(ini.upper(), "initials", *hard)

    def last_comma_first(self, *hard: str) -> E:
        last = self.last.upper() if self.rng.random() < 0.6 else self.last
        return self.e(f"{last}, {self.first}", *hard)

    def caps(self, *hard: str) -> E:
        return self.e(self.full_text.upper(), *hard)

    def possessive(self, use_first: bool = False, *hard: str) -> list:
        base = self.first if use_first else self.last
        return [self.e(base, "possessive", *hard), "'" if base.endswith("s") and self.rng.random() < 0.5 else "'s"]

    def nickname(self, *hard: str) -> E:
        return self.e(NICKNAMES.get(self.first, self.first), *hard)

    def translit(self) -> E | None:
        f = TRANSLIT.get(self.first)
        l = TRANSLIT.get(self.last)
        if not f and not l:
            return None
        return self.e(f"{f or self.first} {l or self.last}", "transliteration_variant")

    def mention(self, rng: random.Random, formal: bool = True) -> list:
        """A later mention in running text (title+surname, first name, or surname)."""
        r = rng.random()
        if formal:
            if r < 0.6:
                return self.title_last()
            if r < 0.8:
                return [self.last_name()]
            return [self.full()]
        if r < 0.7:
            return [self.first_name()]
        if r < 0.85:
            return [self.nickname()]
        return [self.full()]

    # ----------------------------------------------------------------- identifiers
    @cached_property
    def dob_date(self) -> date:
        return ids.dob(self.rng, self.min_age, self.max_age)

    def dob(self, style: int | None = None) -> E:
        st = self.rng.choice([0, 0, 0, 1, 1, 2, 3, 4, 5, 6, 7, 8, 9]) if style is None else style
        return E(ids.format_date(self.dob_date, st), "DOB", self.ref)

    @cached_property
    def ni_raw(self) -> str:
        return ids.ni_number(self.rng)

    def ni(self, style: int | None = None) -> E:
        st = self.rng.choice([0, 0, 1, 2]) if style is None else style
        h = ("spaced_identifier",) if st else ()
        return E(ids.format_ni(self.ni_raw, st), "NI_NUMBER", self.ref, h)

    @cached_property
    def bank(self) -> tuple[str, str, str, str]:
        name, code, prefixes = self.rng.choice(ids.BANKS)
        sc = ids.sort_code(self.rng, self.rng.choice(prefixes))
        acct = ids.account_number(self.rng)
        return name, code, sc, acct

    @property
    def bank_name(self) -> str:
        return self.bank[0]

    def sort_code(self, style: int | None = None) -> E:
        st = self.rng.choice([0, 0, 0, 1, 2]) if style is None else style
        return E(ids.format_sort(self.bank[2], st), "SORT_CODE", self.ref)

    def account(self, spaced: bool = False) -> E:
        a = self.bank[3]
        return E(f"{a[:4]} {a[4:]}" if spaced else a, "BANK_ACCOUNT", self.ref)

    def account_last4(self) -> E:
        return E(self.bank[3][-4:], "BANK_ACCOUNT", self.ref, ("partial_number",))

    @cached_property
    def iban_raw(self) -> str:
        _, code, sc, acct = self.bank
        return ids.gb_iban(code, sc, acct)

    def iban(self, spaced: bool | None = None) -> E:
        sp = self.rng.random() < 0.5 if spaced is None else spaced
        return E(ids.format_iban(self.iban_raw, sp), "IBAN", self.ref, ("spaced_identifier",) if sp else ())

    @cached_property
    def card_raw(self) -> str:
        scheme = self.rng.choices(["visa", "mastercard", "amex"], [55, 35, 10])[0]
        return ids.card_number(self.rng, scheme)

    def card(self, style: int | None = None) -> E:
        st = self.rng.choice([0, 1, 1, 2]) if style is None else style
        return E(ids.format_card(self.card_raw, st), "CARD", self.ref)

    def card_last4(self) -> E:
        return E(self.card_raw[-4:], "CARD", self.ref, ("partial_number",))

    @cached_property
    def mobile_raw(self) -> str:
        return ids.mobile_number(self.rng)

    def mobile(self, style: int | None = None) -> E:
        st = self.rng.choice([0, 0, 0, 1, 1, 2, 3, 4, 5, 6]) if style is None else style
        return E(ids.format_mobile(self.mobile_raw, st), "PHONE", self.ref)

    @cached_property
    def landline_raw(self) -> str:
        return ids.landline_number(self.rng, self.rng.choice([0, 0, 0, 1, 2, 3]))

    def landline(self) -> E:
        return E(self.landline_raw, "PHONE", self.ref)

    def phone(self) -> E:
        return self.mobile() if self.rng.random() < 0.75 else self.landline()

    @cached_property
    def email_raw(self) -> str:
        r = self.rng
        f, l = _slug(self.first), _slug(self.last.split("-")[0])
        pat = r.choice(["{f}.{l}", "{f}{l}", "{fi}{l}", "{f}_{l}", "{f}.{l}{n}", "{fi}.{l}{yy}", "{l}{f}",
                        "{f}{n}", "{f}.{l}", "{l}.{fi}", "{f}{l}{yy}", "{nick}{n}"])
        nick = _slug(NICKNAMES.get(self.first, self.first))
        local = pat.format(f=f, l=l, fi=f[:1], n=r.randint(1, 999), yy=f"{self.dob_date.year % 100:02d}", nick=nick)
        return f"{local}@{r.choice(EMAIL_DOMAINS)}"

    def email(self, *hard: str) -> E:
        return E(self.email_raw, "EMAIL", self.ref, ("name_in_email",) + hard)

    def work_email(self, domain: str) -> E:
        cache = self.__dict__.setdefault("_work_emails", {})
        if domain not in cache:
            f, l = _slug(self.first), _slug(self.last.split("-")[0])
            cache[domain] = self.rng.choice([f"{f}.{l}", f"{f[0]}.{l}", f"{f}{l[0]}", f"{f}", f"{f[0]}{l}"])
        return E(f"{cache[domain]}@{domain}", "EMAIL", self.ref, ("name_in_email",))

    @cached_property
    def passport_raw(self) -> str:
        return ids.passport_number(self.rng)

    def passport(self) -> E:
        return E(self.passport_raw, "ID_DOC", self.ref)

    @cached_property
    def licence_raw(self) -> str:
        return ids.driving_licence(self.rng, self.last, self.first, self.middle, self.dob_date, self.female)

    def licence(self, spaced: bool | None = None) -> E:
        sp = self.rng.random() < 0.3 if spaced is None else spaced
        return E(ids.format_licence(self.licence_raw, sp), "ID_DOC", self.ref)

    @cached_property
    def nhs_raw(self) -> str:
        return ids.nhs_number(self.rng)

    def nhs(self, spaced: bool | None = None) -> E:
        sp = self.rng.random() < 0.75 if spaced is None else spaced
        return E(ids.format_nhs(self.nhs_raw, sp), "ID_DOC", self.ref)


class Cast:
    """Hands out people for one document with unique refs (p1, p2, ...)."""

    def __init__(self, rng: random.Random, common_word_rate: float = 0.07):
        self.rng = rng
        self.people: list[Person] = []
        self.cw_rate = common_word_rate

    def new(self, **kw) -> Person:
        if "common_word" not in kw:
            kw["common_word"] = self.rng.random() < self.cw_rate
        taken = {(q.first, q.last) for q in self.people} | {q.last for q in self.people}
        for _ in range(12):  # no two people in one document share a surname (keeps mentions unambiguous)
            p = Person(self.rng, ref=f"p{len(self.people) + 1}", **kw)
            if (p.first, p.last) not in taken and p.last not in taken:
                break
        self.people.append(p)
        return p
