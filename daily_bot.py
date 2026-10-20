import os
import json
import time
import logging
import random
import re
import html
from datetime import datetime, timezone
from urllib.parse import quote_plus
from xml.etree import ElementTree

import requests
import feedparser

from google import genai
from google.genai import types

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER
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

# =========================================================
# CONFIGURATION
# =========================================================

TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID", "")
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "")

# Change this if your account does not have access to this model.
GEMINI_MODEL = os.environ.get(
    "GEMINI_MODEL",
    "gemini-2.5-flash"
)

OUTPUT_DIR = "daily_pdfs"
os.makedirs(OUTPUT_DIR, exist_ok=True)

TODAY = datetime.now().strftime("%d %B %Y")
TODAY_ID = datetime.now().strftime("%Y%m%d")

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s: %(message)s",
)

if not TELEGRAM_BOT_TOKEN:
    raise RuntimeError("Missing TELEGRAM_BOT_TOKEN secret.")

if not TELEGRAM_CHAT_ID:
    raise RuntimeError("Missing TELEGRAM_CHAT_ID secret.")

if not GEMINI_API_KEY:
    raise RuntimeError("Missing GEMINI_API_KEY secret.")

client = genai.Client(api_key=GEMINI_API_KEY)

# =========================================================
# PDF DESIGN
# =========================================================

PAGE_WIDTH, PAGE_HEIGHT = A4

NAVY = colors.HexColor("#17365D")
BLUE = colors.HexColor("#2463A6")
TEAL = colors.HexColor("#008C95")
PURPLE = colors.HexColor("#7542A6")
ORANGE = colors.HexColor("#D97904")
LIGHT_BLUE = colors.HexColor("#EAF3FB")
LIGHT_TEAL = colors.HexColor("#E6F6F5")
LIGHT_PURPLE = colors.HexColor("#F1EAF8")
LIGHT_ORANGE = colors.HexColor("#FFF2DF")
DARK = colors.HexColor("#263238")
GREY = colors.HexColor("#637381")

styles = getSampleStyleSheet()

styles.add(ParagraphStyle(
    name="CoverTitle",
    parent=styles["Title"],
    fontName="Helvetica-Bold",
    fontSize=23,
    leading=29,
    textColor=colors.white,
    alignment=TA_CENTER,
    spaceAfter=8,
))

styles.add(ParagraphStyle(
    name="CoverSubtitle",
    parent=styles["Normal"],
    fontName="Helvetica",
    fontSize=11,
    leading=16,
    textColor=colors.white,
    alignment=TA_CENTER,
))

styles.add(ParagraphStyle(
    name="SectionTitle",
    parent=styles["Heading2"],
    fontName="Helvetica-Bold",
    fontSize=13,
    leading=17,
    textColor=NAVY,
    spaceBefore=10,
    spaceAfter=7,
))

styles.add(ParagraphStyle(
    name="Question",
    parent=styles["Normal"],
    fontName="Helvetica-Bold",
    fontSize=10,
    leading=14,
    textColor=DARK,
    spaceAfter=5,
))

styles.add(ParagraphStyle(
    name="Option",
    parent=styles["Normal"],
    fontName="Helvetica",
    fontSize=9,
    leading=12,
    leftIndent=10,
    textColor=DARK,
    spaceAfter=2,
))

styles.add(ParagraphStyle(
    name="Explanation",
    parent=styles["Normal"],
    fontName="Helvetica",
    fontSize=9,
    leading=13,
    textColor=colors.HexColor("#34495E"),
    spaceBefore=4,
    spaceAfter=3,
))

styles.add(ParagraphStyle(
    name="SmallText",
    parent=styles["Normal"],
    fontName="Helvetica",
    fontSize=8,
    leading=11,
    textColor=GREY,
))

styles.add(ParagraphStyle(
    name="NewsHeadline",
    parent=styles["Heading3"],
    fontName="Helvetica-Bold",
    fontSize=11,
    leading=15,
    textColor=NAVY,
    spaceBefore=7,
    spaceAfter=4,
))

def safe_text(value):
    """Escape text before putting it inside a ReportLab Paragraph."""
    return html.escape(str(value or ""))

