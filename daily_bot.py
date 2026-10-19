import os
import re
import json
import html
import logging
import calendar
from datetime import datetime
from pathlib import Path
from urllib.parse import quote

import requests
import feedparser

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import mm
from reportlab.platypus import (
    SimpleDocTemplate,
    Paragraph,
    Spacer,
    Table,
    TableStyle,
    PageBreak,
    KeepTogether,
)
from xml.sax.saxutils import escape


# ==========================================================
# CONFIGURATION
# ==========================================================

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

# Change this if your Google AI Studio account uses a
# different available model.
GEMINI_MODEL = os.getenv(
    "GEMINI_MODEL",
    "gemini-3.8-flash"
)

OUTPUT_DIR = Path("daily_pdfs")
OUTPUT_DIR.mkdir(exist_ok=True)

TODAY = datetime.now().astimezone()
TODAY_TEXT = TODAY.strftime("%d %B %Y")
DATE_KEY = TODAY.strftime("%Y-%m-%d")

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s"
)

session = requests.Session()
session.headers.update({
    "User-Agent": "DailyStudyBot/2.0"
})


# ==========================================================
# TOPIC ROTATION
# ==========================================================

STATIC_GK_TOPICS = [
    "Indian History",
    "Indian and World Geography",
    "Indian Constitution and Polity",
    "Indian Economy",
    "General Science"
]

ARITHMETIC_TOPICS = [
    "Percentage and Ratio",
    "Profit, Loss and Discount",
    "Average and Mixture",
    "Time and Work",
    "Speed, Time and Distance",
    "Simple and Compound Interest",
    "Number System and Simplification",
    "Mensuration"
]

day_number = TODAY.timetuple().tm_yday

GK_TOPIC = STATIC_GK_TOPICS[
    (day_number - 1) % len(STATIC_GK_TOPICS)
]

ARITHMETIC_TOPIC = ARITHMETIC_TOPICS[
    (day_number - 1) % len(ARITHMETIC_TOPICS)
]


# ==========================================================
# GEMINI API
# ==========================================================

def gemini_generate(prompt, max_tokens=12000):
    """
    Generate content using the Gemini Developer API.
    Returns the model's text response.
    """

    if not GEMINI_API_KEY:
        raise RuntimeError(
            "GEMINI_API_KEY is missing from GitHub Secrets."
        )

    url = (
        "https://generativelanguage.googleapis.com/"
        f"v1beta/models/{GEMINI_MODEL}:generateContent"
    )

    payload = {
        "contents": [
            {
                "parts": [
                    {"text": prompt}
                ]
            }
        ],
        "generationConfig": {
            "temperature": 0.65,
            "maxOutputTokens": max_tokens,
            "responseMimeType": "application/json"
        }
    }

    response = session.post(
        url,
        params={"key": GEMINI_API_KEY},
        json=payload,
        timeout=180
    )

    if response.status_code != 200:
        # Do not print the request URL because it contains the key.
        logging.error(
            "Gemini API returned HTTP %s: %s",
            response.status_code,
            response.text[:1000]
        )

        if response.status_code == 429:
            raise RuntimeError(
                "Gemini API rate limit or quota reached."
            )

        if response.status_code in (401, 403):
            raise RuntimeError(
                "Gemini API authentication or permission failed. "
                "Check the API key and model access."
            )

        raise RuntimeError(
            f"Gemini API failed with HTTP {response.status_code}."
        )

    data = response.json()

    candidates = data.get("candidates", [])

    if not candidates:
        raise RuntimeError(
            "Gemini returned no usable response."
        )

    parts = (
        candidates[0]
        .get("content", {})
        .get("parts", [])
    )

    text_parts = [
        part.get("text", "")
        for part in parts
        if part.get("text")
    ]

    result = "\n".join(text_parts).strip()

    if not result:
        raise RuntimeError(
            "Gemini returned an empty response."
        )

    return result


