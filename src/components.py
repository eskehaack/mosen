from dash import dcc, html


def get_upload(id: str):
    return dcc.Upload(
        ["Drag and Drop or ", html.A("Select a File")],
        id={"index": id, "type": "database_upload"},
    )


def get_barcode(barcode):
    if barcode is None or barcode == "":
        return barcode
    return str(int(barcode))