def make_cover(title, subtitle, accent):
    banner = Table(
        [[
            Paragraph(safe_text(title), styles["CoverTitle"]),
        ], [
            Paragraph(safe_text(subtitle), styles["CoverSubtitle"]),
        ]],
        colWidths=[174 * mm],
    )

    banner.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), accent),
        ("BOX", (0, 0), (-1, -1), 0, accent),
        ("LEFTPADDING", (0, 0), (-1, -1), 12),
        ("RIGHTPADDING", (0, 0), (-1, -1), 12),
        ("TOPPADDING", (0, 0), (-1, 0), 20),
        ("BOTTOMPADDING", (0, -1), (-1, -1), 20),
    ]))

    return [
        Spacer(1, 8 * mm),
        banner,
        Spacer(1, 5 * mm),
        Paragraph(
            f"<b>Date:</b> {safe_text(TODAY)}",
            styles["SmallText"],
        ),
        Spacer(1, 5 * mm),
    ]

def add_page_number(canvas, document):
    canvas.saveState()

    canvas.setStrokeColor(colors.HexColor("#D8E0E8"))
    canvas.line(
        18 * mm,
        15 * mm,
        PAGE_WIDTH - 18 * mm,
        15 * mm,
    )

    canvas.setFont("Helvetica", 8)
    canvas.setFillColor(GREY)

    canvas.drawString(
        18 * mm,
        9 * mm,
        "Daily Learning PDFs",
    )

    canvas.drawRightString(
        PAGE_WIDTH - 18 * mm,
        9 * mm,
        f"Page {document.page}",
    )

    canvas.restoreState()

def create_pdf(filename, story):
    path = os.path.join(OUTPUT_DIR, filename)

    document = SimpleDocTemplate(
        path,
        pagesize=A4,
        rightMargin=18 * mm,
        leftMargin=18 * mm,
        topMargin=17 * mm,
        bottomMargin=22 * mm,
        title=filename.replace("_", " "),
        author="Daily Learning Bot",
    )

    document.build(
        story,
        onFirstPage=add_page_number,
        onLaterPages=add_page_number,
    )

    logging.info("Created PDF: %s", path)
    return path

# =========================================================
# GEMINI GENERATION
# =========================================================

def generate_json(prompt, retries=3):
    """
    Ask Gemini for JSON and validate the response.
    Retries transient errors with a short delay.
    """

    for attempt in range(retries):
        try:
            response = client.models.generate_content(
                model=GEMINI_MODEL,
                contents=prompt,
                config=types.GenerateContentConfig(
                    response_mime_type="application/json",
                    temperature=0.7,
                ),
            )

            text = response.text

            if not text:
                raise ValueError("Gemini returned an empty response.")

            # Remove code fences if a model returns them.
            text = re.sub(
                r"^\s*```(?:json)?\s*|\s*```\s*$",
                "",
                text,
                flags=re.IGNORECASE,
            ).strip()

            return json.loads(text)

        except Exception as exc:
            logging.warning(
                "Gemini attempt %s/%s failed: %s",
                attempt + 1,
                retries,
                exc,
            )

            if attempt == retries - 1:
                raise

            time.sleep(3 * (attempt + 1))

    raise RuntimeError("Gemini generation failed.")

# =========================================================
# CURRENT AFFAIRS NEWS
# =========================================================

NEWS_SEARCHES = [
    "India national news",
    "India government policy economy",
    "science technology India",
    "international news",
    "environment climate",
    "sports India",
]

def fetch_news():
    """
    Retrieve recent news entries from Google News RSS.
    News dates and source URLs come from the feed.
    """

    collected = []
    seen = set()

    for query in NEWS_SEARCHES:
        url = (
            "https://news.google.com/rss/search?q="
            + quote_plus(query)
            + "&hl=en-IN&gl=IN&ceid=IN:en"
        )

        try:
            feed = feedparser.parse(url)

            for entry in feed.entries[:12]:
                title = entry.get("title", "").strip()
                link = entry.get("link", "").strip()

                if not title or not link or link in seen:
                    continue

                seen.add(link)

                published = entry.get(
                    "published",
                    entry.get("updated", "Date not supplied"),
                )

                source = "News source"

                if " - " in title:
                    title, source = title.rsplit(" - ", 1)

                collected.append({
                    "title": title.strip(),
                    "source": source.strip(),
                    "url": link,
                    "published": published,
                })

        except Exception as exc:
            logging.warning("News feed failed: %s", exc)

    return collected[:35]

