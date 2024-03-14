from dash import dcc, html, dash_table


def get_upload(id: str):
    return dcc.Upload(
        ["Drag and drop or ", html.A("Select a File")],
        id={"index": id, "type": "database_upload"},
        className="upload-field",
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
        style_cell={
            "overflow": "hidden",
            "textOverflow": "ellipsis",
            "maxWidth": 0,
            "textAlign": "left",
        },
        tooltip_data=(
            None
            if data is None
            else [
                {
                    column.replace("_", " ").title(): {
                        "value": str(value),
                        "type": "markdown",
                    }
                    for column, value in row.items()
                }
                for row in data
            ]
        ),
        tooltip_duration=None,
    )


def get_barcode(barcode):
    if barcode is None or barcode == "":
        return barcode
    return str(int(barcode))
