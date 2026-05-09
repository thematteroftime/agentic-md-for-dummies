"""Time-integrator package: one file per scheme.

Structure:
- `base.py`           — `IntegratorBase` abstract parent + interface contract
- `<scheme>.py`       — concrete integrator (BAOAB-drag, Verlet, etc.)
- `__init__.py`       — local INTEGRATOR_REGISTRY mapping the `integrator`
                        config string to the concrete class

External code SHOULD prefer one of:
  - `from integrators import BAOABDrag`             (direct, by class name)
  - `from integrators import INTEGRATOR_REGISTRY`   (config-driven dispatch)
  - `tools.registry.resolve("BAOABDrag")`           (single forwarding station)

When adding a new integrator:
  1. Write `integrators/<your_integrator>.py` with class subclassing `IntegratorBase`
  2. Export it here (line in `from ... import` block AND in INTEGRATOR_REGISTRY)
  3. Mirror the registration in `tools/registry.py:_REGISTRY` for the
     forwarding-station view
  4. Add the matching `integrator` enum value in
     `.claude/skills/paper-to-experiment/templates/plan_config.schema.json`
  5. Document in `.claude/skills/paper-to-experiment/references/force_types.md`
     "Integrator selection" section

See SKILL §"Adding a new integrator" for the full 9-step extension flow.
"""
from integrators.base import IntegratorBase, integratorBase
from integrators.baoab_drag import BAOABDrag
from integrators.baoab_langevin import BAOABLangevin


# Maps the `integrator` string used in configs/plan_*.json to the class.
# Adapter scripts may resolve via INTEGRATOR_REGISTRY[exp.get("integrator",
# "baoab_drag")] when they want config-driven dispatch instead of direct
# class import.
INTEGRATOR_REGISTRY: dict[str, type] = {
    "baoab_drag":     BAOABDrag,
    "baoab_langevin": BAOABLangevin,
}


# Default integrator name when an experiment dict omits the `integrator` field.
# Preserves PRX/ER/KA-LJ legacy behavior — they were all calibrated against
# BAOABDrag. New papers should set `integrator` explicitly in their config.
DEFAULT_INTEGRATOR: str = "baoab_drag"


__all__ = [
    "IntegratorBase",
    "integratorBase",      # back-compat lowercase alias
    "BAOABDrag",
    "BAOABLangevin",
    "INTEGRATOR_REGISTRY",
    "DEFAULT_INTEGRATOR",
]
