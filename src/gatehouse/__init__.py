"""Gatehouse: autonomous fraud-defense agent for households.

Package layout (doc 11 P1 scope):
    constants       shared literals
    config          typed environment settings
    logging_utils   structured JSON logging with mandatory P1 scrubbing
    packs           country-pack schemas, loader, validation
    rules           deterministic rule classifier (offline brain)
    evaluation      seeded case generator + metrics (Wilson CIs)
"""

__all__ = ["config", "constants", "evaluation", "logging_utils", "packs", "rules"]
__version__ = "0.1.0"
