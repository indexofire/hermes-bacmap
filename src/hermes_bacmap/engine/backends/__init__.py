from __future__ import annotations

from collections.abc import Callable
from importlib import import_module
from typing import Any

from ..registry import Registry

_REG = Registry()

_BUILTINS = {
    "blastn": ("hermes_bacmap.engine.backends.blast", "BlastBackend"),
    "blastp": ("hermes_bacmap.engine.backends.blast", "BlastBackend"),
    "blastx": ("hermes_bacmap.engine.backends.blast", "BlastBackend"),
    "tblastn": ("hermes_bacmap.engine.backends.blast", "BlastBackend"),
    "minimap2": ("hermes_bacmap.engine.backends.minimap2", "MinimapBackend"),
    "mash": ("hermes_bacmap.engine.backends.kmer", "MashBackend"),
    "sourmash": ("hermes_bacmap.engine.backends.kmer", "SourmashBackend"),
}


def register(name: str, backend_class: Callable) -> None:
    _REG.register(name, backend_class)


def _ensure(name: str) -> None:
    key = (name or "").strip().lower()
    if not key or _REG.has(key):
        return
    if key in _BUILTINS:
        mod_path, attr = _BUILTINS[key]
        mod = import_module(mod_path)
        cls = getattr(mod, attr)
        register(key, cls)


def get_backend(name: str, **kwargs: Any):
    _ensure(name)
    cls = _REG.get(name)
    if name in ("blastp", "blastx", "tblastn") and "tool" not in kwargs:
        kwargs["tool"] = name
    return cls(**kwargs)


def available() -> list[str]:
    return sorted(_BUILTINS.keys())
