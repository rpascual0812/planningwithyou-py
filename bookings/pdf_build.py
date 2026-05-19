import re
from dataclasses import dataclass, field
from decimal import Decimal
from functools import lru_cache
from io import BytesIO
from pathlib import Path

from django.core.files.base import ContentFile
from django.core.files.storage import default_storage
from django.utils import timezone
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.lib.utils import ImageReader
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfgen import canvas

from companies.models import Company
from suppliers.models import Tier

from planningwithyou.file_storage import (
    booking_pdf_storage_key,
    read_account_brand_logo_file,
)

from .models import BookingItem, BookingLine
from .pricing import (
    client_detail_lines,
    is_client_group_name,
    parse_supplier_field_value,
    resolve_booking_line_price,
)

# Premium palette — navy structure, muted sage accent, soft surfaces
NAVY = colors.HexColor('#1a2b3c')
NAVY_MID = colors.HexColor('#2c4154')
ACCENT = colors.HexColor('#4a7c59')
ACCENT_LIGHT = colors.HexColor('#e8f0eb')
SURFACE = colors.HexColor('#f8f9fb')
SURFACE_ALT = colors.HexColor('#f1f3f6')
BORDER = colors.HexColor('#dde2e8')
TEXT = colors.HexColor('#1f2937')
TEXT_MUTED = colors.HexColor('#6b7280')
WHITE = colors.white

PAGE_SIZE = A4
PAGE_W, PAGE_H = PAGE_SIZE
MARGIN_L = 20 * mm
MARGIN_R = 20 * mm
MARGIN_T = 14 * mm
MARGIN_B = 16 * mm
CONTENT_W = PAGE_W - MARGIN_L - MARGIN_R

PDF_FONT_DIR = Path(__file__).resolve().parent / 'fonts'
PDF_FONT = 'PdfDejaVu'
PDF_FONT_BOLD = 'PdfDejaVu-Bold'

@dataclass
class ProductBlock:
    title: str
    price: Decimal
    specs: list[str] = field(default_factory=list)


@dataclass
class GroupSection:
    name: str
    blocks: list[ProductBlock] = field(default_factory=list)
    subtotal: Decimal = Decimal('0')


@dataclass
class SummaryRow:
    label: str
    amount: Decimal


def delete_booking_pdf_file(stored: str) -> None:
    """Remove a booking PDF from storage (or legacy absolute path on disk)."""
    if not stored:
        return
    try:
        legacy = Path(stored)
        if legacy.is_absolute() and legacy.is_file():
            legacy.unlink(missing_ok=True)
            return
    except OSError:
        pass
    try:
        if default_storage.exists(stored):
            default_storage.delete(stored)
    except OSError:
        pass


@lru_cache(maxsize=1)
def _ensure_pdf_unicode_fonts() -> bool:
    """Register bundled DejaVu fonts so currency symbols like ₱ render in PDFs."""
    if PDF_FONT in pdfmetrics.getRegisteredFontNames():
        return True
    regular = PDF_FONT_DIR / 'DejaVuSans.ttf'
    bold = PDF_FONT_DIR / 'DejaVuSans-Bold.ttf'
    if not regular.is_file() or not bold.is_file():
        return False
    pdfmetrics.registerFont(TTFont(PDF_FONT, str(regular)))
    pdfmetrics.registerFont(TTFont(PDF_FONT_BOLD, str(bold)))
    return True


def _currency_for_account(account) -> tuple[str, str]:
    """Return ``(currency_symbol, currency_code)`` from ``account.country``."""
    country = getattr(account, 'country', None)
    if country is None:
        return '$', 'USD'
    symbol = (getattr(country, 'currency_symbol', None) or '').strip() or '$'
    code = (getattr(country, 'currency_code', None) or '').strip() or 'USD'
    return symbol, code


def _currency_symbol_for_account(account) -> str:
    return _currency_for_account(account)[0]


def _format_money(
    amount: Decimal | None,
    currency_symbol: str = '$',
    currency_code: str = 'USD',
) -> str:
    if amount is None:
        return ''
    sym = (currency_symbol or '$').strip() or '$'
    if sym.isascii() or _ensure_pdf_unicode_fonts():
        return f'{sym} {amount:,.2f}'
    code = (currency_code or '').strip() or 'USD'
    return f'{code} {amount:,.2f}'


