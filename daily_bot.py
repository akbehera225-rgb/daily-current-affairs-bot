import os
import random
import requests
import feedparser
from datetime import datetime
from html import escape
from urllib.parse import quote_plus

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import mm
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle,
    PageBreak, KeepTogether
)

# ==========================================================
# TELEGRAM SETTINGS
# Read securely from GitHub Actions Secrets.
# Never put your bot token directly in this file.
# ==========================================================

BOT_TOKEN = os.environ["TELEGRAM_BOT_TOKEN"]
CHAT_ID = os.environ["TELEGRAM_CHAT_ID"]

TODAY = datetime.now().strftime("%d %B %Y")
DAY_NUMBER = datetime.now().timetuple().tm_yday

OUTPUT_DIR = "daily_pdfs"
os.makedirs(OUTPUT_DIR, exist_ok=True)

# Colour palette
NAVY = colors.HexColor("#172554")
BLUE = colors.HexColor("#2563EB")
CYAN = colors.HexColor("#0891B2")
PURPLE = colors.HexColor("#7C3AED")
GREEN = colors.HexColor("#15803D")
ORANGE = colors.HexColor("#EA580C")
PALE_BLUE = colors.HexColor("#EFF6FF")
PALE_GREEN = colors.HexColor("#F0FDF4")
PALE_PURPLE = colors.HexColor("#F5F3FF")
PALE_ORANGE = colors.HexColor("#FFF7ED")
LIGHT = colors.HexColor("#F8FAFC")
DARK = colors.HexColor("#1E293B")
GREY = colors.HexColor("#64748B")
WHITE = colors.white

styles = getSampleStyleSheet()

styles.add(ParagraphStyle(
    name="CoverTitle",
    parent=styles["Title"],
    fontName="Helvetica-Bold",
    fontSize=23,
    leading=28,
    textColor=WHITE,
    alignment=TA_CENTER,
    spaceAfter=8,
))

styles.add(ParagraphStyle(
    name="CoverSub",
    parent=styles["Normal"],
    fontSize=11,
    leading=16,
    textColor=WHITE,
    alignment=TA_CENTER,
))

styles.add(ParagraphStyle(
    name="Section",
    parent=styles["Heading2"],
    fontName="Helvetica-Bold",
    fontSize=15,
    leading=19,
    textColor=NAVY,
    spaceBefore=12,
    spaceAfter=8,
))

styles.add(ParagraphStyle(
    name="Question",
    parent=styles["Normal"],
    fontName="Helvetica-Bold",
    fontSize=10,
    leading=15,
    textColor=DARK,
    spaceAfter=5,
))

styles.add(ParagraphStyle(
    name="BodyCustom",
    parent=styles["Normal"],
    fontSize=9,
    leading=14,
    textColor=DARK,
    spaceAfter=5,
))

styles.add(ParagraphStyle(
    name="SmallCustom",
    parent=styles["Normal"],
    fontSize=8,
    leading=11,
    textColor=GREY,
))

styles.add(ParagraphStyle(
    name="Answer",
    parent=styles["Normal"],
    fontSize=9,
    leading=14,
    textColor=GREEN,
    spaceAfter=5,
))

styles.add(ParagraphStyle(
    name="WhiteText",
    parent=styles["Normal"],
    fontName="Helvetica-Bold",
    fontSize=10,
    leading=14,
    textColor=WHITE,
    alignment=TA_CENTER,
))

def P(text, style="BodyCustom"):
    return Paragraph(text, styles[style])

def make_banner(title, subtitle, colour):
    data = [
        [Paragraph(title, styles["CoverTitle"])],
        [Paragraph(subtitle, styles["CoverSub"])]
    ]
    table = Table(data, colWidths=[175 * mm])
    table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), colour),
        ("BOX", (0, 0), (-1, -1), 0, colour),
        ("LEFTPADDING", (0, 0), (-1, -1), 12),
        ("RIGHTPADDING", (0, 0), (-1, -1), 12),
        ("TOPPADDING", (0, 0), (-1, 0), 16),
        ("BOTTOMPADDING", (0, 0), (-1, 0), 4),
        ("TOPPADDING", (0, 1), (-1, 1), 2),
        ("BOTTOMPADDING", (0, 1), (-1, 1), 16),
    ]))
    return table

