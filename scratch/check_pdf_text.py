import fitz

pdf_path = r"C:\Users\user\.gemini\antigravity\brain\1d297c6f-4892-4086-9ac4-518910442a40\scratch\dissertation.pdf"
doc = fitz.open(pdf_path)
page = doc[3]
text_dict = page.get_text("dict")
for block in text_dict.get("blocks", []):
    for line in block.get("lines", []):
        for span in line.get("spans", []):
            text = span.get("text")
            if len(text.strip()) > 1:
                print("Span text:", repr(text))
                print("Unicode points:", [ord(c) for c in text])
                break
