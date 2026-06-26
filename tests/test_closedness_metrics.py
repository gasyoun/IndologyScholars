from generate_analytics import compute_closedness


def test_cohort_survival_is_censoring_aware_and_monotone():
    _, _, rows = compute_closedness(
        "Test",
        {
            1: [2000, 2002],
            2: [2000],
            3: [2000, 2004],
        },
    )

    cohort_rows = [row for row in rows if row["debut_year"] == 2000]
    survival = [row["survival_pct"] for row in cohort_rows]

    assert cohort_rows[0]["survival_pct"] == 100.0
    assert all(a >= b for a, b in zip(survival, survival[1:]))
    assert {row["years_since_debut"]: row["survival_pct"] for row in cohort_rows}[2] == 50.0
    assert "active_n" not in cohort_rows[0]
    assert cohort_rows[0]["at_risk"] == 3
