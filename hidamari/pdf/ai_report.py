import html
import re

try:
    from reportlab.lib.styles import ParagraphStyle
    from reportlab.lib.units import mm
    from reportlab.platypus import Paragraph, Spacer
except Exception:
    ParagraphStyle = None
    mm = None
    Paragraph = None
    Spacer = None


AI_INSIGHT_REPORT_TITLE = "AI管理者向け分析レポート"
AI_INSIGHT_REPORT_DISCLAIMER = "このPDFは、健康チェック・排泄・申し送り・短期目標の記録を管理者が確認しやすい形に整理したものです。医療判断・診断・受診判断を行うものではありません。"
AI_INSIGHT_CONFIRMATION_NOTE = "確認メモ：必要に応じて、記録原本・申し送り・職員間共有内容と照合してください。AIの文章は判断の代替ではなく、管理者確認の補助として扱ってください。"
AI_INSIGHT_LOG_SUMMARY_TITLE = "AI分析ログ一覧"
AI_INSIGHT_LOG_EMPTY_TEXT = "AI分析ログはまだありません。"


def ai_admin_report_file_name(user_name, start_date, end_date):
    safe_user = re.sub(r"[^\w一-龥ぁ-んァ-ンー\-]", "_", str(user_name))
    return f"hidamari_ai_admin_report_{safe_user}_{start_date}_{end_date}.pdf"


def append_markdown_lines_to_story(report_text, story, base_style, title_style):
    """Markdown風の管理者レポート本文を既存PDFレイアウト用storyへ追加する。"""
    if Paragraph is None or ParagraphStyle is None or Spacer is None or mm is None:
        return story
    h2_style = ParagraphStyle("hidamari_h2", parent=base_style, fontSize=12, leading=16, spaceBefore=3, spaceAfter=2)
    for line in str(report_text or "").splitlines():
        line = line.rstrip()
        if line.startswith("# "):
            story.append(Paragraph(line.replace("# ", ""), title_style))
            story.append(Spacer(1, 3 * mm))
        elif line.startswith("## "):
            story.append(Spacer(1, 2 * mm))
            story.append(Paragraph(line.replace("## ", ""), h2_style))
        elif line.startswith("- "):
            story.append(Paragraph("・" + html.escape(line[2:]), base_style))
        elif line.strip() == "":
            story.append(Spacer(1, 1.5 * mm))
        else:
            story.append(Paragraph(html.escape(line), base_style))
    return story