def _format_line_value(
    line: BookingLine,
    supplier_names: dict[int, str],
    tier_names: dict[int, str],
) -> str:
    if line.field_type == 'supplier':
        parsed = parse_supplier_field_value(line.value)
        parts = []
        sid = parsed.get('supplier_id')
        tid = parsed.get('tier_id')
        if sid is not None:
            parts.append(supplier_names.get(sid, f'Supplier #{sid}'))
        if tid is not None:
            parts.append(tier_names.get(tid, f'Tier #{tid}'))
        return ' — '.join(parts) if parts else ''
    if line.field_type == 'checkbox':
        return 'Yes' if line.value == 'true' else 'No'
    return (line.value or '').strip()


def _load_supplier_and_tier_names(lines) -> tuple[dict[int, str], dict[int, str]]:
    supplier_ids: set[int] = set()
    tier_ids: set[int] = set()
    for line in lines:
        if line.field_type != 'supplier':
            continue
        parsed = parse_supplier_field_value(line.value)
        if parsed.get('supplier_id') is not None:
            supplier_ids.add(parsed['supplier_id'])
        if parsed.get('tier_id') is not None:
            tier_ids.add(parsed['tier_id'])

    supplier_names = {}
    if supplier_ids:
        for row in Company.all_objects.filter(pk__in=supplier_ids).values('id', 'name'):
            supplier_names[row['id']] = row['name']

    tier_names = {}
    if tier_ids:
        for row in Tier.all_objects.filter(pk__in=tier_ids).values('id', 'name'):
            tier_names[row['id']] = row['name']

    return supplier_names, tier_names


def _line_spec_text(
    line: BookingLine,
    supplier_names: dict[int, str],
    tier_names: dict[int, str],
) -> str | None:
    value = _format_line_value(line, supplier_names, tier_names)
    if not value or value == '—':
        return None
    return f'{line.label} - {value}'


def _group_into_blocks(
    group_lines: list[BookingLine],
    supplier_names: dict[int, str],
    tier_names: dict[int, str],
) -> list[ProductBlock]:
    blocks: list[ProductBlock] = []
    pending_specs: list[str] = []
    for line in group_lines:
        price = resolve_booking_line_price(line)
        if price is not None:
            title = line.label.strip()
            if line.field_type == 'supplier':
                display = _format_line_value(line, supplier_names, tier_names)
                if display:
                    title = display
            blocks.append(ProductBlock(
                title=title,
                price=price,
                specs=pending_specs.copy(),
            ))
            pending_specs = []
            continue
        spec = _line_spec_text(line, supplier_names, tier_names)
        if spec:
            if blocks:
                blocks[-1].specs.append(spec)
            else:
                pending_specs.append(spec)
    return blocks


def _organize_sections(
    lines: list[BookingLine],
    supplier_names: dict[int, str],
    tier_names: dict[int, str],
) -> tuple[list[GroupSection], list[SummaryRow]]:
    groups: dict[int, list[BookingLine]] = {}
    group_names: dict[int, str] = {}
    group_order: list[int] = []

    for line in lines:
        gid = line.booking_group_id or 0
        if gid not in groups:
            groups[gid] = []
            group_order.append(gid)
            group_names[gid] = (
                line.booking_group.name if line.booking_group_id else 'Items'
            )
        groups[gid].append(line)

    sections: list[GroupSection] = []
    summary_rows: list[SummaryRow] = []

    for gid in group_order:
        name = group_names[gid]
        if is_client_group_name(name):
            continue
        group_lines = groups[gid]
        blocks = _group_into_blocks(group_lines, supplier_names, tier_names)
        if not blocks:
            continue
        subtotal = sum(b.price for b in blocks)
        sections.append(GroupSection(name=name, blocks=blocks, subtotal=subtotal))
        lower = name.lower()
        if 'install' in lower:
            summary_rows.append(SummaryRow('Installation', subtotal))
        elif 'fee' in lower or 'additional' in lower:
            for block in blocks:
                summary_rows.append(SummaryRow(block.title, block.price))

    return sections, summary_rows


