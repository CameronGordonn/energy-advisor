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


def _read_raw(path: Path) -> dict:
    raw = yaml.safe_load(path.read_text())
    if not isinstance(raw, dict):
        raise ValueError(f"{path.name}: spec must be a YAML mapping")
    return raw


def _validate(path: Path, raw: dict) -> TariffSpec:
    unverified = _find_unverified(raw)
    if unverified:
        raise UnverifiedSpecError(
            f"{path.name}: {len(unverified)} UNVERIFIED field(s) must be filled from the "
            f"tariff sheet before this spec can bill: {', '.join(sorted(unverified))}"
        )
    return TariffSpec.model_validate(raw)


def load_spec_file(path: str | Path) -> TariffSpec:
    path = Path(path)
    return _validate(path, _read_raw(path))


def _matching_specs(schedule_id: str, layer: Layer, specs_dir: Path) -> list[TariffSpec]:
    """Every version of one schedule/layer in ``specs_dir``.

    Files are filtered on the *raw* ``schedule_id``/``layer`` keys BEFORE the UNVERIFIED
    gate runs, so a half-finished spec for some other schedule cannot block the schedules
    that are complete. The gate still fires — but only for the schedule actually asked
    for, which is the schedule whose numbers are about to reach a dollar figure.
    """
    out: list[TariffSpec] = []
    for p in sorted(specs_dir.glob("*.yaml")):
        raw = _read_raw(p)
        if raw.get("schedule_id") == schedule_id and raw.get("layer") == layer.value:
            out.append(_validate(p, raw))
    return out


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
    candidates = _matching_specs(schedule_id, layer, Path(specs_dir))
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
    versions = _matching_specs(schedule_id, layer, Path(specs_dir))
    if not versions:
        raise ValueError(f"no {layer} spec found for schedule {schedule_id!r}")
    return sorted(versions, key=lambda s: s.effective_date)
