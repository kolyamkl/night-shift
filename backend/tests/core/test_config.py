"""Settings come from the environment, then backend/.env, then the root .env, one name at a time."""

import os

import pytest

from app.core.config import Settings
from app.llm import prompts
from app.llm.models import describe, t1_model
from app.llm.t1 import EVALKIT, REWRITE, T1_CHUNK_CHARS, make_t1_factory
from app.llm.t2 import make_t2


def find_key(files):
    """(key, where it came from), as the app sees them."""
    settings = Settings.load(files)
    return settings.mubit_key(), settings.key_source


def load_settings(files):
    return Settings.load(files)


@pytest.fixture
def key_files(tmp_path, monkeypatch):
    """backend/.env and the root .env in a temp tree, with no MUBIT_API_KEY in the environment."""
    monkeypatch.delenv("MUBIT_API_KEY", raising=False)
    (tmp_path / "backend").mkdir()
    return (("backend/.env", tmp_path / "backend" / ".env"), (".env", tmp_path / ".env"))


def test_key_lookup_order_is_env_then_backend_env_then_root_env(key_files, monkeypatch):
    backend_env, root_env = key_files[0][1], key_files[1][1]
    root_env.write_text("# root\nOTHER=1\nMUBIT_API_KEY=mbt_root\n")
    assert find_key(key_files) == ("mbt_root", ".env")
    backend_env.write_text("export MUBIT_API_KEY='mbt_backend'\n")
    assert find_key(key_files) == ("mbt_backend", "backend/.env")
    monkeypatch.setenv("MUBIT_API_KEY", "mbt_env")
    assert find_key(key_files) == ("mbt_env", "env")


def test_only_mubit_keys_count(key_files, monkeypatch):
    monkeypatch.setenv("MUBIT_API_KEY", "sk-ant-not-a-mubit-key")
    key_files[0][1].write_text("MUBIT_API_KEY=\n")
    key_files[1][1].write_text('MUBIT_API_KEY="mbt_root"\n')
    assert find_key(key_files) == ("mbt_root", ".env")


def test_no_key_anywhere_means_off(key_files):
    assert find_key(key_files) == (None, None)
    assert make_t1_factory(None) is None and make_t2(None) is None


@pytest.fixture
def no_veil_env(monkeypatch):
    for name in ("VEIL_T1_PROMPT", "VEIL_T1_MODEL", "VEIL_T2_MODEL"):
        monkeypatch.delenv(name, raising=False)


def test_settings_come_from_the_same_files_as_the_key_in_the_same_order(key_files, no_veil_env, monkeypatch):
    backend_env, root_env = key_files[0][1], key_files[1][1]
    assert load_settings(key_files).t1_prompt == "rewrite"  # the default
    root_env.write_text("MUBIT_API_KEY=mbt_root\nVEIL_T1_PROMPT=rewrite\nVEIL_T2_MODEL=claude-sonnet-x\n")
    got = load_settings(key_files)
    assert (got.t1_prompt, t1_model(got), got.t2_model) == ("rewrite", "claude-haiku-4-5", "claude-sonnet-x")
    assert {name: got.sources.get(name, "default") for name in ("VEIL_T1_PROMPT", "VEIL_T1_MODEL", "VEIL_T2_MODEL")} == {
        "VEIL_T1_PROMPT": ".env", "VEIL_T1_MODEL": "default", "VEIL_T2_MODEL": ".env"}
    backend_env.write_text("VEIL_T1_PROMPT=evalkit\nVEIL_T1_MODEL=gpt-other\n")
    got = load_settings(key_files)
    assert (got.t1_prompt, t1_model(got), got.sources["VEIL_T1_PROMPT"]) == ("evalkit", "gpt-other", "backend/.env")
    monkeypatch.setenv("VEIL_T1_PROMPT", "Rewrite")  # a real environment variable wins
    got = load_settings(key_files)
    assert (got.t1_prompt, got.sources["VEIL_T1_PROMPT"]) == ("rewrite", "env")


def test_only_the_named_settings_are_read_and_nothing_goes_into_the_environment(key_files, no_veil_env, monkeypatch):
    monkeypatch.delenv("SOME_OTHER_SECRET", raising=False)
    key_files[1][1].write_text("SOME_OTHER_SECRET=1\nMUBIT_API_KEY=mbt_root\nVEIL_T1_PROMPT=rewrite\n")
    load_settings(key_files)
    find_key(key_files)
    assert "SOME_OTHER_SECRET" not in os.environ and "VEIL_T1_PROMPT" not in os.environ
    assert "MUBIT_API_KEY" not in os.environ


def test_a_bad_prompt_setting_names_where_it_came_from(key_files, no_veil_env):
    key_files[1][1].write_text("VEIL_T1_PROMPT=list\n")
    with pytest.raises(ValueError, match=r"VEIL_T1_PROMPT \(from \.env\) must be one of evalkit, rewrite"):
        load_settings(key_files)


def test_the_startup_line_names_the_prompt_and_its_source(key_files, no_veil_env):
    key_files[1][1].write_text("VEIL_T1_PROMPT=rewrite\n")
    settings = load_settings(key_files)
    assert describe(settings, ".env") == (
        "T1 on: prompt rewrite (VEIL_T1_PROMPT from .env), model claude-haiku-4-5, 1400-character chunks, "
        "Mubit key from .env")
    key_files[1][1].write_text("")
    assert describe(load_settings(key_files), None).endswith("regex layer only; prompt rewrite (default)")


def test_each_prompt_has_its_own_model_and_chunk_size(key_files, no_veil_env, monkeypatch):
    monkeypatch.setenv("VEIL_T1_MODEL", "gpt-other")
    monkeypatch.setenv("VEIL_T1_PROMPT", "rewrite")
    assert t1_model(load_settings(key_files)) == prompts.MODEL_ID == "claude-haiku-4-5"
    monkeypatch.setenv("VEIL_T1_PROMPT", "evalkit")
    assert t1_model(load_settings(key_files)) == "gpt-other"
    assert T1_CHUNK_CHARS == {EVALKIT: 4000, REWRITE: 1400}
