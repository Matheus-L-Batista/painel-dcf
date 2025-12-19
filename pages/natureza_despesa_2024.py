# pages/natureza_despesa_2024.py

import dash
from dash import html, dcc, dash_table
import pandas as pd

# Painel: Naturezas de Despesa utilizadas em 2024 sem filtros

dash.register_page(
    __name__,
    path="/natureza-despesa-2024",
    name="Naturezas 2024",
    title="Naturezas de Despesa",
)

URL = (
    "https://docs.google.com/spreadsheets/d/"
    "1ofT3KdBLI26nDp2SsYePjAgaDIObHT3WDZRwb34g2EU/"
    "gviz/tq?tqx=out:csv&sheet=TODOS201"
)

def carregar_dados():
    df = pd.read_csv(URL)
    df.columns = [c.strip() for c in df.columns]
    # Mantém apenas as colunas desejadas
    df = df[["ND SOF", "TITULO"]]
    return df  # [file:2]

df = carregar_dados()

layout = html.Div(
    children=[
        html.H2(
            "Naturezas de Despesa",
            style={"textAlign": "center"},
        ),
        html.Div(
            style={"marginBottom": "10px", "textAlign": "right"},
            children=[
                html.Button(
                    "Baixar Relatório PDF",
                    id="btn_download_relatorio_natureza_2024",
                    n_clicks=0,
                    className="filtros-button",
                ),
                dcc.Download(id="download_relatorio_natureza_2024"),
            ],
        ),
        html.Div(
            style={
                "maxWidth": "800px",
                "margin": "0 auto",
            },
            children=[
                dash_table.DataTable(
                    id="tabela_natureza_2024",
                    data=df.to_dict("records"),
                    columns=[{"name": c, "id": c} for c in df.columns],
                    style_table={
                        "overflowX": "auto",
                        "maxHeight": "80vh",
                        "overflowY": "auto",
                    },
                    style_cell={
                        "textAlign": "left",
                        "padding": "6px",
                        "fontSize": "12px",
                        "whiteSpace": "normal",
                        "height": "auto",
                    },
                    style_header={
                        "fontWeight": "bold",
                        "backgroundColor": "#0b2b57",
                        "color": "white",
                    },
                    page_size=50,
                )
            ],
        ),
    ]
)
