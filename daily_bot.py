import os
import requests
from datetime import datetime
from reportlab.lib import colors
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, PageBreak, Table, TableStyle
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.pdfgen import canvas
from reportlab.graphics.shapes import Drawing, Rect, String, Circle, Polygon, Line

TELEGRAM_BOT_TOKEN = "8395103968:AAH_HQI9IANzBTpFOUczQ4VO5PyjoEYfsK4"
TELEGRAM_CHAT_ID = "-1004360405775"

PAGE_WIDTH = 450
PAGE_HEIGHT = 800

# ==========================================
# 1. CANVAS BASE (Page numbers, top & bottom branding)
# ==========================================
class BaseExamCanvas(canvas.Canvas):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._saved_page_states = []
        self.doc_title = "DAILY EXAM BULLETIN"

    def showPage(self):
        self._saved_page_states.append(dict(self.__dict__))
        self._startPage()

    def save(self):
        num_pages = len(self._saved_page_states)
        for state in self._saved_page_states:
            self.__dict__.update(state)
            self.draw_decorations(num_pages)
            super().showPage()
        super().save()

    def draw_decorations(self, total_pages):
        self.saveState()
        # Header Top Bar
        self.setFillColor(colors.HexColor("#0f172a"))
        self.rect(0, PAGE_HEIGHT - 54, PAGE_WIDTH, 54, fill=1, stroke=0)
        self.setFillColor(colors.HexColor("#f59e0b"))
        self.rect(0, PAGE_HEIGHT - 56, PAGE_WIDTH, 2, fill=1, stroke=0)

        today_str = datetime.now().strftime("%d %B %Y").upper()
        self.setFillColor(colors.HexColor("#38bdf8"))
        self.setFont("Helvetica-Bold", 9.5)
        self.drawString(20, PAGE_HEIGHT - 33, self.doc_title)
        self.setFillColor(colors.white)
        self.setFont("Helvetica-Bold", 9.5)
        self.drawRightString(PAGE_WIDTH - 20, PAGE_HEIGHT - 33, today_str)

        # Footer Banner
        footer_h = 100
        self.setFillColor(colors.HexColor("#0f172a"))
        self.rect(0, 0, PAGE_WIDTH, footer_h, fill=1, stroke=0)
        self.setFillColor(colors.HexColor("#3b82f6"))
        self.rect(0, footer_h, PAGE_WIDTH, 3, fill=1, stroke=0)

        self.setFont("Helvetica-Bold", 11)
        self.setFillColor(colors.HexColor("#f8fafc"))
        self.drawCentredString(PAGE_WIDTH / 2.0, 72, "CRACK GOVT EXAMS | DAILY REVISION")
        self.setFont("Helvetica", 8.5)
        self.setFillColor(colors.HexColor("#94a3b8"))
        self.drawCentredString(PAGE_WIDTH / 2.0, 54, "Target: UPSC • SSC • Banking • Railways • Defence • State PSC")

        btn_w, btn_h = 240, 24
        btn_x = (PAGE_WIDTH - btn_w) / 2.0
        btn_y = 18
        self.setFillColor(colors.HexColor("#2563eb"))
        self.roundRect(btn_x, btn_y, btn_w, btn_h, 5, fill=1, stroke=0)
        self.setFont("Helvetica-Bold", 8.5)
        self.setFillColor(colors.white)
        self.drawCentredString(PAGE_WIDTH / 2.0, btn_y + 7, "JOIN TELEGRAM: @dailyaffairs25")

        self.setFont("Helvetica-Bold", 8)
        self.setFillColor(colors.HexColor("#64748b"))
        self.drawRightString(PAGE_WIDTH - 18, 18, f"{self._pageNumber}/{total_pages}")
        self.restoreState()

class CACanvas(BaseExamCanvas):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.doc_title = "DAILY CURRENT AFFAIRS (THEORY)"

class GKCanvas(BaseExamCanvas):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.doc_title = "CHAPTER-WISE STATIC GK NOTES"

