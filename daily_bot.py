import os
import requests
from datetime import datetime
from reportlab.lib import colors
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, PageBreak
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.pdfgen import canvas
from reportlab.graphics.shapes import Drawing, Rect, String, Circle

# --- CONFIGURATION ---
TELEGRAM_BOT_TOKEN = "8395103968:AAH_HQI9IANzBtPfOUczQ4V05PyjoEYfsK4"
TELEGRAM_CHAT_ID = "@dailyaffairs25"
PAGE_WIDTH = 450
PAGE_HEIGHT = 800

class SlideCardCanvas(canvas.Canvas):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._saved_page_states = []

    def showPage(self):
        self._saved_page_states.append(dict(self.__dict__))
        self._startPage()

    def save(self):
        num_pages = len(self._saved_page_states)
        for state in self._saved_page_states:
            self.__dict__.update(state)
            self.draw_slide_decorations(num_pages)
            super().showPage()
        super().save()

    def draw_slide_decorations(self, total_pages):
        self.saveState()
        today_str = datetime.now().strftime("%d %B %Y").upper()

        # Header Bar
        self.setFillColor(colors.HexColor("#0f172a"))
        self.rect(0, PAGE_HEIGHT - 48, PAGE_WIDTH, 48, fill=1, stroke=0)
        
        self.setFont("Helvetica-Bold", 10)
        self.setFillColor(colors.HexColor("#38bdf8"))
        self.drawString(22, PAGE_HEIGHT - 30, "DAILY EXAM CURRENT AFFAIRS")
        
        self.setFont("Helvetica-Bold", 10)
        self.setFillColor(colors.white)
        self.drawRightString(PAGE_WIDTH - 22, PAGE_HEIGHT - 30, today_str)

        # Footer Branding
        footer_h = 100
        self.setFillColor(colors.HexColor("#1e293b"))
        self.rect(0, 0, PAGE_WIDTH, footer_h, fill=1, stroke=0)

        self.setStrokeColor(colors.HexColor("#3b82f6"))
        self.setLineWidth(3)
        self.line(0, footer_h, PAGE_WIDTH, footer_h)

        self.setFont("Helvetica-Bold", 12)
        self.setFillColor(colors.HexColor("#f8fafc"))
        self.drawCentredString(PAGE_WIDTH / 2.0, 72, "CRACK GOVT EXAMS | DAILY CAPSULE")

        self.setFont("Helvetica", 9)
        self.setFillColor(colors.HexColor("#94a3b8"))
        self.drawCentredString(PAGE_WIDTH / 2.0, 52, "Complete GK/GS • UPSC, SSC, Banking, Railways & State Exams")

        self.setFillColor(colors.HexColor("#2563eb"))
        self.roundRect(PAGE_WIDTH / 2.0 - 90, 16, 180, 24, 6, fill=1, stroke=0)

        self.setFont("Helvetica-Bold", 9)
        self.setFillColor(colors.white)
        self.drawCentredString(PAGE_WIDTH / 2.0, 24, "DOWNLOAD DAILY PDF & NOTES")

        self.setFont("Helvetica-Bold", 8)
        self.setFillColor(colors.HexColor("#64748b"))
        self.drawRightString(PAGE_WIDTH - 18, 18, f"Card {self._pageNumber}/{total_pages}")
        self.restoreState()

def make_art_placeholder(title, bg_color):
    d = Drawing(PAGE_WIDTH - 48, 160)
    d.add(Rect(0, 0, PAGE_WIDTH - 48, 160, rx=10, ry=10, fillColor=colors.HexColor(bg_color), strokeColor=None))
    d.add(Circle(PAGE_WIDTH - 48 - 40, 120, 70, fillColor=colors.HexColor("#ffffff"), fillOpacity=0.08, strokeColor=None))
    d.add(Rect(16, 120, 130, 22, rx=4, ry=4, fillColor=colors.HexColor("#ffffff"), fillOpacity=0.2, strokeColor=None))
    d.add(String(24, 127, "EXAM VISUAL FOCUS", fontSize=8, fontName="Helvetica-Bold", fillColor=colors.white))
    d.add(String(20, 75, title[:30], fontSize=15, fontName="Helvetica-Bold", fillColor=colors.white))
    d.add(String(20, 52, "Target Exam Static & Dynamic GK Connection", fontSize=9, fontName="Helvetica", fillColor=colors.HexColor("#e2e8f0")))
    return d

