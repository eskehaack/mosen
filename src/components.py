from dash import dcc, html
def get_upload(id: str):
    return dcc.Input(
        id = id,
        placeholder = "Full file path",
        type="text",
        minLength=1
    )