          import os
import re
import html
import random
import logging
from datetime import datetime, timezone, timedelta
from urllib.parse import quote_plus

import requests
import feedparser

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import mm
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table,
    TableStyle, PageBreak, KeepTogether
)

# =============== SETTINGS ===============

BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "").strip()

if not BOT_TOKEN or not CHAT_ID:
    raise RuntimeError(
        "Missing TELEGRAM_BOT_TOKEN or TELEGRAM_CHAT_ID "
        "in GitHub Actions Secrets."
    )

IST = timezone(timedelta(hours=5, minutes=30))
NOW = datetime.now(IST)
TODAY = NOW.strftime("%d %B %Y")
DAY = NOW.timetuple().tm_yday

os.makedirs("daily_pdfs", exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format="%(levelname)s: %(message)s"
)
log = logging.getLogger("daily_bot")

NAVY = colors.HexColor("#172554")
BLUE = colors.HexColor("#2563EB")
PURPLE = colors.HexColor("#7C3AED")
TEAL = colors.HexColor("#0F766E")
ORANGE = colors.HexColor("#C2410C")
GREEN = colors.HexColor("#15803D")
PALE_BLUE = colors.HexColor("#EFF6FF")
PALE_PURPLE = colors.HexColor("#F5F3FF")
PALE_TEAL = colors.HexColor("#F0FDFA")
PALE_ORANGE = colors.HexColor("#FFF7ED")
DARK = colors.HexColor("#1E293B")
GREY = colors.HexColor("#64748B")
WHITE = colors.white

styles = getSampleStyleSheet()

styles.add(ParagraphStyle(
    name="BannerTitle",
    parent=styles["Title"],
    fontName="Helvetica-Bold",
    fontSize=19,
    leading=23,
    textColor=WHITE,
    alignment=TA_CENTER
))

styles.add(ParagraphStyle(
    name="BannerSub",
    parent=styles["Normal"],
    fontSize=9,
    leading=12,
    textColor=WHITE,
    alignment=TA_CENTER
))

styles.add(ParagraphStyle(
    name="SectionX",
    parent=styles["Heading2"],
    fontSize=14,
    leading=18,
    textColor=NAVY,
    spaceBefore=8,
    spaceAfter=7
))

styles.add(ParagraphStyle(
    name="QX",
    parent=styles["Normal"],
    fontName="Helvetica-Bold",
    fontSize=9,
    leading=12,
    textColor=DARK,
    spaceAfter=4
))

styles.add(ParagraphStyle(
    name="BodyX",
    parent=styles["Normal"],
    fontSize=8.5,
    leading=11.5,
    textColor=DARK,
    spaceAfter=3
))

styles.add(ParagraphStyle(
    name="SmallX",
    parent=styles["Normal"],
    fontSize=7.5,
    leading=10,
    textColor=GREY
))

styles.add(ParagraphStyle(
    name="AnswerX",
    parent=styles["Normal"],
    fontName="Helvetica-Bold",
    fontSize=8.5,
    leading=11.5,
    textColor=GREEN
))


def safe_text(value):
    value = html.escape(str(value or ""), quote=False)
    return value.replace("\n", " ")


def para(text, style="BodyX"):
    return Paragraph(text, styles[style])


def banner(title, subtitle, colour):
    table = Table(
        [[para(safe_text(title), "BannerTitle")],
         [para(safe_text(subtitle), "BannerSub")]],
        colWidths=[174 * mm]
    )

    table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), colour),
        ("LEFTPADDING", (0, 0), (-1, -1), 10),
        ("RIGHTPADDING", (0, 0), (-1, -1), 10),
        ("TOPPADDING", (0, 0), (-1, 0), 12),
        ("BOTTOMPADDING", (0, 0), (-1, 0), 4),
        ("TOPPADDING", (0, 1), (-1, 1), 2),
        ("BOTTOMPADDING", (0, 1), (-1, 1), 12),
    ]))

    return table


