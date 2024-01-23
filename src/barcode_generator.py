import os
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas
from barcode.upc import UniversalProductCodeA
from barcode.writer import ImageWriter

from src.data_connectors import get_users, get_prods


def get_codes_users():
    users = get_users()
    numbers = list(map(str, users["barcode"]))
    names = list(map(str, users["name"]))
    return numbers, names


def get_codes_guests(number_of_guest_codes):
    users = get_users()
    first_code = max(map(int, users["barcode"])) + 1
    numbers = list(map(str, range(first_code, first_code + number_of_guest_codes)))
    names = [f"GUEST" for _ in numbers]
    return numbers, names


def get_codes_prods():
    users = get_prods()
    numbers = list(map(str, users["barcode"]))
    names = list(map(str, users["name"]))
    return numbers, names


def get_codes_mult():
    numbers = ["00", "02", "03", "04", "05", "10", "25", "24", "30", "60"]
    names = numbers.copy()
    names[0] = "Cancel Product"
    return numbers, names


def generate_pdf(type, pdf_filename="output.pdf", number_of_guest_codes=0):
    if type == "users":
        numbers, names = get_codes_users()

    elif type == "guests":
        if number_of_guest_codes < 1:
            return
        numbers, names = get_codes_guests(number_of_guest_codes)

    elif type == "prods":
        numbers, names = get_codes_prods()

    elif type == "multipliers":
        numbers, names = get_codes_mult()

    else:
        return

    if type == "users" or type == "guests":
        x_0, y_0 = 60, 720
        width_nr, height_nr = 4, 10
        step_x, step_y = 120, 70
        width, height = 110, 50

        x_text_displacement = lambda x: x + int(width / 2)
        y_text_displacement = lambda y: y + 2
        text_func = lambda x, y: f"{x} - {y}"
        font_size = 13
        show_boundary = True

    else:
        x_0, y_0 = 300, 720
        width_nr, height_nr = 1, 10
        step_x, step_y = 120, 70
        width, height = 200, 50

        x_text_displacement = lambda x: x - 100
        y_text_displacement = lambda y: y + int(height / 2)
        text_func = lambda x, y: f"{y}"
        font_size = 30
        show_boundary = False

    # Create PDF
    c = canvas.Canvas(pdf_filename, pagesize=A4)
    c.setFontSize(font_size)
    page_count = 0
    total_barcodes = width_nr * height_nr
    for i, number in enumerate(numbers):
        barcode = UniversalProductCodeA(number.zfill(11), writer=ImageWriter())
        barcode_count = i % total_barcodes

        # Move to the next page
        if i != 0 and i % total_barcodes == 0:
            c.showPage()
            c.setFontSize(font_size)
            page_count += 1

        x = x_0 + (barcode_count % width_nr) * step_x
        y = y_0 - ((barcode_count // width_nr)) * step_y

        # Add barcode to PDF
        c.drawInlineImage(
            barcode.render(text="  "),
            x=x,
            y=y,
            width=width,
            height=height,
            showBoundary=show_boundary,
        )
        c.drawCentredString(
            x=x_text_displacement(x),
            y=y_text_displacement(y),
            text=text_func(number, names[i]),
        )
    c.save()


if __name__ == "__main__":
    # Example usage
    generate_pdf("multipliers", number_of_guest_codes=10)
