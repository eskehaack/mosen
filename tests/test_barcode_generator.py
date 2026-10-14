from datetime import datetime

import pytest
from barcode import Code128
from barcode.writer import ImageWriter
from reportlab.pdfbase.pdfmetrics import stringWidth

from src import barcode_generator


def _assert_label_fits(label):
    width = stringWidth(
        label.text,
        barcode_generator.USER_LABEL_FONT_NAME,
        barcode_generator.USER_LABEL_FONT_SIZE,
    )
    assert width <= barcode_generator.USER_LABEL_MAX_WIDTH, (
        f"Label {label.text!r} is {width:.1f} points wide"
    )


def test_generate_pdf_does_not_require_barcode_caption_font(tmp_path, monkeypatch):
    # Arrange
    missing_font = tmp_path / "missing-barcode-font.ttf"

    def image_writer_without_font():
        writer = ImageWriter()
        writer.font_path = str(missing_font)
        return writer

    monkeypatch.setattr(barcode_generator, "ImageWriter", image_writer_without_font)
    monkeypatch.setattr(
        barcode_generator,
        "get_codes_users",
        lambda: (["1000"], ["Thomas"]),
    )
    output = tmp_path / "users.pdf"

    # Act
    barcode_generator.generate_pdf("users", str(output))

    # Assert
    assert output.read_bytes().startswith(b"%PDF")


def test_barcode_image_reserves_blank_space_for_reportlab_label(tmp_path):
    # Arrange
    writer = ImageWriter()
    writer.font_path = str(tmp_path / "missing-barcode-font.ttf")

    # Act
    image = Code128("1000", writer=writer).render(
        writer_options=barcode_generator._BARCODE_RENDER_OPTIONS
    )
    bottom_quarter = image.crop(
        (0, int(image.height * 0.75), image.width, image.height)
    )

    # Assert
    assert all(channel == (255, 255) for channel in bottom_quarter.getextrema())


@pytest.mark.parametrize(
    ("barcode", "name", "printed_name", "reasons"),
    [
        pytest.param(
            "1013",
            "Example User",
            "Example User",
            (),
            id="preserves-full-name-that-fits",
        ),
        pytest.param(
            "1613",
            "Testuser Alpha Example",
            "Testuser A. E.",
            ("Name abbreviated to fit",),
            id="abbreviates-surnames-to-fit",
        ),
        pytest.param(
            "1603",
            "  Sample   Beta\tExample ",
            "Sample B. E.",
            ("Whitespace normalized", "Name abbreviated to fit"),
            id="normalizes-whitespace-before-abbreviating",
        ),
    ],
)
def test_format_user_label_returns_expected_text_and_change_reasons(
    barcode, name, printed_name, reasons
):
    # Act
    label = barcode_generator.format_user_label(barcode, name)

    # Assert
    assert label.printed_name == printed_name
    assert label.change_reasons == reasons
    _assert_label_fits(label)


def test_format_user_label_truncates_single_word_to_fit():
    # Act
    label = barcode_generator.format_user_label(
        "1000", "ExtraordinarilyLongSingleWordName"
    )

    # Assert
    assert label.printed_name.endswith(".")
    assert label.change_reasons == ("Name truncated to fit",)
    _assert_label_fits(label)


def test_format_user_label_uses_barcode_only_when_no_name_character_fits():
    # Act
    label = barcode_generator.format_user_label("9" * 19, "Testuser")

    # Assert
    assert label.printed_name == ""
    assert label.text == "9" * 19
    assert label.change_reasons == (
        "Name omitted because it did not fit; barcode-only label used",
    )
    _assert_label_fits(label)


def test_find_user_label_collisions_matches_printed_names_case_insensitively():
    # Arrange
    labels = [
        barcode_generator.format_user_label("1000", "Testuser"),
        barcode_generator.format_user_label("1001", "TESTUSER"),
        barcode_generator.format_user_label("1002", "Controluser"),
    ]

    # Act
    collisions = barcode_generator.find_user_label_collisions(labels)

    # Assert
    assert [[label.barcode for label in group] for group in collisions] == [
        ["1000", "1001"]
    ]


def test_build_barcode_export_report_lists_changes_and_collisions_without_truncation():
    # Arrange
    labels = [
        barcode_generator.format_user_label("1000", "Testuser Alpha Example"),
        barcode_generator.format_user_label("1001", "Testuser Another Example"),
        *[
            barcode_generator.format_user_label(str(barcode), "SampleUser")
            for barcode in range(11130, 11141)
        ],
    ]

    # Act
    report = barcode_generator.build_barcode_export_report(
        labels, datetime(2026, 9, 21, 16, 20)
    )

    # Assert
    assert "Generated: 21-09-2026 16:20:00" in report
    assert "Labels changed: 2" in report
    assert "Printed-name collision groups: 2" in report
    assert "COLLISION WARNINGS (2)" in report
    assert (
        "1000 'Testuser Alpha Example'; "
        "1001 'Testuser Another Example'"
    ) in report
    assert "11130, 11131, 11132" in report
    assert "11139, 11140" in report
    assert "..." not in report
    assert "LABEL CHANGES (2)" in report
    assert "Original name" in report
    assert "Printed name" in report
    assert report.index("COLLISION WARNINGS") < report.index("LABEL CHANGES")


def test_build_barcode_export_report_states_when_no_changes_or_collisions_exist():
    # Arrange
    label = barcode_generator.format_user_label("1013", "Example User")

    # Act
    report = barcode_generator.build_barcode_export_report(
        [label], datetime(2026, 9, 21, 16, 20)
    )

    # Assert
    assert "No user labels were changed." in report
    assert "No printed-name collisions detected." in report
    assert "COLLISION WARNINGS (0)" in report
    assert "LABEL CHANGES (0)" in report


def test_generate_user_pdf_writes_pdf_and_returns_formatted_labels(
    tmp_path, monkeypatch
):
    # Arrange
    monkeypatch.setattr(
        barcode_generator,
        "get_codes_users",
        lambda: (["1013"], ["Example User"]),
    )
    output = tmp_path / "users.pdf"

    # Act
    labels = barcode_generator.generate_pdf("users", str(output))

    # Assert
    assert output.read_bytes().startswith(b"%PDF")
    assert labels[0].printed_name == "Example User"


def test_generate_product_pdf_accepts_name_that_fits_label_width(
    tmp_path, monkeypatch
):
    # Arrange
    monkeypatch.setattr(
        barcode_generator,
        "get_codes_prods",
        lambda: (["101"], ["Red Bull Blueberry"]),
    )
    output = tmp_path / "products.pdf"

    # Act
    barcode_generator.generate_pdf("prods", str(output))

    # Assert
    assert output.read_bytes().startswith(b"%PDF")


def test_generate_product_pdf_rejects_name_wider_than_label(
    tmp_path, monkeypatch
):
    # Arrange
    monkeypatch.setattr(
        barcode_generator,
        "get_codes_prods",
        lambda: (["102"], ["An intentionally extremely long product name"]),
    )
    output = tmp_path / "products.pdf"

    # Act / Assert
    with pytest.raises(
        ValueError,
        match=r"Product name .* \(barcode 102\) is too long.*Shorten the name",
    ):
        barcode_generator.generate_pdf("prods", str(output))
    assert not output.exists()