def _load_brand_logo_bytes(account) -> bytes | None:
    """Load main company logo bytes for this account (S3/local)."""
    try:
        data, _, _ = read_account_brand_logo_file(account.pk)
        return data
    except (FileNotFoundError, ValueError, OSError):
        return None


def _format_user_display_name(user) -> str:
    name = f'{user.first_name} {user.last_name}'.strip()
    return name or user.username or user.email or '—'


def _sales_rep_from_booking(booking, metadata: dict[str, str]) -> tuple[str, str]:
    user = getattr(booking, 'created_by', None)
    if user is not None:
        return _format_user_display_name(user), (user.email or '').strip()
    return metadata.get('sales_rep') or '—', metadata.get('sales_rep_email') or ''


def _format_contact_address_lines(address) -> list[str]:
    """Split address into stacked lines so it stays within the client column."""
    lines: list[str] = []
    street = (address.street or '').strip()
    if street:
        lines.append(street)
    locality = ', '.join(
        p.strip()
        for p in (address.city, address.state, address.zip_code)
        if p and str(p).strip()
    )
    if locality:
        lines.append(locality)
    country = (address.country or '').strip()
    if country:
        lines.append(country)
    return lines


def _wrap_text_lines(
    text: str,
    font_name: str,
    font_size: float,
    max_width: float,
) -> list[str]:
    words = text.split()
    if not words:
        return []
    wrapped: list[str] = []
    current: list[str] = []
    for word in words:
        trial = ' '.join(current + [word])
        if pdfmetrics.stringWidth(trial, font_name, font_size) <= max_width:
            current.append(word)
        else:
            if current:
                wrapped.append(' '.join(current))
            current = [word]
    if current:
        wrapped.append(' '.join(current))
    return wrapped


def _metadata_from_lines(
    lines: list[BookingLine],
    supplier_names: dict[int, str],
    tier_names: dict[int, str],
) -> dict[str, str]:
    def pick(pattern: str) -> str:
        for line in lines:
            if re.search(pattern, line.label, re.IGNORECASE):
                val = _format_line_value(line, supplier_names, tier_names)
                if val:
                    return val
        return ''

    return {
        'po': pick(r'\bpo\b|purchase\s*order'),
        'sidemark': pick(r'sidemark|side\s*mark'),
        'sales_rep': pick(r'sales\s*rep|representative'),
        'sales_rep_email': pick(r'sales.*email|rep.*email'),
    }


