"""Reporting: bill reconciliation, and Green Button export inspection.

Submodules are exposed **lazily** (PEP 562). ``report.inspect`` deliberately depends on
nothing but the Green Button parsers, so it can run in constrained environments — notably
the browser tool, which loads this package under Pyodide and should not have to ship
PyYAML and the whole tariff engine just to describe a usage file. Eagerly importing
``.reconcile`` here would have forced exactly that.
"""

from typing import TYPE_CHECKING

if TYPE_CHECKING:  # pragma: no cover - import-time typing only
    from .reconcile import (
        MissingCustomerFactError,
        ReconResult,
        Row,
        customer_facts,
        fixture_utility,
        format_comparison,
        interval_file_for,
        load_fixture,
        load_interval_series,
        parse_interval_file,
        reconcile,
        required_customer_facts,
    )

__all__ = [
    "MissingCustomerFactError",
    "ReconResult",
    "Row",
    "customer_facts",
    "fixture_utility",
    "format_comparison",
    "interval_file_for",
    "load_fixture",
    "load_interval_series",
    "parse_interval_file",
    "reconcile",
    "required_customer_facts",
]

_LAZY = dict.fromkeys(__all__, "reconcile")


def __getattr__(name: str):
    if name in _LAZY:
        from importlib import import_module

        return getattr(import_module(f".{_LAZY[name]}", __name__), name)
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


def __dir__() -> list[str]:
    return sorted(__all__)
