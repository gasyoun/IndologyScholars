"""Приложение Г — статистическая проверка (PPV article).

Builds the inferential backbone the narrative body refers to:
  H1 — degree-preserving permutation null for cross-series segmentation
       (is the 39-scholar overlap LOWER than chance?);
  H2 — Kaplan-Meier career-length survival per series + log-rank test;
  H3 — nonparametric bootstrap 95% CIs for the closedness metrics and for
       the contested Zograf-vs-Roerich differences (core share, retention);
  H4 — confound test: is "city-only affiliation" a function of venue/year
       rather than of the scholar? (Cochran-Mantel-Haenszel, year-stratified).

Read-only on conferences.db. Writes CSVs + SVGs to article/hypothesis_output/.
All machinery lives here; the body keeps only plain-language magnitudes.
"""
from __future__ import annotations

import csv
import re
import sqlite3
import sys
from collections import defaultdict
from pathlib import Path

import numpy as np
from scipy.stats import norm as _norm

sys.stdout.reconfigure(encoding="utf-8")
sys.stderr.reconfigure(encoding="utf-8")

ROOT = Path(__file__).resolve().parents[1]
DB = ROOT / "conferences.db"
OUT = ROOT / "article" / "hypothesis_output"
OUT.mkdir(parents=True, exist_ok=True)

RNG = np.random.default_rng(20260522)
ZOGRAF, ROERICH = 1, 2  # event_series_id
B_PERM = 20000
B_BOOT = 10000
CENSOR_FROM = 2024  # last-seen >= this year => still potentially active (censored)

# ---- affiliation classifier (mirrors work_affiliation_gaps.py) ----
CITY_TOKENS = {
    "москва", "санкт-петербург", "санкт петербург", "спб", "с.-петербург",
    "петербург", "калининград", "новосибирск", "казань", "екатеринбург",
    "владивосток", "уфа", "томск", "элиста", "улан-удэ", "ялта", "нижний новгород",
    "пермь", "воронеж", "ростов-на-дону", "красноярск", "иркутск", "пенза",
    "дели", "тель-авив",
}
INST_TOKENS = [
    "ран", "университет", "институт", "ивр", "ив ", "маэ", "музей", "рггу",
    "вшэ", "спбгу", "мгу", "рудн", "кафедр", "академи", "центр", "library",
    "university", "institute", "museum", "лаборатор", "школа", "семинар",
    "фонд", "общество",
]


def norm(s: str) -> str:
    return re.sub(r"\s+", " ", (s or "").strip()).lower()


def is_city_only(aff: str) -> bool:
    n = norm(aff)
    if not n:
        return True
    core = n
    for c in CITY_TOKENS:
        core = re.sub(rf"[ ,(]+{re.escape(c)}[ ,)]*$", "", core).strip(" ,()")
    if not core or core in CITY_TOKENS:
        return True
    if any(tok in n for tok in INST_TOKENS):
        return False
    if len(n) <= 18 and "," not in n and " " not in n:
        return True
    return False


def gini(counts: np.ndarray) -> float:
    x = np.sort(np.asarray(counts, dtype=float))
    n = len(x)
    if n == 0 or x.sum() == 0:
        return 0.0
    cum = np.cumsum(x)
    return float((n + 1 - 2 * np.sum(cum) / cum[-1]) / n)


# --------------------------------------------------------------------------
def load():
    c = sqlite3.connect(str(DB))
    rows = c.execute(
        """
        SELECT pp.person_id, e.event_series_id, e.year, pp.affiliation_text_raw
        FROM presentation_person pp
        JOIN presentation pr     ON pr.presentation_id = pp.presentation_id
        JOIN session s           ON s.session_id = pr.session_id
        JOIN event_day_venue edv ON edv.event_day_venue_id = s.event_day_venue_id
        JOIN event_day ed        ON ed.event_day_id = edv.event_day_id
        JOIN event e             ON e.event_id = ed.event_id
        """
    ).fetchall()
    c.close()
    return rows


