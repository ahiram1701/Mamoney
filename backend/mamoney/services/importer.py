"""Importación de estados de cuenta (OFX y CSV de cualquier banco).

El archivo se convierte en movimientos con signo: negativo = cargo (gasto), positivo = abono
(ingreso). Para CSV se detectan solas las columnas de fecha, descripción e importe, incluidos
los estados que separan "cargo" y "abono". Cada movimiento lleva una huella (`key`) para no
importarlo dos veces y una categoría sugerida.
"""

import csv
import datetime as dt
import hashlib
import io
import re
import unicodedata
from dataclasses import asdict, dataclass
from typing import Any

from mamoney.models import SpendingCategory


class ImportError_(ValueError):
    pass


@dataclass
class ImportedRow:
    date: dt.date
    description: str
    amount: float  # negativo = cargo
    key: str = ""

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["date"] = self.date.isoformat()
        return data


def _normalize(text: str) -> str:
    text = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode()
    return re.sub(r"\s+", " ", text).strip().lower()


def row_key(row: ImportedRow, account: int | None) -> str:
    raw = f"{account or 0}|{row.date.isoformat()}|{row.amount:.2f}|{_normalize(row.description)}"
    return hashlib.sha1(raw.encode()).hexdigest()


# --- Fechas e importes ------------------------------------------------------------------

MONTHS = {
    "ene": 1, "jan": 1, "feb": 2, "mar": 3, "abr": 4, "apr": 4, "may": 5, "jun": 6, "jul": 7,
    "ago": 8, "aug": 8, "sep": 9, "set": 9, "oct": 10, "nov": 11, "dic": 12, "dec": 12,
}  # fmt: skip


def parse_date(value: str) -> dt.date:
    text = value.strip()
    for fmt in ("%Y-%m-%d", "%d/%m/%Y", "%d-%m-%Y", "%d/%m/%y", "%d-%m-%y", "%Y/%m/%d", "%d.%m.%Y"):
        try:
            return dt.datetime.strptime(text[:10] if fmt.startswith("%Y") else text, fmt).date()
        except ValueError:
            continue
    # "12 ene 2026", "12-ENE-26"
    match = re.match(r"^(\d{1,2})[\s\-/.]+([a-zA-Z]{3})[a-zA-Z]*[\s\-/.]+(\d{2,4})$", text)
    if match and match.group(2).lower() in MONTHS:
        year = int(match.group(3))
        year += 2000 if year < 100 else 0
        return dt.date(year, MONTHS[match.group(2).lower()], int(match.group(1)))
    raise ImportError_(f"Fecha no reconocida: {value!r}")


def parse_amount(value: str) -> float | None:
    text = value.strip().replace("$", "").replace("MXN", "").replace(" ", "")
    if not text or text in {"-", "--"}:
        return None
    negative = (text.startswith("(") and text.endswith(")")) or text.endswith("-")
    text = text.strip("()").rstrip("-")
    # 1.234,56 (coma decimal) vs 1,234.56
    if re.search(r",\d{1,2}$", text) and "." in text:
        text = text.replace(".", "").replace(",", ".")
    elif re.search(r",\d{1,2}$", text) and text.count(",") == 1:
        text = text.replace(",", ".")
    else:
        text = text.replace(",", "")
    try:
        number = float(text)
    except ValueError:
        return None
    return -abs(number) if negative else number


# --- OFX --------------------------------------------------------------------------------


def parse_ofx(text: str) -> list[ImportedRow]:
    rows = []
    for block in re.findall(
        r"<STMTTRN>(.*?)(?:</STMTTRN>|(?=<STMTTRN>)|</BANKTRANLIST>)", text, re.S | re.I
    ):

        def tag(name: str, block: str = block) -> str | None:
            match = re.search(rf"<{name}>([^<\r\n]+)", block, re.I)
            return match.group(1).strip() if match else None

        posted, amount = tag("DTPOSTED"), tag("TRNAMT")
        if not posted or amount is None:
            continue
        description = " ".join(filter(None, [tag("NAME"), tag("MEMO")])) or "Movimiento"
        rows.append(
            ImportedRow(
                date=dt.datetime.strptime(posted[:8], "%Y%m%d").date(),
                description=description,
                amount=float(amount.replace(",", ".")),
            )
        )
    if not rows:
        raise ImportError_("El archivo OFX no contiene movimientos")
    return rows


# --- CSV --------------------------------------------------------------------------------

DATE_HEADERS = ("fecha", "date", "fecha operacion", "fecha de operacion", "dia")
DESC_HEADERS = ("descripcion", "concepto", "description", "detalle", "movimiento", "referencia")
AMOUNT_HEADERS = ("importe", "monto", "amount", "cantidad", "valor")
DEBIT_HEADERS = ("cargo", "cargos", "retiro", "retiros", "debito", "debit", "egreso")
CREDIT_HEADERS = ("abono", "abonos", "deposito", "depositos", "credito", "credit", "ingreso")


def _find(headers: list[str], names: tuple[str, ...]) -> int | None:
    for i, h in enumerate(headers):
        if any(h == n or h.startswith(n) for n in names):
            return i
    return None


