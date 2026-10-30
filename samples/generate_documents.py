"""Generate the fictitious documents of the demo: the files a facilities team keeps.

Everything below is invented: the company, people, buildings, figures and addresses.

Output (in samples/documents/):
  facilities-annual-report-2026.pdf   digital PDF, 5 pages, headings, tables, page numbers
  boiler-inspection-letter.pdf        scanned letter, 2 pages, image only (needs OCR)
  visitor-and-contractor-policy.docx  Word policy with headings, lists and tables
  maintenance-register.xlsx           Excel register with two sheets

Usage:
  python generate_documents.py
"""

from __future__ import annotations

import io
import random
from pathlib import Path

import numpy as np
import pypdfium2 as pdfium
from docx import Document
from docx.shared import Pt
from openpyxl import Workbook
from openpyxl.styles import Font
from PIL import Image, ImageFilter
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import PageBreak, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

HERE = Path(__file__).resolve().parent
OUT = HERE / "documents"
COMPANY = "Larkfield Estates Ltd"

STYLES = getSampleStyleSheet()
H1 = ParagraphStyle("H1", parent=STYLES["Heading1"], fontSize=16, spaceBefore=6, spaceAfter=8)
H2 = ParagraphStyle("H2", parent=STYLES["Heading2"], fontSize=12.5, spaceBefore=10, spaceAfter=6)
BODY = ParagraphStyle("Body", parent=STYLES["BodyText"], fontSize=10, leading=14, spaceAfter=6)
TITLE = ParagraphStyle("Title", parent=STYLES["Title"], fontSize=22, spaceAfter=4)


def table(rows, widths=None):
    t = Table(rows, colWidths=widths, hAlign="LEFT")
    t.setStyle(TableStyle([
        ("FONT", (0, 0), (-1, 0), "Helvetica-Bold", 9.5),
        ("FONT", (0, 1), (-1, -1), "Helvetica", 9.5),
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#E8EBEE")),
        ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#9AA3AB")),
        ("ALIGN", (1, 1), (-1, -1), "RIGHT"),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING", (0, 0), (-1, -1), 3),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
    ]))
    return t


def footer(title):
    def draw(c, doc):
        c.saveState()
        c.setFont("Helvetica", 8)
        c.setFillColor(colors.HexColor("#666666"))
        c.drawString(20 * mm, 12 * mm, f"{COMPANY} - {title}")
        c.drawRightString(A4[0] - 20 * mm, 12 * mm, f"Page {doc.page}")
        c.restoreState()
    return draw


# --------------------------------------------------------------------------
# 1. Annual report (digital PDF)
# --------------------------------------------------------------------------