def footer(canvas, doc):
    canvas.saveState()
    width, height = A4

    canvas.setFillColor(NAVY)
    canvas.rect(0, height - 5 * mm, width, 5 * mm, fill=1, stroke=0)

    canvas.setStrokeColor(colors.HexColor("#CBD5E1"))
    canvas.line(18 * mm, 15 * mm, width - 18 * mm, 15 * mm)

    canvas.setFont("Helvetica", 8)
    canvas.setFillColor(GREY)
    canvas.drawString(18 * mm, 9 * mm, "DAILY EXAM PREPARATION")
    canvas.drawRightString(
        width - 18 * mm, 9 * mm, f"Page {doc.page}"
    )
    canvas.restoreState()

def create_pdf(filename, title, subtitle, colour, story):
    path = os.path.join(OUTPUT_DIR, filename)

    doc = SimpleDocTemplate(
        path,
        pagesize=A4,
        rightMargin=18 * mm,
        leftMargin=18 * mm,
        topMargin=17 * mm,
        bottomMargin=22 * mm,
        title=title,
        author="Daily Exam Preparation"
    )

    complete_story = [
        make_banner(title, subtitle, colour),
        Spacer(1, 7 * mm),
        P(f"<b>Study date:</b> {TODAY}", "SmallCustom"),
        Spacer(1, 3 * mm),
    ]
    complete_story.extend(story)

    doc.build(
        complete_story,
        onFirstPage=footer,
        onLaterPages=footer
    )
    return path

def make_box(title, text, colour, background):
    content = [
        P(title, "Question"),
        P(text)
    ]
    table = Table([[content]], colWidths=[174 * mm])
    table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), background),
        ("BOX", (0, 0), (-1, -1), 1, colour),
        ("LINEBEFORE", (0, 0), (0, -1), 4, colour),
        ("LEFTPADDING", (0, 0), (-1, -1), 10),
        ("RIGHTPADDING", (0, 0), (-1, -1), 10),
        ("TOPPADDING", (0, 0), (-1, -1), 8),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
    ]))
    return table

# ==========================================================
# PDF 1: DAILY CURRENT AFFAIRS
# Headlines come from RSS feeds. Links are included for
# checking the original reporting.
# ==========================================================

def get_current_affairs():
    feeds = [
        (
            "Google News — India",
            "https://news.google.com/rss/search?q="
            + quote_plus("India government science technology economy")
            + "&hl=en-IN&gl=IN&ceid=IN:en"
        ),
        (
            "Google News — Science and Space",
            "https://news.google.com/rss/search?q="
            + quote_plus("India science space ISRO environment")
            + "&hl=en-IN&gl=IN&ceid=IN:en"
        ),
        (
            "Google News — International",
            "https://news.google.com/rss/search?q="
            + quote_plus("international news climate technology")
            + "&hl=en-IN&gl=IN&ceid=IN:en"
        ),
    ]

    articles = []
    seen = set()

    for source_name, url in feeds:
        try:
            response = requests.get(
                url,
                timeout=20,
                headers={"User-Agent": "DailyStudyBot/1.0"}
            )
            response.raise_for_status()
            parsed = feedparser.parse(response.content)

            for entry in parsed.entries:
                title = entry.get("title", "").strip()
                link = entry.get("link", "").strip()
                summary = entry.get("summary", "").strip()

                if not title or not link or title in seen:
                    continue

                seen.add(title)
                articles.append({
                    "title": title,
                    "link": link,
                    "summary": summary,
                    "source": source_name,
                    "published": entry.get("published", "Date not provided")
                })

        except Exception as error:
            print(f"Could not read {source_name}: {error}")

    return articles[:12]

