"""Base class + interface contract for time integrators.

Every integrator in `integrators/` subclasses `IntegratorBase` and provides
two methods:

- `__init__(self, timeStep: float, **kwargs)` — paper/scheme-specific setup.
  Required & optional kwargs are integrator-specific; declare them in the
  subclass's `REQUIRED_KWARGS` and `OPTIONAL_KWARGS` class tuples so the
  adapter / validator can check campaign config completeness up-front.
- `inteBegin(self)` — single-timestep advance. Must obey the simulator's
  contract: read `atomSystem.pos / vel / force / mass`, write back `pos / vel`,
  call `forceField.updateAllF()` once per step (where appropriate),
  call `atomSystem.reduce_pe()` after force update, and (for ndim=2) call
  `atomSystem.zeroZ()` at the end.

The simulator (Layer 1, frozen) calls `inteBegin()` exactly once per step.
The integrator owns the BAOAB / Verlet / etc. step ordering.

# Adding a new integrator

Follow the **9-step extension flow** in `references/force_types.md` "Adding
a new integrator" — analogous to the 8-step force extension. Files touched:

1. `integrators/<your_integrator>.py` — class subclassing IntegratorBase
2. `tests/test_<your_integrator>_*cases.py` — unit tests
3. `integrators/__init__.py:INTEGRATOR_REGISTRY` — register the name
4. `tools/registry.py:_REGISTRY` — mirror in the forwarding station
5. `templates/plan_config.schema.json` — add to `integrator` enum
6. `references/force_types.md` — document scheme + required kwargs
7. (optional) per-paper adapter passes the new class to `systemRun`
8. Regression test: add the new integrator name to the assertion in
   `tests/test_skill_regression.py:test_registry_local_init_sync`-style
   coverage so registration drift is caught
"""
from constSet import *


@ti.data_oriented
class IntegratorBase:
    """Abstract integrator interface. Subclasses declare what kwargs they need."""

    # Subclasses override these to enable adapter-side kwarg-completeness
    # checking. Empty tuples mean "no required kwargs beyond timeStep".
    REQUIRED_KWARGS: tuple = ()
    OPTIONAL_KWARGS: tuple = ()

    # Short human-readable scheme description for logging / preflight.
    SCHEME_NAME: str = "abstract"

    def register(self, atomSystem, forceField):
        """Bind the integrator to its physics neighbours. Called by
        `systemRun.runWithData` after `forceField.register`."""
        self.atomSystem = atomSystem
        self.forceField = forceField
        return

    def inteBegin(self):
        """Advance one step. Subclasses MUST override."""
        raise NotImplementedError(
            f"{type(self).__name__}.inteBegin() not implemented — "
            f"subclasses must define the per-step advance kernel sequence."
        )


# Backward-compat alias: keep `integratorBase` (lowercase) callable as a name
# while older code is migrated. New code MUST import `IntegratorBase`.
integratorBase = IntegratorBase
