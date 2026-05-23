import sqlite3
import re
import math
from collections import Counter, defaultdict

try:
    from scipy.stats import chi2_contingency, fisher_exact, spearmanr
except ImportError:
    chi2_contingency = None
    fisher_exact = None
    spearmanr = None

# AFFIL_GROUPS
AFFIL_GROUPS = [
    ("ИКВИА/ВШЭ", re.compile(r"ИКВИА|ВШЭ|Высш", re.I)),
    ("ИВ РАН", re.compile(r"\bИВ РАН\b|Институт востоковедения", re.I)),
    ("ИВР РАН", re.compile(r"ИВР|Институт восточных рукопис|СПбФ ИВ", re.I)),
    ("СПбГУ", re.compile(r"СПбГУ|Санкт-Петербургский государственный", re.I)),
    ("ИФ РАН", re.compile(r"\bИФ РАН\b|Институт философии", re.I)),
    ("ИМЛИ РАН", re.compile(r"ИМЛИ", re.I)),
    ("РГГУ", re.compile(r"РГГУ", re.I)),
    ("РУДН", re.compile(r"РУДН", re.I)),
    ("ИСАА МГУ", re.compile(r"ИСАА|МГУ", re.I)),
    ("ИЭА РАН", re.compile(r"ИЭА", re.I)),
    ("МАЭ РАН", re.compile(r"МАЭ|Кунсткам", re.I)),
    ("ИЯз/ИЯ РАН", re.compile(r"ИЯз|ИЯ РАН", re.I)),
    ("независимый исследователь", re.compile(r"\bНИ\b|независ", re.I)),
]

def affiliation_groups(values):
    joined = " | ".join(v for v in values if v)
    groups = [name for name, pattern in AFFIL_GROUPS if pattern.search(joined)]
    # Correct mapping: if both ИВ РАН and СПб/ИВР match, map to ИВР РАН instead of ИВ РАН
    if "ИВР РАН" in groups and "ИВ РАН" in groups:
        groups.remove("ИВ РАН")
    return groups or ["не нормализовано/только город"]

# City inference
SPB_PATTERNS = re.compile(
    r"СПб|Санкт-Петербург|Ленинград|ИВР|МАЭ|Кунсткам|РХГА|ЕУСПб|ГМИР|РНБ|Герцен|С\.-Петербург|С\.-Петерб|Эрмитаж",
    re.I
)
MOSCOW_PATTERNS = re.compile(
    r"Москва|МГУ|ИВ РАН|ВШЭ|ИКВИА|Высш|РГГУ|ИФ РАН|Институт философии|ИМЛИ|РУДН|ИСАА|ИЭА|этнологии и антропологии|ИЯз|ИЯ РАН|Институт языкознания|МГИМО|ПСТГУ|МГХПА|РГСУ|МПГУ|РАНХиГС|РХТУ|РГХПУ",
    re.I
)

def infer_city(affil):
    if not affil:
        return "Unknown"
    affil_clean = affil.strip()
    if not affil_clean or affil_clean == "":
        return "Unknown"
        
    if SPB_PATTERNS.search(affil_clean):
        return "SPb"
    elif MOSCOW_PATTERNS.search(affil_clean):
        return "Moscow"
    else:
        return "Regions/Foreign"

# Serialized title check
def is_serialized(title):
    if not title:
        return False
    t = title.lower().strip()
    part_patterns = [
        r"\bчасть\s+[0-9ivxл]+\b",
        r"\bч\.\s*[0-9ivxл]+\b",
        r"\bpart\s+[0-9ivx]+\b",
        r"\bсообщение\s+[0-9ivx]+\b",
        r"\bвыпуск\s+[0-9]+\b",
        r"\bвып\.\s*[0-9]+\b",
        r"\b[ixv]+\s*$",
        r"\(\s*[ixv]+\s*\)"
    ]
    for p in part_patterns:
        if re.search(p, t):
            return True
            
    prefixes = [
        "к вопросу о", "еще раз о", "материалы к", "заметки о", "к истории",
        "к изучению", "к интерпретации", "к анализу", "к характеристике",
        "к описанию", "к семантике", "к переводу", "к этимологии", "к пониманию",
        "к реконструкции", "к проблеме", "предварительные заметки о"
    ]
    for pref in prefixes:
        if t.startswith(pref):
            return True
    return False

def pct(n, d):
    return round(100 * n / d, 1) if d else 0.0

