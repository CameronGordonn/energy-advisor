"""Load tariff specs from YAML, enforcing the never-fabricate invariants.

A spec file is rejected at load time if any value is left as the literal
``UNVERIFIED`` (CLAUDE.md: mark unknowns, raise rather than guess) or if the
mandatory ``citation`` is missing. Effective-dated selection lets a schedule change
mid-year (e.g. PG&E's March-2026 Base Services Charge) without a code change.
"""

from __future__ import annotations

from datetime import date
from pathlib import Path

import yaml

from .schema import UNVERIFIED, Layer, TariffSpec

SPECS_DIR = Path(__file__).parent / "specs"


class UnverifiedSpecError(ValueError):
    """A spec still contains an UNVERIFIED placeholder — fill it from the tariff sheet."""


def _find_unverified(node: object, path: str = "") -> list[str]:
    """Return dotted paths of every value equal to the UNVERIFIED sentinel."""
    hits: list[str] = []
    if isinstance(node, dict):
        for k, v in node.items():
            hits += _find_unverified(v, f"{path}.{k}" if path else str(k))
    elif isinstance(node, list):
        for i, v in enumerate(node):
            hits += _find_unverified(v, f"{path}[{i}]")
    elif isinstance(node, str) and node.strip().upper() == UNVERIFIED:
        hits.append(path or "<root>")
    return hits


def load_spec_file(path: str | Path) -> TariffSpec:
    path = Path(path)
    raw = yaml.safe_load(path.read_text())
    if not isinstance(raw, dict):
        raise ValueError(f"{path.name}: spec must be a YAML mapping")

    unverified = _find_unverified(raw)
    if unverified:
        raise UnverifiedSpecError(
            f"{path.name}: {len(unverified)} UNVERIFIED field(s) must be filled from the "
            f"tariff sheet before this spec can bill: {', '.join(sorted(unverified))}"
        )
    return TariffSpec.model_validate(raw)


def load_specs(
    schedule_id: str,
    layer: Layer,
    *,
    on: date,
    specs_dir: str | Path = SPECS_DIR,
) -> TariffSpec:
    """Return the spec for ``schedule_id``/``layer`` effective on date ``on``.

    Picks the newest spec whose ``effective_date`` is on or before ``on``.
    """
    specs_dir = Path(specs_dir)
    candidates: list[TariffSpec] = []
    for p in sorted(specs_dir.glob("*.yaml")):
        spec = load_spec_file(p)
        if spec.schedule_id == schedule_id and spec.layer is layer:
            candidates.append(spec)
    effective = [s for s in candidates if s.effective_date <= on]
    if not effective:
        raise ValueError(
            f"no {layer} spec for {schedule_id!r} effective on {on} "
            f"(found {len(candidates)} version(s) for this schedule)"
        )
    return max(effective, key=lambda s: s.effective_date)


def load_spec_versions(
    schedule_id: str,
    layer: Layer,
    *,
    specs_dir: str | Path = SPECS_DIR,
) -> list[TariffSpec]:
    """Return every version of ``schedule_id``/``layer``, sorted by effective_date.

    A billing period can straddle a rate change, so the billing function needs all
    versions (not just the one effective on the period start) to split the period at
    each effective date. Raises if none are found.
    """
    specs_dir = Path(specs_dir)
    versions = [
        spec
        for p in sorted(specs_dir.glob("*.yaml"))
        if (spec := load_spec_file(p)).schedule_id == schedule_id and spec.layer is layer
    ]
    if not versions:
        raise ValueError(f"no {layer} spec found for schedule {schedule_id!r}")
    return sorted(versions, key=lambda s: s.effective_date)
