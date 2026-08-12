"""AUTOMATION-DIGITAL-TWIN — vendor-neutral automation graph, simulator and policy engine.

Read-only with respect to every external system. No module here may import or
invoke a write-capable external client. See policy.py::assert_no_production_adapter.
"""
__all__ = ["model", "adapters", "policy", "simulator", "cli"]