def annual_report(path: Path) -> None:
    title = "Facilities Annual Report 2026"
    doc = SimpleDocTemplate(str(path), pagesize=A4, title=title, author=COMPANY,
                            leftMargin=20 * mm, rightMargin=20 * mm, topMargin=20 * mm, bottomMargin=22 * mm)
    s = []
    s += [Paragraph(title, TITLE), Paragraph(f"{COMPANY}, facilities department. Reporting year January to December 2026.", BODY), Spacer(1, 6)]
    s += [Paragraph("1. Overview", H1),
          Paragraph("Larkfield Estates manages three office buildings: North House, River Court and Mill Yard. "
                    "The facilities team of eleven people looks after maintenance, energy, cleaning, security and "
                    "health and safety for about 1,350 staff and tenants.", BODY),
          Paragraph("The main goals for 2026 were to cut electricity use by 10 percent, to close maintenance "
                    "tickets faster and to run a fire evacuation drill in every building twice a year. "
                    "All three goals were met.", BODY),
          Paragraph("1.1 Key figures", H2),
          table([["Indicator", "2025", "2026"],
                 ["Buildings managed", "3", "3"],
                 ["Floor area (m2)", "41,200", "41,200"],
                 ["Maintenance tickets opened", "1,184", "1,062"],
                 ["Average days to close a ticket", "4.6", "3.4"],
                 ["Electricity use (kWh)", "890,650", "787,400"],
                 ["Facilities operating cost (GBP)", "2,318,000", "2,241,500"]], [80 * mm, 35 * mm, 35 * mm]),
          PageBreak()]

    s += [Paragraph("2. Energy", H1),
          Paragraph("2.1 Electricity", H2),
          Paragraph("Electricity use fell by 11.6 percent across the portfolio. The largest saving came from the "
                    "LED lighting retrofit at North House, completed in April 2026 at a cost of GBP 148,000. "
                    "The retrofit replaced 2,140 fluorescent fittings and added occupancy sensors in meeting rooms.", BODY),
          table([["Building", "2025 kWh", "2026 kWh", "Change"],
                 ["North House", "412,000", "361,500", "-12.3%"],
                 ["River Court", "288,400", "259,100", "-10.2%"],
                 ["Mill Yard", "190,250", "166,800", "-12.3%"],
                 ["Total", "890,650", "787,400", "-11.6%"]], [55 * mm, 35 * mm, 35 * mm, 25 * mm]),
          Spacer(1, 8),
          Paragraph("2.2 Gas and heating", H2),
          Paragraph("Gas is only used for heating at River Court, which has two gas boilers installed in 2011. "
                    "Gas use rose by 3 percent because of a cold February. Boiler 2 was inspected in October; "
                    "see the inspection letter for the findings.", BODY),
          table([["Building", "Heating", "2026 gas use (kWh)"],
                 ["North House", "Air source heat pumps", "0"],
                 ["River Court", "Two gas boilers", "512,300"],
                 ["Mill Yard", "District heating", "0"]], [55 * mm, 55 * mm, 45 * mm]),
          PageBreak()]

    s += [Paragraph("3. Maintenance", H1),
          Paragraph("The team closed 1,041 of the 1,062 tickets opened in 2026. The average time to close a ticket "
                    "fell from 4.6 to 3.4 working days, mainly because reactive jobs are now assigned to a contractor "
                    "on the day they are logged.", BODY),
          Paragraph("3.1 Tickets by category", H2),
          table([["Category", "Opened", "Closed", "Average days to close"],
                 ["Lighting", "318", "316", "1.8"],
                 ["Heating and cooling", "244", "236", "4.1"],
                 ["Plumbing", "201", "198", "3.2"],
                 ["Lifts", "57", "55", "6.9"],
                 ["Doors and access control", "142", "140", "2.7"],
                 ["Other", "100", "96", "4.4"]], [60 * mm, 25 * mm, 25 * mm, 45 * mm]),
          Spacer(1, 8),
          Paragraph("3.2 Lifts", H2),
          Paragraph("Lift faults took the longest to fix because spare parts for the two River Court lifts must be "
                    "ordered from the manufacturer. Lift maintenance is contracted to Vertex Lift Services under a "
                    "three-year contract that ends in June 2028.", BODY),
          PageBreak()]

    s += [Paragraph("4. Health and safety", H1),
          Paragraph("Fire alarms are tested every Monday at 10:00 in every building. Each building held two "
                    "evacuation drills. The target evacuation time is under five minutes.", BODY),
          Paragraph("4.1 Evacuation drills", H2),
          table([["Date", "Building", "People", "Evacuation time"],
                 ["11 March 2026", "North House", "640", "4 min 05 s"],
                 ["18 March 2026", "River Court", "430", "4 min 40 s"],
                 ["25 March 2026", "Mill Yard", "280", "3 min 20 s"],
                 ["16 September 2026", "North House", "655", "3 min 55 s"],
                 ["23 September 2026", "River Court", "425", "4 min 10 s"],
                 ["30 September 2026", "Mill Yard", "290", "3 min 05 s"]], [40 * mm, 40 * mm, 25 * mm, 40 * mm]),
          Spacer(1, 8),
          Paragraph("4.2 Incidents", H2),
          Paragraph("Four minor injuries were reported, all slips on wet floors at building entrances. Entrance "
                    "matting was extended at North House and Mill Yard in November. No incident was reportable "
                    "to the regulator.", BODY),
          PageBreak()]

    s += [Paragraph("5. Budget 2027", H1),
          Paragraph("The facilities budget for 2027 is GBP 2,410,000, including three capital projects.", BODY),
          table([["Project", "Building", "Budget (GBP)", "Planned"],
                 ["Roof replacement", "River Court", "185,000", "Q2 2027"],
                 ["Replace gas boilers with heat pumps", "River Court", "420,000", "Q3 2027"],
                 ["Access control upgrade", "All buildings", "96,000", "Q1 2027"]], [65 * mm, 35 * mm, 30 * mm, 25 * mm]),
          Spacer(1, 8),
          Paragraph("6. Contacts", H1),
          Paragraph("Head of facilities: Daniel Ashworth. Health and safety manager: Priya Nandakumar. "
                    "Energy manager: Tom Reyes. The facilities help desk is reachable on extension 4400.", BODY)]
    doc.build(s, onFirstPage=footer(title), onLaterPages=footer(title))