def main():
    con = sqlite3.connect("conferences.db")
    out_lines = []
    
    # ----------------------------------------------------
    # H7: Fractional Counting
    # ----------------------------------------------------
    out_lines.append("--- H7: Fractional Counting ---")
    pres_ppl = defaultdict(list)
    for p_id, year, series, pers_id, affil in con.execute("""
        select pr.presentation_id, e.year, es.series_name_en, pp.person_id, pp.affiliation_text_raw
        from presentation pr
        join session s using(session_id)
        join event_day_venue edv using(event_day_venue_id)
        join event_day ed using(event_day_id)
        join event e using(event_id)
        join event_series es using(event_series_id)
        join presentation_person pp on pp.presentation_id = pr.presentation_id
    """):
        pres_ppl[p_id].append((year, series, pers_id, affil))
        
    org_counts = defaultdict(lambda: {"simple": 0, "fractional": 0})
    org_by_year = defaultdict(lambda: {"simple": 0, "fractional": 0})
    
    target_orgs = {"ИВ РАН", "ИВР РАН", "СПбГУ", "ИКВИА/ВШЭ"}
    
    for p_id, ppl in pres_ppl.items():
        k = len(ppl)
        for year, series, pers_id, affil in ppl:
            gps = affiliation_groups([affil])
            m = len(gps)
            for org in gps:
                frac_weight = 1.0 / (k * m)
                simp_weight = 1.0
                
                org_counts[org]["simple"] += simp_weight
                org_counts[org]["fractional"] += frac_weight
                
                if org in target_orgs:
                    org_by_year[(org, year, series)]["simple"] += simp_weight
                    org_by_year[(org, year, series)]["fractional"] += frac_weight
                    
    out_lines.append("Total org stats:")
    for org in sorted(target_orgs):
        out_lines.append(f"  {org}: Simple={org_counts[org]['simple']:.1f}, Fractional={org_counts[org]['fractional']:.3f}")
        
    # ----------------------------------------------------
    # H8: Organizing Committee & Era Influence
    # ----------------------------------------------------
    out_lines.append("\n--- H8: Era Influence on Zograf Readings ---")
    z_speaker_years = defaultdict(list)
    z_presentations = []
    
    import csv
    theme_lookup = {}
    with open("analytics_output/theme_codes_final.csv", "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            series = "Zograf" if row["series"] == "Zograf Readings" else "Roerich"
            title_norm = row["title"].lower().replace("ё", "е").strip()
            title_norm = re.sub(r"\s+", " ", title_norm)
            title_norm = re.sub(r"[«»“”\"'`.,:;!?()\[\]{}<>/\\|–—-]+", " ", title_norm)
            title_norm = re.sub(r"\s+", " ", title_norm).strip()
            theme_lookup[(series, int(row["year"]), title_norm)] = row

    for p_id, year, title, pers_id in con.execute("""
        select pr.presentation_id, e.year, pr.title, pp.person_id
        from presentation pr
        join session s using(session_id)
        join event_day_venue edv using(event_day_venue_id)
        join event_day ed using(event_day_id)
        join event e using(event_id)
        join event_series es using(event_series_id)
        join presentation_person pp on pp.presentation_id = pr.presentation_id
        where es.series_name_en = 'Zograf Readings'
    """):
        z_speaker_years[pers_id].append(year)
        t_norm = title.lower().replace("ё", "е").strip()
        t_norm = re.sub(r"\s+", " ", t_norm)
        t_norm = re.sub(r"[«»“”\"'`.,:;!?()\[\]{}<>/\\|–—-]+", " ", t_norm)
        t_norm = re.sub(r"\s+", " ", t_norm).strip()
        
        coded_row = theme_lookup.get(("Zograf", year, t_norm))
        z_presentations.append({
            "presentation_id": p_id,
            "year": year,
            "person_id": pers_id,
            "l1": coded_row["l1"] if coded_row else "unknown",
            "l2": coded_row["l2"] if coded_row else "unknown",
        })
        
    z_speaker_debut = {pers_id: min(years) for pers_id, years in z_speaker_years.items()}
    
    year_speakers = defaultdict(set)
    year_newcomers = defaultdict(set)
    for pers_id, years in z_speaker_years.items():
        debut = z_speaker_debut[pers_id]
        for y in years:
            year_speakers[y].add(pers_id)
            if y == debut:
                year_newcomers[y].add(pers_id)
                
    vasilkov_speakers = 0
    vasilkov_newcomers = 0
    albedil_speakers = 0
    albedil_newcomers = 0
    for y in sorted(year_speakers.keys()):
        spk_count = len(year_speakers[y])
        new_count = len(year_newcomers[y])
        if y <= 2024:
            vasilkov_speakers += spk_count
            vasilkov_newcomers += new_count
        else:
            albedil_speakers += spk_count
            albedil_newcomers += new_count
            
    p_vas = pct(vasilkov_newcomers, vasilkov_speakers)
    p_alb = pct(albedil_newcomers, albedil_speakers)
    out_lines.append(f"Era Newcomers:")
    out_lines.append(f"  Vasilkov Era (<=2024): {vasilkov_newcomers}/{vasilkov_speakers} ({p_vas}%)")
    out_lines.append(f"  Albedil-Ivanov Era (2025-2026): {albedil_newcomers}/{albedil_speakers} ({p_alb}%)")
    
    if chi2_contingency:
        contingency = [
            [vasilkov_newcomers, vasilkov_speakers - vasilkov_newcomers],
            [albedil_newcomers, albedil_speakers - albedil_newcomers]
        ]
        chi2, p_val, dof, _ = chi2_contingency(contingency)
        out_lines.append(f"  Newcomer Era Chi2: Chi2={chi2:.3f}, p-value={p_val:.4f}")
        
    vasilkov_l1 = Counter()
    albedil_l1 = Counter()
    vasilkov_l2 = Counter()
    albedil_l2 = Counter()
    
    seen_pres = set()
    for pres in z_presentations:
        p_id = pres["presentation_id"]
        if p_id in seen_pres:
            continue
        seen_pres.add(p_id)
        
        y = pres["year"]
        l1 = pres["l1"]
        l2 = pres["l2"]
        if y <= 2024:
            vasilkov_l1[l1] += 1
            vasilkov_l2[l2] += 1
        else:
            albedil_l1[l1] += 1
            albedil_l2[l2] += 1
            
    out_lines.append("Theme distributions L1:")
    all_l1 = sorted(set(vasilkov_l1.keys()) | set(albedil_l1.keys()))
    for cat in all_l1:
        if cat != "unknown":
            out_lines.append(f"  {cat}: Vasilkov={vasilkov_l1[cat]} ({pct(vasilkov_l1[cat], sum(vasilkov_l1.values()))}%), Albedil={albedil_l1[cat]} ({pct(albedil_l1[cat], sum(albedil_l1.values()))}%)")
            
    if chi2_contingency:
        matrix_l1 = []
        for cat in all_l1:
            if cat != "unknown" and (vasilkov_l1[cat] > 0 or albedil_l1[cat] > 0):
                matrix_l1.append([vasilkov_l1[cat], albedil_l1[cat]])
        matrix_l1_t = list(map(list, zip(*matrix_l1)))
        if len(matrix_l1_t) > 1 and len(matrix_l1_t[0]) > 1:
            chi2, p_val, dof, _ = chi2_contingency(matrix_l1_t)
            out_lines.append(f"  L1 distribution Era Chi2: Chi2={chi2:.3f}, p-value={p_val:.4f}")
            
    out_lines.append("Theme distributions L2:")
    all_l2 = sorted(set(vasilkov_l2.keys()) | set(albedil_l2.keys()))
    for cat in all_l2:
        if cat != "unknown":
            out_lines.append(f"  {cat}: Vasilkov={vasilkov_l2[cat]} ({pct(vasilkov_l2[cat], sum(vasilkov_l2.values()))}%), Albedil={albedil_l2[cat]} ({pct(albedil_l2[cat], sum(albedil_l2.values()))}%)")
            
    if chi2_contingency:
        matrix_l2 = []
        for cat in all_l2:
            if cat != "unknown" and (vasilkov_l2[cat] > 0 or albedil_l2[cat] > 0):
                matrix_l2.append([vasilkov_l2[cat], albedil_l2[cat]])
        matrix_l2_t = list(map(list, zip(*matrix_l2)))
        if len(matrix_l2_t) > 1 and len(matrix_l2_t[0]) > 1:
            chi2, p_val, dof, _ = chi2_contingency(matrix_l2_t)
            out_lines.append(f"  L2 distribution Era Chi2: Chi2={chi2:.3f}, p-value={p_val:.4f}")

    # ----------------------------------------------------
    # H9: Geographic Gravity & Cohort Survival
    # ----------------------------------------------------
    out_lines.append("\n--- H9: Geographic Gravity & Cohort Survival ---")
    zograf_cities = Counter()
    roerich_cities = Counter()
    
    speaker_city_years = defaultdict(lambda: {"city": "Unknown", "years": set()})
    
    for p_id, year, series, pers_id, affil in con.execute("""
        select pr.presentation_id, e.year, es.series_name_en, pp.person_id, pp.affiliation_text_raw
        from presentation pr
        join session s using(session_id)
        join event_day_venue edv using(event_day_venue_id)
        join event_day ed using(event_day_id)
        join event e using(event_id)
        join event_series es using(event_series_id)
        join presentation_person pp on pp.presentation_id = pr.presentation_id
    """):
        city = infer_city(affil)
        if "Zograf" in series:
            zograf_cities[city] += 1
        else:
            roerich_cities[city] += 1
            
        speaker_city_years[pers_id]["years"].add(year)
        if speaker_city_years[pers_id]["city"] == "Unknown" or city != "Regions/Foreign":
            speaker_city_years[pers_id]["city"] = city
            
    out_lines.append("Zograf (SPb) presentation counts by speaker city:")
    total_z = sum(zograf_cities.values())
    for city, count in zograf_cities.items():
        out_lines.append(f"  {city}: {count} ({pct(count, total_z)}%)")
        
    out_lines.append("Roerich (Moscow) presentation counts by speaker city:")
    total_r = sum(roerich_cities.values())
    for city, count in roerich_cities.items():
        out_lines.append(f"  {city}: {count} ({pct(count, total_r)}%)")
        
    survival_data = defaultdict(lambda: {"total": 0, "returning": 0})
    for pers_id, info in speaker_city_years.items():
        city = info["city"]
        if city == "Unknown":
            continue
        nyears = len(info["years"])
        is_returning = 1 if nyears >= 2 else 0
        survival_data[city]["total"] += 1
        survival_data[city]["returning"] += is_returning
        
    out_lines.append("Speaker retention rate (participated in >= 2 different years):")
    for city in sorted(survival_data.keys()):
        tot = survival_data[city]["total"]
        ret = survival_data[city]["returning"]
        out_lines.append(f"  {city}: Speakers={tot}, Returning={ret} ({pct(ret, tot)}%)")
        
    metropolitan_speakers = survival_data["SPb"]["total"] + survival_data["Moscow"]["total"]
    metropolitan_returning = survival_data["SPb"]["returning"] + survival_data["Moscow"]["returning"]
    
    regions_speakers = survival_data["Regions/Foreign"]["total"]
    regions_returning = survival_data["Regions/Foreign"]["returning"]
    
    if chi2_contingency:
        contingency_survival = [
            [metropolitan_returning, metropolitan_speakers - metropolitan_returning],
            [regions_returning, regions_speakers - regions_returning]
        ]
        chi2, p_val, dof, _ = chi2_contingency(contingency_survival)
        out_lines.append(f"  Survival Chi2 (Metropolitan vs Regions): Chi2={chi2:.3f}, p-value={p_val:.4f}")

    # ----------------------------------------------------
    # H10: Serialization & Salami Slicing
    # ----------------------------------------------------
    out_lines.append("\n--- H10: Serialization & Salami Slicing ---")
    speaker_talks = defaultdict(list)
    for pres_id, title, pers_id in con.execute("""
        select pr.presentation_id, pr.title, pp.person_id
        from presentation pr
        join presentation_person pp on pp.presentation_id = pr.presentation_id
    """):
        speaker_talks[pers_id].append(title)
        
    core_serialized_count = 0
    core_total_count = 0
    periph_serialized_count = 0
    periph_total_count = 0
    
    person_stats = []
    
    for pers_id, titles in speaker_talks.items():
        total = len(titles)
        serialized = sum(1 for t in titles if is_serialized(t))
        is_core = total >= 5
        
        person_stats.append({
            "pers_id": pers_id,
            "total": total,
            "serialized": serialized,
            "is_core": is_core
        })
        
        if is_core:
            core_serialized_count += serialized
            core_total_count += total
        else:
            periph_serialized_count += serialized
            periph_total_count += total
            
    out_lines.append(f"Serialization rates by core status:")
    out_lines.append(f"  Core (>=5 talks): {core_serialized_count}/{core_total_count} ({pct(core_serialized_count, core_total_count)}%)")
    out_lines.append(f"  Peripheral (<5 talks): {periph_serialized_count}/{periph_total_count} ({pct(periph_serialized_count, periph_total_count)}%)")
    
    if chi2_contingency:
        contingency_serialization = [
            [core_serialized_count, core_total_count - core_serialized_count],
            [periph_serialized_count, periph_total_count - periph_serialized_count]
        ]
        if fisher_exact:
            oddsratio, p_val = fisher_exact(contingency_serialization)
            out_lines.append(f"  Serialization Fisher Exact p-value: {p_val:.4f}")
        else:
            chi2, p_val, dof, _ = chi2_contingency(contingency_serialization)
            out_lines.append(f"  Serialization Chi2 p-value: {p_val:.4f}")
            
    if spearmanr:
        totals = [p["total"] for p in person_stats]
        serializeds = [p["serialized"] for p in person_stats]
        rho, p_val = spearmanr(totals, serializeds)
        out_lines.append(f"  Spearman rho (Total talks vs Serialized talks): rho={rho:.3f}, p-value={p_val:.4f}")

    with open("scratch/hypotheses_run_results.txt", "w", encoding="utf-8") as f:
        f.write("\n".join(out_lines))
    print("Wrote results to scratch/hypotheses_run_results.txt")

if __name__ == '__main__':
    main()