def parse_json_response(text):
    """
    Parse JSON, including a response accidentally wrapped
    in Markdown code fences.
    """

    cleaned = text.strip()

    cleaned = re.sub(
        r"^```(?:json)?\s*",
        "",
        cleaned,
        flags=re.IGNORECASE
    )

    cleaned = re.sub(
        r"\s*```$",
        "",
        cleaned
    )

    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        pass

    # Try extracting a JSON object from surrounding text.
    start = cleaned.find("{")
    end = cleaned.rfind("}")

    if start != -1 and end > start:
        return json.loads(cleaned[start:end + 1])

    raise ValueError(
        "Gemini did not return valid JSON."
    )


# ==========================================================
# NEWS COLLECTION
# ==========================================================

def fetch_current_news():
    """
    Collect recent news from Google News RSS.
    RSS headlines and source links are preserved.
    """

    queries = [
        "India government science economy education when:7d",
        "India national news current affairs when:7d"
    ]

    articles = []
    seen_links = set()

    for query in queries:
        rss_url = (
            "https://news.google.com/rss/search?q="
            + quote(query)
            + "&hl=en-IN&gl=IN&ceid=IN:en"
        )

        try:
            feed = feedparser.parse(rss_url)

            for entry in feed.entries:
                link = entry.get("link", "").strip()
                title = entry.get("title", "").strip()

                if not title or not link:
                    continue

                if link in seen_links:
                    continue

                seen_links.add(link)

                published = entry.get(
                    "published",
                    TODAY_TEXT
                )

                summary = entry.get(
                    "summary",
                    ""
                )

                # Remove HTML markup from RSS descriptions.
                summary = re.sub(
                    r"<[^>]+>",
                    " ",
                    summary
                )

                summary = html.unescape(summary)
                summary = re.sub(
                    r"\s+",
                    " ",
                    summary
                ).strip()

                source = ""

                source_info = entry.get("source", {})

                if isinstance(source_info, dict):
                    source = source_info.get(
                        "title",
                        ""
                    )

                articles.append({
                    "title": title,
                    "date": published,
                    "source": source,
                    "link": link,
                    "description": summary
                })

        except Exception:
            logging.exception(
                "Could not read one RSS news feed."
            )

    # Avoid duplicate articles.
    return articles[:20]


def summarize_news(articles):
    """
    Produce readable summaries based on supplied RSS content.
    Headlines and links remain tied to the original sources.
    """

    if not articles:
        return []

    prompt = f"""
You are preparing an Indian competitive-exam current affairs
digest for {TODAY_TEXT}.

The supplied records are news collected from RSS feeds.

Return ONLY valid JSON in this format:

{{
  "items": [
    {{
      "summary": "A concise, factual summary in 2-3 sentences."
    }}
  ]
}}

Rules:
1. Return exactly one summary for each supplied record.
2. Preserve the original order.
3. Use only facts supported by the supplied headline
   and description.
4. Never invent dates, numbers, names, or events.
5. If details are insufficient, say only what the headline
   supports.
6. Use clear English suitable for Indian competitive exams.
7. Do not invent exam facts or give political opinions.

NEWS RECORDS:
{json.dumps(articles, ensure_ascii=False)}
"""

    try:
        raw = gemini_generate(
            prompt,
            max_tokens=6000
        )

        data = parse_json_response(raw)

        summaries = data.get("items", [])

        for index, article in enumerate(articles):
            if index < len(summaries):
                article["ai_summary"] = summaries[index].get(
                    "summary",
                    article["description"]
                )
            else:
                article["ai_summary"] = article["description"]

    except Exception:
        logging.exception(
            "AI news summaries failed; using RSS descriptions."
        )

        for article in articles:
            article["ai_summary"] = (
                article["description"]
                or "See the linked source for further details."
            )

    return articles


# ==========================================================
# QUESTION GENERATION
# ==========================================================

