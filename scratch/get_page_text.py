import fitz

pdf_path = r"C:\Users\user\.gemini\antigravity\brain\1d297c6f-4892-4086-9ac4-518910442a40\scratch\dissertation.pdf"
doc = fitz.open(pdf_path)

pages_to_extract = [38, 39, 40, 41, 42, 43] # 0-indexed: pages 39 to 44

with open("extracted_pages.txt", "w", encoding="utf-8") as f:
    for page_idx in pages_to_extract:
        f.write(f"=== Page {page_idx+1} ===\n")
        f.write(doc[page_idx].get_text())
        f.write("\n\n")

print("Done extracting pages to extracted_pages.txt")
