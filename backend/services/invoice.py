"""PDF invoice generation with reportlab."""
import os
from datetime import datetime, timedelta, timezone
from typing import Optional

from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.lib.colors import HexColor, black
from reportlab.platypus import SimpleDocTemplate, Paragraph, Table, TableStyle, Spacer
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle


def _storage_path() -> str:
    p = os.environ.get("INVOICE_STORAGE_PATH") or "/app/backend/storage/invoices"
    os.makedirs(p, exist_ok=True)
    return p


def _company() -> dict:
    return {
        "name": os.environ.get("COMPANY_NAME", "DeployHub"),
        "address": os.environ.get("COMPANY_ADDRESS", ""),
        "postcode": os.environ.get("COMPANY_POSTCODE", ""),
        "city": os.environ.get("COMPANY_CITY", ""),
        "country": os.environ.get("COMPANY_COUNTRY", ""),
        "vat_id": os.environ.get("COMPANY_VAT_ID", ""),
    }


async def effective_company() -> dict:
    """Company identity for invoices. Admin-edited platform_settings override
    the static env defaults so the agency can rebrand without redeploys."""
    fallback = _company()
    try:
        from db import get_db
        db = get_db()
        doc = await db.platform_settings.find_one(
            {"id": "platform-singleton"}, {"_id": 0}
        ) or {}
        mapping = {
            "name": "company_name",
            "address": "company_address",
            "postcode": "company_postcode",
            "city": "company_city",
            "country": "company_country",
            "vat_id": "company_vat_id",
        }
        for k, db_key in mapping.items():
            v = doc.get(db_key)
            if v:
                fallback[k] = v
    except Exception:
        pass
    return fallback


def file_path_for(invoice_number: str) -> str:
    return os.path.join(_storage_path(), f"{invoice_number.replace('/', '-')}.pdf")