def footer(canvas, doc):
    canvas.saveState()
    width, height = A4

    canvas.setFillColor(NAVY)
    canvas.rect(0, height - 4 * mm, width, 4 * mm, fill=1, stroke=0)

    canvas.setStrokeColor(colors.HexColor("#CBD5E1"))
    canvas.line(18 * mm, 14 * mm, width - 18 * mm, 14 * mm)

    canvas.setFont("Helvetica", 7.5)
    canvas.setFillColor(GREY)
    canvas.drawString(18 * mm, 8 * mm, "DAILY EXAM PRACTICE")
    canvas.drawRightString(width - 18 * mm, 8 * mm, f"Page {doc.page}")

    canvas.restoreState()


def make_pdf(filename, title, subtitle, colour, content):
    path = os.path.join("daily_pdfs", filename)

    doc = SimpleDocTemplate(
        path,
        pagesize=A4,
        leftMargin=18 * mm,
        rightMargin=18 * mm,
        topMargin=14 * mm,
        bottomMargin=20 * mm,
        title=title
    )

    story = [
        banner(title, subtitle, colour),
        Spacer(1, 5 * mm),
        para(f"<b>Date:</b> {safe_text(TODAY)}", "SmallX"),
        Spacer(1, 2 * mm)
    ] + content

    doc.build(story, onFirstPage=footer, onLaterPages=footer)

    log.info("Created %s", path)
    return path


def info_box(title, body, border, background):
    inner = [
        para(safe_text(title), "QX"),
        para(body, "BodyX")
    ]

    table = Table([[inner]], colWidths=[174 * mm])

    table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), background),
        ("BOX", (0, 0), (-1, -1), 0.7, border),
        ("LINEBEFORE", (0, 0), (0, -1), 3, border),
        ("LEFTPADDING", (0, 0), (-1, -1), 8),
        ("RIGHTPADDING", (0, 0), (-1, -1), 8),
        ("TOPPADDING", (0, 0), (-1, -1), 6),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
    ]))

    return table


# =============== CURRENT AFFAIRS ===============

def strip_markup(text):
    text = html.unescape(str(text or ""))
    text = re.sub(
        r"(?is)<(script|style).*?>.*?</\\1>",
        " ",
        text
    )
    text = re.sub(r"(?s)<[^>]+>", " ", text)
    return re.sub(r"\\s+", " ", text).strip()


def get_news():
    searches = [
        ("India", "India government economy science technology"),
        ("Science and Space", "India ISRO science space environment"),
        ("World", "world climate international science technology"),
    ]

    found = []
    seen = set()

    for category, query in searches:
        url = (
            "https://news.google.com/rss/search?q="
            + quote_plus(query)
            + "&hl=en-IN&gl=IN&ceid=IN:en"
        )

        try:
            response = requests.get(
                url,
                timeout=18,
                headers={"User-Agent": "Mozilla/5.0"}
            )
            response.raise_for_status()

            feed = feedparser.parse(response.content)

            for entry in feed.entries:
                title = strip_markup(entry.get("title", ""))
                link = entry.get("link", "")
                summary = strip_markup(entry.get("summary", ""))

                if not title or not link:
                    continue

                if title.lower() in seen:
                    continue

                seen.add(title.lower())

                found.append({
                    "title": title,
                    "link": link,
                    "summary": summary[:650],
                    "category": category,
                    "published": strip_markup(
                        entry.get("published", "Date not provided")
                    )
                })

        except Exception as error:
            log.warning("News feed unavailable: %s", error)

    return found[:18]


