import re
import json

file_path = r"c:\Users\user\Documents\GitHub\IndologyScholars\extract_hypotheses.py"

meta_updates = {
    "H1": {"reproducibility": "hybrid", "contribution": "conceptual", "data_scope": "comparative", "interdisciplinary": "interdisciplinary", "impact": "regional"},
    "H2": {"reproducibility": "computational", "contribution": "empirical", "data_scope": "comparative", "interdisciplinary": "interdisciplinary", "impact": "regional"},
    "H3": {"reproducibility": "computational", "contribution": "empirical", "data_scope": "comparative", "interdisciplinary": "interdisciplinary", "impact": "regional"},
    "H4": {"reproducibility": "computational", "contribution": "empirical", "data_scope": "comparative", "interdisciplinary": "interdisciplinary", "impact": "regional"},
    "H5": {"reproducibility": "computational", "contribution": "empirical", "data_scope": "comparative", "interdisciplinary": "interdisciplinary", "impact": "regional"},
    "H6": {"reproducibility": "computational", "contribution": "empirical", "data_scope": "cohort", "interdisciplinary": "domain_specific", "impact": "niche"},
    "H7": {"reproducibility": "computational", "contribution": "conceptual", "data_scope": "whole_corpus", "interdisciplinary": "transdisciplinary", "impact": "broad"},
    "H8": {"reproducibility": "computational", "contribution": "empirical", "data_scope": "comparative", "interdisciplinary": "interdisciplinary", "impact": "regional"},
    "H9": {"reproducibility": "computational", "contribution": "empirical", "data_scope": "whole_corpus", "interdisciplinary": "interdisciplinary", "impact": "broad"},
    "H10": {"reproducibility": "computational", "contribution": "empirical", "data_scope": "whole_corpus", "interdisciplinary": "interdisciplinary", "impact": "regional"},
    "H11": {"reproducibility": "hybrid", "contribution": "conceptual", "data_scope": "whole_corpus", "interdisciplinary": "interdisciplinary", "impact": "regional"},
    "H12": {"reproducibility": "hybrid", "contribution": "empirical", "data_scope": "cohort", "interdisciplinary": "interdisciplinary", "impact": "regional"},
    "H13": {"reproducibility": "computational", "contribution": "methodological", "data_scope": "whole_corpus", "interdisciplinary": "interdisciplinary", "impact": "broad"},
    "H14": {"reproducibility": "hybrid", "contribution": "conceptual", "data_scope": "whole_corpus", "interdisciplinary": "transdisciplinary", "impact": "broad"},
    "H15": {"reproducibility": "computational", "contribution": "methodological", "data_scope": "cohort", "interdisciplinary": "interdisciplinary", "impact": "broad"},
    "H16": {"reproducibility": "computational", "contribution": "empirical", "data_scope": "cohort", "interdisciplinary": "interdisciplinary", "impact": "regional"},
    "H17": {"reproducibility": "computational", "contribution": "empirical", "data_scope": "whole_corpus", "interdisciplinary": "interdisciplinary", "impact": "broad"},
    "H18": {"reproducibility": "computational", "contribution": "empirical", "data_scope": "whole_corpus", "interdisciplinary": "interdisciplinary", "impact": "broad"},
    "H19": {"reproducibility": "hybrid", "contribution": "empirical", "data_scope": "comparative", "interdisciplinary": "interdisciplinary", "impact": "regional"},
    "H20": {"reproducibility": "hybrid", "contribution": "conceptual", "data_scope": "whole_corpus", "interdisciplinary": "transdisciplinary", "impact": "broad"},
    "H21": {"reproducibility": "computational", "contribution": "empirical", "data_scope": "whole_corpus", "interdisciplinary": "interdisciplinary", "impact": "broad"},
    "H22": {"reproducibility": "computational", "contribution": "empirical", "data_scope": "cohort", "interdisciplinary": "interdisciplinary", "impact": "regional"},
    "H23": {"reproducibility": "hybrid", "contribution": "empirical", "data_scope": "whole_corpus", "interdisciplinary": "interdisciplinary", "impact": "broad"},
    "H24": {"reproducibility": "computational", "contribution": "empirical", "data_scope": "whole_corpus", "interdisciplinary": "interdisciplinary", "impact": "broad"},
    "H25": {"reproducibility": "computational", "contribution": "empirical", "data_scope": "whole_corpus", "interdisciplinary": "interdisciplinary", "impact": "broad"},
    "H26": {"reproducibility": "hybrid", "contribution": "conceptual", "data_scope": "whole_corpus", "interdisciplinary": "transdisciplinary", "impact": "broad"},
    "H27": {"reproducibility": "computational", "contribution": "empirical", "data_scope": "whole_corpus", "interdisciplinary": "interdisciplinary", "impact": "broad"},
    "H28": {"reproducibility": "computational", "contribution": "empirical", "data_scope": "comparative", "interdisciplinary": "interdisciplinary", "impact": "regional"},
    "H29": {"reproducibility": "computational", "contribution": "empirical", "data_scope": "whole_corpus", "interdisciplinary": "interdisciplinary", "impact": "regional"},
    "H30": {"reproducibility": "computational", "contribution": "empirical", "data_scope": "whole_corpus", "interdisciplinary": "interdisciplinary", "impact": "broad"},
    "H31": {"reproducibility": "qualitative", "contribution": "conceptual", "data_scope": "cohort", "interdisciplinary": "domain_specific", "impact": "regional"},
    "H32": {"reproducibility": "computational", "contribution": "empirical", "data_scope": "whole_corpus", "interdisciplinary": "interdisciplinary", "impact": "broad"},
    "H33": {"reproducibility": "computational", "contribution": "empirical", "data_scope": "cohort", "interdisciplinary": "interdisciplinary", "impact": "regional"},
    "H34": {"reproducibility": "computational", "contribution": "empirical", "data_scope": "whole_corpus", "interdisciplinary": "interdisciplinary", "impact": "broad"},
    "H35": {"reproducibility": "computational", "contribution": "empirical", "data_scope": "cohort", "interdisciplinary": "interdisciplinary", "impact": "broad"},
}

with open(file_path, "r", encoding="utf-8") as f:
    content = f.read()

# We want to parse the `hypotheses` list from the content
# Since it is a valid python file, let's load it dynamically!
import sys
import os
sys.path.append(os.path.dirname(file_path))
import extract_hypotheses

updated_hypotheses = []
for h in extract_hypotheses.hypotheses:
    hid = h["id"]
    if hid in meta_updates:
        h.update(meta_updates[hid])
    updated_hypotheses.append(h)

# Now, we reconstruct the file `extract_hypotheses.py` content
# The first part is imports and out_file definitions
header = """import json

out_file = r"C:\\Users\\user\\Documents\\GitHub\\IndologyScholars\\assets\\data\\hypotheses.json"

# Полный реестр всех 35 гипотез с формулировками из статьи и верифицированными метриками
hypotheses = """

# Pretty format the hypotheses list
formatted_hypotheses = json.dumps(updated_hypotheses, ensure_ascii=False, indent=2)

footer = """

# Записываем в файл
with open(out_file, 'w', encoding='utf-8') as f:
    json.dump(hypotheses, f, ensure_ascii=False, indent=2)

print(f"Successfully wrote {len(hypotheses)} hypotheses to {out_file}")
"""

new_content = header + formatted_hypotheses + footer

with open(file_path, "w", encoding="utf-8") as f:
    f.write(new_content)

print("Successfully updated extract_hypotheses.py with new scientometric metadata!")