def generate_question_batch(
    subject,
    topic,
    start_number,
    count=25
):
    """
    Generate a batch of MCQs with answers and explanations.

    Smaller batches reduce the risk of responses being
    truncated when generating detailed solutions.
    """

    if subject == "Static GK":
        subject_instructions = """
Create accurate competitive-exam general knowledge questions.
Focus on established facts, standard exam knowledge and
unambiguous answers.
Avoid obscure facts and disputed claims.
"""

    elif subject == "Reasoning":
        subject_instructions = """
Create logical reasoning MCQs suitable for Indian competitive
examinations.

Use a varied selection appropriate to the topic, such as:
analogy, classification, number series, alphabet series,
coding-decoding, directions, blood relations, ranking,
syllogisms, and logical patterns.

Every question must have exactly one correct option.
Make sure each puzzle contains enough information to solve it.
Explain the reasoning step by step.
"""

    else:
        subject_instructions = """
Create arithmetic MCQs suitable for Indian competitive
examinations.

Include formulas, calculations, shortcuts where appropriate,
and step-by-step worked solutions.

Verify all calculations and ensure the stated correct option
matches the actual answer.
Use clear numbers and unambiguous units.
"""

    prompt = f"""
You are an experienced Indian competitive-exam question setter.

DATE: {TODAY_TEXT}
SUBJECT: {subject}
TOPIC: {topic}
QUESTION NUMBERS: {start_number} to {start_number + count - 1}

{subject_instructions}

Return ONLY valid JSON with this exact structure:

{{
  "questions": [
    {{
      "question": "Full question text",
      "options": {{
        "A": "First option",
        "B": "Second option",
        "C": "Third option",
        "D": "Fourth option"
      }},
      "answer": "A",
      "explanation": "Detailed explanation of the correct answer.",
      "formula": "Relevant formula or method, or an empty string."
    }}
  ]
}}

STRICT RULES:
1. Generate exactly {count} questions.
2. Every question must have exactly four options: A, B, C, D.
3. The answer field must contain only A, B, C or D.
4. The correct answer must actually match the selected option.
5. Do not repeat questions within this batch.
6. Avoid unnecessarily repetitive templates.
7. Explanations must teach the learner, not merely repeat the answer.
8. For arithmetic, show the calculation and formula where useful.
9. For reasoning, explain the logical steps.
10. For Static GK, explain why the answer is correct.
11. Do not include questions outside the specified topic.
12. Do not include Markdown or text outside the JSON.
13. Use clear English.
14. Create a varied set for the specified date.
"""

    raw = gemini_generate(
        prompt,
        max_tokens=12000
    )

    data = parse_json_response(raw)

    questions = data.get("questions", [])

    if not isinstance(questions, list):
        raise ValueError(
            f"{subject}: questions must be a list."
        )

    if len(questions) != count:
        raise ValueError(
            f"{subject}: expected {count} questions, "
            f"received {len(questions)}."
        )

    validated = []

    for index, question in enumerate(questions):
        if not isinstance(question, dict):
            raise ValueError(
                f"{subject}: invalid question at position {index + 1}."
            )

        text = str(question.get("question", "")).strip()
        options = question.get("options", {})
        answer = str(
            question.get("answer", "")
        ).strip().upper()

        explanation = str(
            question.get("explanation", "")
        ).strip()

        formula = str(
            question.get("formula", "")
        ).strip()

        if not text or not explanation:
            raise ValueError(
                f"{subject}: missing question or explanation."
            )

        if not isinstance(options, dict):
            raise ValueError(
                f"{subject}: invalid options."
            )

        options = {
            letter: str(options.get(letter, "")).strip()
            for letter in ("A", "B", "C", "D")
        }

        if not all(options.values()):
            raise ValueError(
                f"{subject}: one or more options are missing."
            )

        if answer not in ("A", "B", "C", "D"):
            raise ValueError(
                f"{subject}: invalid answer key."
            )

        validated.append({
            "question": text,
            "options": options,
            "answer": answer,
            "explanation": explanation,
            "formula": formula
        })

    return validated


