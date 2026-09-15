"""Extract readable text from a .docx, preserving paragraph and heading structure."""
import re
import sys
import zipfile
import xml.etree.ElementTree as ET

NS = {"w": "http://schemas.openxmlformats.org/wordprocessingml/2006/main"}
W = NS["w"]


def para_text(p):
    """Concatenate all w:t runs in a paragraph, honouring w:tab and w:br."""
    parts = []
    for node in p.iter():
        tag = node.tag
        if tag == f"{{{W}}}t":
            parts.append(node.text or "")
        elif tag == f"{{{W}}}tab":
            parts.append("\t")
        elif tag == f"{{{W}}}br":
            parts.append("\n")
    return "".join(parts)


def para_style(p):
    ppr = p.find(f"{{{W}}}pPr")
    if ppr is None:
        return ""
    st = ppr.find(f"{{{W}}}pStyle")
    if st is None:
        return ""
    return st.get(f"{{{W}}}val", "")


def main(path, out_path):
    with zipfile.ZipFile(path) as z:
        xml = z.read("word/document.xml")
    root = ET.fromstring(xml)
    body = root.find(f"{{{W}}}body")

    lines = []
    for el in body:
        tag = el.tag
        if tag == f"{{{W}}}p":
            text = para_text(el)
            style = para_style(el)
            if text.strip():
                prefix = ""
                if style.lower().startswith("heading") or style.lower().startswith("标题"):
                    prefix = "## "
                lines.append(prefix + text)
            else:
                lines.append("")
        elif tag == f"{{{W}}}tbl":
            lines.append("[表格]")
            for row in el.findall(f"{{{W}}}tr"):
                cells = []
                for cell in row.findall(f"{{{W}}}tc"):
                    cells.append(" ".join(para_text(p) for p in cell.findall(f"{{{W}}}p")).strip())
                lines.append(" | ".join(cells))
            lines.append("[/表格]")

    # Collapse runs of blank lines.
    out = []
    blank = 0
    for line in lines:
        if line.strip():
            blank = 0
            out.append(line)
        else:
            blank += 1
            if blank <= 1:
                out.append("")

    text = "\n".join(out)
    with open(out_path, "w", encoding="utf-8") as fh:
        fh.write(text)
    print(f"wrote {out_path}: {len(text)} chars, {len(out)} lines")


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
