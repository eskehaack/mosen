from dash import dcc, html
def get_upload(id: str):
    return dcc.Upload(
        id = id,
        children = [
            'Drag and Drop or ',
            html.A('Select a File')
        ], 
        style={
            'width': '70%',
            'height': '80%',
            'borderWidth': '1px',
            'borderStyle': 'dashed',
            'borderRadius': '5px',
            'textAlign': 'center'
        }
    )