def parse_csv(text: str) -> list[ImportedRow]:
    sample = text[:4096]
    try:
        dialect: Any = csv.Sniffer().sniff(sample, delimiters=",;\t|")
    except csv.Error:
        dialect = csv.excel
    lines = list(csv.reader(io.StringIO(text), dialect))
    # La cabecera es la primera fila con una columna de fecha y otra de importe/cargo.
    header_row = -1
    for index, line in enumerate(lines[:30]):
        header_row = index
        headers = [_normalize(c) for c in line]
        date_col = _find(headers, DATE_HEADERS)
        amount_col = _find(headers, AMOUNT_HEADERS)
        debit_col, credit_col = _find(headers, DEBIT_HEADERS), _find(headers, CREDIT_HEADERS)
        if date_col is not None and (amount_col is not None or debit_col is not None):
            desc_col = _find(headers, DESC_HEADERS)
            break
    else:
        raise ImportError_(
            "No se encontraron columnas de fecha e importe. El CSV debe tener una cabecera como "
            "Fecha, Descripción, Importe (o Cargo y Abono)."
        )

    rows = []
    for line in lines[header_row + 1 :]:
        if not line or len(line) <= date_col or not line[date_col].strip():
            continue
        try:
            day = parse_date(line[date_col])
        except ImportError_:
            continue  # totales, notas al pie, etc.
        if amount_col is not None and amount_col < len(line):
            amount = parse_amount(line[amount_col])
        else:
            debit = (
                parse_amount(line[debit_col])
                if debit_col is not None and debit_col < len(line)
                else None
            )
            credit = (
                parse_amount(line[credit_col])
                if credit_col is not None and credit_col < len(line)
                else None
            )
            amount = (credit or 0) - abs(debit or 0) if (debit or credit) else None
        if not amount:
            continue
        description = (
            line[desc_col].strip() if desc_col is not None and desc_col < len(line) else ""
        )
        rows.append(ImportedRow(date=day, description=description or "Movimiento", amount=amount))
    if not rows:
        raise ImportError_("El CSV no contiene movimientos con fecha e importe válidos")
    return rows


def parse_statement(content: bytes, filename: str) -> list[ImportedRow]:
    for encoding in ("utf-8-sig", "cp1252", "latin-1"):
        try:
            text = content.decode(encoding)
            break
        except UnicodeDecodeError:
            continue
    if filename.lower().endswith((".ofx", ".qfx")) or "<OFX>" in text.upper()[:2000]:
        return parse_ofx(text)
    return parse_csv(text)


# --- Categorías -------------------------------------------------------------------------

RULES: list[tuple[SpendingCategory, tuple[str, ...]]] = [
    (
        SpendingCategory.groceries,
        (
            "oxxo",
            "walmart",
            "soriana",
            "chedraui",
            "bodega aurrera",
            "superama",
            "la comer",
            "city market",
            "heb",
            "costco",
            "sams",
            "7-eleven",
            "super",
        ),
    ),
    (
        SpendingCategory.restaurants,
        (
            "restaurant",
            "rest ",
            "starbucks",
            "uber eats",
            "rappi",
            "didi food",
            "mcdonald",
            "burger",
            "pizza",
            "taco",
            "cafe",
            "sushi",
            "vips",
            "sanborns",
        ),
    ),
    (
        SpendingCategory.transport,
        (
            "uber",
            "didi",
            "cabify",
            "pemex",
            "gasolin",
            "shell",
            "bp ",
            "mobil",
            "estacionamiento",
            "parking",
            "caseta",
            "iave",
            "pase",
            "metro",
            "ado",
        ),
    ),
    (
        SpendingCategory.shopping,
        (
            "amazon",
            "mercado libre",
            "mercadolibre",
            "liverpool",
            "palacio",
            "zara",
            "h&m",
            "shein",
            "coppel",
            "sears",
            "best buy",
            "apple.com",
        ),
    ),
    (
        SpendingCategory.entertainment,
        (
            "cinepolis",
            "cinemex",
            "ticketmaster",
            "steam",
            "playstation",
            "xbox",
            "nintendo",
            "spotify",
            "netflix",
            "disney",
            "hbo",
            "max ",
        ),
    ),
    (
        SpendingCategory.health,
        (
            "farmacia",
            "similares",
            "benavides",
            "guadalajara",
            "hospital",
            "medic",
            "doctor",
            "dental",
            "laboratorio",
            "chopo",
        ),
    ),
    (SpendingCategory.home, ("home depot", "homedepot", "ikea", "sodimac", "ferreteria", "comex")),
    (
        SpendingCategory.travel,
        (
            "aeromexico",
            "volaris",
            "viva aerobus",
            "vivaaerobus",
            "airbnb",
            "booking",
            "hotel",
            "expedia",
            "despegar",
        ),
    ),
    (
        SpendingCategory.services,
        (
            "telcel",
            "att ",
            "at&t",
            "izzi",
            "totalplay",
            "megacable",
            "cfe",
            "telmex",
            "infinitum",
            "agua",
            "gas natural",
        ),
    ),
    (
        SpendingCategory.education,
        ("colegiatura", "universidad", "escuela", "udemy", "coursera", "platzi"),
    ),
    (SpendingCategory.personal, ("gym", "smart fit", "sport city", "barber", "estetica", "salon")),
]


def suggest_category(description: str, learned: dict[str, str] | None = None) -> SpendingCategory:
    """Usa lo que el usuario ya categorizó antes y, si no, reglas por palabra clave."""
    norm = _normalize(description)
    if learned and norm in learned:
        return SpendingCategory(learned[norm])
    for category, words in RULES:
        if any(w in norm for w in words):
            return category
    return SpendingCategory.other


def learned_categories(descriptions: list[tuple[str, str]]) -> dict[str, str]:
    """Descripción normalizada -> última categoría que el usuario le asignó."""
    return {_normalize(d): c for d, c in descriptions}
