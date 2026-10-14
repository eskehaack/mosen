from dataclasses import dataclass
from datetime import datetime

from barcode import Code128
from barcode.writer import ImageWriter
import pandas as pd
from reportlab.lib.pagesizes import A4
from reportlab.pdfbase.pdfmetrics import stringWidth
from reportlab.pdfgen import canvas

from src.database.data_connection import get_prods, get_users


BARCODE_EXPORT_REPORT_FILENAME = "Barcode label report.txt"
USER_LABEL_FONT_NAME = "Helvetica"
USER_LABEL_FONT_SIZE = 11
USER_LABEL_MAX_WIDTH = 120
PRODUCT_LABEL_FONT_SIZE = 30
PRODUCT_LABEL_MAX_WIDTH = 280

_BARCODE_RENDER_OPTIONS = {
    "write_text": False,  # Do not load the barcode writer's caption font.
    "margin_bottom": 8,
}


@dataclass(frozen=True)
class UserBarcodeLabel:
    barcode: str
    original_name: str
    printed_name: str
    change_reasons: tuple[str, ...] = ()

    @property
    def text(self) -> str:
        if self.printed_name:
            return f"{self.barcode} - {self.printed_name}"
        return self.barcode


def get_codes_users():
    users = get_users()
    return list(map(str, users["barcode"])), list(map(str, users["name"]))


def get_codes_prods():
    products = get_prods()
    return list(map(str, products["barcode"])), list(map(str, products["name"]))


def get_codes_mult():
    numbers = ["00", "02", "03", "04", "06", "10", "12", "24", "30", "60"]
    names = numbers.copy()
    names[0] = "Cancel Product"
    return numbers, names


def _validate_product_names(numbers, names):
    for barcode, name in zip(numbers, names):
        width = stringWidth(name, USER_LABEL_FONT_NAME, PRODUCT_LABEL_FONT_SIZE)
        if width > PRODUCT_LABEL_MAX_WIDTH:
            raise ValueError(
                f"Product name {name!r} (barcode {barcode}) is too long for its "
                "printed barcode label. Shorten the name and export again."
            )


def _user_label_fits(barcode, name) -> bool:
    text = f"{barcode} - {name}" if name else str(barcode)
    return stringWidth(text, USER_LABEL_FONT_NAME, USER_LABEL_FONT_SIZE) <= USER_LABEL_MAX_WIDTH


def _fit_shortened_name(barcode, words):
    first_name = words[0]
    initials = [f"{word[0].upper()}." for word in words[1:]]
    for initial_count in range(len(initials), -1, -1):
        suffix = " ".join(initials[:initial_count])
        for length in range(len(first_name), 0, -1):
            first = first_name if length == len(first_name) else f"{first_name[:length]}."
            candidate = " ".join(part for part in (first, suffix) if part)
            if _user_label_fits(barcode, candidate):
                return candidate, length < len(first_name)
    return "", False


def format_user_label(barcode, name) -> UserBarcodeLabel:
    barcode = str(barcode)
    original_name = "" if name is None else str(name)
    normalized_name = " ".join(original_name.split())
    reasons = []

    def result(printed_name):
        return UserBarcodeLabel(barcode, original_name, printed_name, tuple(reasons))

    if normalized_name != original_name:
        reasons.append("Whitespace normalized")
    if normalized_name and _user_label_fits(barcode, normalized_name):
        return result(normalized_name)
    if not _user_label_fits(barcode, ""):
        raise ValueError(f"User barcode {barcode!r} is too wide for the barcode label")
    if not normalized_name:
        reasons.append("Empty name; barcode-only label used")
        return result("")

    words = normalized_name.split()
    if len(words) > 1:
        reasons.append("Name abbreviated to fit")
    printed_name, truncated = _fit_shortened_name(barcode, words)
    if truncated:
        reasons.append("Name truncated to fit")
    if not printed_name:
        reasons.append("Name omitted because it did not fit; barcode-only label used")
    return result(printed_name)


def format_user_labels(numbers, names) -> list[UserBarcodeLabel]:
    if len(numbers) != len(names):
        raise ValueError("User barcode and name counts do not match")
    return [format_user_label(number, name) for number, name in zip(numbers, names)]