def build_current_affairs():
    story = [
        P("TODAY'S NEWS DESK", "Section"),
        P(
            "Read the headline, open the source link, and make a short "
            "note of the event, place, organisation and important numbers."
        ),
        Spacer(1, 3 * mm)
    ]

    articles = get_current_affairs()

    if not articles:
        story.append(make_box(
            "Live news feeds unavailable",
            "The news feeds could not be reached during this run. "
            "No unverified headlines have been presented as today's news. "
            "Check the next scheduled run or your internet/feed settings.",
            ORANGE, PALE_ORANGE
        ))
        story.append(Spacer(1, 5 * mm))
        story.append(P(
            "Exam tip: Revise recent government schemes, important "
            "appointments, awards, science and space missions, environment, "
            "sports and major national and international events."
        ))
    else:
        for i, article in enumerate(articles, 1):
            title = escape(article["title"])
            link = escape(article["link"], quote=True)
            published = escape(article["published"])
            source = escape(article["source"])

            # RSS summaries may contain HTML. Remove tags for clean PDF text.
            import re
            summary = re.sub(r"<[^>]+>", " ", article["summary"])
            summary = escape(" ".join(summary.split())[:450])

            content = [
                P(f"{i:02d}. {title}", "Question"),
                P(f"<b>Feed:</b> {source} &nbsp; | &nbsp; "
                  f"<b>Published:</b> {published}", "SmallCustom"),
            ]

            if summary:
                content.append(P(summary))

            content.append(P(
                f'<link href="{link}" color="#2563EB">'
                "<u>Open original news report</u></link>",
                "BodyCustom"
            ))

            story.append(KeepTogether(content))
            story.append(Spacer(1, 4 * mm))

    story.append(Spacer(1, 4 * mm))
    story.append(make_box(
        "Daily revision task",
        "For each important story, write: What happened? Where? Which "
        "organisation or person was involved? Why is it important for an exam?",
        BLUE, PALE_BLUE
    ))

    return create_pdf(
        "01_Daily_Current_Affairs.pdf",
        "DAILY CURRENT AFFAIRS",
        "Fresh headlines • Source links • Exam-oriented reading",
        BLUE,
        story
    )

# ==========================================================
# PDF 2: STATIC GK
# Daily chapter rotation with revision notes and MCQs.
# ==========================================================