def generate_questions(subject, topic, total=50):
    """
    Generate 50 questions using two batches of 25.
    """

    result = []

    for start in range(1, total + 1, 25):
        count = min(25, total - start + 1)

        logging.info(
            "Generating %s questions %s-%s...",
            subject,
            start,
            start + count - 1
        )

        batch = generate_question_batch(
            subject=subject,
            topic=topic,
            start_number=start,
            count=count
        )

        result.extend(batch)

    if len(result) != total:
        raise RuntimeError(
            f"{subject}: expected {total} questions; "
            f"got {len(result)}."
        )

    return result


# ==========================================================
# PDF DESIGN
# ==========================================================

def make_styles():
    styles = getSampleStyleSheet()

    styles.add(ParagraphStyle(
        name="CoverTitle",
        parent=styles["Title"],
        fontName="Helvetica-Bold",
        fontSize=23,
        leading=29,
        alignment=TA_CENTER,
        textColor=colors.HexColor("#17365D"),
        spaceAfter=8
    ))

    styles.add(ParagraphStyle(
        name="SubtitleCustom",
        parent=styles["Normal"],
        fontSize=10,
        leading=15,
        alignment=TA_CENTER,
        textColor=colors.HexColor("#526579"),
        spaceAfter=14
    ))

    styles.add(ParagraphStyle(
        name="SectionCustom",
        parent=styles["Heading2"],
        fontName="Helvetica-Bold",
        fontSize=15,
        leading=19,
        textColor=colors.HexColor("#17365D"),
        spaceBefore=8,
        spaceAfter=9
    ))

    styles.add(ParagraphStyle(
        name="QuestionCustom",
        parent=styles["Normal"],
        fontName="Helvetica-Bold",
        fontSize=10.5,
        leading=15,
        spaceBefore=7,
        spaceAfter=5
    ))

    styles.add(ParagraphStyle(
        name="OptionCustom",
        parent=styles["Normal"],
        fontSize=9.5,
        leading=13,
        leftIndent=10,
        spaceAfter=2
    ))

    styles.add(ParagraphStyle(
        name="ExplanationCustom",
        parent=styles["Normal"],
        fontSize=9.5,
        leading=14,
        leftIndent=5,
        spaceAfter=8
    ))

    styles.add(ParagraphStyle(
        name="NewsTitle",
        parent=styles["Normal"],
        fontName="Helvetica-Bold",
        fontSize=11,
        leading=15,
        textColor=colors.HexColor("#17365D"),
        spaceAfter=4
    ))

    styles.add(ParagraphStyle(
        name="SmallCustom",
        parent=styles["Normal"],
        fontSize=8.5,
        leading=12,
        textColor=colors.HexColor("#555555")
    ))

    return styles


STYLES = make_styles()


def safe_paragraph(text, style):
    """
    Escape text before passing it to ReportLab's Paragraph.
    """

    return Paragraph(
        escape(str(text)).replace("\n", "<br/>"),
        style
    )


def add_page_design(canvas, doc):
    """
    Add a coloured header and footer to every page.
    """

    canvas.saveState()

    page_width, page_height = A4

    canvas.setFillColor(
        colors.HexColor("#17365D")
    )

    canvas.rect(
        0,
        page_height - 10 * mm,
        page_width,
        10 * mm,
        fill=1,
        stroke=0
    )

    canvas.setFillColor(colors.white)
    canvas.setFont("Helvetica-Bold", 8.5)

    canvas.drawString(
        15 * mm,
        page_height - 6.5 * mm,
        "DAILY STUDY HUB"
    )

    canvas.setStrokeColor(
        colors.HexColor("#D9E2F3")
    )

    canvas.line(
        15 * mm,
        14 * mm,
        page_width - 15 * mm,
        14 * mm
    )

    canvas.setFillColor(
        colors.HexColor("#526579")
    )

    canvas.setFont("Helvetica", 8)

    canvas.drawString(
        15 * mm,
        9 * mm,
        f"Generated: {TODAY_TEXT}"
    )

    canvas.drawRightString(
        page_width - 15 * mm,
        9 * mm,
        f"Page {doc.page}"
    )

    canvas.restoreState()


