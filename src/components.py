from dash import dcc, html, dash_table


def _display_column_name(column):
    return column.replace("_", " ").title()


def _get_columns(data):
    if not data:
        return None
    return [
        {"name": _display_column_name(column), "id": column}
        for column in data[0].keys()
    ]


def get_tooltip_data(data):
    if data is None:
        return None
    return [
        {
            column: {
                "value": str(value),
                "type": "markdown",
            }
            for column, value in row.items()
        }
        for row in data
    ]


def get_upload(id: str):
    return dcc.Upload(
        ["Drag and drop or ", html.A("Select a File")],
        id={"index": id, "type": "database_upload"},
        className="upload-field",
    )


def get_table(id, data, height, row_selectable=None):
    return dash_table.DataTable(
        id=id,
        data=data,
        columns=_get_columns(data),
        row_deletable=False,
        row_selectable=row_selectable,
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
            "padding": "2px 4px",
        },
        style_header={
            "whiteSpace": "normal",
            "height": "auto",
            "overflow": "visible",
            "textOverflow": "clip",
            "fontWeight": "bold",
            "lineHeight": "1.1",
            "padding": "2px 4px",
        },
        tooltip_data=get_tooltip_data(data),
        tooltip_duration=None,
        sort_action="native",
    )


def get_barcode(barcode):
    if barcode is None or barcode == "":
        return barcode
    if not str(barcode).isdigit():
        print(f"Warning: Could not convert barcode {barcode} to integer value.")
        return "bad barcode"
    return str(int(barcode))