GK_CHAPTERS = [
    {
        "name": "Indian Constitution",
        "notes": [
            ("Constitution adopted", "26 November 1949."),
            ("Constitution came into force", "26 January 1950."),
            ("Fundamental Rights", "Part III of the Constitution."),
            ("Directive Principles", "Part IV of the Constitution."),
            ("Fundamental Duties", "Part IVA; Article 51A."),
            ("Constitutional remedies", "Article 32 concerns remedies for enforcement of Fundamental Rights.")
        ],
        "questions": [
            ("When was the Constitution of India adopted?",
             ["15 August 1947", "26 November 1949", "26 January 1950", "2 October 1950"], 1,
             "It was adopted by the Constituent Assembly on 26 November 1949."),
            ("Fundamental Rights are primarily contained in which part?",
             ["Part I", "Part II", "Part III", "Part IV"], 2,
             "Part III contains Fundamental Rights."),
            ("Fundamental Duties are listed under which article?",
             ["Article 14", "Article 21", "Article 32", "Article 51A"], 3,
             "Article 51A lists Fundamental Duties.")
        ]
    },
    {
        "name": "Indian Geography",
        "notes": [
            ("Standard Meridian of India", "82°30′ East longitude."),
            ("Tropic of Cancer", "Passes through eight Indian states."),
            ("Largest Indian state by area", "Rajasthan."),
            ("Himalayas", "Young fold mountains in northern India."),
            ("Monsoon", "Seasonal reversal of winds is a key feature."),
            ("Western Ghats", "A mountain range running roughly parallel to India's western coast.")
        ],
        "questions": [
            ("What is India's Standard Meridian?",
             ["68°7′ E", "82°30′ E", "90° E", "75° E"], 1,
             "India's Standard Meridian is 82°30′ E."),
            ("Which is the largest Indian state by area?",
             ["Madhya Pradesh", "Uttar Pradesh", "Rajasthan", "Maharashtra"], 2,
             "Rajasthan is the largest state by area."),
            ("The Himalayas are mainly which type of mountains?",
             ["Block", "Volcanic", "Residual", "Fold"], 3,
             "The Himalayas are young fold mountains.")
        ]
    },
    {
        "name": "Indian History",
        "notes": [
            ("Battle of Plassey", "1757."),
            ("Revolt of 1857", "A major uprising against British rule."),
            ("Indian National Congress founded", "1885."),
            ("Non-Cooperation Movement", "Launched in 1920."),
            ("Dandi March", "1930; associated with the Salt Satyagraha."),
            ("Quit India Movement", "Launched in 1942.")
        ],
        "questions": [
            ("In which year was the Indian National Congress founded?",
             ["1857", "1885", "1905", "1942"], 1,
             "The Indian National Congress was founded in 1885."),
            ("The Dandi March took place in which year?",
             ["1919", "1920", "1930", "1942"], 2,
             "The Salt March took place in 1930."),
            ("The Quit India Movement began in which year?",
             ["1920", "1930", "1935", "1942"], 3,
             "The Quit India Movement was launched in 1942.")
        ]
    },
    {
        "name": "Indian Economy",
        "notes": [
            ("RBI", "The Reserve Bank of India is India's central bank."),
            ("GDP", "Measures the value of final goods and services produced within a country over a period."),
            ("Inflation", "A sustained increase in the general price level."),
            ("Repo rate", "The rate at which the RBI lends short-term funds to banks against eligible securities."),
            ("Direct tax", "A tax paid directly by the person or organisation on whom it is imposed."),
            ("GST", "Goods and Services Tax is an indirect tax.")
        ],
        "questions": [
            ("Which is India's central bank?",
             ["SBI", "RBI", "NABARD", "SEBI"], 1,
             "The Reserve Bank of India is India's central bank."),
            ("A sustained rise in the general price level is called:",
             ["Deflation", "Depreciation", "Inflation", "Recession"], 2,
             "Inflation refers to a rise in the general price level."),
            ("GST is generally classified as which kind of tax?",
             ["Direct", "Property", "Income", "Indirect"], 3,
             "GST is an indirect tax.")
        ]
    },
    {
        "name": "General Science",
        "notes": [
            ("SI unit of force", "Newton."),
            ("SI unit of power", "Watt."),
            ("Photosynthesis", "Plants use light energy to produce chemical energy."),
            ("Vitamin C deficiency", "Can cause scurvy."),
            ("Blood oxygen transport", "Haemoglobin in red blood cells transports much of the oxygen."),
            ("Speed of light in vacuum", "Approximately 3 × 10⁸ m/s.")
        ],
        "questions": [
            ("What is the SI unit of force?",
             ["Joule", "Newton", "Watt", "Pascal"], 1,
             "Force is measured in newtons."),
            ("Deficiency of vitamin C can cause:",
             ["Rickets", "Night blindness", "Scurvy", "Beriberi"], 2,
             "Vitamin C deficiency can cause scurvy."),
            ("What is the approximate speed of light in vacuum?",
             ["3 × 10⁶ m/s", "3 × 10⁷ m/s", "3 × 10⁹ m/s", "3 × 10⁸ m/s"], 3,
             "The speed of light in vacuum is approximately 3 × 10⁸ m/s.")
        ]
    },
]