def main():
    rows = load()
    # per (person, series): participation count + set of years
    counts = defaultdict(lambda: defaultdict(int))      # person -> series -> n
    years = defaultdict(lambda: defaultdict(set))        # person -> series -> {year}
    aff_rows = []                                        # (series, year, city_only)
    for pid, sid, year, aff in rows:
        counts[pid][sid] += 1
        years[pid][sid].add(year)
        aff_rows.append((sid, year, is_city_only(aff)))

    persons = list(counts)
    n_z = sum(counts[p][ZOGRAF] for p in persons)
    n_r = sum(counts[p][ROERICH] for p in persons)
    overlap_obs = sum(1 for p in persons if counts[p][ZOGRAF] > 0 and counts[p][ROERICH] > 0)
    only_z = sum(1 for p in persons if counts[p][ZOGRAF] > 0 and counts[p][ROERICH] == 0)
    only_r = sum(1 for p in persons if counts[p][ROERICH] > 0 and counts[p][ZOGRAF] == 0)
    print(f"SANITY: persons={len(persons)} | Z part={n_z} R part={n_r} | "
          f"both={overlap_obs} onlyZ={only_z} onlyR={only_r}")

    report = []

    # ===== H1: permutation null for overlap =====
    slots_person = []   # person index per participation slot
    pidx = {p: i for i, p in enumerate(persons)}
    for p in persons:
        slots_person += [pidx[p]] * (counts[p][ZOGRAF] + counts[p][ROERICH])
    slots_person = np.array(slots_person)
    P = len(persons)
    base_labels = np.array([0] * n_z + [1] * n_r)  # 0=Z, 1=R
    assert len(base_labels) == len(slots_person)

    null_overlap = np.empty(B_PERM)
    for b in range(B_PERM):
        lab = RNG.permutation(base_labels)
        z = np.bincount(slots_person, weights=(lab == 0), minlength=P)
        r = np.bincount(slots_person, weights=(lab == 1), minlength=P)
        null_overlap[b] = np.sum((z > 0) & (r > 0))
    mu, sd = null_overlap.mean(), null_overlap.std(ddof=1)
    p_low = (np.sum(null_overlap <= overlap_obs) + 1) / (B_PERM + 1)
    z_score = (overlap_obs - mu) / sd if sd else 0.0
    print(f"\nH1 null model: observed overlap={overlap_obs}, "
          f"expected={mu:.1f}±{sd:.1f}, z={z_score:.2f}, "
          f"one-sided p(<=obs)={p_low:.4g}")
    report.append(("H1_overlap_observed", overlap_obs))
    report.append(("H1_overlap_expected_mean", round(mu, 2)))
    report.append(("H1_overlap_expected_sd", round(sd, 2)))
    report.append(("H1_z", round(z_score, 3)))
    report.append(("H1_p_one_sided_low", p_low))

    # ===== H3: bootstrap CIs for closedness metrics =====
    z_counts_vec = np.array([counts[p][ZOGRAF] for p in persons if counts[p][ZOGRAF] > 0])
    r_counts_vec = np.array([counts[p][ROERICH] for p in persons if counts[p][ROERICH] > 0])

    def metrics(v):
        v = np.asarray(v)
        return {
            "one_talk": np.mean(v == 1) * 100,
            "retention": np.mean(v >= 2) * 100,
            "core5": np.mean(v >= 5) * 100,
            "gini": gini(v) ,
        }

    def boot_ci(v, key, B=B_BOOT):
        v = np.asarray(v); n = len(v)
        vals = np.empty(B)
        for b in range(B):
            s = v[RNG.integers(0, n, n)]
            vals[b] = metrics(s)[key]
        return np.percentile(vals, [2.5, 97.5])

    print("\nH3 bootstrap 95% CIs:")
    metric_table = []
    for name, v in [("Зограф", z_counts_vec), ("Рерих", r_counts_vec)]:
        m = metrics(v)
        for key, label in [("one_talk", "Разовые, %"), ("retention", "Удержание, %"),
                           ("core5", "Ядро ≥5, %"), ("gini", "Джини")]:
            lo, hi = boot_ci(v, key)
            metric_table.append({"series": name, "metric": label,
                                 "point": round(m[key], 3),
                                 "ci_low": round(lo, 3), "ci_high": round(hi, 3)})
            print(f"  {name:6} {label:14} = {m[key]:6.2f}  [{lo:.2f}, {hi:.2f}]")

    # difference CIs (Roerich - Zograf) for contested claims
    def boot_diff(key, B=B_BOOT):
        nz, nr = len(z_counts_vec), len(r_counts_vec)
        d = np.empty(B)
        for b in range(B):
            sz = z_counts_vec[RNG.integers(0, nz, nz)]
            sr = r_counts_vec[RNG.integers(0, nr, nr)]
            d[b] = metrics(sr)[key] - metrics(sz)[key]
        return d

    print("\nH3 difference CIs (Рерих − Зограф):")
    diff_table = []
    for key, label in [("core5", "Ядро ≥5, п.п."), ("retention", "Удержание, п.п."),
                       ("one_talk", "Разовые, п.п."), ("gini", "Джини")]:
        d = boot_diff(key)
        lo, hi = np.percentile(d, [2.5, 97.5])
        p_two = 2 * min(np.mean(d <= 0), np.mean(d >= 0))
        excl0 = "да" if (lo > 0 or hi < 0) else "нет"
        diff_table.append({"metric": label, "diff": round(d.mean(), 2),
                           "ci_low": round(lo, 2), "ci_high": round(hi, 2),
                           "excludes_zero": excl0, "p_boot": round(float(p_two), 4)})
        print(f"  {label:18} Δ={d.mean():6.2f}  [{lo:.2f}, {hi:.2f}]  "
              f"CI excl 0: {excl0}  p≈{p_two:.3f}")

    # ===== H2: Kaplan-Meier career length + log-rank =====
    def survival_data(series_id):
        dur, event = [], []
        for p in persons:
            ys = years[p][series_id]
            if not ys:
                continue
            debut, last = min(ys), max(ys)
            dur.append(last - debut)
            event.append(0 if last >= CENSOR_FROM else 1)  # 1=dropout observed
        return np.array(dur), np.array(event)

    def km(dur, event):
        times = np.sort(np.unique(dur[event == 1]))
        n = len(dur)
        surv, S = [], 1.0
        var_sum, se = 0.0, []
        atrisk_out, d_out = [], []
        for t in times:
            at_risk = np.sum(dur >= t)
            d = np.sum((dur == t) & (event == 1))
            if at_risk == 0:
                continue
            S *= (1 - d / at_risk)
            if at_risk > d:
                var_sum += d / (at_risk * (at_risk - d))
            surv.append(S); se.append(S * np.sqrt(var_sum))
            atrisk_out.append(at_risk); d_out.append(d)
        return times, np.array(surv), np.array(se), atrisk_out, d_out

    def logrank(d1, e1, d2, e2):
        dur = np.concatenate([d1, d2]); ev = np.concatenate([e1, e2])
        grp = np.concatenate([np.zeros(len(d1)), np.ones(len(d2))])
        times = np.sort(np.unique(dur[ev == 1]))
        O1 = E1 = V = 0.0
        for t in times:
            at_risk = np.sum(dur >= t); d = np.sum((dur == t) & (ev == 1))
            r1 = np.sum((dur >= t) & (grp == 0))
            o1 = np.sum((dur == t) & (ev == 1) & (grp == 0))
            if at_risk <= 1:
                continue
            O1 += o1; E1 += d * r1 / at_risk
            V += d * (r1 / at_risk) * (1 - r1 / at_risk) * (at_risk - d) / (at_risk - 1)
        chi = (O1 - E1) ** 2 / V if V else 0.0
        p = 1 - _norm.cdf(np.sqrt(chi)) if False else float(np.exp(-chi / 2)) if False else None
        from scipy.stats import chi2
        return chi, float(chi2.sf(chi, 1))

    dz, ez = survival_data(ZOGRAF)
    dr, er = survival_data(ROERICH)
    tz, sz_, sez, arz, ddz = km(dz, ez)
    tr, sr_, ser, arr, ddr = km(dr, er)
    chi, p_lr = logrank(dz, ez, dr, er)
    med_z = tz[np.searchsorted(-sz_, -0.5)] if np.any(sz_ <= 0.5) else None
    med_r = tr[np.searchsorted(-sr_, -0.5)] if np.any(sr_ <= 0.5) else None
    print(f"\nH2 Kaplan-Meier (career length, censor last-seen>={CENSOR_FROM}):")
    print(f"  Zograf  n={len(dz)} events={int(ez.sum())} median span={med_z}")
    print(f"  Roerich n={len(dr)} events={int(er.sum())} median span={med_r}")
    print(f"  log-rank chi2={chi:.3f}  p={p_lr:.4g}")
    report += [("H2_logrank_chi2", round(chi, 3)), ("H2_logrank_p", p_lr),
               ("H2_median_span_zograf", med_z), ("H2_median_span_roerich", med_r)]

    # ===== H4: city-only ~ series, stratified by year (CMH) =====
    by_year = defaultdict(lambda: {"z_city": 0, "z_inst": 0, "r_city": 0, "r_inst": 0})
    for sid, year, city in aff_rows:
        key = "z" if sid == ZOGRAF else "r"
        slot = f"{key}_city" if city else f"{key}_inst"
        by_year[year][slot] += 1
    # pooled rates
    zc = sum(v["z_city"] for v in by_year.values()); zi = sum(v["z_inst"] for v in by_year.values())
    rc = sum(v["r_city"] for v in by_year.values()); ri = sum(v["r_inst"] for v in by_year.values())
    print(f"\nH4 city-only affiliation rate: "
          f"Zograf {zc}/{zc+zi}={100*zc/(zc+zi):.1f}%  "
          f"Roerich {rc}/{rc+ri}={100*rc/(rc+ri):.1f}%")
    # CMH
    num = den = R = S = 0.0
    for v in by_year.values():
        a, b_, c_, d_ = v["z_city"], v["z_inst"], v["r_city"], v["r_inst"]
        n = a + b_ + c_ + d_
        if n == 0:
            continue
        num += a - (a + b_) * (a + c_) / n
        den += (a + b_) * (c_ + d_) * (a + c_) * (b_ + d_) / (n * n * (n - 1)) if n > 1 else 0
        R += a * d_ / n
        S += b_ * c_ / n
    cmh_chi = (abs(num) - 0.5) ** 2 / den if den else float("inf")
    from scipy.stats import chi2 as _chi2
    cmh_p = float(_chi2.sf(cmh_chi, 1)) if den else 0.0
    or_mh = R / S if S else float("inf")
    print(f"  CMH (year-stratified) OR={or_mh:.2f}  chi2={cmh_chi:.1f}  p={cmh_p:.3g}")
    report += [("H4_zograf_cityonly_pct", round(100*zc/(zc+zi), 1)),
               ("H4_roerich_cityonly_pct", round(100*rc/(rc+ri), 1)),
               ("H4_cmh_OR", round(or_mh, 2) if or_mh != float("inf") else "inf"),
               ("H4_cmh_chi2", round(cmh_chi, 1)), ("H4_cmh_p", cmh_p)]

    # ---- write CSVs ----
    with (OUT / "appendix_g_summary.csv").open("w", encoding="utf-8", newline="") as f:
        w = csv.writer(f); w.writerow(["key", "value"]); w.writerows(report)
    with (OUT / "appendix_g_metrics_ci.csv").open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["series", "metric", "point", "ci_low", "ci_high"]); w.writeheader(); w.writerows(metric_table)
    with (OUT / "appendix_g_diff_ci.csv").open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["metric", "diff", "ci_low", "ci_high", "excludes_zero", "p_boot"]); w.writeheader(); w.writerows(diff_table)

    # ---- SVGs ----
    write_null_svg(null_overlap, overlap_obs, mu)
    write_km_svg(tz, sz_, sez, tr, sr_, ser, med_z, med_r)
    print("\nWrote CSVs + SVGs to", OUT)


