import dash
from dash import dcc, html
from src.main_layout import layout_func
import dash_bootstrap_components as dbc
from app import app

app.layout = layout_func
# app.layout=html.H1("test")

# Run the app
if __name__ == "__main__":
    print("Running....")
    app.run(debug=True)