def build_pdf(filename, title, subtitle, story):
    path = OUTPUT_DIR / filename

    doc = SimpleDocTemplate(
        str(path),
        pagesize=A4,
        rightMargin=16 * mm,
        leftMargin=16 * mm,
        topMargin=18 * mm,
        bottomMargin=20 * mm,
        title=title,
        author="Daily Study Bot"
    )

    full_story = [
        Spacer(1, 5 * mm),
        Paragraph(title, STYLES["CoverTitle"]),
        Paragraph(subtitle, STYLES["SubtitleCustom"]),
        Spacer(1, 2 * mm),
    ]

    full_story.extend(story)

    doc.build(
        full_story,
        onFirstPage=add_page_design,
        onLaterPages=add_page_design
    )

    logging.info("Created PDF: %s", path)

    return path


# ==========================================================
# CURRENT AFFAIRS PDF
# ==========================================================

def create_current_affairs_pdf():
    articles = fetch_current_news()

    if not articles:
        raise RuntimeError(
            "No current-affairs news could be retrieved."
        )

    articles = summarize_news(articles)

    story = [
        Paragraph(
            "Today's Current Affairs",
            STYLES["SectionCustom"]
        ),
        safe_paragraph(
            "Read the news summaries and open the original "
            "source links for further details.",
            STYLES["Normal"]
        ),
        Spacer(1, 8)
    ]

    for number, article in enumerate(articles, start=1):
        title = article.get("title", "News item")
        date = article.get("date", TODAY_TEXT)
        source = article.get("source", "")
        summary = article.get(
            "ai_summary",
            article.get("description", "")
        )
        link = article.get("link", "")

        if not summary:
            summary = (
                "Open the original source for more information."
            )

        block = [
            Paragraph(
                f"{number}. {escape(title)}",
                STYLES["NewsTitle"]
            ),
            safe_paragraph(
                f"Date: {date}",
                STYLES["SmallCustom"]
            ),
        ]

        if source:
            block.append(
                safe_paragraph(
                    f"Source: {source}",
                    STYLES["SmallCustom"]
                )
            )

        block.append(
            safe_paragraph(
                summary,
                STYLES["Normal"]
            )
        )

        if link:
            safe_url = html.escape(link, quote=True)

            block.append(
                Paragraph(
                    f'<link href="{safe_url}" '
                    'color="#0563C1">Open original news article</link>',
                    STYLES["SmallCustom"]
                )
            )

        block.append(Spacer(1, 10))

        story.append(
            KeepTogether(block)
        )

    return build_pdf(
        "01_Daily_Current_Affairs.pdf",
        "CURRENT AFFAIRS",
        f"Daily News Digest | {TODAY_TEXT}",
        story
    )


# ==========================================================
# MCQ PDF
# ==========================================================