# ---------- minimal SVG helpers ----------
def _svg(w, h, body):
    return (f'<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="{h}" '
            f'viewBox="0 0 {w} {h}" font-family="Georgia, serif">\n' + "\n".join(body) + "\n</svg>\n")


def write_null_svg(null_overlap, obs, mu):
    W, H, ml, mb = 640, 380, 50, 40
    lo, hi = int(null_overlap.min()), int(null_overlap.max())
    bins = np.arange(lo, hi + 2)
    hist, _ = np.histogram(null_overlap, bins=bins)
    bw = (W - ml - 20) / len(hist); ymax = hist.max()
    def sx(i): return ml + i * bw
    def sy(v): return H - mb - (H - mb - 20) * v / ymax
    body = [f'<rect width="{W}" height="{H}" fill="white"/>']
    for i, v in enumerate(hist):
        body.append(f'<rect x="{sx(i):.1f}" y="{sy(v):.1f}" width="{bw-1:.1f}" '
                    f'height="{H-mb-sy(v):.1f}" fill="#9bb4c9"/>')
    xobs = ml + (obs - lo) * bw
    xmu = ml + (mu - lo) * bw
    body.append(f'<line x1="{xobs:.1f}" y1="20" x2="{xobs:.1f}" y2="{H-mb}" stroke="#c0392b" stroke-width="2.5"/>')
    body.append(f'<text x="{xobs+5:.1f}" y="35" fill="#c0392b" font-size="13">наблюдаемое: {obs}</text>')
    body.append(f'<line x1="{xmu:.1f}" y1="20" x2="{xmu:.1f}" y2="{H-mb}" stroke="#2c3e50" stroke-dasharray="4 3"/>')
    body.append(f'<text x="{xmu+5:.1f}" y="55" fill="#2c3e50" font-size="13">ожидаемое: {mu:.0f}</text>')
    body.append(f'<text x="{ml}" y="{H-10}" font-size="12" fill="#333">число учёных, выступавших на обеих площадках (нулевое распределение)</text>')
    (OUT / "null_model_overlap.svg").write_text(_svg(W, H, body), encoding="utf-8")


