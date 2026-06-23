try:
    import pandas as pd
except Exception:
    pd = None

try:
    from reportlab.lib.units import mm
    from reportlab.platypus import Paragraph, Spacer
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.cidfonts import UnicodeCIDFont
except Exception:
    mm = None
    Paragraph = None
    Spacer = None
    pdfmetrics = None
    UnicodeCIDFont = None

from hidamari.core.text_utils import clean_text


def register_japanese_pdf_fonts(
    gothic="HeiseiKakuGo-W5",
    mincho="HeiseiMin-W3",
    fallback="Helvetica",
):
    """ReportLab標準CIDフォントを登録し、利用できるフォント名を返す。"""
    if pdfmetrics is None or UnicodeCIDFont is None:
        return fallback, fallback
    gothic_font = fallback
    mincho_font = fallback
    try:
        pdfmetrics.registerFont(UnicodeCIDFont(gothic))
        gothic_font = gothic
    except Exception:
        pass
    try:
        pdfmetrics.registerFont(UnicodeCIDFont(mincho))
        mincho_font = mincho
    except Exception:
        pass
    return gothic_font, mincho_font


def register_single_japanese_pdf_font(preferred="HeiseiKakuGo-W5", fallback_preferred="HeiseiMin-W3", fallback="Helvetica"):
    """1種類だけ使うPDF用フォントを安全に登録する。"""
    if pdfmetrics is None or UnicodeCIDFont is None:
        return fallback
    try:
        pdfmetrics.registerFont(UnicodeCIDFont(preferred))
        return preferred
    except Exception:
        try:
            pdfmetrics.registerFont(UnicodeCIDFont(fallback_preferred))
            return fallback_preferred
        except Exception:
            return fallback


def pdf_safe_text(value):
    """ReportLab Paragraph向けに文字列を安全化する。"""
    try:
        if pd is not None and pd.isna(value):
            return ""
    except Exception:
        pass
    text = str(value)
    text = text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    return text


def paragraph_lines(text, style):
    """複数行テキストをPDF用Paragraphのリストへ変換する。"""
    safe = pdf_safe_text(text)
    if Paragraph is None or Spacer is None or mm is None:
        return []
    if not safe.strip():
        return [Paragraph("記録なし", style)]
    parts = []
    for line in safe.split("\n"):
        line = line.strip()
        if not line:
            parts.append(Spacer(1, 2 * mm))
        else:
            parts.append(Paragraph(line, style))
    return parts


def short_goal_pdf_text(value, default="記録なし"):
    """PDF出力用に空欄・NaNを安全な文字列へ整える。"""
    try:
        text = clean_text(value, default)
    except Exception:
        text = str(value or "").strip()
    if not text or text.lower() in ["nan", "none", "nat"]:
        return default
    return text


def short_goal_join_for_pdf(values, limit=5):
    """PDFの1ページに収めるため、本人の様子などを短く整理する。"""
    items = []
    try:
        iterable = list(values)
    except Exception:
        iterable = []
    for value in iterable:
        text = short_goal_pdf_text(value, "")
        if not text:
            continue
        if text not in items:
            items.append(text)
    if not items:
        return "記録なし"
    return "\n".join([f"・{x}" for x in items[:limit]])
