import fitz

pdf_path = r"C:\Users\user\.gemini\antigravity\brain\1d297c6f-4892-4086-9ac4-518910442a40\scratch\dissertation.pdf"
doc = fitz.open(pdf_path)

search_terms = ["Матфея", "кумулятив", "динамик", "MNCS", "Ферхюльст"]
results = []

for i, page in enumerate(doc):
    text = page.get_text()
    found = []
    for term in search_terms:
        if term.lower() in text.lower():
            found.append(term)
    if found:
        results.append((i+1, found, text[:300].replace('\n', ' ')))

print(f"Total matching pages: {len(results)}")
for r in results[:20]:
    print(f"Page {r[0]}: terms {r[1]} | Snippet: {r[2]}")