def build_current_affairs():
    news = fetch_news()

    if not news:
        raise RuntimeError(
            "No current-affairs news could be retrieved. "
            "Check the RSS connection and try again."
        )

    # Send the actual feed data to Gemini. Instruct it not to
    # invent facts, dates, or source links.
    prompt = f"""
You are preparing a factual daily current-affairs briefing
for Indian competitive-exam candidates.

Today's date is {TODAY}.

Use ONLY the supplied news feed entries.

Return valid JSON in this format:
{{
  "title": "Daily Current Affairs",
  "items": [
    {{
      "headline": "Short headline",
      "category": "National/International/Economy/Science/
                   Environment/Sports/Other",
      "date": "Publication date as supplied",
      "summary": "A clear factual summary in 2-4 sentences",
      "exam_point": "One useful exam-relevant takeaway",
      "source": "Source name",
      "url": "Exact supplied URL"
    }}
  ]
}}

Requirements:
- Select up to 20 distinct, useful stories.
- Prefer entries that appear recent and relevant.
- Do not claim that an old story happened today.
- Preserve the supplied source URL exactly.
- Do not invent dates, statistics, names, or quotations.
- If a detail is uncertain, omit it.
- Do not add stories that are not in the feed.
- Summaries must be original and concise.
- Include a variety of categories where available.

SUPPLIED FEED ENTRIES:
{json.dumps(news, ensure_ascii=False)}
"""

    result = generate_json(prompt)
    items = result.get("items", [])

    if not isinstance(items, list) or not items:
        raise RuntimeError(
            "Gemini did not return usable current-affairs items."
        )

    valid_urls = {item["url"] for item in news}

    cleaned = []

    for item in items:
        url = str(item.get("url", "")).strip()

        # Never accept a source link invented by the model.
        if url not in valid_urls:
            continue

        cleaned.append({
            "headline": str(item.get("headline", "Untitled")),
            "category": str(item.get("category", "General")),
            "date": str(item.get("date", "Date not supplied")),
            "summary": str(item.get("summary", "")),
            "exam_point": str(item.get("exam_point", "")),
            "source": str(item.get("source", "News source")),
            "url": url,
        })

    if not cleaned:
        raise RuntimeError(
            "Gemini returned no stories with valid source links."
        )

    return cleaned[:20]

def create_current_affairs_pdf():
    items = build_current_affairs()

    story = make_cover(
        "DAILY CURRENT AFFAIRS",
        "News summaries • Exam takeaways • Source links",
        NAVY,
    )

    story.append(Paragraph(
        "Today's News Briefing",
        styles["SectionTitle"],
    ))

    story.append(Paragraph(
        "Summaries are based on retrieved RSS entries. "
        "Check the linked original source for full details.",
        styles["SmallText"],
    ))

    for index, item in enumerate(items, 1):
        block = [
            Paragraph(
                f"{index}. {safe_text(item['headline'])}",
                styles["NewsHeadline"],
            ),
            Paragraph(
                f"<b>Category:</b> {safe_text(item['category'])}"
                f" &nbsp; | &nbsp; "
                f"<b>Published:</b> {safe_text(item['date'])}",
                styles["SmallText"],
            ),
            Spacer(1, 3),
            Paragraph(
                safe_text(item["summary"]),
                styles["Explanation"],
            ),
            Paragraph(
                f"<b>Exam takeaway:</b> "
                f"{safe_text(item['exam_point'])}",
                styles["Explanation"],
            ),
            Paragraph(
                f"<b>Source:</b> {safe_text(item['source'])}",
                styles["SmallText"],
            ),
            Paragraph(
                f'<link href="{html.escape(item["url"], quote=True)}">'
                f'<font color="#2463A6">Open original source</font>'
                f'</link>',
                styles["SmallText"],
            ),
            Spacer(1, 6),
        ]

        story.append(KeepTogether(block))

    return create_pdf(
        f"current_affairs_{TODAY_ID}.pdf",
        story,
    )

# =========================================================
# MCQ QUESTION GENERATION
# =========================================================

SUBJECTS = {
    "static_gk": {
        "title": "STATIC GENERAL KNOWLEDGE",
        "subtitle": "50 AI-generated MCQs • Answers • Explanations",
        "accent": TEAL,
        "light": LIGHT_TEAL,
        "instruction": """
Generate static general knowledge questions suitable for
Indian competitive exams such as SSC.

Cover a balanced range of:
- Indian polity and Constitution
- Indian and world geography
- Indian history and culture
- Basic economics
- General science
- Important institutions and static facts

Avoid current-affairs questions because those belong in the
separate current-affairs PDF.
Avoid ambiguous questions and disputed facts.
""",
    },
    "reasoning": {
        "title": "REASONING PRACTICE",
        "subtitle": "50 MCQs • Answers • Step-by-step solutions",
        "accent": PURPLE,
        "light": LIGHT_PURPLE,
        "instruction": """
Generate a balanced reasoning practice set suitable for SSC.

Include different types, for example:
- Number and letter series
- Analogy and classification
- Coding and decoding
- Direction sense
- Blood relations
- Ranking and order
- Syllogisms
- Mathematical operations
- Alphabet reasoning
- Simple logical problems

Use clear wording and make sure every question has exactly
one correct answer.
Provide a short step-by-step explanation.
Do not use questions requiring missing diagrams or images.
""",
    },
    "arithmetic": {
        "title": "ARITHMETIC PRACTICE",
        "subtitle": "50 MCQs • Formulas • Worked solutions",
        "accent": ORANGE,
        "light": LIGHT_ORANGE,
        "instruction": """
Generate arithmetic MCQs suitable for SSC competitive exams.

Cover a balanced range of:
- Number system
- Simplification
- HCF and LCM
- Fractions and decimals
- Percentages
- Ratio and proportion
- Average
- Profit, loss and discount
- Simple and compound interest
- Time and work
- Speed, time and distance
- Mensuration
- Basic algebra

For each question provide:
- Four options
- One correct answer
- The relevant formula or method
- A worked solution with calculations

Use sensible numbers and ensure the calculation and answer
are correct. Avoid advanced topics outside SSC-level arithmetic.
""",
    },
}