def current_affairs_pdf():
    content = [
        para("TODAY'S NEWS DESK", "SectionX"),
        para(
            "Recent headlines from RSS feeds. Open each source link "
            "to read the complete report and verify important facts.",
            "BodyX"
        ),
        Spacer(1, 3 * mm)
    ]

    articles = get_news()

    if not articles:
        content.append(info_box(
            "News feeds temporarily unavailable",
            "No live headlines were retrieved. This PDF does not invent "
            "current news. Try running the workflow again later.",
            ORANGE,
            PALE_ORANGE
        ))

    for number, item in enumerate(articles, 1):
        title = safe_text(item["title"])
        summary = safe_text(
            item["summary"] or "No short summary was provided."
        )
        category = safe_text(item["category"])
        published = safe_text(item["published"])
        link = html.escape(item["link"], quote=True)

        content.append(KeepTogether([
            para(f"{number:02d}. {title}", "QX"),
            para(
                f"<b>Category:</b> {category} &nbsp; "
                f"<b>Published:</b> {published}",
                "SmallX"
            ),
            para(summary, "BodyX"),
            para(
                f'<link href="{link}" color="#2563EB">'
                f'<u>Read original report</u></link>',
                "BodyX"
            ),
            Spacer(1, 3 * mm)
        ]))

    content.append(info_box(
        "Exam note-making tip",
        "For each important event, note the date, place, organisation, "
        "person, key number and why the event matters.",
        BLUE,
        PALE_BLUE
    ))

    return make_pdf(
        "01_Daily_Current_Affairs.pdf",
        "DAILY CURRENT AFFAIRS",
        "Recent headlines • Summaries • Source links",
        BLUE,
        content
    )


# =============== STATIC GK ===============

