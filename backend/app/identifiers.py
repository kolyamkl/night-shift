"""IP addresses and UUIDs for the regex layer.

An IP address in a contract or a log ("Logged IP Address: 64.137.54.89") points to a person's device,
so UK GDPR counts it as personal data, and T1's prompt does not name it. E-signature services stamp
each signature with a UUID ("Signature Reference: 1BA790A7-C543-4DED-8A6B-1782F7D6FDE0") that leads
back to the signer's record. Both have a fixed shape, so a regex finds them better than a model.

Four-part clause numbers ("4.2.1.3") look like IPv4 addresses, so an IPv4 address needs "IP" just
before it or at least two parts of two or more digits.
"""

import ipaddress
import re

from evalkit.spans import Span

_OCTET = r"(?:25[0-5]|2[0-4]\d|1\d\d|[1-9]?\d)"
IPV4 = re.compile(rf"(?<![\w.]){_OCTET}(?:\.{_OCTET}){{3}}(?![\w]|\.\d)")
IPV6 = re.compile(r"(?<![\w:.])[0-9A-Fa-f]{0,4}(?::[0-9A-Fa-f]{0,4}){2,7}(?![\w:])")
IP_LABEL = re.compile(r"(?i)\bip(?:v[46])?\b[^\n]{0,20}$")
VERSION = re.compile(r"(?i)\b(?:v|version|ver\.?)\s*$")
UUID = re.compile(r"(?<![\w-])[0-9A-Fa-f]{8}-[0-9A-Fa-f]{4}-[0-9A-Fa-f]{4}-[0-9A-Fa-f]{4}-[0-9A-Fa-f]{12}(?![\w-])")


def _ipv4_ok(text: str, m: re.Match) -> bool:
    before = text[max(0, m.start() - 30):m.start()]
    if VERSION.search(before):
        return False
    return bool(IP_LABEL.search(before)) or sum(len(p) >= 2 for p in m.group().split(".")) >= 2


def _ipv6_ok(value: str) -> bool:
    if value.count(":") < 3:  # "17:06:16" is a time
        return False
    try:
        ipaddress.IPv6Address(value)
    except ValueError:
        return False
    return True


def detect(text: str) -> list[Span]:
    found: list[Span] = []
    for m in IPV4.finditer(text):
        if _ipv4_ok(text, m):
            found.append(Span(m.start(), m.end(), "IP_ADDRESS", m.group()))
    for m in IPV6.finditer(text):
        if _ipv6_ok(m.group()):
            found.append(Span(m.start(), m.end(), "IP_ADDRESS", m.group()))
    for m in UUID.finditer(text):
        found.append(Span(m.start(), m.end(), "CUSTOM", m.group()))
    return found
