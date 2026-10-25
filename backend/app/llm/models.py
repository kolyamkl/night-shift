"""The model calls the app runs with, built once from Settings.

Models is what the services see: the T1 maker and T2 (None when off), and the names the API reports
(/api/health, the scan stream's start event). Tests swap these attributes for fakes.
"""

from dataclasses import dataclass

from app.core.config import Settings
from app.llm import prompts
from app.llm.t1 import REWRITE, T1_CHUNK_CHARS, T1Factory, make_t1_factory
from app.llm.t2 import T2, make_t2


@dataclass
class Models:
    t1_factory: T1Factory | None
    t2: T2 | None
    t1_prompt: str  # "evalkit" or "rewrite"
    t1_model: str  # the model the chosen prompt runs on
    t2_model: str
    key_source: str | None  # where the Mubit key came from ("env", "backend/.env", ".env"); never the key

    @property
    def t1_on(self) -> bool:
        return self.t1_factory is not None

    @property
    def chunk_chars(self) -> int:
        """Chunk size for the chosen prompt, read at scan time."""
        return T1_CHUNK_CHARS[self.t1_prompt]


def t1_model(settings: Settings) -> str:
    """The rewrite prompt always runs on prompts.MODEL_ID: another model would be another Mubit task."""
    return prompts.MODEL_ID if settings.t1_prompt == REWRITE else settings.evalkit_model


def build_models(settings: Settings) -> Models:
    key = settings.mubit_key()
    return Models(
        t1_factory=make_t1_factory(key, settings.t1_prompt, settings.evalkit_model, base=settings.mubit_base),
        t2=make_t2(key, settings.t2_model, base=settings.mubit_base),
        t1_prompt=settings.t1_prompt,
        t1_model=t1_model(settings),
        t2_model=settings.t2_model,
        key_source=settings.key_source,
    )


def describe(settings: Settings, key_source: str | None) -> str:
    """The startup log line: which prompt and model T1 uses and where they and the key came from."""
    src = settings.sources.get("VEIL_T1_PROMPT", "default")
    origin = "default" if src == "default" else f"VEIL_T1_PROMPT from {src}"
    prompt = f"prompt {settings.t1_prompt} ({origin})"
    if key_source is None:
        return f"T1 off: no Mubit key (mbt_...) in MUBIT_API_KEY, backend/.env or .env; regex layer only; {prompt}"
    return (f"T1 on: {prompt}, model {t1_model(settings)}, {T1_CHUNK_CHARS[settings.t1_prompt]}-character chunks, "
            f"Mubit key from {key_source}")