def create_mcq_pdf(
    filename,
    title,
    subtitle,
    questions
):
    story = []

    story.append(
        Paragraph(
            "Instructions",
            STYLES["SectionCustom"]
        )
    )

    story.append(
        safe_paragraph(
            "Attempt all questions before checking the answer "
            "key and explanations at the end.",
            STYLES["Normal"]
        )
    )

    story.append(Spacer(1, 8))

    # Questions first: no answers shown in this section.
    story.append(
        Paragraph(
            "PART A — QUESTIONS",
            STYLES["SectionCustom"]
        )
    )

    for index, item in enumerate(questions, start=1):
        block = [
            Paragraph(
                f"Q{index}. {escape(item['question'])}",
                STYLES["QuestionCustom"]
            )
        ]

        for letter in ("A", "B", "C", "D"):
            option_text = item["options"][letter]

            block.append(
                Paragraph(
                    f"<b>{letter}.</b> {escape(option_text)}",
                    STYLES["OptionCustom"]
                )
            )

        block.append(Spacer(1, 5))

        story.append(
            KeepTogether(block)
        )

    # Answers and solutions start after the question section.
    story.append(PageBreak())

    story.append(
        Paragraph(
            "PART B — ANSWER KEY",
            STYLES["SectionCustom"]
        )
    )

    answer_rows = [
        [
            safe_paragraph("<b>Question</b>", STYLES["SmallCustom"]),
            safe_paragraph("<b>Answer</b>", STYLES["SmallCustom"])
        ]
    ]

    for index, item in enumerate(questions, start=1):
        answer_rows.append([
            str(index),
            item["answer"]
        ])

    answer_table = Table(
        answer_rows,
        colWidths=[35 * mm, 35 * mm],
        repeatRows=1
    )

    answer_table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0),
         colors.HexColor("#D9EAF7")),
        ("TEXTCOLOR", (0, 0), (-1, 0),
         colors.HexColor("#17365D")),
        ("GRID", (0, 0), (-1, -1), 0.4,
         colors.HexColor("#CCD6E0")),
        ("ALIGN", (0, 0), (-1, -1), "CENTER"),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("FONTSIZE", (0, 1), (-1, -1), 9),
        ("TOPPADDING", (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
    ]))

    story.append(answer_table)
    story.append(Spacer(1, 12))

    story.append(
        Paragraph(
            "PART C — DETAILED SOLUTIONS",
            STYLES["SectionCustom"]
        )
    )

    for index, item in enumerate(questions, start=1):
        correct_option = item["options"][item["answer"]]

        block = [
            Paragraph(
                f"Q{index}. Answer: {item['answer']} — "
                f"{escape(correct_option)}",
                STYLES["QuestionCustom"]
            )
        ]

        formula = item.get("formula", "").strip()

        if formula:
            block.append(
                Paragraph(
                    f"<b>Formula / Method:</b> "
                    f"{escape(formula)}",
                    STYLES["ExplanationCustom"]
                )
            )

        block.append(
            Paragraph(
                f"<b>Explanation:</b> "
                f"{escape(item['explanation'])}",
                STYLES["ExplanationCustom"]
            )
        )

        block.append(Spacer(1, 5))

        story.append(
            KeepTogether(block)
        )

    return build_pdf(
        filename,
        title,
        subtitle,
        story
    )


# ==========================================================
# TELEGRAM DELIVERY
# ==========================================================