class PracticeCanvas(BaseExamCanvas):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.doc_title = "DAILY EXAM DRILL (MATH + REASONING)"

# ==========================================
# 2. VECTOR VISUAL ILLUSTRATIONS
# ==========================================
def draw_asian_games_gold_winner():
    d = Drawing(PAGE_WIDTH - 40, 160)
    w, h = PAGE_WIDTH - 40, 160
    d.add(Rect(0, 0, w, h, rx=10, ry=10, fillColor=colors.HexColor("#061a40"), strokeColor=None))
    d.add(Circle(w - 30, 120, 80, fillColor=colors.HexColor("#003554"), fillOpacity=0.5, strokeColor=None))
    d.add(Line(0, 30, w, 30, strokeColor=colors.HexColor("#ef4444"), strokeWidth=2))
    d.add(Circle(65, 80, 24, fillColor=colors.HexColor("#eab308"), strokeColor=colors.HexColor("#fef08a"), strokeWidth=2))
    d.add(Circle(65, 80, 18, fillColor=colors.HexColor("#ca8a04"), strokeColor=None))
    d.add(String(58, 74, "1st", fontSize=13, fontName="Helvetica-Bold", fillColor=colors.white))
    d.add(Line(48, 120, 65, 102, strokeColor=colors.HexColor("#1d4ed8"), strokeWidth=5))
    d.add(Line(82, 120, 65, 102, strokeColor=colors.HexColor("#1d4ed8"), strokeWidth=5))
    d.add(Circle(135, 110, 12, fillColor=colors.HexColor("#fcd34d"), strokeColor=None))
    d.add(Polygon([125, 95, 145, 95, 140, 50, 130, 50], fillColor=colors.HexColor("#0284c7"), strokeColor=None))
    d.add(Line(115, 85, 165, 125, strokeColor=colors.HexColor("#f59e0b"), strokeWidth=3))
    d.add(Rect(16, 128, 150, 20, rx=10, ry=10, fillColor=colors.HexColor("#ca8a04"), strokeColor=None))
    d.add(String(24, 134, "ASIAN GAMES GOLD", fontSize=8.5, fontName="Helvetica-Bold", fillColor=colors.white))
    d.add(String(180, 85, "NEERAJ CHOPRA", fontSize=15, fontName="Helvetica-Bold", fillColor=colors.white))
    d.add(String(180, 65, "Men's Javelin Throw • Historic Gold", fontSize=9, fontName="Helvetica", fillColor=colors.HexColor("#cbd5e1")))
    d.add(String(180, 48, "Season Best Throw: 88.88m", fontSize=8.5, fontName="Helvetica-Bold", fillColor=colors.HexColor("#facc15")))
    return d

def draw_space_mission_art():
    d = Drawing(PAGE_WIDTH - 40, 160)
    w, h = PAGE_WIDTH - 40, 160
    d.add(Rect(0, 0, w, h, rx=10, ry=10, fillColor=colors.HexColor("#0b132b"), strokeColor=None))
    d.add(Circle(w/2, -180, 250, fillColor=colors.HexColor("#1d4ed8"), strokeColor=colors.HexColor("#38bdf8"), strokeWidth=2))
    for x, y in [(35, 130), (90, 140), (140, 120), (280, 145), (340, 125)]:
        d.add(Circle(x, y, 1.5, fillColor=colors.HexColor("#e2e8f0"), strokeColor=None))
    d.add(Rect(210, 55, 95, 45, rx=3, ry=3, fillColor=colors.HexColor("#e2e8f0"), strokeColor=colors.HexColor("#64748b"), strokeWidth=1))
    d.add(Polygon([130, 77, 190, 58, 190, 96], fillColor=colors.HexColor("#f8fafc"), strokeColor=colors.HexColor("#94a3b8"), strokeWidth=1))
    d.add(Line(192, 77, 208, 77, strokeColor=colors.HexColor("#facc15"), strokeWidth=2))
    d.add(Rect(16, 128, 140, 20, rx=10, ry=10, fillColor=colors.HexColor("#1e293b"), strokeColor=colors.HexColor("#38bdf8"), strokeWidth=1))
    d.add(String(24, 134, "ISRO SPACE MISSION", fontSize=8.5, fontName="Helvetica-Bold", fillColor=colors.HexColor("#38bdf8")))
    return d