# Each question: topic, difficulty, question, options, correct index, explanation
GK = [
("Polity","The Constitution of India was adopted on:",["15 Aug 1947","26 Nov 1949","26 Jan 1950","2 Oct 1950"],1,"It was adopted on 26 November 1949."),
("Polity","The Constitution came into force on:",["15 Aug 1947","26 Nov 1949","26 Jan 1950","26 Nov 1950"],2,"It came into force on 26 January 1950."),
("Polity","Fundamental Rights are mainly in which Part?",["Part II","Part III","Part IV","Part IVA"],1,"Part III contains Fundamental Rights."),
("Polity","Fundamental Duties are listed in:",["Article 14","Article 21","Article 32","Article 51A"],3,"Article 51A lists Fundamental Duties."),
("Polity","Which Article is associated with constitutional remedies?",["Article 17","Article 21","Article 32","Article 44"],2,"Article 32 provides constitutional remedies."),
("Polity","The minimum voting age in India is:",["16 years","18 years","21 years","25 years"],1,"The voting age is 18 years."),
("Polity","A Money Bill is defined under:",["Article 110","Article 123","Article 356","Article 368"],0,"Article 110 defines a Money Bill."),
("Polity","Who is the constitutional head of the Union?",["Prime Minister","President","Chief Justice","Speaker"],1,"The President is the constitutional head."),
("Polity","The normal term of the Lok Sabha is:",["4 years","5 years","6 years","7 years"],1,"The normal term is five years unless dissolved earlier."),
("Polity","Directive Principles are in:",["Part II","Part III","Part IV","Part V"],2,"Part IV contains Directive Principles."),
("Geography","India's Standard Meridian is:",["68°7′ E","82°30′ E","90° E","75° E"],1,"India's Standard Meridian is 82°30′ E."),
("Geography","The largest Indian state by area is:",["Madhya Pradesh","Maharashtra","Rajasthan","Uttar Pradesh"],2,"Rajasthan is the largest state by area."),
("Geography","The smallest Indian state by area is:",["Sikkim","Tripura","Goa","Manipur"],2,"Goa is the smallest state by area."),
("Geography","The Tropic of Cancer lies near:",["0°","23.5° N","23.5° S","66.5° N"],1,"It lies at approximately 23.5° north."),
("Geography","The Himalayas are primarily:",["Block mountains","Young fold mountains","Volcanic mountains","Residual hills"],1,"The Himalayas are young fold mountains."),
("Geography","Which river is often called the Dakshin Ganga?",["Narmada","Godavari","Kaveri","Tapti"],1,"The Godavari is often called the Dakshin Ganga."),
("Geography","The Thar Desert is mainly in:",["Rajasthan","Assam","Kerala","Bihar"],0,"Most of India's Thar Desert is in Rajasthan."),
("Geography","Which soil is associated with cotton cultivation?",["Laterite","Black soil","Mountain soil","Desert soil"],1,"Black soil retains moisture and suits cotton."),
("Geography","The Sundarbans are famous for:",["Coral reefs","Mangrove forests","Cold deserts","Alpine meadows"],1,"The Sundarbans contain extensive mangrove forests."),
("Geography","Which ocean lies south of India?",["Atlantic","Arctic","Indian","Pacific"],2,"The Indian Ocean lies south of India."),
("History","The Indian National Congress was founded in:",["1857","1885","1905","1942"],1,"The INC was founded in 1885."),
("History","The Battle of Plassey took place in:",["1757","1764","1857","1947"],0,"The Battle of Plassey was fought in 1757."),
("History","The Dandi March took place in:",["1919","1920","1930","1942"],2,"Gandhi's Salt March took place in 1930."),
("History","The Quit India Movement began in:",["1919","1920","1930","1942"],3,"It was launched in August 1942."),
("History","Who popularised 'Jai Jawan Jai Kisan'?",["Jawaharlal Nehru","Lal Bahadur Shastri","Sardar Patel","Subhas Bose"],1,"Lal Bahadur Shastri popularised the slogan."),
("History","The Jallianwala Bagh massacre occurred in:",["1905","1919","1928","1942"],1,"It occurred in Amritsar in 1919."),
("History","Who founded the Maurya Empire?",["Ashoka","Chandragupta Maurya","Harsha","Kanishka"],1,"Chandragupta Maurya founded the Maurya Empire."),
("History","The first Mughal emperor in India was:",["Akbar","Humayun","Babur","Shah Jahan"],2,"Babur founded Mughal rule after the First Battle of Panipat in 1526."),
("History","The Vijayanagara Empire's capital was:",["Hampi","Madurai","Patna","Kannauj"],0,"Hampi was the capital of Vijayanagara."),
("History","The Non-Cooperation Movement began in:",["1905","1915","1920","1935"],2,"It began in 1920."),
("Economy","The Reserve Bank of India is India's:",["Commercial bank","Central bank","Rural bank only","Stock exchange"],1,"The RBI is India's central bank."),
("Economy","GDP measures the value of:",["Only exports","Final goods and services produced domestically","Only taxes","Only agriculture"],1,"GDP measures final production within a country's borders."),
("Economy","A general sustained rise in prices is:",["Deflation","Inflation","Depreciation","Recession"],1,"Inflation is a general rise in prices."),
("Economy","GST is generally classified as:",["Direct tax","Indirect tax","Wealth tax","Dividend"],1,"GST is an indirect tax."),
("Economy","Which institution regulates India's securities market?",["SEBI","ISRO","DRDO","UGC"],0,"SEBI regulates India's securities market."),
("Economy","India's currency is the:",["Rupee","Yen","Euro","Pound"],0,"The Indian rupee is India's currency."),
("Economy","A budget deficit occurs when expenditure is:",["Less than income","Equal to income","Greater than receipts","Always zero"],2,"A deficit occurs when spending exceeds relevant receipts."),
("Economy","NABARD is associated with:",["Space research","Agriculture and rural development","Atomic energy","Telecom"],1,"NABARD supports agriculture and rural development."),
("Economy","Income tax is generally a:",["Direct tax","Indirect tax","Custom duty only","Consumption tax only"],0,"Income tax is imposed directly on taxable income."),
("Economy","The policy repo rate is set by the:",["Election Commission","RBI Monetary Policy Committee","Supreme Court","Finance Commission"],1,"The RBI's Monetary Policy Committee sets the policy repo rate."),
("Science","The SI unit of force is:",["Joule","Newton","Watt","Pascal"],1,"Force is measured in newtons."),
("Science","The SI unit of power is:",["Watt","Joule","Newton","Coulomb"],0,"Power is measured in watts."),
("Science","The speed of light in vacuum is approximately:",["3×10^6 m/s","3×10^7 m/s","3×10^8 m/s","3×10^9 m/s"],2,"It is approximately 3 × 10^8 m/s."),
("Science","Vitamin C deficiency can cause:",["Rickets","Scurvy","Beriberi","Night blindness"],1,"Vitamin C deficiency causes scurvy."),
("Science","Which pigment helps plants absorb light?",["Haemoglobin","Chlorophyll","Melanin","Keratin"],1,"Chlorophyll absorbs light for photosynthesis."),
("Science","The most abundant gas in Earth's atmosphere is:",["Oxygen","Carbon dioxide","Nitrogen","Hydrogen"],2,"Nitrogen makes up about 78% of dry air."),
("Science","The pH of neutral water at about 25°C is:",["0","5","7","14"],2,"Neutral water has pH 7 at about 25°C."),
("Science","Which blood cells mainly carry oxygen?",["Red blood cells","Platelets","White blood cells","Plasma only"],0,"Haemoglobin in red blood cells carries most oxygen."),
("Science","The largest organ of the human body is:",["Liver","Skin","Heart","Lung"],1,"The skin is the body's largest organ."),
("Science","Which vitamin can be produced in skin with sunlight?",["Vitamin A","Vitamin B12","Vitamin C","Vitamin D"],3,"Sunlight enables vitamin D synthesis in skin.")
]


