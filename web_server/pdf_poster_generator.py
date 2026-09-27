import os
import io
import qrcode
from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.lib.units import inch
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Image, Table, TableStyle, HRFlowable
)
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT

def draw_genz_tech_background(canvas, doc):
    """
    Draws a dark-mode, cyberpunk/tech-professional background on the A4 canvas.
    """
    canvas.saveState()
    width, height = doc.pagesize

    # 1. Fill obsidian dark background
    canvas.setFillColor(colors.HexColor("#090d16"))
    canvas.rect(0, 0, width, height, fill=True, stroke=False)

    # 2. Draw outer neon cyan glowing frame border
    canvas.setStrokeColor(colors.HexColor("#0ea5e9"))
    canvas.setLineWidth(2)
    canvas.roundRect(14, 14, width - 28, height - 28, radius=12, fill=True, stroke=True)

    # Re-fill main body background
    canvas.setFillColor(colors.HexColor("#090d16"))
    canvas.roundRect(16, 16, width - 32, height - 32, radius=10, fill=True, stroke=False)

    # Inner subtle indigo border
    canvas.setStrokeColor(colors.HexColor("#1e293b"))
    canvas.setLineWidth(1)
    canvas.roundRect(18, 18, width - 36, height - 36, radius=10, fill=False, stroke=True)

    # 3. Top Cyber Corner Accent lines
    canvas.setStrokeColor(colors.HexColor("#38bdf8"))
    canvas.setLineWidth(3)
    # Top Left Corner
    canvas.line(14, height - 30, 40, height - 30)
    canvas.line(30, height - 14, 30, height - 40)
    # Top Right Corner
    canvas.line(width - 40, height - 30, width - 14, height - 30)
    canvas.line(width - 30, height - 14, width - 30, height - 40)

    # Bottom Accent line
    canvas.setStrokeColor(colors.HexColor("#8b5cf6"))
    canvas.line(30, 30, width - 30, 30)

    canvas.restoreState()