def draw_banner_card(title, subtitle, badge, bg_color, accent_color):
    d = Drawing(PAGE_WIDTH - 40, 110)
    w, h = PAGE_WIDTH - 40, 110
    d.add(Rect(0, 0, w, h, rx=10, ry=10, fillColor=colors.HexColor(bg_color), strokeColor=None))
    d.add(Circle(w - 25, 80, 55, fillColor=colors.HexColor(accent_color), fillOpacity=0.25, strokeColor=None))
    d.add(Rect(16, 75, 150, 20, rx=10, ry=10, fillColor=colors.HexColor(accent_color), strokeColor=None))
    d.add(String(24, 81, badge, fontSize=8, fontName="Helvetica-Bold", fillColor=colors.white))
    d.add(String(20, 44, title, fontSize=14, fontName="Helvetica-Bold", fillColor=colors.white))
    d.add(String(20, 26, subtitle, fontSize=8.5, fontName="Helvetica", fillColor=colors.HexColor("#e2e8f0")))
    return d

# ==========================================
# 3. PDF BUILDERS
# ==========================================
def build_current_affairs_pdf(filename):
    doc = SimpleDocTemplate(filename, pagesize=(PAGE_WIDTH, PAGE_HEIGHT), leftMargin=20, rightMargin=20, topMargin=68, bottomMargin=110)
    styles = getSampleStyleSheet()
    head_style = ParagraphStyle('CAHead', fontName='Helvetica-Bold', fontSize=13.5, leading=17.5, textColor=colors.HexColor('#0f172a'), spaceAfter=8)
    story = []

    story.append(draw_asian_games_gold_winner())
    story.append(Spacer(1, 10))
    story.append(Paragraph("NEERAJ CHOPRA CLINCHES HISTORIC GOLD IN ASIAN GAMES JAVELIN THROW", head_style))
    sports_points = [
        ("Achievement", "Neeraj Chopra successfully defended his Asian Games gold medal with a season-best effort of 88.88m."),
        ("Double Podium", "Kishore Jena secured the silver medal with a personal best of 87.54m, securing India's historic 1-2 finish."),
        ("Olympic Qualification", "Both athletes confirmed direct qualification for international athletic competitions."),
        ("Static Sports GK", "First Indian track-and-field athlete to win Olympic gold (Tokyo 2020) and World Athletics Championship gold.")
    ]
    for label, text in sports_points:
        cell = [Paragraph(f"<font color='#ca8a04'><b>▶ {label}:</b></font> <font color='#334155'>{text}</font>",
                          ParagraphStyle('P1', fontName='Helvetica', fontSize=9, leading=13.5))]
        t = Table([cell], colWidths=[PAGE_WIDTH - 40])
        t.setStyle(TableStyle([
            ('BACKGROUND', (0,0), (-1,-1), colors.HexColor("#ffffff")),
            ('BOX', (0,0), (-1,-1), 0.75, colors.HexColor("#e2e8f0")),
            ('LINELEFT', (0,0), (0,-1), 3.5, colors.HexColor("#ca8a04")),
            ('TOPPADDING', (0,0), (-1,-1), 5), ('BOTTOMPADDING', (0,0), (-1,-1), 5),
            ('LEFTPADDING', (0,0), (-1,-1), 10), ('RIGHTPADDING', (0,0), (-1,-1), 10),
        ]))
        story.append(t)
        story.append(Spacer(1, 5))

    story.append(PageBreak())

    story.append(draw_space_mission_art())
    story.append(Spacer(1, 10))
    story.append(Paragraph("ISRO COMPLETES GAGANYAAN MODULE SEPARATION TESTS AT VSSC", head_style))
    space_points = [
        ("Core Update", "ISRO successfully validated critical separation mechanisms between Crew Module and Service Module."),
        ("Test Centre", "Conducted under simulated orbital conditions at Vikram Sarabhai Space Centre (VSSC), Thiruvananthapuram."),
        ("Mission Target", "Crucial clearance ahead of the uncrewed Gaganyaan-1 (G1) test flight carrying robot Vyommitra."),
        ("Static Anchor", "Crew Module houses astronauts; Service Module provides orbital power, fluids, and propulsion support.")
    ]
    for label, text in space_points:
        cell = [Paragraph(f"<font color='#2563eb'><b>▶ {label}:</b></font> <font color='#334155'>{text}</font>",
                          ParagraphStyle('P2', fontName='Helvetica', fontSize=9, leading=13.5))]
        t = Table([cell], colWidths=[PAGE_WIDTH - 40])
        t.setStyle(TableStyle([
            ('BACKGROUND', (0,0), (-1,-1), colors.HexColor("#ffffff")),
            ('BOX', (0,0), (-1,-1), 0.75, colors.HexColor("#e2e8f0")),
            ('LINELEFT', (0,0), (0,-1), 3.5, colors.HexColor("#2563eb")),
            ('TOPPADDING', (0,0), (-1,-1), 5), ('BOTTOMPADDING', (0,0), (-1,-1), 5),
            ('LEFTPADDING', (0,0), (-1,-1), 10), ('RIGHTPADDING', (0,0), (-1,-1), 10),
        ]))
        story.append(t)
        story.append(Spacer(1, 5))

    doc.build(story, canvasmaker=CACanvas)

