"""Command line interface for keylimits."""

from __future__ import annotations

import argparse
import sys
from typing import List, Optional

from . import __version__
from .checker import check_env, check_key, check_many, resolve_provider
from .formatting import configure_console
from .models import KeyLimits
from .report import render
from . import providers


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="keylimits",
        description="Check the rate limits and validity of an API key.",
    )
    parser.add_argument("key", nargs="?", help="the API key to inspect (omit to read stdin/--env)")
    parser.add_argument(
        "-p",
        "--provider",
        default="auto",
        help="provider to use: auto, openai, anthropic, groq, gemini, tokenharbor, generic (default: auto)",
    )
    parser.add_argument("--env", action="store_true", help="read the key from the environment")
    parser.add_argument("--file", metavar="PATH", help="read one or more keys from a file (one per line)")
    parser.add_argument("--json", action="store_true", help="emit machine readable JSON")
    parser.add_argument("--base-url", help="override the provider API base URL")
    parser.add_argument("--timeout", type=float, default=30.0, help="request timeout in seconds")
    parser.add_argument("--workers", type=int, default=5, help="concurrency when checking many keys")
    parser.add_argument("--api-version", help="Anthropic API version header (default 2023-06-01)")
    parser.add_argument(
        "--model",
        help="model used for the allowance probe (tokenharbor; default a free model)",
    )
    parser.add_argument("--list-providers", action="store_true", help="list supported providers and exit")
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")

    generic = parser.add_argument_group("generic provider options")
    generic.add_argument("--url", help="full URL to request (generic provider)")
    generic.add_argument("--auth-header", help="header that carries the key (default Authorization)")
    generic.add_argument("--auth-scheme", help="prefix before the key, e.g. 'Bearer' (use '' for none)")
    generic.add_argument("--method", default=None, help="HTTP method for the generic provider (default GET)")
    return parser


def _read_file(path: str) -> List[str]:
    keys: List[str] = []
    with open(path, "r", encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            keys.append(line)
    return keys


def _gather_keys(args) -> List[str]:
    if args.file:
        return _read_file(args.file)
    if args.env:
        return []
    if args.key:
        return [part.strip() for part in args.key.split(",") if part.strip()]
    if not sys.stdin.isatty():
        data = sys.stdin.read().strip()
        if data:
            return [line.strip() for line in data.splitlines() if line.strip()]
    return []


def main(argv: Optional[List[str]] = None) -> int:
    configure_console()
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.list_providers:
        for provider in providers.all_providers():
            env = ", ".join(provider.env_vars) or "-"
            print(f"{provider.name:<10} {provider.label:<24} env: {env}")
        return 0

    try:
        resolve_provider(args.provider)
    except ValueError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2

    kwargs = dict(
        base_url=args.base_url,
        timeout=args.timeout,
        api_version=args.api_version,
        url=args.url,
        auth_header=args.auth_header,
        auth_scheme=args.auth_scheme,
        method=args.method,
        model=args.model,
    )

    try:
        if args.env:
            results = check_env(args.provider, **kwargs)
        else:
            keys = _gather_keys(args)
            if not keys:
                parser.error("no API key provided (pass one, use --env, --file, or pipe via stdin)")
            if len(keys) == 1:
                results = [check_key(keys[0], args.provider, **kwargs)]
            else:
                results = check_many(keys, args.provider, workers=args.workers, **kwargs)
    except ValueError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    except FileNotFoundError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2

    render(results, as_json=args.json)
    return _exit_code(results)


def _exit_code(results: List[KeyLimits]) -> int:
    if any(result.valid is False for result in results):
        return 1
    if any(result.valid is None for result in results):
        return 3
    return 0


if __name__ == "__main__":
    raise SystemExit(main())