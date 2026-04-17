import dash
from dash import Dash, dcc, html


app = Dash(
    __name__,
    use_pages=True,
    suppress_callback_exceptions=True,
    meta_tags=[{"name": "viewport", "content": "width=device-width, initial-scale=1"}],
    title="Painel DCF",
)
server = app.server


menu_links = [
    {"label": "Gastos com Passagens", "href": "/passagens-dcf"},
    {"label": "Pagamentos Efetivados", "href": "/pagamentos"},
    {"label": "Dotação Atualizada e Destaques Recebidos", "href": "/dotacao"},
    {"label": "Execução do Orçamento UNIFEI", "href": "/execucao-orcamento-unifei"},
    {"label": "Execução TED", "href": "/execucao-ted"},
    # {"label": "tabela", "href": "/consultartabelas"},
]


app.layout = html.Div(
    className="app-root",
    children=[
        dcc.Location(id="url"),
        dcc.Interval(
            id="interval-atualizacao",
            interval=60 * 60 * 1000,
            n_intervals=0,
        ),
        html.Div(
            className="app-container",
            children=[
                html.Div(
                    className="sidebar",
                    children=[
                        html.Div(
                            className="sidebar-header",
                            children=[
                                html.Img(
                                    src="/assets/logo_unifei.png",
                                    className="sidebar-logo",
                                ),
                                html.Div(
                                    [
                                        html.Strong(
                                            [
                                                "PARA MELHOR VISUALIZAÇÃO DO PAINEL,",
                                                html.Br(),
                                                "AJUSTE O ZOOM DO NAVEGADOR!",
                                            ]
                                        )
                                    ],
                                    className="zoom-alert",
                                ),
                                html.H2(
                                    "Painéis",
                                    className="sidebar-title",
                                ),
                            ],
                        ),
                        html.Div(
                            id="sidebar-menu",
                            className="sidebar-menu",
                        ),
                    ],
                ),
                html.Div(
                    className="main-content",
                    children=html.Div(
                        className="page-wrapper",
                        children=dash.page_container,
                    ),
                ),
            ],
        ),
    ],
)


@app.callback(
    dash.Output("sidebar-menu", "children"),
    dash.Input("url", "pathname"),
)
def atualizar_menu(pathname):
    itens = []
    for item in menu_links:
        class_name = (
            "sidebar-button sidebar-button-active"
            if pathname == item["href"]
            else "sidebar-button"
        )
        itens.append(
            dcc.Link(
                item["label"],
                href=item["href"],
                className=class_name,
            )
        )
    return itens


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8051, debug=False)
