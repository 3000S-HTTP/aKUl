"""High-level entry points used by the CLI and by other programs."""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from typing import Dict, Iterable, List, Optional, Type

from . import providers  # noqa: F401  (ensures providers are registered)
from .models import KeyLimits
from .providers.base import Provider, get_provider


def resolve_provider(name: str) -> Type[Provider]:
    provider = get_provider(name)
    if provider is None:
        available = ", ".join(p.name for p in providers.all_providers())
        raise ValueError(f"Unknown provider '{name}'. Available: {available}")
    return provider


def check_key(
    key: str,
    provider: str = "auto",
    *,
    base_url: Optional[str] = None,
    timeout: float = 30.0,
    api_version: Optional[str] = None,
    url: Optional[str] = None,
    auth_header: Optional[str] = None,
    auth_scheme: Optional[str] = None,
    method: Optional[str] = None,
    model: Optional[str] = None,
) -> KeyLimits:
    """Probe a single key and return its :class:`KeyLimits`."""
    cls = resolve_provider(provider)

    if provider == "generic":
        return cls(
            key,
            base_url,
            timeout,
            url=url,
            auth_header=auth_header,
            auth_scheme=auth_scheme,
            method=method,
        ).check()

    if provider == "tokenharbor":
        return cls(key, base_url, timeout, model=model).check()

    if provider == "auto":
        return cls(key, base_url, timeout, model=model).check()

    instance = cls(key, base_url=base_url, timeout=timeout)
    if api_version and hasattr(instance, "api_version"):
        instance.api_version = api_version
    return instance.check()


def check_many(
    keys: Iterable[str],
    provider: str = "auto",
    *,
    workers: int = 5,
    **kwargs,
) -> List[KeyLimits]:
    """Probe several keys concurrently, preserving input order."""
    keys = list(keys)
    if not keys:
        return []
    workers = max(1, min(workers, len(keys)))
    with ThreadPoolExecutor(max_workers=workers) as pool:
        return list(pool.map(lambda k: check_key(k, provider, **kwargs), keys))


def check_env(provider: str = "auto", **kwargs) -> List[KeyLimits]:
    """Probe every key found in the environment for the chosen provider(s)."""
    import os

    cls = resolve_provider(provider)
    names = cls.env_vars
    if provider == "auto":
        seen: Dict[str, str] = {}
        for name in names:
            value = os.environ.get(name)
            if value and name not in seen:
                seen[name] = value
        return [check_key(value, provider, **kwargs) for value in seen.values()]

    for name in names:
        value = os.environ.get(name)
        if value:
            return [check_key(value, provider, **kwargs)]
    raise ValueError(f"No key found in environment ({', '.join(names)})")