def send_telegram_message(message):
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        raise RuntimeError(
            "Telegram bot token or chat ID is missing."
        )

    url = (
        f"https://api.telegram.org/"
        f"bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    )

    response = session.post(
        url,
        data={
            "chat_id": TELEGRAM_CHAT_ID,
            "text": message
        },
        timeout=30
    )

    if response.status_code != 200:
        logging.error(
            "Telegram message failed: %s",
            response.text[:500]
        )

        response.raise_for_status()


def send_pdf_to_telegram(pdf_path):
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        raise RuntimeError(
            "Telegram bot token or chat ID is missing."
        )

    url = (
        f"https://api.telegram.org/"
        f"bot{TELEGRAM_BOT_TOKEN}/sendDocument"
    )

    caption = (
        f"📚 Daily Study PDF\n"
        f"📅 {TODAY_TEXT}\n"
        f"📄 {pdf_path.name}"
    )

    with open(pdf_path, "rb") as pdf_file:
        response = session.post(
            url,
            data={
                "chat_id": TELEGRAM_CHAT_ID,
                "caption": caption
            },
            files={
                "document": (
                    pdf_path.name,
                    pdf_file,
                    "application/pdf"
                )
            },
            timeout=120
        )

    if response.status_code != 200:
        logging.error(
            "PDF upload failed: %s",
            response.text[:500]
        )

        response.raise_for_status()

    logging.info(
        "Sent to Telegram: %s",
        pdf_path.name
    )


# ==========================================================
# MAIN PROGRAM
# ==========================================================

def main():
    logging.info("======================================")
    logging.info("DAILY STUDY BOT STARTING")
    logging.info("Date: %s", TODAY_TEXT)
    logging.info("Model: %s", GEMINI_MODEL)
    logging.info("Static GK topic: %s", GK_TOPIC)
    logging.info("Arithmetic topic: %s", ARITHMETIC_TOPIC)
    logging.info("======================================")

    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        raise RuntimeError(
            "Missing Telegram GitHub Secrets."
        )

    pdf_files = []

    try:
        # 1. Current affairs
        logging.info("Preparing current-affairs PDF...")

        pdf_files.append(
            create_current_affairs_pdf()
        )

        # 2. Static GK
        logging.info("Generating Static GK questions...")

        gk_questions = generate_questions(
            subject="Static GK",
            topic=GK_TOPIC,
            total=50
        )

        pdf_files.append(
            create_mcq_pdf(
                filename="02_Static_GK.pdf",
                title="STATIC GENERAL KNOWLEDGE",
                subtitle=(
                    f"{GK_TOPIC} | 50 MCQs | {TODAY_TEXT}"
                ),
                questions=gk_questions
            )
        )

        # 3. Reasoning
        logging.info("Generating reasoning questions...")

        reasoning_questions = generate_questions(
            subject="Reasoning",
            topic=(
                "Mixed reasoning: series, analogy, "
                "classification, coding-decoding, directions, "
                "blood relations, ranking and logical reasoning"
            ),
            total=50
        )

        pdf_files.append(
            create_mcq_pdf(
                filename="03_Reasoning_Practice.pdf",
                title="REASONING PRACTICE",
                subtitle=(
                    f"50 MCQs | Easy to Difficult | {TODAY_TEXT}"
                ),
                questions=reasoning_questions
            )
        )

        # 4. Arithmetic
        logging.info("Generating arithmetic questions...")

        arithmetic_questions = generate_questions(
            subject="Arithmetic",
            topic=ARITHMETIC_TOPIC,
            total=50
        )

        pdf_files.append(
            create_mcq_pdf(
                filename="04_Arithmetic_Practice.pdf",
                title="ARITHMETIC PRACTICE",
                subtitle=(
                    f"{ARITHMETIC_TOPIC} | 50 MCQs | {TODAY_TEXT}"
                ),
                questions=arithmetic_questions
            )
        )

        # Send PDFs only after all four have been created.
        logging.info("All PDFs generated successfully.")

        send_telegram_message(
            f"🎯 Daily Study Pack — {TODAY_TEXT}\n\n"
            f"Your four study PDFs are ready!\n\n"
            f"📰 Current Affairs: recent news digest\n"
            f"🌍 Static GK: {GK_TOPIC}\n"
            f"🧠 Reasoning: 50 questions\n"
            f"➗ Arithmetic: {ARITHMETIC_TOPIC}\n\n"
            f"Answers and explanations are included."
        )

        for pdf_path in pdf_files:
            send_pdf_to_telegram(pdf_path)

        send_telegram_message(
            "✅ All four PDFs have been delivered successfully!"
        )

        logging.info("BOT COMPLETED SUCCESSFULLY.")

    except Exception as error:
        logging.exception(
            "The study bot failed."
        )

        # Notify Telegram about the failure if possible.
        try:
            send_telegram_message(
                "⚠️ Daily Study Bot encountered an error.\n"
                "Please check the GitHub Actions log.\n"
                f"Error: {str(error)[:700]}"
            )
        except Exception:
            logging.exception(
                "Could not send the error notification."
            )

        raise


if __name__ == "__main__":
    main()
