"""Reporting: bill reconciliation, and Green Button export inspection.

Submodules are exposed **lazily** (PEP 562). ``report.inspect`` deliberately depends on
nothing but the Green Button parsers, so it can run in constrained environments — notably
the browser tool, which loads this package under Pyodide and should not have to ship
PyYAML and the whole tariff engine just to describe a usage file. Eagerly importing
``.reconcile`` here would have forced exactly that.
"""

from typing import TYPE_CHECKING

if TYPE_CHECKING:  # pragma: no cover - import-time typing only
    from .reconcile import ReconResult, Row, format_comparison, load_fixture, reconcile

__all__ = ["ReconResult", "Row", "format_comparison", "load_fixture", "reconcile"]

_LAZY = {
    "ReconResult": "reconcile",
    "Row": "reconcile",
    "format_comparison": "reconcile",
    "load_fixture": "reconcile",
    "reconcile": "reconcile",
}


def __getattr__(name: str):
    if name in _LAZY:
        from importlib import import_module

        return getattr(import_module(f".{_LAZY[name]}", __name__), name)
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


def __dir__() -> list[str]:
    return sorted(__all__)
