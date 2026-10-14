import json
from pathlib import Path
from unittest.mock import patch

import pytest
from dash import no_update
from PIL import Image
from reportlab.graphics.barcode.qrencoder import QRCode, QRErrorCorrectLevel

from src import main_layout
from src.analytics.TopUserChartData import TopUserChartData
from src.container import Container
from src.modals import DOCUMENTATION_URL, documentation_modal, password_modal


@pytest.mark.parametrize(
    "trigger, password_open, expected",
    [
        ("open_documentation", True, True),
        ("open_documentation", False, False),
        ("password_modal", False, False),
        ("password_modal", True, no_update),
    ],
)
def test_documentation_opens_before_login_and_closes_with_login_dialog(
    trigger, password_open, expected
):
    with patch.object(main_layout, "ctx") as context:
        context.triggered_id = trigger

        result = main_layout.toggle_documentation(1, password_open)

    assert result is expected


def test_static_qr_image_encodes_the_documentation_url():
    # Regenerate only during testing to catch an outdated bundled QR image.
    qr = QRCode(None, QRErrorCorrectLevel.M)
    qr.addData(DOCUMENTATION_URL)
    qr.make()
    asset = Path(__file__).resolve().parents[1] / "assets/documentation-qr.png"

    with Image.open(asset) as image:
        border = 4
        module_count = len(qr.modules)
        scale = image.width // (module_count + border * 2)
        assert image.width == image.height == (module_count + border * 2) * scale
        assert image.getpixel((0, 0)) == (255, 255, 255)
        for y, row in enumerate(qr.modules):
            for x, dark in enumerate(row):
                position = ((x + border) * scale + scale // 2, (y + border) * scale + scale // 2)
                assert image.getpixel(position) == ((0, 0, 0) if dark else (255, 255, 255))


def test_dialog_is_compact_and_has_no_footer():
    modal = documentation_modal()

    assert modal.children[1].children[0].src == "assets/documentation-qr.png"
    assert modal.children[1].children[2].children == DOCUMENTATION_URL
    assert len(modal.children) == 2
    assert modal.is_open is False
    assert modal.size == "md"


def test_documentation_button_is_available_in_login_footer():
    login = password_modal()

    assert [button.id for button in login.children[2].children] == [
        "open_documentation", "confirm_password"
    ]


def test_dash_serves_documentation_layout_and_static_qr_asset(temp_db, monkeypatch):
    Container.set(TopUserChartData, TopUserChartData())
    app = main_layout.app
    # Restore the unset layout after the test without invoking Dash's setter.
    monkeypatch.setattr(app, "_layout", main_layout.layout_func)
    monkeypatch.setattr(app, "_layout_is_function", True)
    client = app.server.test_client()

    response = client.get("/_dash-layout")
    asset = client.get("/assets/documentation-qr.png")

    assert response.status_code == 200
    layout_json = json.dumps(response.get_json())
    assert DOCUMENTATION_URL in layout_json
    assert '"id": "open_documentation"' in layout_json
    assert '"id": "documentation_modal"' in layout_json
    assert "documentation_copy_status" not in layout_json
    assert "documentation_close_app" not in layout_json
    assert "close_documentation" not in layout_json
    dependencies = client.get("/_dash-dependencies").get_json()
    focus_callback = next(
        callback for callback in dependencies
        if callback["output"] == "retain_focus_password.data"
    )
    assert focus_callback["inputs"] == [{"id": "documentation_modal", "property": "is_open"}]
    assert focus_callback["state"] == [{"id": "password_modal", "property": "is_open"}]
    assert asset.status_code == 200
    assert asset.mimetype == "image/png"
