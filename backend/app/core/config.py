"""Settings: one pydantic-settings class, read once at startup.

Each setting comes from the first place that has a usable value: the environment, then backend/.env,
then the repo-root .env (both gitignored). Empty values are skipped, and MUBIT_API_KEY counts only if
it is a Mubit key (mbt_...), so a provider key in the environment falls through to the files. Only
the names below are read from those files and nothing is loaded into os.environ. Settings.sources
records where each value came from ("env", "backend/.env", ".env"); that, never a secret value, is
what the app may report.
"""

import os
from collections.abc import Callable, Iterator, Mapping, Sequence
from pathlib import Path
from typing import Annotated, Any, Literal

from pydantic import Field, SecretStr, field_validator, model_validator
from pydantic_settings import BaseSettings, NoDecode, PydanticBaseSettingsSource, SettingsConfigDict

BACKEND_DIR = Path(__file__).resolve().parents[2]
REPO_DIR = BACKEND_DIR.parent

EnvFile = tuple[str, Path]  # (label for reports, path)
# Where settings may live, in lookup order after the environment.
ENV_FILES: tuple[EnvFile, ...] = (("backend/.env", BACKEND_DIR / ".env"), (".env", REPO_DIR / ".env"))

T1Prompt = Literal["evalkit", "rewrite"]  # the two T1 designs, see app/llm/t1.py
T1_PROMPTS: tuple[str, ...] = ("evalkit", "rewrite")

# A value that is set but not usable is skipped, as if it were empty.
ACCEPT: Mapping[str, Callable[[str], bool]] = {"MUBIT_API_KEY": lambda value: value.startswith("mbt_")}


def read_env_file(path: Path, name: str) -> str | None:
    """The value of one NAME=value line in a .env file (the last one wins), or None. Nothing else is kept."""
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


class LayeredEnvSource(PydanticBaseSettingsSource):
    """Each field from the environment, then each env file in order; records where each value came from."""

    def __init__(self, settings_cls: type[BaseSettings], files: Sequence[EnvFile]) -> None:
        super().__init__(settings_cls)
        self.files = files

    def _places(self, name: str) -> Iterator[tuple[str, str | None]]:
        yield "env", os.environ.get(name)
        for label, path in self.files:  # read lazily: a file is opened only if no earlier place had it
            yield label, read_env_file(path, name)

    def lookup(self, name: str) -> tuple[str, str] | None:
        """(value, source) of one setting, or None when no place has a usable value."""
        accept = ACCEPT.get(name, bool)
        for source, raw in self._places(name):
            value = (raw or "").strip()
            if value and accept(value):
                return value, source
        return None

    def get_field_value(self, field: Any, field_name: str) -> tuple[Any, str, bool]:
        found = self.lookup(field.validation_alias or field_name)
        return (found[0] if found else None), field_name, False

    def __call__(self) -> dict[str, Any]:
        values: dict[str, Any] = {}
        sources: dict[str, str] = {}
        for name, field in self.settings_cls.model_fields.items():
            alias = field.validation_alias
            if not isinstance(alias, str):
                continue
            found = self.lookup(alias)
            if found:
                values[name], sources[alias] = found
        return {**values, "sources": sources}


class Settings(BaseSettings):
    model_config = SettingsConfigDict(extra="ignore", populate_by_name=True)

    # Storage. See docs/DATABASE.md.
    database_url: str = Field("", validation_alias="DATABASE_URL")
    storage_key: SecretStr = Field(SecretStr(""), validation_alias="VEIL_STORAGE_KEY", repr=False)

    # Models. Without a Mubit key both model calls are off and the app runs on the regex layer only.
    mubit_api_key: SecretStr | None = Field(None, validation_alias="MUBIT_API_KEY", repr=False)
    # Used by the evalkit prompt and T2; the rewrite prompt always calls api.mubit.ai, like send_batch.py.
    mubit_base: str = Field("https://api.mubit.ai", validation_alias="MUBIT_BASE")
    t1_prompt: T1Prompt = Field("rewrite", validation_alias="VEIL_T1_PROMPT")
    evalkit_model: str = Field("gpt-6-luna", validation_alias="VEIL_T1_MODEL")  # the evalkit prompt only
    t2_model: str = Field("claude-haiku-4-5", validation_alias="VEIL_T2_MODEL")

    # HTTP.
    cors_origins: Annotated[list[str], NoDecode] = Field(
        ["http://localhost:5173", "http://127.0.0.1:5173"], validation_alias="VEIL_CORS"
    )
    cookie_secure: bool = Field(False, validation_alias="VEIL_COOKIE_SECURE")  # True when served over HTTPS
    samples_dir: Path = Field(REPO_DIR / "data" / "synthetic" / "pdfs", validation_alias="VEIL_SAMPLES_DIR")

    # Where each value came from: setting name -> "env", "backend/.env" or ".env". Absent means default.
    sources: dict[str, str] = Field(default_factory=dict, exclude=True)

    @classmethod
    def settings_customise_sources(
        cls,
        settings_cls: type[BaseSettings],
        init_settings: PydanticBaseSettingsSource,
        env_settings: PydanticBaseSettingsSource,
        dotenv_settings: PydanticBaseSettingsSource,
        file_secret_settings: PydanticBaseSettingsSource,
    ) -> tuple[PydanticBaseSettingsSource, ...]:
        # Values passed in (Settings.load, tests) win; everything else comes from the layered lookup.
        return init_settings, LayeredEnvSource(settings_cls, ENV_FILES)

    @classmethod
    def load(cls, files: Sequence[EnvFile] = ENV_FILES) -> "Settings":
        """Settings from the environment and the given env files only (tests pass temporary files)."""
        return cls.model_validate(LayeredEnvSource(cls, files)())

    @model_validator(mode="before")
    @classmethod
    def _name_a_bad_prompt(cls, data: Any) -> Any:
        if isinstance(data, dict):
            prompt = str(data.get("t1_prompt") or data.get("VEIL_T1_PROMPT") or "rewrite").lower()
            if prompt not in T1_PROMPTS:
                source = data.get("sources", {}).get("VEIL_T1_PROMPT", "default")
                raise ValueError(f"VEIL_T1_PROMPT (from {source}) must be one of {', '.join(T1_PROMPTS)}, "
                                 f"not {prompt!r}")
        return data

    @field_validator("t1_prompt", mode="before")
    @classmethod
    def _lower(cls, value: Any) -> Any:
        return value.lower() if isinstance(value, str) else value

    @field_validator("cors_origins", mode="before")
    @classmethod
    def _split_origins(cls, value: Any) -> Any:
        return value.split(",") if isinstance(value, str) else value

    @property
    def key_source(self) -> str | None:
        """Where the Mubit key came from, or None without one. Safe to log; the key itself never is."""
        return self.sources.get("MUBIT_API_KEY")

    def mubit_key(self) -> str | None:
        return self.mubit_api_key.get_secret_value() if self.mubit_api_key else None