def build_static_gk_pdf(filename):
    doc = SimpleDocTemplate(filename, pagesize=(PAGE_WIDTH, PAGE_HEIGHT), leftMargin=20, rightMargin=20, topMargin=68, bottomMargin=110)
    story = []

    story.append(draw_banner_card("CHAPTER 1: INDIAN POLITY", "Constitutional Framework & Fundamental Rights", "EXAM STATIC REVISION", "#1e1b4b", "#4f46e5"))
    story.append(Spacer(1, 10))

    gk_theory = [
        ("Fundamental Rights (Part III)", "Enshrined in Articles 12 to 35. Known as the Magna Carta of India. Borrowed from USA Bill of Rights."),
        ("Article 21 (Life & Liberty)", "No person shall be deprived of life or personal liberty except according to procedure established by law. Encompasses Right to Privacy, Internet & Clean Environment."),
        ("Article 32 (Constitutional Remedies)", "Dr. B.R. Ambedkar called it the 'Heart and Soul of the Constitution'. Supreme Court issues 5 writs: Habeas Corpus, Mandamus, Prohibition, Certiorari, Quo-Warranto."),
        ("Fundamental Duties (Part IVA)", "Added by 42nd Amendment (1976) on Swaran Singh Committee recommendation. Currently 11 duties under Article 51A.")
    ]
    for title, desc in gk_theory:
        cell = [
            Paragraph(f"<b><font color='#4338ca'>{title}</font></b>", ParagraphStyle('G1', fontName='Helvetica-Bold', fontSize=9.5, leading=13)),
            Spacer(1, 3),
            Paragraph(f"<font color='#334155'>{desc}</font>", ParagraphStyle('G2', fontName='Helvetica', fontSize=8.5, leading=12.5))
        ]
        t = Table([cell], colWidths=[PAGE_WIDTH - 40])
        t.setStyle(TableStyle([
            ('BACKGROUND', (0,0), (-1,-1), colors.HexColor("#ffffff")),
            ('BOX', (0,0), (-1,-1), 0.75, colors.HexColor("#e2e8f0")),
            ('LINELEFT', (0,0), (0,-1), 3.5, colors.HexColor("#4f46e5")),
            ('TOPPADDING', (0,0), (-1,-1), 6), ('BOTTOMPADDING', (0,0), (-1,-1), 6),
            ('LEFTPADDING', (0,0), (-1,-1), 10), ('RIGHTPADDING', (0,0), (-1,-1), 10),
        ]))
        story.append(t)
        story.append(Spacer(1, 5))

    doc.build(story, canvasmaker=GKCanvas)