# --------------------------------------------------------------------------
# 2. Inspection letter, printed and scanned
# --------------------------------------------------------------------------


def inspection_letter_clean() -> bytes:
    buf = io.BytesIO()
    title = "Boiler inspection, River Court"
    doc = SimpleDocTemplate(buf, pagesize=A4, leftMargin=25 * mm, rightMargin=25 * mm, topMargin=22 * mm, bottomMargin=22 * mm)
    letter = ParagraphStyle("Letter", parent=BODY, fontName="Times-Roman", fontSize=11, leading=15)
    head = ParagraphStyle("Head", parent=letter, fontName="Times-Bold", fontSize=14)
    sub = ParagraphStyle("Sub", parent=letter, fontName="Times-Bold", fontSize=11.5, spaceBefore=8)
    s = [Paragraph("Hartwell Heating Services Ltd", head),
         Paragraph("7 Tanner Row, Ashby Vale, AV2 6HT. Gas safe registered engineers.", letter),
         Spacer(1, 10),
         Paragraph("Facilities Department<br/>Larkfield Estates Ltd<br/>River Court, 3 Weir Lane<br/>Ashby Vale AV1 2RC", letter),
         Spacer(1, 10),
         Paragraph("21 October 2026", letter),
         Paragraph("Our reference: HHS/RC/2026-114", letter),
         Spacer(1, 6),
         Paragraph(f"{title}: annual service report", sub),
         Paragraph("Dear Mr Ashworth,", letter),
         Paragraph("Our engineer, Martin Clegg, serviced the two gas boilers in the River Court plant room on "
                   "14 October 2026. Boiler 1 is in good condition. Boiler 2 is safe to use, but two findings need "
                   "action before the next heating season.", letter),
         Paragraph("Findings", sub),
         Paragraph("1. The expansion vessel of boiler 2 has lost pressure (0.4 bar against 1.0 bar required). "
                   "We recommend replacing the expansion vessel within three months.", letter),
         Paragraph("2. The flue gas analysis of boiler 2 shows a carbon monoxide reading of 62 ppm. This is below "
                   "the action level of 100 ppm, but higher than last year, and the burner should be cleaned at "
                   "the next visit.", letter),
         PageBreak(),
         Paragraph("Measurements", sub),
         Table([["Reading", "Boiler 1", "Boiler 2", "Limit"],
                ["Carbon monoxide (ppm)", "18", "62", "100"],
                ["CO/CO2 ratio", "0.0011", "0.0039", "0.0080"],
                ["Combustion efficiency (%)", "91.2", "88.4", "-"],
                ["System pressure (bar)", "1.4", "1.3", "1.0 - 2.0"],
                ["Expansion vessel (bar)", "1.0", "0.4", "1.0"]],
               style=TableStyle([("GRID", (0, 0), (-1, -1), 0.6, colors.black),
                                 ("FONT", (0, 0), (-1, 0), "Times-Bold", 11),
                                 ("FONT", (0, 1), (-1, -1), "Times-Roman", 11),
                                 ("ALIGN", (1, 1), (-1, -1), "RIGHT"),
                                 ("TOPPADDING", (0, 0), (-1, -1), 4), ("BOTTOMPADDING", (0, 0), (-1, -1), 4)]),
               hAlign="LEFT"),
         Spacer(1, 10),
         Paragraph("Next service", sub),
         Paragraph("The next annual service of both boilers is due by 14 March 2027. The quotation for the "
                   "expansion vessel replacement is GBP 1,240 excluding VAT, parts and labour included.", letter),
         Spacer(1, 10),
         Paragraph("Yours sincerely,", letter),
         Spacer(1, 18),
         Paragraph("Helen Marsh<br/>Service Manager, Hartwell Heating Services Ltd", letter)]
    doc.build(s)
    return buf.getvalue()