def render_invoice_pdf(
    *,
    invoice_number: str,
    buyer: dict,
    items: list[dict],
    subtotal: float,
    vat_rate: float,
    vat_amount: float,
    vat_note: str,
    total: float,
    currency: str = "EUR",
    invoice_date: Optional[datetime] = None,
    due_date: Optional[datetime] = None,
    payment_method: Optional[str] = None,
    mollie_payment_id: Optional[str] = None,
    status: str = "paid",
    company: Optional[dict] = None,
) -> str:
    """Generate the invoice PDF and return its absolute file path. Accepts
    an optional `company` dict; falls back to env-based `_company()`."""
    invoice_date = invoice_date or datetime.now(timezone.utc)
    due_date = due_date or (invoice_date + timedelta(days=30))

    company = (company or _company())
    path = file_path_for(invoice_number)

    doc = SimpleDocTemplate(
        path, pagesize=A4,
        leftMargin=20 * mm, rightMargin=20 * mm,
        topMargin=20 * mm, bottomMargin=20 * mm,
    )
    styles = getSampleStyleSheet()
    small = ParagraphStyle("small", parent=styles["Normal"], fontSize=9, leading=12, textColor=HexColor("#333333"))
    body = ParagraphStyle("body", parent=styles["Normal"], fontSize=10, leading=14)
    heading = ParagraphStyle("h", parent=styles["Heading1"], fontSize=24, spaceAfter=6, textColor=HexColor("#0A0D14"))
    accent_small = ParagraphStyle("a", parent=styles["Normal"], fontSize=8, leading=11, textColor=HexColor("#00B3CC"))
    _ = (heading, accent_small, black)  # reserved for future template variants
    note_style = ParagraphStyle("note", parent=styles["Normal"], fontSize=9, leading=12, textColor=HexColor("#555555"), spaceBefore=12)

    elements: list = []

    # Header: company on left, invoice title on right
    seller_html = (
        f"<b>{company['name']}</b><br/>"
        f"{company['address']}<br/>"
        f"{company['postcode']} {company['city']}<br/>"
        f"{company['country']}<br/>"
        f"<font color='#888'>VAT ID: {company['vat_id']}</font>"
    )
    invoice_meta_html = (
        f"<font size='18' color='#0A0D14'><b>INVOICE</b></font><br/>"
        f"<font size='9'>Number: <b>{invoice_number}</b><br/>"
        f"Date: {invoice_date.strftime('%Y-%m-%d')}<br/>"
        f"Due: {due_date.strftime('%Y-%m-%d')}<br/>"
        f"Status: <b>{status.upper()}</b></font>"
    )
    header = Table(
        [[Paragraph(seller_html, small), Paragraph(invoice_meta_html, small)]],
        colWidths=[90 * mm, 80 * mm],
    )
    header.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
    ]))
    elements.append(header)
    elements.append(Spacer(1, 12))

    # Buyer
    buyer_html = (
        f"<b>Bill to:</b><br/>"
        f"{buyer.get('company_name') or buyer.get('name') or ''}<br/>"
        f"{buyer.get('address') or ''}<br/>"
        f"{buyer.get('postal_code') or ''} {buyer.get('city') or ''}<br/>"
        f"{buyer.get('country') or ''}<br/>"
    )
    if buyer.get("vat_id"):
        buyer_html += f"<font color='#888'>VAT ID: {buyer['vat_id']}</font><br/>"
    if buyer.get("email"):
        buyer_html += f"<font color='#888'>{buyer['email']}</font>"
    buyer_tbl = Table([[Paragraph(buyer_html, body)]], colWidths=[170 * mm])
    buyer_tbl.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), HexColor("#F5F7FA")),
        ("LEFTPADDING", (0, 0), (-1, -1), 10),
        ("TOPPADDING", (0, 0), (-1, -1), 10),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 10),
    ]))
    elements.append(buyer_tbl)
    elements.append(Spacer(1, 16))

    # Line items
    data = [["Description", "Qty", f"Unit ({currency})", f"Total ({currency})"]]
    for it in items:
        data.append([
            it.get("description", ""),
            str(it.get("quantity", 1)),
            f"{it.get('unit_price', 0):.2f}",
            f"{(it.get('unit_price', 0) * it.get('quantity', 1)):.2f}",
        ])
    items_tbl = Table(data, colWidths=[95 * mm, 15 * mm, 30 * mm, 30 * mm])
    items_tbl.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), HexColor("#0A0D14")),
        ("TEXTCOLOR", (0, 0), (-1, 0), HexColor("#FFFFFF")),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, -1), 9),
        ("ALIGN", (1, 0), (-1, -1), "RIGHT"),
        ("ALIGN", (0, 0), (0, -1), "LEFT"),
        ("GRID", (0, 0), (-1, -1), 0.25, HexColor("#E5E7EB")),
        ("TOPPADDING", (0, 0), (-1, -1), 7),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 7),
    ]))
    elements.append(items_tbl)
    elements.append(Spacer(1, 10))

    # Totals
    vat_label = f"VAT ({vat_rate:.1f}%)" if vat_rate > 0 else "VAT"
    totals_data = [
        ["Subtotal", f"{currency} {subtotal:.2f}"],
        [vat_label, f"{currency} {vat_amount:.2f}"],
        ["Total", f"{currency} {total:.2f}"],
    ]
    totals_tbl = Table(totals_data, colWidths=[140 * mm, 30 * mm])
    totals_tbl.setStyle(TableStyle([
        ("ALIGN", (0, 0), (-1, -1), "RIGHT"),
        ("FONTSIZE", (0, 0), (-1, -1), 9),
        ("FONTNAME", (0, -1), (-1, -1), "Helvetica-Bold"),
        ("BACKGROUND", (0, -1), (-1, -1), HexColor("#F5F7FA")),
        ("TOPPADDING", (0, 0), (-1, -1), 6),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
    ]))
    elements.append(totals_tbl)

    if vat_note:
        elements.append(Paragraph(f"<i>{vat_note}</i>", note_style))

    footer_bits = []
    if payment_method:
        footer_bits.append(f"Payment method: {payment_method}")
    if mollie_payment_id:
        footer_bits.append(f"Mollie payment ID: {mollie_payment_id}")
    footer_bits.append("Thank you for your business.")
    elements.append(Spacer(1, 20))
    elements.append(Paragraph("<br/>".join(footer_bits), small))

    doc.build(elements)
    return path
