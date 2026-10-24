"""Model settings: the Mubit key and the VEIL_* settings, read from the environment, then backend/.env,
then the repo-root .env. Only the names asked for are read from those files, and the key itself is never
logged or returned to a client.
"""

import os
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path

from ..domain.pipeline import MAX_CHARS
from . import prompts

BACKEND_DIR = Path(__file__).resolve().parents[2]
# Where the key and the VEIL_* settings may live, in lookup order after the environment. Both gitignored.
KEY_FILES: tuple[tuple[str, Path], ...] = (
    ("backend/.env", BACKEND_DIR / ".env"),
    (".env", BACKEND_DIR.parent / ".env"),
)

EVALKIT, REWRITE = "evalkit", "rewrite"
T1_PROMPTS = (EVALKIT, REWRITE)
T1_CHUNK_CHARS = {EVALKIT: MAX_CHARS, REWRITE: 1400}
DEFAULT_EVALKIT_MODEL = "gpt-6-luna"
DEFAULT_T2_MODEL = "claude-haiku-4-5"


def _from_env_file(path: Path, name: str) -> str | None:
    """The value of one NAME=value line in a .env file (the last one wins), or None. Nothing else is read."""
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except (OSError, UnicodeDecodeError):
        return None
    value = None
    for line in lines:
        key, _, rest = line.strip().removeprefix("export ").partition("=")
        if key.strip() == name:
            value = rest.strip().strip("'\"")
    return value


def find_key(files: Sequence[tuple[str, Path]] = KEY_FILES) -> tuple[str | None, str | None]:
    """(key, where it came from): the first value starting with mbt_ in MUBIT_API_KEY, then each file.
    Callers must never log or return the key itself; the source ("env", "backend/.env", ".env") is safe."""
    value = os.environ.get("MUBIT_API_KEY", "").strip()
    if value.startswith("mbt_"):
        return value, "env"
    for source, path in files:
        value = (_from_env_file(path, "MUBIT_API_KEY") or "").strip()
        if value.startswith("mbt_"):
            return value, source
    return None, None


def setting(name: str, default: str, files: Sequence[tuple[str, Path]] = KEY_FILES) -> tuple[str, str]:
    """(value, source) of one setting: a non-empty environment variable wins, then each file, then the
    default ("default"). Only this name is read; nothing is loaded into os.environ."""
    value = os.environ.get(name, "").strip()
    if value:
        return value, "env"
    for source, path in files:
        value = (_from_env_file(path, name) or "").strip()
        if value:
            return value, source
    return default, "default"


@dataclass
class Settings:
    t1_prompt: str  # "evalkit" or "rewrite"
    t1_model: str  # the model the chosen prompt runs on
    evalkit_model: str  # VEIL_T1_MODEL, used by the evalkit prompt only
    t2_model: str
    sources: dict[str, str]  # setting name -> "env", "backend/.env", ".env" or "default"


def load_settings(files: Sequence[tuple[str, Path]] = KEY_FILES) -> Settings:
    prompt, prompt_source = setting("VEIL_T1_PROMPT", REWRITE, files)
    prompt = prompt.lower()
    if prompt not in T1_PROMPTS:
        raise ValueError(f"VEIL_T1_PROMPT (from {prompt_source}) must be one of {', '.join(T1_PROMPTS)}, "
                         f"not {prompt!r}")
    evalkit_model, model_source = setting("VEIL_T1_MODEL", DEFAULT_EVALKIT_MODEL, files)
    t2_model, t2_source = setting("VEIL_T2_MODEL", DEFAULT_T2_MODEL, files)
    # The rewrite prompt always runs on prompts.MODEL_ID: another model would be another Mubit task.
    return Settings(prompt, prompts.MODEL_ID if prompt == REWRITE else evalkit_model, evalkit_model, t2_model,
                    {"VEIL_T1_PROMPT": prompt_source, "VEIL_T1_MODEL": model_source, "VEIL_T2_MODEL": t2_source})


def describe(settings: Settings, key_source: str | None) -> str:
    """The startup log line: which prompt and model T1 uses and where they and the key came from."""
    src = settings.sources["VEIL_T1_PROMPT"]
    origin = "default" if src == "default" else f"VEIL_T1_PROMPT from {src}"
    prompt = f"prompt {settings.t1_prompt} ({origin})"
    if key_source is None:
        return f"T1 off: no Mubit key (mbt_...) in MUBIT_API_KEY, backend/.env or .env; regex layer only; {prompt}"
    return (f"T1 on: {prompt}, model {settings.t1_model}, {T1_CHUNK_CHARS[settings.t1_prompt]}-character chunks, "
            f"Mubit key from {key_source}")