def scan(pdf_bytes: bytes, path: Path, seed: int) -> None:
    rng = np.random.default_rng(seed)
    pdf = pdfium.PdfDocument(pdf_bytes)
    pages = []
    for i in range(len(pdf)):
        img = pdf[i].render(scale=200 / 72, grayscale=True).to_pil().convert("L")
        img = img.rotate([0.7, -0.5][i % 2], resample=Image.BICUBIC, fillcolor=255)
        arr = np.asarray(img).astype(np.float32)
        arr = 238 - (238 - arr) * 0.9 + rng.normal(0, 6, arr.shape)
        pages.append(Image.fromarray(np.clip(arr, 0, 255).astype(np.uint8), "L").filter(ImageFilter.GaussianBlur(0.4)))
    pdf.close()
    pages[0].save(path, "PDF", resolution=200, save_all=True, append_images=pages[1:], quality=70)


# --------------------------------------------------------------------------
# 3. Word policy
# --------------------------------------------------------------------------


def policy(path: Path) -> None:
    d = Document()
    d.core_properties.title = "Visitor and Contractor Policy"
    d.core_properties.author = COMPANY
    style = d.styles["Normal"]
    style.font.name = "Calibri"
    style.font.size = Pt(11)
    d.add_heading("Visitor and Contractor Policy", 0)
    d.add_paragraph(f"{COMPANY}. Version 3.2, approved by the head of facilities on 2 June 2026. Review date: June 2027.")

    d.add_heading("1. Purpose", 1)
    d.add_paragraph("This policy keeps visitors, contractors and staff safe in all Larkfield Estates buildings and "
                    "makes sure everyone on site can be accounted for in an emergency.")

    d.add_heading("2. Visitors", 1)
    d.add_paragraph("All visitors sign in at reception and receive a visitor badge, which must be visible at all times.", style="List Bullet")
    d.add_paragraph("Visitors are met at reception by their host and escorted while in the building.", style="List Bullet")
    d.add_paragraph("Badges are returned at reception when leaving. Lost badges are reported to security.", style="List Bullet")

    d.add_heading("3. Contractors", 1)
    d.add_paragraph("Contractors must hold a valid permit to work before starting any job. Permits are issued by the "
                    "facilities help desk on extension 4400 and are valid for one day only.")
    d.add_heading("3.1 Escort and permit rules", 2)
    rows = [("Type of work", "Permit to work", "Escort required"),
            ("Routine maintenance in public areas", "Yes", "No"),
            ("Work in plant rooms or on roofs", "Yes, plus a risk assessment", "Yes"),
            ("Hot work (welding, cutting)", "Yes, hot work permit", "Yes, plus a fire watch of 60 minutes"),
            ("Deliveries", "No", "No")]
    t = d.add_table(rows=len(rows), cols=3)
    t.style = "Table Grid"
    for r, row in enumerate(rows):
        for c, value in enumerate(row):
            t.cell(r, c).text = value
            if r == 0:
                t.cell(r, c).paragraphs[0].runs[0].bold = True
    d.add_paragraph()
    d.add_paragraph("Contractors working alone in a plant room must check in with the help desk every two hours.")

    d.add_heading("4. Parking", 1)
    d.add_paragraph("Visitor parking spaces are numbered 1 to 12 at North House and 1 to 6 at River Court. "
                    "Mill Yard has no visitor parking; visitors use the public car park on Canal Street. "
                    "Contractor vans may park in the loading bay for up to 30 minutes.")

    d.add_heading("5. Emergencies", 1)
    d.add_paragraph("When the fire alarm sounds, everyone leaves by the nearest exit and goes to the assembly point. "
                    "Hosts are responsible for their visitors.")
    rows = [("Building", "Assembly point", "Fire warden on duty"),
            ("North House", "Car park A, by the main gate", "Reception manager"),
            ("River Court", "Weir Lane, in front of number 8", "Plant room supervisor"),
            ("Mill Yard", "Canal Street car park, level 0", "Security officer")]
    t = d.add_table(rows=len(rows), cols=3)
    t.style = "Table Grid"
    for r, row in enumerate(rows):
        for c, value in enumerate(row):
            t.cell(r, c).text = value
            if r == 0:
                t.cell(r, c).paragraphs[0].runs[0].bold = True
    d.save(path)


