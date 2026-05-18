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

from suppliers.models import Tier
from users.models import Account

from planningwithyou.file_storage import (
    booking_pdf_storage_key,
    read_account_logo_file,
)

from .models import BookingItem, BookingLine
from .pricing import (
    client_detail_lines,
    is_client_group_name,
    parse_supplier_field_value,
    resolve_booking_line_price,
)

GREEN = colors.HexColor('#6dad3a')
GREY = colors.HexColor('#666666')
LIGHT_GREY = colors.HexColor('#dddddd')
PAGE_SIZE = A4
PAGE_W, PAGE_H = PAGE_SIZE
MARGIN_L = 18 * mm
MARGIN_R = 18 * mm
MARGIN_T = 16 * mm
MARGIN_B = 18 * mm
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
        for row in Account.all_objects.filter(pk__in=supplier_ids).values('id', 'name'):
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


def _load_account_logo_bytes(account) -> bytes | None:
    """Load account logo bytes from storage (S3/local), not the proxy URL."""
    try:
        data, _, _ = read_account_logo_file(account.pk)
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

    def _draw_page_footer(self):
        assert self.c is not None
        self.c.setFont('Helvetica', 8)
        self.c.setFillColor(GREY)
        if self.total_pages:
            label = f'Page {self.page_num}/{self.total_pages}'
        else:
            label = f'Page {self.page_num}'
        self.c.drawString(MARGIN_L, 10 * mm, label)

    def _new_page(self):
        assert self.c is not None
        if self.total_pages is not None:
            self._draw_page_footer()
        self.c.showPage()
        self.page_num += 1
        self.y = PAGE_H - MARGIN_T

    def _ensure_space(self, needed: float):
        if self.y - needed < MARGIN_B + 8 * mm:
            self._new_page()

    def _count_pages(self) -> int:
        from io import BytesIO

        self.page_num = 1
        self.total_pages = None
        self.y = PAGE_H - MARGIN_T
        self.c = canvas.Canvas(BytesIO(), pagesize=PAGE_SIZE)
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
                parts = [
                    address.street,
                    address.city,
                    address.state,
                    address.zip_code,
                    address.country,
                ]
                line = ', '.join(p.strip() for p in parts if p and p.strip())
                if line:
                    texts.append(line)
            return texts or ['—']

        client_lines = client_detail_lines(self.lines)
        texts = []
        for line in client_lines:
            val = _format_line_value(line, self.supplier_names, self.tier_names)
            if val:
                texts.append(val)
        return texts or ['—']

    def _draw_header(self):
        assert self.c is not None
        col_w = CONTENT_W / 3
        top = PAGE_H - MARGIN_T
        left_x = MARGIN_L
        mid_x = MARGIN_L + col_w
        right_x = MARGIN_L + 2 * col_w

        # Account logo (right column top)
        logo_h = 14 * mm
        logo_w = 38 * mm
        logo_x = PAGE_W - MARGIN_R - logo_w
        logo_y = top - logo_h
        account = self.booking.account
        logo_bytes = _load_account_logo_bytes(account)
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
            self.c.setStrokeColor(LIGHT_GREY)
            self.c.setFillColor(colors.HexColor('#f5f5f5'))
            self.c.rect(logo_x, logo_y, logo_w, logo_h, stroke=1, fill=1)
            self.c.setFont('Helvetica-Oblique', 7)
            self.c.setFillColor(GREY)
            self.c.drawCentredString(
                logo_x + logo_w / 2,
                logo_y + logo_h / 2 - 2,
                'your logo here',
            )

        y_left = top
        y_mid = top
        y_right = logo_y - 4 * mm

        # Client details (left)
        self.c.setFont('Helvetica-Bold', 9)
        self.c.setFillColor(GREEN)
        self.c.drawString(left_x, y_left, 'Client Details')
        y_left -= 12
        client_texts = self._client_detail_texts()
        self.c.setFont('Helvetica', 8.5)
        self.c.setFillColor(colors.black)
        for text in client_texts:
            self.c.drawString(left_x, y_left, text[:55])
            y_left -= 11

        # Quote meta (center)
        quote_date = timezone.localtime(
            self.booking.updated_at or timezone.now(),
        ).strftime('%d/%m/%Y')
        meta_rows = [
            quote_date,
            f'#{self.booking.unique_id}',
        ]
        if self.metadata['po']:
            meta_rows.append(f'PO {self.metadata["po"]}')
        if self.metadata['sidemark']:
            meta_rows.append(f'Sidemark {self.metadata["sidemark"]}')
        self.c.setFont('Helvetica', 8.5)
        self.c.setFillColor(colors.black)
        for row in meta_rows:
            self.c.drawString(mid_x, y_mid, row)
            y_mid -= 11
        y_mid -= 2
        self.c.setFont('Helvetica-Bold', 9)
        self.c.setFillColor(GREEN)
        self.c.drawString(mid_x, y_mid, 'Sales Representative')
        y_mid -= 12
        rep_name, rep_email = _sales_rep_from_booking(self.booking, self.metadata)
        self.c.setFont('Helvetica', 8.5)
        self.c.setFillColor(colors.black)
        self.c.drawString(mid_x, y_mid, rep_name)
        y_mid -= 11
        if rep_email:
            self.c.drawString(mid_x, y_mid, rep_email)
            y_mid -= 11

        # Company details (right, below logo)
        self.c.setFont('Helvetica-Bold', 9)
        self.c.setFillColor(GREEN)
        self.c.drawString(right_x, y_right, 'Company Details')
        y_right -= 12
        company_lines = [account.name]
        country = getattr(account, 'country', None)
        if country is not None:
            company_lines.append(getattr(country, 'name', '') or '')
        company_lines.extend(['', '', ''])  # address / phone placeholders
        self.c.setFont('Helvetica', 8.5)
        self.c.setFillColor(colors.black)
        for text in company_lines:
            if text:
                self.c.drawString(right_x, y_right, text[:50])
            y_right -= 11

        header_bottom = min(y_left, y_mid, y_right) - 6 * mm
        self.y = header_bottom

    def _draw_group_rule(self, group_name: str, subtotal: Decimal):
        assert self.c is not None
        self._ensure_space(20)
        rule_y = self.y
        self.c.setStrokeColor(GREEN)
        self.c.setLineWidth(1.2)
        self.c.line(MARGIN_L, rule_y, PAGE_W - MARGIN_R, rule_y)
        self.y -= 10
        self.c.setFont('Helvetica-Bold', 9)
        self.c.setFillColor(GREEN)
        self.c.drawString(MARGIN_L, self.y, group_name)
        self.c.drawRightString(PAGE_W - MARGIN_R, self.y, 'Total Amount')
        self.y -= 14

    def _money_font(self, bold: bool = False) -> str:
        if _ensure_pdf_unicode_fonts():
            return PDF_FONT_BOLD if bold else PDF_FONT
        return 'Helvetica-Bold' if bold else 'Helvetica'

    def _format_amount(self, amount: Decimal | None) -> str:
        return _format_money(
            amount,
            self.currency_symbol,
            self.currency_code,
        )

    def _draw_product_block(self, block: ProductBlock):
        assert self.c is not None
        self._ensure_space(16 + 11 * max(len(block.specs), 1))
        self.c.setFont('Helvetica-Bold', 9.5)
        self.c.setFillColor(colors.black)
        self.c.drawString(MARGIN_L, self.y, block.title[:70])
        price_text = self._format_amount(block.price)
        self.c.setFont(self._money_font(bold=True), 9.5)
        self.c.drawRightString(PAGE_W - MARGIN_R, self.y, price_text)
        self.y -= 12
        self.c.setFont('Helvetica', 8.5)
        self.c.setFillColor(colors.black)
        for spec in block.specs:
            self._ensure_space(11)
            self.c.drawString(MARGIN_L + 4 * mm, self.y, f'• {spec[:95]}')
            self.y -= 11
        self.y -= 4

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
        rows.append(('Deposit Due', deposit, False))
        rows.append(('Balance Due', balance, False))

        table_h = 14 * len(rows) + 8
        self._ensure_space(table_h + 10)
        table_w = 72 * mm
        table_x = PAGE_W - MARGIN_R - table_w
        row_h = 14
        y_top = self.y

        self.c.setStrokeColor(LIGHT_GREY)
        self.c.setLineWidth(0.5)
        for i, (label, amount, bold) in enumerate(rows):
            y = y_top - i * row_h
            self.c.line(table_x, y, table_x + table_w, y)
            self.c.setFont(
                'Helvetica-Bold' if bold else 'Helvetica',
                9,
            )
            self.c.setFillColor(colors.black)
            self.c.drawString(table_x + 4, y - 10, label)
            self.c.setFont(self._money_font(bold=bold), 9)
            self.c.drawRightString(
                table_x + table_w - 4,
                y - 10,
                self._format_amount(amount),
            )

        self.c.line(table_x, y_top - len(rows) * row_h, table_x + table_w, y_top - len(rows) * row_h)
        self.c.line(table_x, y_top, table_x, y_top - len(rows) * row_h)
        self.c.line(table_x + table_w, y_top, table_x + table_w, y_top - len(rows) * row_h)
        self.y = y_top - len(rows) * row_h - 8

    def render(self) -> bytes:
        buffer = BytesIO()
        self.total_pages = self._count_pages()
        self.page_num = 1
        self.y = PAGE_H - MARGIN_T
        self.c = canvas.Canvas(buffer, pagesize=PAGE_SIZE)
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