def mcq_story(items):
    content = []

    for number, item in enumerate(items, 1):
        topic, level, question, options, answer, explanation = item

        option_text = "<br/>".join(
            f"{chr(65 + j)}. {safe_text(option)}"
            for j, option in enumerate(options)
        )

        content.append(KeepTogether([
            para(
                f"Q{number}. [{safe_text(topic)} | "
                f"{safe_text(level)}] {safe_text(question)}",
                "QX"
            ),
            para(option_text, "BodyX"),
            Spacer(1, 2 * mm)
        ]))

    content.append(PageBreak())
    content.append(para("ANSWER KEY & EXPLANATIONS", "SectionX"))

    for number, item in enumerate(items, 1):
        topic, level, question, options, answer, explanation = item

        content.append(para(
            f"Q{number}. Answer: {chr(65 + answer)}. "
            f"{safe_text(options[answer])}",
            "AnswerX"
        ))
        content.append(para(safe_text(explanation), "BodyX"))
        content.append(Spacer(1, 1.5 * mm))

    return content


def static_gk_pdf():
    topics = ["Polity", "Geography", "History", "Economy", "Science"]
    rng = random.Random(DAY + 10)

    all_items = []

    for topic in topics:
        group = [q for q in GK if q[0] == topic]
        rng.shuffle(group)
        all_items.extend(group[:10])

    if len(all_items) != 50:
        raise RuntimeError(
            f"Static GK bank has {len(all_items)} questions, expected 50."
        )

    content = [
        para("50 MCQs • FIVE SUBJECT AREAS", "SectionX"),
        info_box(
            "Today's practice",
            "10 questions each from Polity, Geography, History, Economy "
            "and General Science. Attempt first; check answers afterward.",
            PURPLE,
            PALE_PURPLE
        ),
        Spacer(1, 4 * mm)
    ]

    content.extend(mcq_story(all_items))

    return make_pdf(
        "02_Static_GK_50_MCQs.pdf",
        "STATIC GK — 50 MCQs",
        "Polity • Geography • History • Economy • General Science",
        PURPLE,
        content
    )


# =============== REASONING ===============

