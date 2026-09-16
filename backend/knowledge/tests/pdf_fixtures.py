"""Builds tiny, valid, hand-assembled PDFs for tests - no reportlab/fpdf
dependency needed. Byte offsets are computed from actual object lengths, so
this produces a real PDF pypdf can read back correctly."""

import io


def _escape(text: str) -> str:
    return text.replace("\\", r"\\").replace("(", r"\(").replace(")", r"\)")


def build_minimal_pdf(pages: list) -> bytes:
    """pages: a list of plain-ASCII strings, one per PDF page."""
    catalog_num = 1
    pages_num = 2
    page_nums, font_nums, content_nums = [], [], []
    next_num = 3
    for _ in pages:
        page_nums.append(next_num)
        font_nums.append(next_num + 1)
        content_nums.append(next_num + 2)
        next_num += 3

    objects = [
        (catalog_num, f"<< /Type /Catalog /Pages {pages_num} 0 R >>"),
        (
            pages_num,
            f"<< /Type /Pages /Kids [{' '.join(f'{p} 0 R' for p in page_nums)}] "
            f"/Count {len(pages)} >>",
        ),
    ]
    for i, text in enumerate(pages):
        p, f, c = page_nums[i], font_nums[i], content_nums[i]
        objects.append(
            (
                p,
                f"<< /Type /Page /Parent {pages_num} 0 R "
                f"/Resources << /Font << /F1 {f} 0 R >> >> "
                f"/MediaBox [0 0 612 792] /Contents {c} 0 R >>",
            )
        )
        objects.append((f, "<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>"))
        stream_body = f"BT /F1 12 Tf 72 700 Td ({_escape(text)}) Tj ET"
        objects.append((c, f"<< /Length {len(stream_body)} >>\nstream\n{stream_body}\nendstream"))

    objects.sort(key=lambda pair: pair[0])

    out = io.BytesIO()
    out.write(b"%PDF-1.4\n")
    offsets = {}
    for num, body in objects:
        offsets[num] = out.tell()
        out.write(f"{num} 0 obj\n{body}\nendobj\n".encode("latin-1"))

    xref_offset = out.tell()
    max_num = max(offsets) + 1
    out.write(f"xref\n0 {max_num}\n".encode("latin-1"))
    out.write(b"0000000000 65535 f \n")
    for num in range(1, max_num):
        out.write(f"{offsets.get(num, 0):010d} 00000 n \n".encode("latin-1"))

    out.write(f"trailer\n<< /Size {max_num} /Root {catalog_num} 0 R >>\n".encode("latin-1"))
    out.write(f"startxref\n{xref_offset}\n%%EOF".encode("latin-1"))
    return out.getvalue()
