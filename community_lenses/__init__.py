"""Shared five-lens community data contract (Wave 1A, H1893).

This package defines the common schema, stable-ID rules, source-manifest
contract, and versioned codebook shells used to compare the Roerich/Zograf
conferences, nagari, ORS/VK, INDOLOGY-L, and BVP lenses. It intentionally
contains no adapters, no substantive crosswalk mappings, no identity merging,
and no quote selection: those are later waves (H1894, H1895, ...). See
docs/ARCHITECTURE_IndologyScholars_sanskrit-community-lenses.md for the full
data model this package implements a subset of.
"""

from .schema import SCHEMA_VERSION

__all__ = ["SCHEMA_VERSION"]