def reasoning_bank():
    bank = []

    # 20 number-series questions
    for i in range(1, 11):
        start = i + 2
        step = i + 2
        sequence = [start + j * step for j in range(4)]
        answer = start + 4 * step

        options = [
            answer,
            answer + step,
            answer - 1,
            answer + 2
        ]

        options = list(dict.fromkeys(options))
        while len(options) < 4:
            options.append(answer + len(options) + 5)

        options = options[:4]

        bank.append((
            "Number series", "Easy",
            f"Find the next number: {', '.join(map(str, sequence))}, ?",
            options, options.index(answer),
            f"The sequence increases by {step} each time. Answer: {answer}."
        ))

    for i in range(2, 12):
        start = i
        sequence = [start, start * 2, start * 4, start * 8]
        answer = start * 16

        options = [
            answer + start,
            answer,
            answer // 2,
            answer + 2 * start
        ]

        options = list(dict.fromkeys(options))
        while len(options) < 4:
            options.append(answer + len(options) * 3)

        options = options[:4]

        bank.append((
            "Number series", "Medium",
            f"Find the next number: {', '.join(map(str, sequence))}, ?",
            options, options.index(answer),
            f"Each term doubles. Answer: {answer}."
        ))

    analogies = [
        ("Bird is to Nest as Bee is to:", ["Hive","Web","Stable","Den"],0,"A bird lives in a nest; a bee lives in a hive."),
        ("Puppy is to Dog as Kitten is to:", ["Calf","Cat","Foal","Cub"],1,"A kitten is a young cat."),
        ("Pen is to Write as Knife is to:", ["Cut","Read","Sing","Paint"],0,"A knife is used to cut."),
        ("Doctor is to Hospital as Teacher is to:", ["Court","School","Farm","Bank"],1,"A teacher commonly works in a school."),
        ("Eye is to See as Ear is to:", ["Smell","Hear","Touch","Taste"],1,"The ear is used for hearing."),
        ("Fish is to Water as Bird is to:", ["Soil","Air","Fire","Stone"],1,"Birds move through air."),
        ("Wheel is to Car as Page is to:", ["Book","Road","Pen","Desk"],0,"A page is part of a book."),
        ("Hot is to Cold as Light is to:", ["Bright","Dark","Sun","Day"],1,"Light and dark are opposites.")
    ]

    for question, options, answer, solution in analogies:
        bank.append((
            "Analogy", "Easy", question, options, answer, solution
        ))

    coding = [
        ("CAT becomes DBU; DOG becomes:", ["EPH","EOG","FPH","DPH"],0,"Move every letter one step forward: D→E, O→P, G→H."),
        ("SUN becomes TVO; MAP becomes:", ["NBQ","NBO","MBQ","OBQ"],0,"Move every letter one step forward: MAP becomes NBQ."),
        ("If each letter moves forward one step, PEN becomes:", ["QFO","QEN","RFO","PFN"],0,"P→Q, E→F and N→O."),
        ("If each letter moves backward one step, DOG becomes:", ["CNF","EPH","COF","DNG"],0,"D→C, O→N and G→F."),
        ("If each letter moves forward one step, BOX becomes:", ["CPY","COY","BPY","CQY"],0,"B→C, O→P and X→Y.")
    ]

    for question, options, answer, solution in coding:
        bank.append((
            "Coding-decoding", "Medium",
            question, options, answer, solution
        ))

    misc = [
        ("Odd one out", "Easy", "Choose the odd one out.", ["Square","Triangle","Circle","Cube"],3,"Cube is three-dimensional; the others are two-dimensional."),
        ("Direction sense", "Medium", "A person walks 3 m north and 4 m east. How far from the start?", ["5 m","7 m","1 m","12 m"],0,"Distance = √(3² + 4²) = 5 m."),
        ("Direction sense", "Medium", "Facing north, turn right twice. Which direction now?", ["East","West","South","North"],2,"North → east → south."),
        ("Blood relation", "Easy", "A is the brother of B. B is the sister of C. A is C's:", ["Brother","Father","Uncle","Cousin"],0,"A and C are siblings; A is male."),
        ("Alphabet series", "Medium", "Find the next letter: A, C, F, J, O, ?", ["S","T","U","V"],2,"The jumps are +2, +3, +4, +5, then +6: U."),
        ("Ranking", "Medium", "Ravi is 7th from the top and 9th from the bottom. Total people?", ["14","15","16","17"],1,"Total = 7 + 9 − 1 = 15."),
        ("Calendar", "Easy", "How many days are in a leap year?", ["364","365","366","367"],2,"A leap year has 366 days."),
        ("Syllogism", "Easy", "All roses are flowers. Which statement must be true?", ["All flowers are roses","All roses are flowers","No roses are flowers","All plants are roses"],1,"This repeats the given statement."),
        ("Comparison", "Easy", "If A > B and B > C, then:", ["A < C","A = C","A > C","Cannot say"],2,"By transitivity, A > C."),
        ("Number relation", "Medium", "If 4 : 16, then 7 : ?", ["14","21","28","49"],3,"The second number is the square of the first: 7² = 49."),
        ("Classification", "Easy", "Which does not belong?", ["January","March","May","Monday"],3,"Monday is a weekday; the others are months."),
        ("Direction sense", "Medium", "Walk 5 km east, then 5 km west. Position?", ["5 km east","5 km west","At start","10 km north"],2,"The movements cancel."),
        ("Number analogy", "Easy", "If 3 : 9, then 5 : ?", ["10","15","20","25"],3,"The second number is the square of the first."),
        ("Alphabet position", "Easy", "What is the position of M in the alphabet?", ["11","12","13","14"],2,"M is the 13th letter."),
        ("Odd one out", "Easy", "Choose the odd one out.", ["2","3","5","9"],3,"2, 3 and 5 are prime; 9 is composite."),
        ("Logical order", "Easy", "Choose the sensible order.", ["Seed–Plant–Flower–Fruit","Fruit–Seed–Plant–Flower","Plant–Fruit–Seed–Flower","Flower–Seed–Fruit–Plant"],0,"A seed grows into a plant, which can flower and produce fruit."),
        ("Comparison", "Easy", "If P = Q and Q > R, then:", ["P < R","P > R","P = R","Cannot say"],1,"Since P = Q and Q > R, P > R.")
    ]

    for topic, level, question, options, answer, solution in misc:
        bank.append((
            topic, level, question, options, answer, solution
        ))

    return bank