def generate_question_batch(subject_key, start_number, batch_size):
    subject = SUBJECTS[subject_key]

    prompt = f"""
You are an expert Indian competitive-exam question setter.

Create exactly {batch_size} original multiple-choice questions.

SUBJECT:
{subject["title"]}

GUIDELINES:
{subject["instruction"]}

Return ONLY valid JSON in this structure:
{{
  "questions": [
    {{
      "question": "Question text",
      "options": [
        "Option A",
        "Option B",
        "Option C",
        "Option D"
      ],
      "answer": "Exact text of the correct option",
      "explanation": "Clear explanation of the correct answer",
      "formula": "Relevant formula, or an empty string if not applicable",
      "topic": "Topic name"
    }}
  ]
}}

STRICT REQUIREMENTS:
- Generate exactly {batch_size} questions.
- All questions must be different within this batch.
- Every question must have exactly four distinct options.
- The answer must exactly match one option.
- Verify the answer before returning it.
- Explanations must support the stated answer.
- For arithmetic, show calculations and formulas.
- For reasoning, explain the logical steps.
- For GK, explain the relevant fact.
- Do not include question numbers.
- Do not include Markdown or commentary.
- Do not repeat any of these earlier question texts in this batch:
{json.dumps(getattr(generate_question_batch, "previous_questions", {}).get(subject_key, []), ensure_ascii=False)}
"""

    result = generate_json(prompt)
    questions = result.get("questions", [])

    if not isinstance(questions, list) or len(questions) != batch_size:
        raise ValueError(
            f"{subject_key}: expected {batch_size} questions, "
            f"received {len(questions) if isinstance(questions, list) else 'invalid data'}."
        )

    validated = []

    for q in questions:
        question = str(q.get("question", "")).strip()
        options = q.get("options", [])
        answer = str(q.get("answer", "")).strip()
        explanation = str(q.get("explanation", "")).strip()
        formula = str(q.get("formula", "")).strip()
        topic = str(q.get("topic", "General")).strip()

        if not question or not explanation:
            raise ValueError("A question or explanation is empty.")

        if not isinstance(options, list) or len(options) != 4:
            raise ValueError("Each question must have exactly four options.")

        options = [str(option).strip() for option in options]

        if len(set(options)) != 4:
            raise ValueError("A question has duplicate options.")

        # Case-insensitive matching tolerates small capitalization differences.
        matches = [
            option for option in options
            if option.casefold() == answer.casefold()
        ]

        if len(matches) != 1:
            raise ValueError(
                "The answer must exactly match one of the four options."
            )

        validated.append({
            "question": question,
            "options": options,
            "answer": matches[0],
            "explanation": explanation,
            "formula": formula,
            "topic": topic,
        })

    return validated

def generate_50_questions(subject_key):
    questions = []
    previous = []

    # Five batches help keep each Gemini response manageable.
    for batch_index in range(5):
        batch = generate_question_batch(
            subject_key=subject_key,
            start_number=batch_index * 10 + 1,
            batch_size=10,
        )

        for question in batch:
            # Avoid duplicates across batches.
            normalized = re.sub(
                r"\s+",
                " ",
                question["question"].lower(),
            ).strip()

            if any(
                normalized == re.sub(
                    r"\s+",
                    " ",
                    old.lower(),
                ).strip()
                for old in previous
            ):
                raise ValueError(
                    f"Gemini generated a repeated question in {subject_key}."
                )

            previous.append(question["question"])
            questions.append(question)

        generate_question_batch.previous_questions = getattr(
            generate_question_batch,
            "previous_questions",
            {},
        )
        generate_question_batch.previous_questions[subject_key] = previous

        logging.info(
            "%s: generated %s/50 questions",
            subject_key,
            len(questions),
        )

        time.sleep(1)

    if len(questions) != 50:
        raise RuntimeError(
            f"{subject_key}: expected 50 questions."
        )

    return questions

