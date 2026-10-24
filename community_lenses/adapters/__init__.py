"""Wave 1B adapters (H1895): load real per-source data into the H1893 contract.

Each adapter module (``conferences``, ``nagari``, ``vk_ors``, ``indology_l``)
exposes a ``build_fixture() -> dict`` returning a fixture-shaped structure
(same keys as ``community_lenses/fixtures/*.json``) and a
``coverage_report(fixture) -> str`` rendering the per-source coverage report
required by H1895 step 6. BVP is H1896's territory and is not touched here.
"""

from __future__ import annotations