def write_km_svg(tz, sz, sez, tr, sr, ser, med_z, med_r):
    W, H, ml, mb = 640, 400, 55, 45
    tmax = max(tz.max() if len(tz) else 1, tr.max() if len(tr) else 1)
    def sx(t): return ml + (W - ml - 20) * t / tmax
    def sy(s): return 20 + (H - mb - 20) * (1 - s)
    body = [f'<rect width="{W}" height="{H}" fill="white"/>']
    # axes
    body.append(f'<line x1="{ml}" y1="20" x2="{ml}" y2="{H-mb}" stroke="#333"/>')
    body.append(f'<line x1="{ml}" y1="{H-mb}" x2="{W-20}" y2="{H-mb}" stroke="#333"/>')
    for frac in (0, 0.25, 0.5, 0.75, 1.0):
        y = sy(frac); body.append(f'<text x="{ml-8}" y="{y+4:.1f}" text-anchor="end" font-size="11">{frac:.0%}</text>')
        body.append(f'<line x1="{ml}" y1="{y:.1f}" x2="{W-20}" y2="{y:.1f}" stroke="#eee"/>')
    def step(t, s, color, label, yl):
        pts = [f'M {ml:.1f} {sy(1.0):.1f}']
        prev = 1.0
        for ti, si in zip(t, s):
            pts.append(f'L {sx(ti):.1f} {sy(prev):.1f} L {sx(ti):.1f} {sy(si):.1f}')
            prev = si
        body.append(f'<path d="{" ".join(pts)}" fill="none" stroke="{color}" stroke-width="2.2"/>')
        body.append(f'<text x="{W-160}" y="{yl}" fill="{color}" font-size="13">{label}</text>')
    step(tz, sz, "#2980b9", "Зограф", 40)
    step(tr, sr, "#c0392b", "Рерих", 58)
    body.append(f'<text x="{ml}" y="{H-12}" font-size="12" fill="#333">лет от дебюта до последнего выступления</text>')
    body.append(f'<text x="14" y="{(H-mb)/2:.0f}" font-size="12" fill="#333" transform="rotate(-90 14 {(H-mb)/2:.0f})">доля ещё активных</text>')
    (OUT / "km_retention.svg").write_text(_svg(W, H, body), encoding="utf-8")


if __name__ == "__main__":
    main()
