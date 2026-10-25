"""Deprecated import path: the pipeline lives in app.redaction.pipeline.

Kept for scripts/readme_numbers.py, which also calls the two helpers that used to be private here
(_regex, now app.redaction.detectors.detect; _merge, now app.redaction.spans.merge). Remove once it
imports the new modules.
"""

from app.redaction.detectors import detect as _regex
from app.redaction.pipeline import PipelineResult, T1Result, rebuild, run_pipeline
from app.redaction.spans import merge as _merge

__all__ = ["PipelineResult", "T1Result", "_merge", "_regex", "rebuild", "run_pipeline"]