def build_practice_drill_pdf(filename):
    doc = SimpleDocTemplate(filename, pagesize=(PAGE_WIDTH, PAGE_HEIGHT), leftMargin=20, rightMargin=20, topMargin=68, bottomMargin=110)
    story = []

    story.append(draw_banner_card("SECTION A: SPEED ARITHMETIC", "Percentages, Profit & Loss and Time-Work", "10-MINUTE DAILY DRILL", "#064e3b", "#059669"))
    story.append(Spacer(1, 8))

    math_questions = [
        ("Q1. Percentage & Successive Discount",
         "A shopkeeper marks an article 40% above cost price and allows a discount of 25%. Find his profit percentage.",
         "A) 5%     B) 8%     C) 10%     D) 12%",
         "Sol: Let CP = 100. MP = 140. SP = 140 × 0.75 = 105. Profit% = ((105-100)/100) × 100 = 5% (Ans: A)"),
        ("Q2. Time and Work",
         "A can finish a work in 12 days and B in 18 days. If they work together for 4 days, what fraction of work is left?",
         "A) 5/9     B) 4/9     C) 1/3     D) 2/5",
         "Sol: 1 day work = 1/12 + 1/18 = 5/36. 4 days work = 4 × 5/36 = 5/9. Remaining = 1 - 5/9 = 4/9 (Ans: B)")
    ]
    for q_title, q_text, opts, sol in math_questions:
        cell = [
            Paragraph(f"<b><font color='#065f46'>{q_title}</font></b>", ParagraphStyle('M1', fontName='Helvetica-Bold', fontSize=9, leading=12)),
            Spacer(1, 2),
            Paragraph(f"<font color='#0f172a'>{q_text}</font>", ParagraphStyle('M2', fontName='Helvetica', fontSize=8.5, leading=12)),
            Spacer(1, 2),
            Paragraph(f"<b><font color='#475569'>{opts}</font></b>", ParagraphStyle('M3', fontName='Helvetica', fontSize=8, leading=11)),
            Spacer(1, 3),
            Paragraph(f"<b><font color='#059669'>✓ {sol}</font></b>", ParagraphStyle('M4', fontName='Helvetica-Bold', fontSize=8, leading=10.5))
        ]
        t = Table([cell], colWidths=[PAGE_WIDTH - 40])
        t.setStyle(TableStyle([
            ('BACKGROUND', (0,0), (-1,-1), colors.HexColor("#ffffff")),
            ('BOX', (0,0), (-1,-1), 0.75, colors.HexColor("#e2e8f0")),
            ('LINELEFT', (0,0), (0,-1), 3.5, colors.HexColor("#059669")),
            ('TOPPADDING', (0,0), (-1,-1), 5), ('BOTTOMPADDING', (0,0), (-1,-1), 5),
            ('LEFTPADDING', (0,0), (-1,-1), 8), ('RIGHTPADDING', (0,0), (-1,-1), 8),
        ]))
        story.append(t)
        story.append(Spacer(1, 4))

    story.append(PageBreak())

    story.append(draw_banner_card("SECTION B: SPEED REASONING", "Puzzles, Syllogisms & Coding-Decoding", "LOGICAL APTITUDE", "#431407", "#ea580c"))
    story.append(Spacer(1, 8))

    reasoning_questions = [
        ("Q1. Number Series Analogy",
         "Find the next term: 6, 25, 62, 123, 214, ?",
         "A) 341     B) 343     C) 339     D) 342",
         "Sol: Pattern is n³ - 2: 2³-2=6, 3³-2=25, 4³-2=62, 5³-2=123, 6³-2=214, 7³-2 = 343 - 2 = 341 (Ans: A)"),
        ("Q2. Syllogism Logic",
         "Statements: All metals are solids. Some solids are conductors.<br/>Conclusions: I. Some conductors are metals. II. Some conductors are solids.",
         "A) Only I follows     B) Only II follows     C) Both     D) Neither",
         "Sol: Direct converse of 'Some solids are conductors' is 'Some conductors are solids'. II follows. (Ans: B)")
    ]
    for q_title, q_text, opts, sol in reasoning_questions:
        cell = [
            Paragraph(f"<b><font color='#9a3412'>{q_title}</font></b>", ParagraphStyle('R1', fontName='Helvetica-Bold', fontSize=9, leading=12)),
            Spacer(1, 2),
            Paragraph(f"<font color='#0f172a'>{q_text}</font>", ParagraphStyle('R2', fontName='Helvetica', fontSize=8.5, leading=12)),
            Spacer(1, 2),
            Paragraph(f"<b><font color='#475569'>{opts}</font></b>", ParagraphStyle('R3', fontName='Helvetica', fontSize=8, leading=11)),
            Spacer(1, 3),
            Paragraph(f"<b><font color='#ea580c'>✓ {sol}</font></b>", ParagraphStyle('R4', fontName='Helvetica-Bold', fontSize=8, leading=10.5))
        ]
        t = Table([cell], colWidths=[PAGE_WIDTH - 40])
        t.setStyle(TableStyle([
            ('BACKGROUND', (0,0), (-1,-1), colors.HexColor("#ffffff")),
            ('BOX', (0,0), (-1,-1), 0.75, colors.HexColor("#e2e8f0")),
            ('LINELEFT', (0,0), (0,-1), 3.5, colors.HexColor("#ea580c")),
            ('TOPPADDING', (0,0), (-1,-1), 5), ('BOTTOMPADDING', (0,0), (-1,-1), 5),
            ('LEFTPADDING', (0,0), (-1,-1), 8), ('RIGHTPADDING', (0,0), (-1,-1), 8),
        ]))
        story.append(t)
        story.append(Spacer(1, 4))

    doc.build(story, canvasmaker=PracticeCanvas)

