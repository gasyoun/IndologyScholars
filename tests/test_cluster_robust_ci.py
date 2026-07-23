"""Tests for cluster-robust proportion intervals (H1473)."""

import math

from publication_helpers import cluster_robust_proportion_interval, wilson_interval


def test_empty_and_single_cluster_fallbacks():
    assert cluster_robust_proportion_interval([]) == (0.0, 0.0)
    # One cluster: Wilson fallback — not narrower/wider by sandwich.
    lo_w, hi_w = wilson_interval(3, 10)
    lo_c, hi_c = cluster_robust_proportion_interval([(3, 10)])
    assert (lo_c, hi_c) == (lo_w, hi_w)


def test_iid_equal_clusters_near_wilson_point():
    # Ten independent 1-trial clusters with 4 successes → p=0.4.
    clusters = [(1, 1)] * 4 + [(0, 1)] * 6
    lo, hi = cluster_robust_proportion_interval(clusters)
    assert 0.0 <= lo < 0.4 < hi <= 1.0
    # Width should be positive.
    assert hi - lo > 0.05


def test_clustering_widens_vs_naive_wilson():
    # Same totals (S=10, n=20) but only 2 scholars with uneven within-cluster rates.
    # Cluster residual is non-zero → sandwich SE > 0; i.i.d. Wilson ignores clustering.
    lo_w, hi_w = wilson_interval(10, 20)
    lo_c, hi_c = cluster_robust_proportion_interval([(9, 10), (1, 10)])
    assert 0.0 <= lo_c <= 0.5 <= hi_c <= 1.0
    assert (hi_c - lo_c) >= (hi_w - lo_w) - 1e-9


def test_all_success_or_failure_bounds():
    lo, hi = cluster_robust_proportion_interval([(3, 3), (2, 2), (1, 1)])
    assert lo >= 0.0 and hi <= 1.0
    assert lo <= 1.0 <= hi or math.isclose(hi, 1.0)
    lo0, hi0 = cluster_robust_proportion_interval([(0, 3), (0, 2)])
    assert lo0 == 0.0
    assert hi0 >= 0.0