def build_static_gk():
    chapter = GK_CHAPTERS[(DAY_NUMBER - 1) % len(GK_CHAPTERS)]
    story = [
        P("CHAPTER OF THE DAY", "Section"),
        make_box(
            chapter["name"].upper(),
            "Read these quick facts, then answer the MCQs without looking at the answers.",
            PURPLE, PALE_PURPLE
        ),
        Spacer(1, 5 * mm),
        P("QUICK REVISION NOTES", "Section")
    ]

    for title, text in chapter["notes"]:
        story.append(make_box(title, text, PURPLE, PALE_PURPLE))
        story.append(Spacer(1, 2 * mm))

    story.extend([
        Spacer(1, 4 * mm),
        P("PRACTICE MCQs", "Section")
    ])

    for i, (question, options, answer, explanation) in enumerate(
        chapter["questions"], 1
    ):
        option_text = "<br/>".join(
            f"{chr(65+j)}. {escape(option)}"
            for j, option in enumerate(options)
        )
        story.append(P(f"Q{i}. {escape(question)}", "Question"))
        story.append(P(option_text))
        story.append(Spacer(1, 3 * mm))

    story.extend([
        PageBreak(),
        P("ANSWER KEY WITH EXPLANATIONS", "Section")
    ])

    for i, (question, options, answer, explanation) in enumerate(
        chapter["questions"], 1
    ):
        story.append(P(
            f"Q{i}. Answer: {chr(65+answer)}. {escape(options[answer])}",
            "Answer"
        ))
        story.append(P(escape(explanation)))
        story.append(Spacer(1, 3 * mm))

    return create_pdf(
        "02_Static_GK.pdf",
        "STATIC GK",
        f"Chapter-wise revision • {chapter['name']} • MCQs",
        PURPLE,
        story
    )

# ==========================================================
# PDF 3: REASONING PRACTICE
# ==========================================================

REASONING_QUESTIONS = [
    {
        "topic": "Number series",
        "level": "Easy",
        "q": "Find the next number: 3, 6, 12, 24, ?",
        "options": ["30", "36", "48", "60"],
        "answer": 2,
        "solution": "Each number is multiplied by 2. Therefore, 24 × 2 = 48."
    },
    {
        "topic": "Number series",
        "level": "Medium",
        "q": "Find the missing number: 2, 6, 12, 20, 30, ?",
        "options": ["36", "40", "42", "44"],
        "answer": 2,
        "solution": "The differences are 4, 6, 8 and 10. The next difference is 12, so 30 + 12 = 42."
    },
    {
        "topic": "Analogy",
        "level": "Easy",
        "q": "Book is to Reading as Fork is to:",
        "options": ["Writing", "Eating", "Drawing", "Sleeping"],
        "answer": 1,
        "solution": "A book is used for reading; a fork is used for eating."
    },
    {
        "topic": "Coding-decoding",
        "level": "Medium",
        "q": "If CAT is coded as DBU by moving every letter one step forward, DOG becomes:",
        "options": ["EPH", "EOG", "FPH", "DPH"],
        "answer": 0,
        "solution": "D → E, O → P and G → H. Therefore, DOG becomes EPH."
    },
    {
        "topic": "Odd one out",
        "level": "Easy",
        "q": "Choose the odd one out.",
        "options": ["Square", "Triangle", "Circle", "Cube"],
        "answer": 3,
        "solution": "Cube is three-dimensional; the other figures are two-dimensional."
    },
    {
        "topic": "Direction sense",
        "level": "Medium",
        "q": "A person walks 4 m north and then 3 m east. How far is the person from the starting point?",
        "options": ["5 m", "7 m", "1 m", "12 m"],
        "answer": 0,
        "solution": "The path forms a right triangle. Distance = √(4² + 3²) = √25 = 5 m."
    },
    {
        "topic": "Blood relation",
        "level": "Easy",
        "q": "A is the brother of B. B is the sister of C. How is A related to C?",
        "options": ["Brother", "Father", "Uncle", "Cousin"],
        "answer": 0,
        "solution": "A and C are siblings, and A is male. Therefore, A is C's brother."
    },
    {
        "topic": "Alphabet series",
        "level": "Medium",
        "q": "Find the next letter: A, C, F, J, O, ?",
        "options": ["S", "T", "U", "V"],
        "answer": 2,
        "solution": "Letter jumps are +2, +3, +4 and +5. The next jump is +6, giving U."
    },
]

def build_reasoning():
    rng = random.Random
