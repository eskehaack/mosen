from dash import dcc, html, dash_table


def get_upload(id: str):
    return dcc.Upload(
        ["Drag and Drop or ", html.A("Select a File")],
        id={"index": id, "type": "database_upload"},
    )


def get_table(id, data, height):
    return dash_table.DataTable(
        id=id,
        data=data,
        row_deletable=False,
        fixed_rows={"headers": True},
        style_table={
            "height": f"{str(height)}px",
            "overflowY": "auto",
        },
    )


def get_barcode(barcode):
    if barcode is None or barcode == "":
        return barcode
    return str(int(barcode))