def create_mcq_pdf(subject_key):
    subject = SUBJECTS[subject_key]
    questions = generate_50_questions(subject_key)

    story = make_cover(
        subject["title"],
        subject["subtitle"],
        subject["accent"],
    )

    story.append(Paragraph(
        "Instructions",
        styles["SectionTitle"],
    ))

    story.append(Paragraph(
        "Attempt each question before checking the answer. "
        "Review the explanation carefully.",
        styles["Explanation"],
    ))

    story.append(Spacer(1, 5))

    for index, q in enumerate(questions, 1):
        block = []

        block.append(Paragraph(
            f"Q{index}. {safe_text(q['question'])}",
            styles["Question"],
        ))

        for option_index, option in enumerate(q["options"]):
            letter = chr(65 + option_index)

            block.append(Paragraph(
                f"{letter}. {safe_text(option)}",
                styles["Option"],
            ))

        answer_box = Table(
            [[
                Paragraph(
                    f"<b>Correct answer:</b> "
                    f"{safe_text(q['answer'])}",
                    styles["Explanation"],
                )
            ]],
            colWidths=[174 * mm],
        )

        answer_box.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, -1), subject["light"]),
            ("BOX", (0, 0), (-1, -1), 0.5, subject["accent"]),
            ("LEFTPADDING", (0, 0), (-1, -1), 7),
            ("RIGHTPADDING", (0, 0), (-1, -1), 7),
            ("TOPPADDING", (0, 0), (-1, -1), 4),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ]))

        block.append(Spacer(1, 4))
        block.append(answer_box)

        if subject_key == "arithmetic" and q["formula"]:
            block.append(Paragraph(
                f"<b>Formula:</b> {safe_text(q['formula'])}",
                styles["Explanation"],
            ))

        block.append(Paragraph(
            f"<b>Solution:</b> {safe_text(q['explanation'])}",
            styles["Explanation"],
        ))

        block.append(Paragraph(
            f"<font color='#637381'>Topic: "
            f"{safe_text(q['topic'])}</font>",
            styles["SmallText"],
        ))

        block.append(Spacer(1, 10))

        story.append(KeepTogether(block))

    return create_pdf(
        f"{subject_key}_{TODAY_ID}.pdf",
        story,
    )

# =========================================================
# TELEGRAM DELIVERY
# =========================================================

def send_telegram_document(path, caption):
    url = (
        f"https://api.telegram.org/"
        f"bot{TELEGRAM_BOT_TOKEN}/sendDocument"
    )

    with open(path, "rb") as file:
        response = requests.post(
            url,
            data={
                "chat_id": TELEGRAM_CHAT_ID,
                "caption": caption[:1024],
            },
            files={
                "document": (
                    os.path.basename(path),
                    file,
                    "application/pdf",
                ),
            },
            timeout=120,
        )

    try:
        result = response.json()
    except ValueError:
        result = {}

    if not response.ok or not result.get("ok"):
        raise RuntimeError(
            "Telegram upload failed: "
            + str(result or response.text)
        )

    logging.info("Sent %s to Telegram.", os.path.basename(path))

def main():
    logging.info("Starting daily Gemini PDF bot.")
    logging.info("Date: %s", TODAY)
    logging.info("Gemini model: %s", GEMINI_MODEL)

    # Generate each PDF separately so one failure is identifiable.
    tasks = [
        (
            "Current Affairs",
            create_current_affairs_pdf,
        ),
        (
            "Static GK",
            lambda: create_mcq_pdf("static_gk"),
        ),
        (
            "Reasoning",
            lambda: create_mcq_pdf("reasoning"),
        ),
        (
            "Arithmetic",
            lambda: create_mcq_pdf("arithmetic"),
        ),
    ]

    completed = []
    failures = []

    for label, task in tasks:
        try:
            logging.info("Generating %s PDF.", label)
            path = task()

            send_telegram_document(
                path,
                f"{label} | {TODAY}",
            )

            completed.append(label)

        except Exception as exc:
            logging.exception("%s failed.", label)
            failures.append(f"{label}: {str(exc)[:250]}")

    logging.info("Completed PDFs: %s", completed)

    if failures:
        raise RuntimeError(
            "Some PDFs failed:\n" + "\n".join(failures)
        )

    logging.info("All four PDFs generated and sent successfully.")

if __name__ == "__main__":
    main()