# =============== ARITHMETIC ===============

def arithmetic_bank():
    bank = []

    # Percentage questions
    for i in range(1, 11):
        number = i * 5 + 10
        percent = [10, 15, 20, 25, 30][(i - 1) % 5]
        target = number * 10
        answer = target * percent // 100

        bank.append((
            "Percentage", "Easy",
            f"Find {percent}% of {target}.",
            [
                str(answer),
                str(answer + 5),
                str(max(0, answer - 5)),
                str(answer + 10)
            ],
            0,
            f"{percent}/100 × {target} = {answer}."
        ))

    # Profit and loss
    for i in range(1, 11):
        cost = i * 100
        profit_percent = [10, 12, 15, 20, 25][(i - 1) % 5]
        selling = cost * (100 + profit_percent) // 100

        bank.append((
            "Profit and loss", "Medium",
            f"An item costs ₹{cost} and sells for ₹{selling}. "
            "Find the profit percentage.",
            [
                f"{profit_percent}%",
                f"{profit_percent + 5}%",
                f"{max(1, profit_percent - 5)}%",
                f"{profit_percent + 10}%"
            ],
            0,
            f"Profit = ₹{selling - cost}. Profit % = "
            f"({selling - cost}/{cost}) × 100 = {profit_percent}%."
        ))

    # Ratio
    for i in range(1, 11):
        a, b = i + 1, i + 3
        total = (a + b) * 10
        small = a * 10

        bank.append((
            "Ratio", "Easy",
            f"Divide {total} in the ratio {a}:{b}. "
            "What is the smaller share?",
            [str(small), str(small + 10), str(small - 10), str(small + 20)],
            0,
            f"Total parts = {a+b}; one part = {total}/{a+b} = 10. "
            f"Smaller share = {a} × 10 = {small}."
        ))

    # Simple interest
    for i in range(1, 11):
        principal = i * 1000
        rate = [4, 5, 6, 8, 10][(i - 1) % 5]
        years = [2, 3][i % 2]
        interest = principal * rate * years // 100

        bank.append((
            "Simple interest", "Medium",
            f"Find simple interest on ₹{principal} at {rate}% per year "
            f"for {years} years.",
            [
                f"₹{interest}",
                f"₹{interest + 100}",
                f"₹{max(0, interest - 100)}",
                f"₹{interest + 200}"
            ],
            0,
            f"SI = P × R × T / 100 = ({principal} × {rate} × "
            f"{years})/100 = ₹{interest}."
        ))

    # Speed, distance and time
    for i in range(1, 11):
        speed = i * 5 + 20
        hours = (i % 4) + 2
        distance = speed * hours

        bank.append((
            "Speed, distance and time", "Easy",
            f"A vehicle travels {distance} km in {hours} hours. "
            "Find its average speed.",
            [
                f"{speed} km/h",
                f"{speed + 5} km/h",
                f"{speed - 5} km/h",
                f"{speed + 10} km/h"
            ],
            0,
            f"Speed = distance/time = {distance}/{hours} = {speed} km/h."
        ))

    return bank