def generate_pdf(filename, news_items):
    doc = SimpleDocTemplate(
        filename,
        pagesize=(PAGE_WIDTH, PAGE_HEIGHT),
        leftMargin=24,
        rightMargin=24,
        topMargin=64,
        bottomMargin=115
    )
    styles = getSampleStyleSheet()

    cat_style = ParagraphStyle('Cat', fontName='Helvetica-Bold', fontSize=10, leading=13, textColor=colors.HexColor('#2563eb'), spaceAfter=6)
    head_style = ParagraphStyle('Head', fontName='Helvetica-Bold', fontSize=14, leading=19, textColor=colors.HexColor('#0f172a'), spaceAfter=14)
    body_style = ParagraphStyle('Body', fontName='Helvetica', fontSize=10.5, leading=16, textColor=colors.HexColor('#334155'), spaceAfter=11)

    story = []
    palette = ["#1e3a8a", "#0369a1", "#047857", "#7c2d12", "#4338ca", "#0f766e"]

    for idx, item in enumerate(news_items):
        color = palette[idx % len(palette)]
        story.append(make_art_placeholder(item["category"], color))
        story.append(Spacer(1, 14))
        story.append(Paragraph(item["category"], cat_style))
        story.append(Paragraph(item["headline"], head_style))

        for bullet in item["bullets"]:
            story.append(Paragraph(f"<b>•</b>  {bullet}", body_style))

        if idx < len(news_items) - 1:
            story.append(PageBreak())

    doc.build(story, canvasmaker=SlideCardCanvas)

def send_to_telegram(pdf_path):
    today = datetime.now().strftime("%d %B %Y")
    caption = f"📚 *Daily Current Affairs Bulletin*\n🗓 *Date:* {today}\n🎯 *For:* UPSC, SSC, Banking, Railways & Defence Exams\n\n⬇️ Download the complete slide deck attached below."
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendDocument"

    with open(pdf_path, 'rb') as f:
        files = {'document': f}
        data = {'chat_id': TELEGRAM_CHAT_ID, 'caption': caption, 'parse_mode': 'Markdown'}
        response = requests.post(url, files=files, data=data)

    if response.status_code == 200:
        print("Successfully posted to Telegram channel!")
    else:
        print(f"Failed to post: {response.text}")

if __name__ == "__main__":
    # Sample daily feed (can also be connected directly to your news API or database)
    sample_news = [
        {
            "category": "DEFENCE & SECURITY",
            "headline": "INDIAN NAVY COMMISSIONS FIRST INDIGENOUS MPV INS SAMARTHAK",
            "bullets": [
                "Commissioned at INS Kadamba Naval Base, Karwar, Karnataka.",
                "Built by L&T Shipyard with over 75% indigenous content under Make in India.",
                "Specialised in warship towing, target recovery, and coastal surface patrol.",
                "Relieves destroyers and frigates from routine fleet logistics duties."
            ]
        },
        {
            "category": "SPACE TECHNOLOGY",
            "headline": "ISRO COMPLETES GAGANYAAN MODULE SEPARATION TESTS AT VSSC",
            "bullets": [
                "Validated separation of Crew Module (CM) and Service Module (SM).",
                "Tests conducted under simulated flight conditions at VSSC, Thiruvananthapuram.",
                "Paves the way for the uncrewed G1 mission featuring humanoid Vyommitra.",
                "Crew module protects human astronauts during extreme orbital re-entry."
            ]
        }
    ]

    pdf_file = f"Current_Affairs_{datetime.now().strftime('%d_%b_%Y')}.pdf"
    generate_pdf(pdf_file, sample_news)
    send_to_telegram(pdf_file)
      
