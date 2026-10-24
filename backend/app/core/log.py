"""The app's logger. Lines name documents by id and errors by type only, never document text."""

import logging

log = logging.getLogger("veil")
if not log.handlers:
    _handler = logging.StreamHandler()
    _handler.setFormatter(logging.Formatter("%(levelname)s:     %(name)s %(message)s"))
    log.addHandler(_handler)
    log.setLevel(logging.INFO)