def create_shop_poster_pdf(shop: dict, customer_url: str) -> bytes:
    """
    Generates a Gen-Z Tech Professional Dark-Mode A4 Printable QR Poster PDF.
    Accurately designed for Web Upload Portal access with UPI Payment integration options.
    """
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        leftMargin=32,
        rightMargin=32,
        topMargin=32,
        bottomMargin=32
    )

    story = []
    styles = getSampleStyleSheet()

    # Gen-Z Tech Color Palette
    NEON_CYAN = colors.HexColor("#38bdf8")       # Cyan 400
    ELECTRIC_BLUE = colors.HexColor("#0ea5e9")   # Sky 500
    NEON_PURPLE = colors.HexColor("#a855f7")     # Purple 500
    EMERALD_GREEN = colors.HexColor("#10b981")   # Emerald 500
    DARK_CARD_BG = colors.HexColor("#0f172a")    # Slate 900
    LIGHT_TEXT = colors.HexColor("#f8fafc")       # Slate 50
    MUTED_TEXT = colors.HexColor("#94a3b8")       # Slate 400

    # Custom Typography Styles
    top_badge_style = ParagraphStyle(
        'TopBadge',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=10,
        leading=13,
        alignment=TA_CENTER,
        textColor=colors.HexColor("#38bdf8")
    )

    shop_title_style = ParagraphStyle(
        'ShopTitleGenZ',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=30,
        leading=36,
        alignment=TA_CENTER,
        textColor=colors.white
    )

    shop_sub_style = ParagraphStyle(
        'ShopSubGenZ',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=12.5,
        leading=16,
        alignment=TA_CENTER,
        textColor=NEON_PURPLE
    )

    scan_btn_style = ParagraphStyle(
        'ScanBtn',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=11.5,
        leading=15,
        alignment=TA_CENTER,
        textColor=colors.white
    )

    step_desc_style = ParagraphStyle(
        'StepDescGenZ',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=10,
        leading=14,
        alignment=TA_LEFT,
        textColor=colors.HexColor("#cbd5e1")
    )

    footer_info_style = ParagraphStyle(
        'FooterInfoGenZ',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=9.5,
        leading=13,
        alignment=TA_CENTER,
        textColor=LIGHT_TEXT
    )

    footer_sub_style = ParagraphStyle(
        'FooterSubGenZ',
        parent=styles['Normal'],
        fontName='Helvetica-Oblique',
        fontSize=8.5,
        leading=11,
        alignment=TA_CENTER,
        textColor=MUTED_TEXT
    )

    # -------------------------------------------------------------
    # 1. TOP NEON TECH HEADER TAG
    # -------------------------------------------------------------
    top_badge_p = Paragraph(
        "⚡ <b>QWIKPRINT INSTANT PRINTING PORTAL</b> ⚡",
        top_badge_style
    )
    top_table = Table([[top_badge_p]], colWidths=[530], rowHeights=[28])
    top_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, -1), DARK_CARD_BG),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('BOX', (0, 0), (-1, -1), 1, NEON_CYAN),
        ('TOPPADDING', (0, 0), (-1, -1), 4),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
    ]))
    story.append(top_table)
    story.append(Spacer(1, 14))

    # -------------------------------------------------------------
    # 2. SHOP NAME & TECH TAGLINE
    # -------------------------------------------------------------
    shop_name = shop.get('name', 'SMART PRINT COUNTER').upper()
    story.append(Paragraph(f"<b>{shop_name}</b>", shop_title_style))
    story.append(Spacer(1, 4))

    sub_p = Paragraph(
        "🚀 <b>SKIP THE COUNTER LINE &bull; DIRECT MOBILE FILE UPLOAD &bull; SILENT PRINTING</b>",
        shop_sub_style
    )
    story.append(sub_p)
    story.append(Spacer(1, 14))

    # -------------------------------------------------------------
    # 3. GLOWING WEB UPLOAD QR CODE CONTAINER
    # -------------------------------------------------------------
    qr = qrcode.QRCode(
        version=1,
        error_correction=qrcode.constants.ERROR_CORRECT_H,
        box_size=10,
        border=2
    )
    qr.add_data(customer_url)
    qr.make(fit=True)
    img_qr = qr.make_image(fill_color="#090d16", back_color="#ffffff")

    qr_img_buffer = io.BytesIO()
    img_qr.save(qr_img_buffer, format="PNG")
    qr_img_buffer.seek(0)

    qr_image = Image(qr_img_buffer, width=2.45 * inch, height=2.45 * inch)

    # Neon Green Scan Pill (Clear & Accurate: Web Upload QR)
    scan_pill = Paragraph(
        "📱 <b>SCAN WITH CAMERA OR GOOGLE LENS TO UPLOAD FILES</b>",
        scan_btn_style
    )
    pill_table = Table([[scan_pill]], colWidths=[310], rowHeights=[26])
    pill_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, -1), ELECTRIC_BLUE),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('TOPPADDING', (0, 0), (-1, -1), 4),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
    ]))

    scanner_support_p = Paragraph(
        "<font color='#94a3b8'><b>How to scan:</b> Open Phone Camera &bull; Google Lens &bull; Chrome / Safari &bull; Any QR Scanner App</font>",
        ParagraphStyle('ScannerText', parent=styles['Normal'], fontName='Helvetica-Bold', fontSize=8.5, alignment=TA_CENTER)
    )

    qr_container = Table(
        [[qr_image], [Spacer(1, 6)], [pill_table], [Spacer(1, 6)], [scanner_support_p]],
        colWidths=[330]
    )
    qr_container.setStyle(TableStyle([
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('BACKGROUND', (0, 0), (-1, -1), DARK_CARD_BG),
        ('BOX', (0, 0), (-1, -1), 2, NEON_CYAN),
        ('TOPPADDING', (0, 0), (-1, -1), 12),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 10),
        ('LEFTPADDING', (0, 0), (-1, -1), 10),
        ('RIGHTPADDING', (0, 0), (-1, -1), 10),
    ]))
    story.append(qr_container)
    story.append(Spacer(1, 14))

    # -------------------------------------------------------------
    # 4. 3-STEP GEN-Z WORKFLOW (ACCURATE & SNAPPY)
    # -------------------------------------------------------------
    b1 = Paragraph("<font color='#ffffff'><b>01</b></font>", ParagraphStyle('B1', parent=styles['Normal'], fontName='Helvetica-Bold', fontSize=12, alignment=TA_CENTER))
    b2 = Paragraph("<font color='#ffffff'><b>02</b></font>", ParagraphStyle('B2', parent=styles['Normal'], fontName='Helvetica-Bold', fontSize=12, alignment=TA_CENTER))
    b3 = Paragraph("<font color='#ffffff'><b>03</b></font>", ParagraphStyle('B3', parent=styles['Normal'], fontName='Helvetica-Bold', fontSize=12, alignment=TA_CENTER))

    pill1 = Table([[b1]], colWidths=[28], rowHeights=[24])
    pill1.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, -1), ELECTRIC_BLUE),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE')
    ]))

    pill2 = Table([[b2]], colWidths=[28], rowHeights=[24])
    pill2.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, -1), NEON_PURPLE),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE')
    ]))

    pill3 = Table([[b3]], colWidths=[28], rowHeights=[24])
    pill3.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, -1), EMERALD_GREEN),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE')
    ]))

    step1_desc = Paragraph(
        "<b>SCAN QR WITH CAMERA / GOOGLE LENS</b><br/>Point your Mobile Camera or Lens at the QR code above to open the instant file upload portal.",
        step_desc_style
    )
    step2_desc = Paragraph(
        "<b>UPLOAD DOCUMENT & CHOOSE SETTINGS</b><br/>Select PDF/Photos, choose B&W or Color, number of copies, and double-sided printing.",
        step_desc_style
    )
    step3_desc = Paragraph(
        "<b>PAY VIA UPI & COLLECT INSTANT PRINTS</b><br/>Pay online via PhonePe/GPay/Paytm or Cash at counter. Your pages print out automatically!",
        step_desc_style
    )

    steps_table = Table([
        [pill1, step1_desc],
        [pill2, step2_desc],
        [pill3, step3_desc]
    ], colWidths=[40, 470])

    steps_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, -1), DARK_CARD_BG),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('BOX', (0, 0), (-1, -1), 1, colors.HexColor("#1e293b")),
        ('INNERGRID', (0, 0), (-1, -1), 0.5, colors.HexColor("#1e293b")),
        ('TOPPADDING', (0, 0), (-1, -1), 9),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 9),
        ('LEFTPADDING', (0, 0), (-1, -1), 10),
        ('RIGHTPADDING', (0, 0), (-1, -1), 10),
    ]))
    story.append(steps_table)
    story.append(Spacer(1, 14))

    # -------------------------------------------------------------
    # 5. ONLINE UPI PAYMENT SUPPORT BADGE & FEATURE PILLS
    # -------------------------------------------------------------
    upi_bar_p = Paragraph(
        "💳 <b>UPI PAYMENTS ACCEPTED:</b> GPay &bull; PhonePe &bull; Paytm &bull; BHIM &bull; Cards / Cash at Counter",
        ParagraphStyle('UPIBar', parent=styles['Normal'], fontName='Helvetica-Bold', fontSize=9.5, alignment=TA_CENTER, textColor=colors.HexColor("#38bdf8"))
    )
    upi_table = Table([[upi_bar_p]], colWidths=[510], rowHeights=[24])
    upi_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, -1), DARK_CARD_BG),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('BOX', (0, 0), (-1, -1), 1, colors.HexColor("#1e293b")),
        ('TOPPADDING', (0, 0), (-1, -1), 4),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
    ]))
    story.append(upi_table)
    story.append(Spacer(1, 12))

    f1 = Paragraph("⚡ <b>ZERO WAIT TIME</b>", ParagraphStyle('F1', parent=styles['Normal'], fontName='Helvetica-Bold', fontSize=9.5, alignment=TA_CENTER, textColor=NEON_CYAN))
    f2 = Paragraph("💬 <b>NO WHATSAPP / CABLE</b>", ParagraphStyle('F2', parent=styles['Normal'], fontName='Helvetica-Bold', fontSize=9.5, alignment=TA_CENTER, textColor=NEON_PURPLE))
    f3 = Paragraph("🔒 <b>100% PRIVATE & PURGED</b>", ParagraphStyle('F3', parent=styles['Normal'], fontName='Helvetica-Bold', fontSize=9.5, alignment=TA_CENTER, textColor=EMERALD_GREEN))

    feat_table = Table([[f1, f2, f3]], colWidths=[170, 170, 170])
    feat_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, -1), DARK_CARD_BG),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('BOX', (0, 0), (-1, -1), 1, colors.HexColor("#334155")),
        ('TOPPADDING', (0, 0), (-1, -1), 6),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
    ]))
    story.append(feat_table)
    story.append(Spacer(1, 12))

    # -------------------------------------------------------------
    # 6. FOOTER DETAILS & PRIVACY GUARANTEE
    # -------------------------------------------------------------
    owner_name = shop.get('owner_name', 'Shop Manager')
    phone = shop.get('phone', 'N/A')
    address = shop.get('address', 'Counter Location')

    footer_info_p = Paragraph(
        f"📍 <b>Location:</b> {address} &nbsp;&nbsp;|&nbsp;&nbsp; 📞 <b>Phone:</b> {phone} &nbsp;&nbsp;|&nbsp;&nbsp; 👤 <b>Owner:</b> {owner_name}",
        footer_info_style
    )
    footer_sub_p = Paragraph(
        "🛡️ <b>Zero Log Guarantee:</b> Documents are end-to-end encrypted and automatically destroyed after printing. Powered by QwikPrint SaaS System.",
        footer_sub_style
    )

    story.append(footer_info_p)
    story.append(Spacer(1, 4))
    story.append(footer_sub_p)

    doc.build(story, onFirstPage=draw_genz_tech_background)
    pdf_bytes = buffer.getvalue()
    buffer.close()
    return pdf_bytes