# --------------------------------------------------------------------------
# 4. Excel register
# --------------------------------------------------------------------------


def register(path: Path) -> None:
    wb = Workbook()
    ws = wb.active
    ws.title = "Tickets"
    head = ["Ticket", "Opened", "Building", "Category", "Priority", "Days to close", "Contractor", "Notes"]
    rows = [
        ("MT-2026-0912", "2026-10-02", "North House", "Lighting", "Low", 1, "Brightline Electrical", "Corridor light, level 3"),
        ("MT-2026-0915", "2026-10-03", "River Court", "Lifts", "High", 12, "Vertex Lift Services", "Lift 2 door motor, part ordered from manufacturer"),
        ("MT-2026-0921", "2026-10-06", "Mill Yard", "Plumbing", "Medium", 3, "Aqua Facilities", "Leaking tap, kitchen level 1"),
        ("MT-2026-0930", "2026-10-08", "River Court", "Heating and cooling", "High", 5, "Hartwell Heating Services", "Boiler 2 pressure loss"),
        ("MT-2026-0934", "2026-10-09", "North House", "Doors and access control", "Medium", 2, "Keyline Security", "Card reader, east entrance"),
        ("MT-2026-0941", "2026-10-13", "Mill Yard", "Lighting", "Low", 1, "Brightline Electrical", "Emergency light test failure"),
        ("MT-2026-0948", "2026-10-15", "North House", "Heating and cooling", "Medium", 4, "Hartwell Heating Services", "Meeting room 4 too warm"),
        ("MT-2026-0953", "2026-10-17", "River Court", "Plumbing", "High", 2, "Aqua Facilities", "Blocked drain, ground floor"),
        ("MT-2026-0960", "2026-10-21", "Mill Yard", "Doors and access control", "Low", 3, "Keyline Security", "Door closer, stairwell B"),
        ("MT-2026-0966", "2026-10-23", "North House", "Lifts", "Medium", 6, "Vertex Lift Services", "Lift 1 levelling fault"),
    ]
    ws.append(head)
    for row in rows:
        ws.append(row)
    for cell in ws[1]:
        cell.font = Font(bold=True)
    for col, width in zip("ABCDEFGH", (15, 12, 13, 24, 9, 13, 26, 48)):
        ws.column_dimensions[col].width = width

    ws2 = wb.create_sheet("Contractors")
    ws2.append(["Contractor", "Trade", "Contract ends", "Emergency phone"])
    for row in [("Brightline Electrical", "Electrical and lighting", "2027-03-31", "0300 555 0141"),
                ("Vertex Lift Services", "Lifts", "2028-06-30", "0300 555 0177"),
                ("Aqua Facilities", "Plumbing", "2027-09-30", "0300 555 0123"),
                ("Hartwell Heating Services", "Heating and boilers", "2027-12-31", "0300 555 0190"),
                ("Keyline Security", "Doors and access control", "2027-01-31", "0300 555 0166")]:
        ws2.append(row)
    for cell in ws2[1]:
        cell.font = Font(bold=True)
    for col, width in zip("ABCD", (26, 26, 14, 17)):
        ws2.column_dimensions[col].width = width
    wb.properties.title = "Maintenance register"
    wb.properties.creator = COMPANY
    wb.save(path)


def main() -> None:
    OUT.mkdir(exist_ok=True)
    random.seed(7)
    annual_report(OUT / "facilities-annual-report-2026.pdf")
    scan(inspection_letter_clean(), OUT / "boiler-inspection-letter.pdf", seed=11)
    policy(OUT / "visitor-and-contractor-policy.docx")
    register(OUT / "maintenance-register.xlsx")
    for f in sorted(OUT.iterdir()):
        print(f"{f.relative_to(HERE)}  {f.stat().st_size:,} bytes")


if __name__ == "__main__":
    main()
