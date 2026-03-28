import fitz
import docx
import os

files = [
    r"d:\usuario\descargas\Manual_Definitivo_Inversion (2).docx",
    r"d:\usuario\descargas\checklist_analisis_fundamental_v2 (1).pdf",
    r"d:\usuario\descargas\Pdf-Definitivo-Curso-Analisis-Fundamental (1).pdf"
]

def parse_docx(path):
    doc = docx.Document(path)
    return "\n".join([p.text for p in doc.paragraphs])

def parse_pdf(path):
    doc = fitz.open(path)
    text = ""
    for page in doc:
        text += page.get_text()
    return text

with open("temp_output.txt", "w", encoding="utf-8") as out:
    for f in files:
        out.write(f"--- START OF {os.path.basename(f)} ---\n")
        try:
            if f.endswith(".docx"):
                out.write(parse_docx(f))
            elif f.endswith(".pdf"):
                out.write(parse_pdf(f))
        except Exception as e:
            out.write(f"Error reading {f}: {e}")
        out.write(f"\n--- END OF {os.path.basename(f)} ---\n\n")