# ==========================================
# 4. TELEGRAM SENDER
# ==========================================
def send_telegram_doc(pdf_path, caption_text):
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendDocument"
    with open(pdf_path, 'rb') as f:
        files = {'document': f}
        data = {'chat_id': TELEGRAM_CHAT_ID, 'caption': caption_text, 'parse_mode': 'Markdown'}
        resp = requests.post(url, files=files, data=data)
    print(f"Sent {pdf_path}: {resp.status_code}")
    if resp.status_code != 200:
        raise RuntimeError(f"Error posting {pdf_path}: {resp.text}")

if __name__ == "__main__":
    today = datetime.now().strftime("%d_%b_%Y")
    
    # 1. Build and send Current Affairs PDF
    ca_pdf = f"1_Daily_Current_Affairs_Theory_{today}.pdf"
    build_current_affairs_pdf(ca_pdf)
    send_telegram_doc(ca_pdf, f"📑 *[1/3] Daily Current Affairs Theory & Sports Capsule*\n🗓 Date: {datetime.now().strftime('%d %B %Y')}\nIncludes Asian Games champion analysis & space updates.")

    # 2. Build and send Static GK PDF
    gk_pdf = f"2_Static_GK_Chapter_Notes_{today}.pdf"
    build_static_gk_pdf(gk_pdf)
    send_telegram_doc(gk_pdf, f"🏛️ *[2/3] Chapter-Wise Static GK Notes*\nTopic: Indian Polity • Fundamental Rights (Articles 12-35)")

    # 3. Build and send Practice Drill PDF
    drill_pdf = f"3_Daily_Practice_Drill_Math_Reasoning_{today}.pdf"
    build_practice_drill_pdf(drill_pdf)
    send_telegram_doc(drill_pdf, f"🎯 *[3/3] Daily Exam Practice Drill*\nQuantitative Arithmetic + Speed Reasoning + Complete Solutions")
    