def shuffled_daily(bank, count, seed):
    rng = random.Random(seed)
    items = list(bank)
    rng.shuffle(items)

    if len(items) < count:
        items = (
            items * ((count // len(items)) + 1)
        )[:count]

    return items[:count]


def reasoning_pdf():
    bank = reasoning_bank()
    items = shuffled_daily(bank, 50, DAY + 1000)

    content = [
        para("50 QUESTIONS • EASY TO MEDIUM", "SectionX"),
        info_box(
            "How to use this paper",
            "Attempt without a calculator. Mark difficult questions, "
            "then check the explanations. This built-in question bank "
            "rotates; some patterns can repeat on later days.",
            TEAL,
            PALE_TEAL
        ),
        Spacer(1, 4 * mm)
    ]

    content.extend(mcq_story(items))

    return make_pdf(
        "03_Reasoning_50_Questions.pdf",
        "REASONING — 50 QUESTIONS",
        "Series • Analogy • Coding • Directions • Relations • Logic",
        TEAL,
        content
    )


def arithmetic_pdf():
    bank = arithmetic_bank()
    items = shuffled_daily(bank, 50, DAY + 2000)

    content = [
        para("50 QUESTIONS • FORMULAS & SOLUTIONS", "SectionX"),
        info_box(
            "Formula quick sheet",
            "<b>Percentage:</b> (Part / Whole) × 100<br/>"
            "<b>Profit:</b> SP − CP; Profit % = Profit / CP × 100<br/>"
            "<b>Ratio share:</b> Total × required parts / total parts<br/>"
            "<b>Simple interest:</b> P × R × T / 100<br/>"
            "<b>Speed:</b> Distance / Time",
            ORANGE,
            PALE_ORANGE
        ),
        Spacer(1, 4 * mm)
    ]

    content.extend(mcq_story(items))

    return make_pdf(
        "04_Arithmetic_50_Questions.pdf",
        "ARITHMETIC — 50 QUESTIONS",
        "Percentages • Profit and loss • Ratio • Interest • Speed",
        ORANGE,
        content
    )


# =============== TELEGRAM ===============

def send_document(path, caption):
    api = f"https://api.telegram.org/bot{BOT_TOKEN}/sendDocument"

    with open(path, "rb") as file:
        response = requests.post(
            api,
            data={"chat_id": CHAT_ID, "caption": caption},
            files={
                "document": (
                    os.path.basename(path),
                    file,
                    "application/pdf"
                )
            },
            timeout=90
        )

    if not response.ok:
        raise RuntimeError(
            f"Telegram returned HTTP {response.status_code}: "
            f"{response.text[:300]}"
        )

    result = response.json()

    if not result.get("ok"):
        raise RuntimeError(
            "Telegram rejected the document: "
            + result.get("description", "unknown error")
        )

    log.info("Telegram sent: %s", os.path.basename(path))


def main():
    tasks = [
        (
            current_affairs_pdf,
            "Daily Current Affairs — recent headlines and source links"
        ),
        (
            static_gk_pdf,
            "Static GK — 50 MCQs with explanations"
        ),
        (
            reasoning_pdf,
            "Reasoning — 50 questions with explanations"
        ),
        (
            arithmetic_pdf,
            "Arithmetic — 50 questions with worked solutions"
        )
    ]

    for build_pdf, caption in tasks:
        path = build_pdf()
        send_document(path, caption)

    log.info("SUCCESS: all four PDFs generated and sent.")


if __name__ == "__main__":
    main()