def find_user_label_collisions(
    labels: list[UserBarcodeLabel],
) -> list[list[UserBarcodeLabel]]:
    groups = {}
    for label in labels:
        groups.setdefault(label.printed_name.casefold(), []).append(label)
    return [group for group in groups.values() if len(group) > 1]


def build_barcode_export_report(
    labels: list[UserBarcodeLabel], generated_at: datetime
) -> str:
    changed = [label for label in labels if label.change_reasons]
    collisions = find_user_label_collisions(labels)
    lines = [
        "Barcode export report",
        f"Generated: {generated_at.strftime('%d-%m-%Y %H:%M:%S')}",
        "",
        f"User labels checked: {len(labels)}",
        f"Labels changed: {len(changed)}",
        f"Printed-name collision groups: {len(collisions)}",
        "",
        f"COLLISION WARNINGS ({len(collisions)})",
        "----------------------",
    ]

    if not collisions:
        lines.append("No printed-name collisions detected.")
    else:
        collision_rows = []
        for group in collisions:
            printed_name = group[0].printed_name or "<barcode only>"
            if all(label.original_name == printed_name for label in group):
                affected_users = ", ".join(label.barcode for label in group)
            else:
                affected_users = "; ".join(
                    f"{label.barcode} {label.original_name!r}" for label in group
                )
            collision_rows.append(
                {"Printed name": repr(printed_name), "Affected users": affected_users}
            )
        lines.extend(
            [
                "The following users share the same printed name:",
                pd.DataFrame(collision_rows).to_string(index=False, justify="left"),
                "The barcode prefix on each PDF label remains unique.",
            ]
        )

    lines.extend(["", f"LABEL CHANGES ({len(changed)})", "-----------------"])
    if not changed:
        lines.append("No user labels were changed.")
    else:
        change_rows = [
            {
                "Barcode": label.barcode,
                "Original name": repr(label.original_name),
                "Printed name": repr(label.printed_name or "<barcode only>"),
                "Change": "; ".join(label.change_reasons),
            }
            for label in changed
        ]
        lines.append(
            pd.DataFrame(change_rows).to_string(index=False, justify="left")
        )

    return "\n".join(lines).rstrip() + "\n"


def generate_pdf(barcode_type, pdf_filename="output.pdf") -> list[UserBarcodeLabel]:
    user_labels = []
    if barcode_type == "users":
        numbers, names = get_codes_users()
        user_labels = format_user_labels(numbers, names)
        text_values = [label.text for label in user_labels]
    elif barcode_type == "prods":
        numbers, text_values = get_codes_prods()
        _validate_product_names(numbers, text_values)
    elif barcode_type == "multipliers":
        numbers, text_values = get_codes_mult()
    else:
        return []

    if barcode_type == "users":
        x_0, y_0 = 50, 740
        width_nr, height_nr = 4, 11
        step_x, step_y = 130, 70
        width, height = 120, 50
        x_text = lambda x: x + width / 2
        y_text = lambda y: y + 2
        font_size = USER_LABEL_FONT_SIZE
        show_boundary = True
    else:
        x_0, y_0 = 300, 720
        width_nr, height_nr = 1, 10
        step_x, step_y = 120, 70
        width, height = 200, 50
        x_text = lambda x: x - 150
        y_text = lambda y: y + height / 2
        font_size = PRODUCT_LABEL_FONT_SIZE
        show_boundary = False

    pdf = canvas.Canvas(pdf_filename, pagesize=A4)
    pdf.setFont(USER_LABEL_FONT_NAME, font_size)
    total_barcodes = width_nr * height_nr
    for index, number in enumerate(numbers):
        if index and index % total_barcodes == 0:
            pdf.showPage()
            pdf.setFont(USER_LABEL_FONT_NAME, font_size)

        position = index % total_barcodes
        x = x_0 + (position % width_nr) * step_x
        y = y_0 - (position // width_nr) * step_y
        image = Code128(number, writer=ImageWriter()).render(
            writer_options=_BARCODE_RENDER_OPTIONS
        )
        pdf.drawInlineImage(
            image,
            x=x,
            y=y,
            width=width,
            height=height,
            showBoundary=show_boundary,
        )
        pdf.drawCentredString(x_text(x), y_text(y), text_values[index])

    pdf.save()
    return user_labels


if __name__ == "__main__":
    generate_pdf("multipliers")