class BookingQuotePDF:
    def __init__(self, booking: BookingItem, lines: list[BookingLine]):
        self.booking = booking
        self.lines = lines
        self.supplier_names, self.tier_names = _load_supplier_and_tier_names(lines)
        self.sections, self.extra_summary_rows = _organize_sections(
            lines, self.supplier_names, self.tier_names,
        )
        self.metadata = _metadata_from_lines(
            lines, self.supplier_names, self.tier_names,
        )
        self.currency_symbol, self.currency_code = _currency_for_account(
            booking.account,
        )
        _ensure_pdf_unicode_fonts()
        self.y = PAGE_H - MARGIN_T
        self.c: canvas.Canvas | None = None
        self.page_num = 1
        self.total_pages: int | None = None

    def _body_font(self, bold: bool = False) -> str:
        if _ensure_pdf_unicode_fonts():
            return PDF_FONT_BOLD if bold else PDF_FONT
        return 'Helvetica-Bold' if bold else 'Helvetica'

    def _label_font(self) -> str:
        return 'Helvetica-Bold'

    def _draw_hrule(self, y: float, color=BORDER, width: float = 0.5):
        assert self.c is not None
        self.c.setStrokeColor(color)
        self.c.setLineWidth(width)
        self.c.line(MARGIN_L, y, PAGE_W - MARGIN_R, y)

    def _draw_page_chrome(self):
        """Top accent bar and footer on every page."""
        assert self.c is not None
        self.c.setFillColor(NAVY)
        self.c.rect(0, PAGE_H - 4 * mm, PAGE_W, 4 * mm, stroke=0, fill=1)

        footer_y = 11 * mm
        self._draw_hrule(footer_y + 5 * mm, BORDER, 0.35)
        self.c.setFont(self._body_font(), 7.5)
        self.c.setFillColor(TEXT_MUTED)
        ref = f'Quote #{self.booking.unique_id}'
        if self.total_pages:
            page_label = f'Page {self.page_num} of {self.total_pages}'
        else:
            page_label = f'Page {self.page_num}'
        self.c.drawString(MARGIN_L, footer_y, ref)
        self.c.drawRightString(PAGE_W - MARGIN_R, footer_y, page_label)

    def _draw_page_footer(self):
        self._draw_page_chrome()

    def _new_page(self):
        assert self.c is not None
        if self.total_pages is not None:
            self._draw_page_footer()
        self.c.showPage()
        self.page_num += 1
        self.y = PAGE_H - MARGIN_T - 4 * mm

    def _ensure_space(self, needed: float):
        if self.y - needed < MARGIN_B + 12 * mm:
            self._new_page()
            self._draw_page_chrome()

    def _count_pages(self) -> int:
        from io import BytesIO

        self.page_num = 1
        self.total_pages = None
        self.y = PAGE_H - MARGIN_T
        self.c = canvas.Canvas(BytesIO(), pagesize=PAGE_SIZE)
        self._draw_page_chrome()
        self._draw_header()
        self._draw_sections()
        self._draw_summary()
        return self.page_num

    def _client_detail_texts(self) -> list[str]:
        contact = getattr(self.booking, 'contact', None)
        if contact is not None:
            texts: list[str] = []
            name = f'{contact.first_name} {contact.last_name}'.strip()
            if name:
                texts.append(name)
            mobile = ''
            default_phone = contact.phone_numbers.filter(is_default=True).first()
            if default_phone and default_phone.number.strip():
                mobile = default_phone.number.strip()
            if not mobile:
                for phone in contact.phone_numbers.all():
                    if phone.label == 'mobile' and phone.number.strip():
                        mobile = phone.number.strip()
                        break
            if not mobile:
                first = contact.phone_numbers.first()
                if first and first.number.strip():
                    mobile = first.number.strip()
            if mobile:
                texts.append(mobile)
            if contact.email:
                texts.append(contact.email)
            address = contact.addresses.filter(is_default=True).first()
            if address is None:
                address = contact.addresses.first()
            if address:
                texts.extend(_format_contact_address_lines(address))
            return texts or ['—']

        client_lines = client_detail_lines(self.lines)
        texts = []
        for line in client_lines:
            val = _format_line_value(line, self.supplier_names, self.tier_names)
            if val:
                texts.append(val)
        return texts or ['—']

    def _draw_column_label(
        self,
        x: float,
        y: float,
        label: str,
        *,
        spacing_after: float = 0,
    ) -> float:
        assert self.c is not None
        self.c.setFont(self._label_font(), 7)
        self.c.setFillColor(ACCENT)
        self.c.drawString(x, y, label.upper())
        return y - spacing_after

    def _draw_column_lines(
        self,
        x: float,
        y: float,
        lines: list[str],
        width: int = 52,
        *,
        max_width_pt: float | None = None,
    ) -> float:
        assert self.c is not None
        for i, text in enumerate(lines):
            if not text:
                y -= 4
                continue
            font = self._body_font(bold=(i == 0))
            size = 9 if i == 0 else 8
            self.c.setFont(font, size)
            self.c.setFillColor(TEXT if i == 0 else TEXT_MUTED)
            if max_width_pt is not None:
                display_lines = _wrap_text_lines(text, font, size, max_width_pt)
            else:
                display_lines = [text[:width]]
            line_step = 10.5 if i == 0 else 10
            for j, display in enumerate(display_lines):
                self.c.drawString(x, y, display)
                if j < len(display_lines) - 1:
                    y -= line_step
            y -= line_step
        return y

    def _company_detail_lines(self, account) -> list[str]:
        lines = [account.name]
        country = getattr(account, 'country', None)
        if country is not None and getattr(country, 'name', ''):
            lines.append(country.name)
        if account.contact_person.strip():
            lines.append(account.contact_person.strip())
        if account.contact_email.strip():
            lines.append(account.contact_email.strip())
        if account.contact_mobile_number.strip():
            lines.append(account.contact_mobile_number.strip())
        return lines

    def _draw_header(self):
        assert self.c is not None
        account = self.booking.account
        top = PAGE_H - MARGIN_T - 4 * mm

        # Title row
        self.c.setFont(self._label_font(), 18)
        self.c.setFillColor(NAVY)
        title = (self.booking.title or 'Booking Quote').strip()[:60]
        self.c.drawString(MARGIN_L, top - 6 * mm, title)

        quote_date = timezone.localtime(
            self.booking.updated_at or timezone.now(),
        ).strftime('%d %b %Y')
        self.c.setFont(self._body_font(), 8)
        self.c.setFillColor(TEXT_MUTED)
        self.c.drawRightString(PAGE_W - MARGIN_R, top - 4 * mm, quote_date)
        self.c.setFont(self._label_font(), 8)
        self.c.setFillColor(NAVY_MID)
        self.c.drawRightString(
            PAGE_W - MARGIN_R,
            top - 12 * mm,
            f'#{self.booking.unique_id}',
        )

        band_top = top - 20 * mm
        band_h = 58 * mm
        self.c.setFillColor(SURFACE)
        self.c.setStrokeColor(BORDER)
        self.c.setLineWidth(0.5)
        self.c.roundRect(
            MARGIN_L,
            band_top - band_h,
            CONTENT_W,
            band_h,
            3 * mm,
            stroke=1,
            fill=1,
        )

        col_w = CONTENT_W / 3
        pad = 5 * mm
        left_x = MARGIN_L + pad
        mid_x = MARGIN_L + col_w + pad
        right_x = MARGIN_L + 2 * col_w + pad
        col_inner_w = 48
        col_text_w = col_w - 2 * pad

        # Logo (top-right inside band)
        logo_h = 16 * mm
        logo_w = 42 * mm
        logo_x = PAGE_W - MARGIN_R - pad - logo_w
        logo_y = band_top - pad - logo_h
        logo_bytes = _load_brand_logo_bytes(account)
        if logo_bytes:
            try:
                self.c.drawImage(
                    ImageReader(BytesIO(logo_bytes)),
                    logo_x,
                    logo_y,
                    width=logo_w,
                    height=logo_h,
                    preserveAspectRatio=True,
                    mask='auto',
                )
            except Exception:
                logo_bytes = None
        if not logo_bytes:
            self.c.setFillColor(SURFACE_ALT)
            self.c.setStrokeColor(BORDER)
            self.c.roundRect(
                logo_x, logo_y, logo_w, logo_h, 2 * mm, stroke=1, fill=1,
            )
            self.c.setFont('Helvetica-Oblique', 6.5)
            self.c.setFillColor(TEXT_MUTED)
            self.c.drawCentredString(
                logo_x + logo_w / 2,
                logo_y + logo_h / 2 - 2,
                'Logo',
            )

        content_top = band_top - pad
        y_left = content_top
        y_mid = content_top
        y_right = logo_y - 3 * mm

        y_left = self._draw_column_label(left_x, y_left, 'Client', spacing_after=9)
        y_left = self._draw_column_lines(
            left_x,
            y_left,
            self._client_detail_texts(),
            width=col_inner_w,
            max_width_pt=col_text_w,
        )

        meta_lines = []
        if self.metadata['po']:
            meta_lines.append(f'PO {self.metadata["po"]}')
        if self.metadata['sidemark']:
            meta_lines.append(f'Sidemark {self.metadata["sidemark"]}')
        rep_name, rep_email = _sales_rep_from_booking(self.booking, self.metadata)
        y_mid = self._draw_column_label(
            mid_x, y_mid, 'Quote details', spacing_after=9,
        )
        y_mid = self._draw_column_lines(
            mid_x, y_mid, meta_lines, width=col_inner_w, max_width_pt=col_text_w,
        )
        if meta_lines:
            y_mid -= 3 * mm
        y_mid = self._draw_column_label(
            mid_x,
            y_mid,
            'Sales representative',
            spacing_after=4 * mm,
        )
        rep_lines = [rep_name]
        if rep_email:
            rep_lines.append(rep_email)
        y_mid = self._draw_column_lines(
            mid_x, y_mid, rep_lines, width=col_inner_w, max_width_pt=col_text_w,
        )

        y_right = self._draw_column_label(right_x, y_right, 'From', spacing_after=9)
        y_right = self._draw_column_lines(
            right_x,
            y_right,
            self._company_detail_lines(account),
            width=col_inner_w,
            max_width_pt=col_text_w,
        )

        # Column dividers
        div_x1 = MARGIN_L + col_w
        div_x2 = MARGIN_L + 2 * col_w
        div_y0 = band_top - band_h + 4 * mm
        div_y1 = band_top - 4 * mm
        self.c.setStrokeColor(BORDER)
        self.c.setLineWidth(0.35)
        self.c.line(div_x1, div_y0, div_x1, div_y1)
        self.c.line(div_x2, div_y0, div_x2, div_y1)

        self.y = band_top - band_h - 8 * mm
        self._draw_hrule(self.y)
        self.y -= 10 * mm

    def _draw_group_rule(self, group_name: str, subtotal: Decimal):
        assert self.c is not None
        self._ensure_space(22)
        bar_h = 9 * mm
        bar_y = self.y - bar_h
        self.c.setFillColor(NAVY)
        self.c.roundRect(
            MARGIN_L, bar_y, CONTENT_W, bar_h, 2 * mm, stroke=0, fill=1,
        )
        self.c.setFont(self._label_font(), 9)
        self.c.setFillColor(WHITE)
        self.c.drawString(MARGIN_L + 4 * mm, bar_y + 2.8 * mm, group_name[:55])
        self.c.setFont(self._body_font(), 7.5)
        self.c.setFillColor(colors.HexColor('#b8c5d0'))
        self.c.drawRightString(
            PAGE_W - MARGIN_R - 4 * mm,
            bar_y + 3.2 * mm,
            'SECTION TOTAL',
        )
        self.y = bar_y - 6 * mm

    def _format_amount(self, amount: Decimal | None) -> str:
        return _format_money(
            amount,
            self.currency_symbol,
            self.currency_code,
        )

    def _draw_product_block(self, block: ProductBlock):
        assert self.c is not None
        spec_count = max(len(block.specs), 0)
        card_h = 11 * mm + spec_count * 10 + (4 * mm if spec_count else 0)
        self._ensure_space(card_h + 4 * mm)

        card_y = self.y - card_h
        self.c.setFillColor(WHITE)
        self.c.setStrokeColor(BORDER)
        self.c.setLineWidth(0.5)
        self.c.roundRect(
            MARGIN_L, card_y, CONTENT_W, card_h, 2.5 * mm, stroke=1, fill=1,
        )

        text_y = self.y - 8 * mm
        self.c.setFont(self._body_font(bold=True), 9.5)
        self.c.setFillColor(TEXT)
        self.c.drawString(MARGIN_L + 4 * mm, text_y, block.title[:68])

        price_text = self._format_amount(block.price)
        self.c.setFont(self._body_font(bold=True), 9.5)
        self.c.setFillColor(NAVY)
        self.c.drawRightString(PAGE_W - MARGIN_R - 4 * mm, text_y, price_text)

        spec_y = text_y - 11
        self.c.setFont(self._body_font(), 8)
        self.c.setFillColor(TEXT_MUTED)
        for spec in block.specs:
            self.c.drawString(MARGIN_L + 6 * mm, spec_y, f'—  {spec[:92]}')
            spec_y -= 10

        self.y = card_y - 5 * mm

    def _draw_sections(self):
        for section in self.sections:
            self._draw_group_rule(section.name, section.subtotal)
            for block in section.blocks:
                self._draw_product_block(block)

    def _grand_total(self) -> Decimal:
        return sum(section.subtotal for section in self.sections)

    def _draw_summary(self):
        assert self.c is not None
        total = self._grand_total()
        deposit = (total / 2).quantize(Decimal('0.01'))
        balance = total - deposit

        rows: list[tuple[str, Decimal, bool]] = []
        for row in self.extra_summary_rows:
            rows.append((row.label, row.amount, False))
        rows.append(('Total', total, True))
        rows.append(('Deposit due', deposit, False))
        rows.append(('Balance due', balance, False))

        row_h = 13 * mm
        header_h = 8 * mm
        table_w = 78 * mm
        table_h = header_h + row_h * len(rows)
        self._ensure_space(table_h + 14 * mm)

        table_x = PAGE_W - MARGIN_R - table_w
        y_top = self.y

        # Summary card shadow band
        self.c.setFillColor(SURFACE_ALT)
        self.c.roundRect(
            table_x - 2 * mm,
            y_top - table_h - 2 * mm,
            table_w + 4 * mm,
            table_h + 4 * mm,
            3 * mm,
            stroke=0,
            fill=1,
        )
        self.c.setFillColor(WHITE)
        self.c.setStrokeColor(BORDER)
        self.c.setLineWidth(0.5)
        self.c.roundRect(
            table_x, y_top - table_h, table_w, table_h, 3 * mm, stroke=1, fill=1,
        )

        self.c.setFillColor(NAVY_MID)
        self.c.roundRect(
            table_x,
            y_top - header_h,
            table_w,
            header_h,
            3 * mm,
            stroke=0,
            fill=1,
        )
        self.c.setFont(self._label_font(), 8)
        self.c.setFillColor(WHITE)
        self.c.drawString(table_x + 5 * mm, y_top - header_h + 2.5 * mm, 'SUMMARY')

        for i, (label, amount, is_total) in enumerate(rows):
            row_top = y_top - header_h - i * row_h
            row_bottom = row_top - row_h
            if is_total:
                self.c.setFillColor(NAVY)
                self.c.rect(
                    table_x + 0.5,
                    row_bottom + 0.5,
                    table_w - 1,
                    row_h - 1,
                    stroke=0,
                    fill=1,
                )
                label_color = WHITE
                amount_color = WHITE
                label_font = self._label_font()
                amount_font = self._body_font(bold=True)
            else:
                if i % 2 == 0:
                    self.c.setFillColor(SURFACE)
                    self.c.rect(
                        table_x + 0.5,
                        row_bottom + 0.5,
                        table_w - 1,
                        row_h - 1,
                        stroke=0,
                        fill=1,
                    )
                label_color = TEXT
                amount_color = NAVY if i == len(rows) - 1 else TEXT
                label_font = self._body_font()
                amount_font = self._body_font(bold=(i >= len(rows) - 2))

            self.c.setFont(label_font, 9 if is_total else 8.5)
            self.c.setFillColor(label_color)
            self.c.drawString(table_x + 5 * mm, row_bottom + 4 * mm, label)

            self.c.setFont(amount_font, 9.5 if is_total else 9)
            self.c.setFillColor(amount_color)
            self.c.drawRightString(
                table_x + table_w - 5 * mm,
                row_bottom + 4 * mm,
                self._format_amount(amount),
            )

        self.y = y_top - table_h - 10 * mm

    def render(self) -> bytes:
        buffer = BytesIO()
        self.total_pages = self._count_pages()
        self.page_num = 1
        self.y = PAGE_H - MARGIN_T - 4 * mm
        self.c = canvas.Canvas(buffer, pagesize=PAGE_SIZE)
        self._draw_page_chrome()
        self._draw_header()
        self._draw_sections()
        self._draw_summary()
        self._draw_page_footer()
        self.c.save()
        return buffer.getvalue()


def build_booking_pdf(booking: BookingItem) -> None:
    """Build the quote PDF and store it on default storage (S3/local)."""
    lines = list(
        booking.lines.select_related('booking_group').order_by(
            'booking_group__id', 'sort_order', 'id',
        ),
    )
    storage_key = booking_pdf_storage_key(booking)
    if default_storage.exists(storage_key):
        default_storage.delete(storage_key)
    legacy = (booking.pdf or '').strip()
    if legacy and not legacy.startswith(('http://', 'https://', '/')):
        delete_booking_pdf_file(legacy)
    pdf_bytes = BookingQuotePDF(booking, lines).render()
    default_storage.save(storage_key, ContentFile(pdf_bytes))
