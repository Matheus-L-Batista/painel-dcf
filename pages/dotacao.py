# pages/dotacao.py

import dash
from dash import html, dcc, Input, Output, State, dash_table
from dash.exceptions import PreventUpdate
import pandas as pd
import plotly.express as px
from io import BytesIO

from reportlab.lib.pagesizes import landscape, A4
from reportlab.lib.units import inch
from reportlab.platypus import (
    SimpleDocTemplate,
    Paragraph,
    Spacer,
    Table,
    TableStyle,
    Image,
)
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_CENTER, TA_RIGHT
from reportlab.lib import colors
import datetime as dt
from datetime import datetime
import os
from utils.formatting import format_brl, parse_brl_value
from utils.runtime import format_datetime_sp, get_default_year, now_sp
from utils.ui import BUTTON_CLEAR_STYLE, BUTTON_PDF_STYLE, BUTTON_REFRESH_STYLE

# --------------------------------------------------
# Registro da página no Dash Pages
# --------------------------------------------------
dash.register_page(
    __name__,
    path="/dotacao",
    name="Dotação Atualizada",
    title="Dotação Atualizada e Destaques",
)

# --------------------------------------------------
# 1. Dados
# --------------------------------------------------
URL = (
    "https://docs.google.com/spreadsheets/d/"
    "1MkiWDH-MBnLeSUlqV91qjzCVRTlTAVh9xYooENJ151o/"
    "gviz/tq?tqx=out:csv&sheet=Dotacao%20Atualizada%20e%20Destaques%20Recebidos"
)

def carregar_dados():
    df = pd.read_csv(URL)
    df.columns = [c.strip() for c in df.columns]

    df["DOTACAO ATUALIZADA_VAL"] = df["DOTACAO ATUALIZADA"].apply(parse_brl_value)
    df["DESTAQUE RECEBIDO_VAL"] = df["DESTAQUE RECEBIDO"].apply(parse_brl_value)
    return df

# DF base
df_base = carregar_dados()
try:
    ANO_PADRAO = int(sorted(df_base["ANO"].dropna().unique())[-1])
except Exception:
    ANO_PADRAO = get_default_year()

dropdown_style = {
    "color": "black",
    "width": "100%",
    "marginBottom": "6px",
    "whiteSpace": "normal",
}

AZUL = "#003A70"
VERMELHO = "#DA291C"
CINZA = "#A2AAAD"
ZEBRA_LARANJA_BG = "#FFF3E6"

KPI_CARD_STYLE = {
    "background": "#ffffff",
    "border": f"1px solid {CINZA}",
    "borderRadius": "14px",
    "padding": "6px 8px",
    "textAlign": "center",
    "boxShadow": "0 1px 3px rgba(0,0,0,0.06)",
    "minHeight": "46px",
    "display": "flex",
    "flexDirection": "column",
    "justifyContent": "center",
}
KPI_TITLE_STYLE = {
    "margin": "0 0 2px",
    "fontSize": "10px",
    "fontWeight": "800",
    "color": AZUL,
    "textTransform": "uppercase",
    "lineHeight": "1.05",
}
KPI_VALUE_STYLE_BASE = {
    "margin": "0",
    "fontSize": "16px",
    "fontWeight": "900",
    "letterSpacing": "0.2px",
    "lineHeight": "1.05",
}


def _common_graph_layout():
    return dict(
        plot_bgcolor="white",
        paper_bgcolor="white",
        font=dict(color=AZUL),
        xaxis=dict(showgrid=False),
        yaxis=dict(gridcolor=CINZA),
        hovermode="closest",
        height=420,
        margin=dict(t=55, r=20, b=60, l=60),
    )

# --------------------------------------------------
# 2. Layout da página
# --------------------------------------------------
layout = html.Div(
    style={"padding": "10px 22px"},
    children=[
        # Barra de filtros fixa no topo
        html.Div(
            id="barra-filtros-dotacao",
            className="filtros-sticky",
            children=[
                html.H3("Filtros", className="sidebar-title"),
                html.Div(
                    style={"display": "flex", "flexWrap": "wrap", "gap": "10px"},
                    children=[
                        html.Div(
                            style={"minWidth": "220px", "flex": "1"},
                            children=[
                                html.Label("Grupo da Despesa"),
                                dcc.Dropdown(
                                    id="filtro_grupo_dotacao",
                                    options=[
                                        {"label": g, "value": g}
                                        for g in sorted(
                                            df_base["GRUPO DA DESPESA"]
                                            .dropna()
                                            .unique()
                                        )
                                    ],
                                    value=None,
                                    placeholder="Todos",
                                    clearable=True,
                                    style=dropdown_style,
                                ),
                            ],
                        ),
                        html.Div(
                            style={"minWidth": "120px", "flex": "0 0 150px"},
                            children=[
                                html.Label("Ano"),
                                dcc.Dropdown(
                                    id="filtro_ano_dotacao",
                                    options=[
                                        {"label": int(a), "value": int(a)}
                                        for a in sorted(
                                            df_base["ANO"].dropna().unique()
                                        )
                                    ],
                                    value=ANO_PADRAO,
                                    clearable=False,
                                    style=dropdown_style,
                                ),
                            ],
                        ),
                        html.Div(
                            style={"minWidth": "220px", "flex": "1"},
                            children=[
                                html.Label("Unidade Orçamentária"),
                                dcc.Dropdown(
                                    id="filtro_unidade_dotacao",
                                    options=[
                                        {"label": u, "value": u}
                                        for u in sorted(
                                            df_base["UNIDADE ORÇAMENTÁRIA"]
                                            .dropna()
                                            .unique()
                                        )
                                    ],
                                    value=None,
                                    placeholder="Todas",
                                    clearable=True,
                                    style=dropdown_style,
                                ),
                            ],
                        ),
                        html.Div(
                            style={"minWidth": "220px", "flex": "1"},
                            children=[
                                html.Label("Fonte Recursos Detalhada"),
                                dcc.Dropdown(
                                    id="filtro_fonte_dotacao",
                                    options=[
                                        {"label": f, "value": f}
                                        for f in sorted(
                                            df_base["Fonte Recursos Detalhada"]
                                            .dropna()
                                            .unique()
                                        )
                                    ],
                                    value=None,
                                    placeholder="Todas",
                                    clearable=True,
                                    style=dropdown_style,
                                ),
                            ],
                        ),
                    ],
                ),
                html.Div(
                    style={"marginTop": "10px", "display": "flex", "gap": "10px"},
                    children=[
                        html.Button(
                            "Limpar filtros",
                            id="btn_limpar_filtros_dotacao",
                            n_clicks=0,
                            style=BUTTON_CLEAR_STYLE,
                        ),
                        html.Button(
                            "Atualizar Dados",
                            id="btn_reload_dotacao",
                            n_clicks=0,
                            style=BUTTON_REFRESH_STYLE,
                        ),
                        html.Button(
                            "Baixar Relatório PDF",
                            id="btn_download_relatorio_dotacao",
                            n_clicks=0,
                            style=BUTTON_PDF_STYLE,
                        ),
                        dcc.Download(id="download_relatorio_dotacao"),
                    ],
                ),
            ],
        ),

        html.Div(id="info-atualizacao-dotacao", style={"marginBottom": "10px"}),
        html.Div(
            id="cards_container_dotacao",
            style={"display": "grid", "gridTemplateColumns": "repeat(auto-fit, minmax(210px, 1fr))", "gap": "10px", "marginBottom": "10px"},
        ),
        html.Div(
            style={"display": "grid", "gridTemplateColumns": "repeat(auto-fit, minmax(360px, 1fr))", "gap": "12px", "marginBottom": "12px"},
            children=[dcc.Graph(id="grafico_pizza_dotacao"), dcc.Graph(id="grafico_pizza_destaque")],
        ),
        html.Div(
            style={"display": "grid", "gridTemplateColumns": "repeat(auto-fit, minmax(360px, 1fr))", "gap": "12px", "marginBottom": "12px"},
            children=[dcc.Graph(id="grafico_barra_dotacao_fonte"), dcc.Graph(id="grafico_barra_destaque_fonte")],
        ),
        html.H4("Detalhamento", style={"marginTop": "8px"}),
        html.Div(
            style={"width": "100%", "overflowX": "auto", "border": f"1px solid {CINZA}", "borderRadius": "10px", "paddingBottom": "8px"},
            children=dash_table.DataTable(
            id="tabela_dotacao",
            columns=[
                {"name": "GRUPO DA DESPESA", "id": "GRUPO DA DESPESA"},
                {"name": "ANO", "id": "ANO"},
                {
                    "name": "UNIDADE ORÇAMENTÁRIA",
                    "id": "UNIDADE ORÇAMENTÁRIA",
                },
                {
                    "name": "Fonte Recursos Detalhada",
                    "id": "Fonte Recursos Detalhada",
                },
                {"name": "DOTACAO ATUALIZADA", "id": "DOTACAO ATUALIZADA"},
                {"name": "DESTAQUE RECEBIDO", "id": "DESTAQUE RECEBIDO"},
            ],
            data=[],
            style_as_list_view=True,
            style_table={"minWidth": "100%", "overflowX": "auto", "maxHeight": "520px", "overflowY": "auto"},
            style_cell={"fontSize": "12px", "padding": "8px", "whiteSpace": "normal", "height": "auto", "textAlign": "left", "border": f"1px solid {CINZA}", "lineHeight": "1.25", "backgroundColor": "white", "color": "#111"},
            style_header={"fontWeight": "bold", "backgroundColor": AZUL, "color": "white", "textAlign": "left", "position": "sticky", "top": 0, "zIndex": 10, "padding": "8px"},
            style_data_conditional=[
                {"if": {"row_index": "odd"}, "backgroundColor": ZEBRA_LARANJA_BG},
                {"if": {"column_id": "DOTACAO ATUALIZADA"}, "textAlign": "right"},
                {"if": {"column_id": "DESTAQUE RECEBIDO"}, "textAlign": "right"},
            ],
        )),
        dcc.Store(id="store_pdf_dotacao"),
    ],
)

# --------------------------------------------------
# 3. Callback principal
# --------------------------------------------------
@dash.callback(
    Output("tabela_dotacao", "data"),
    Output("cards_container_dotacao", "children"),
    Output("info-atualizacao-dotacao", "children"),
    Output("grafico_pizza_dotacao", "figure"),
    Output("grafico_pizza_destaque", "figure"),
    Output("grafico_barra_dotacao_fonte", "figure"),
    Output("grafico_barra_destaque_fonte", "figure"),
    Output("store_pdf_dotacao", "data"),
    Input("filtro_grupo_dotacao", "value"),
    Input("filtro_ano_dotacao", "value"),
    Input("filtro_unidade_dotacao", "value"),
    Input("filtro_fonte_dotacao", "value"),
    Input("btn_reload_dotacao", "n_clicks"),
    Input("interval-atualizacao", "n_intervals"),
)
def atualizar_painel(grupo, ano, unidade, fonte, n_reload, n_intervals):
    global df_base

    agora = now_sp().time()
    if getattr(dash.ctx, "triggered_id", None) == "btn_reload_dotacao":
        df_base = carregar_dados()
    elif dt.time(8, 0) <= agora <= dt.time(20, 0):
        if n_intervals is not None:
            df_base = carregar_dados()

    dff = df_base.copy()

    if ano:
        dff = dff[dff["ANO"] == ano]
    if grupo:
        dff = dff[dff["GRUPO DA DESPESA"] == grupo]
    if unidade:
        dff = dff[dff["UNIDADE ORÇAMENTÁRIA"] == unidade]
    if fonte:
        dff = dff[dff["Fonte Recursos Detalhada"] == fonte]

    def fmt(v):
        return format_brl(v)

    total_dotacao = dff["DOTACAO ATUALIZADA_VAL"].sum()
    total_destaque = dff["DESTAQUE RECEBIDO_VAL"].sum()

    info_msg = html.Div(
        [
            html.B("Dados disponiveis. "),
            html.Span(f"Ultima visualizacao em {format_datetime_sp(now_sp())}."),
        ]
    )

    cards = [
        html.Div(
            style={**KPI_CARD_STYLE, "borderTop": f"4px solid {AZUL}"},
            children=[
                html.P("Dotação Atualizada", style={**KPI_TITLE_STYLE, "color": AZUL}),
                html.P(
                    fmt(total_dotacao),
                    style={**KPI_VALUE_STYLE_BASE, "color": AZUL},
                ),
            ],
        ),
        html.Div(
            style={**KPI_CARD_STYLE, "borderTop": f"4px solid {VERMELHO}"},
            children=[
                html.P("Destaques Recebidos", style={**KPI_TITLE_STYLE, "color": VERMELHO}),
                html.P(
                    fmt(total_destaque),
                    style={**KPI_VALUE_STYLE_BASE, "color": VERMELHO},
                ),
            ],
        ),
    ]

    dff_display = dff.copy()
    dff_display["DOTACAO ATUALIZADA"] = dff_display[
        "DOTACAO ATUALIZADA_VAL"
    ].apply(fmt)
    dff_display["DESTAQUE RECEBIDO"] = dff_display[
        "DESTAQUE RECEBIDO_VAL"
    ].apply(fmt)

    colunas = [
        "GRUPO DA DESPESA",
        "ANO",
        "UNIDADE ORÇAMENTÁRIA",
        "Fonte Recursos Detalhada",
        "DOTACAO ATUALIZADA",
        "DESTAQUE RECEBIDO",
    ]
    dff_display = dff_display[colunas]

    # Colunas - Dotação por Grupo
    if not dff.empty:
        grp_dot_grupo = dff.groupby(
            "GRUPO DA DESPESA", as_index=False
        )["DOTACAO ATUALIZADA_VAL"].sum()
        fig_pizza_dot = px.bar(
            grp_dot_grupo,
            x="GRUPO DA DESPESA",
            y="DOTACAO ATUALIZADA_VAL",
            color="GRUPO DA DESPESA",
            color_discrete_sequence=["#003A70", "#DA291C", "#A2AAAD"],
            text="DOTACAO ATUALIZADA_VAL",
            title="Dotação Atualizada por Grupo de Despesa",
        )
        fig_pizza_dot.update_traces(
            texttemplate="R$ %{y:,.2f}",
            textposition="outside",
            cliponaxis=False,
            hovertemplate="<b>%{x}</b><br>R$ %{y:,.2f}<extra></extra>",
        )
        fig_pizza_dot.update_layout(
            **_common_graph_layout(),
            xaxis_title="Grupo da Despesa",
            yaxis_title="Dotação Atualizada (R$)",
            yaxis_tickprefix="R$ ",
            yaxis_tickformat=",.2f",
            showlegend=False,
            title_y=0.95,
        )
    else:
        fig_pizza_dot = px.bar(
            title="Sem dados para os filtros selecionados"
        )

    # Colunas - Destaques por Grupo
    if not dff.empty:
        grp_des_grupo = dff.groupby(
            "GRUPO DA DESPESA", as_index=False
        )["DESTAQUE RECEBIDO_VAL"].sum()
        fig_pizza_des = px.bar(
            grp_des_grupo,
            x="GRUPO DA DESPESA",
            y="DESTAQUE RECEBIDO_VAL",
            color="GRUPO DA DESPESA",
            color_discrete_sequence=["#003A70", "#DA291C", "#A2AAAD"],
            text="DESTAQUE RECEBIDO_VAL",
            title="Destaques Recebidos por Grupo de Despesa",
        )
        fig_pizza_des.update_traces(
            texttemplate="R$ %{y:,.2f}",
            textposition="outside",
            cliponaxis=False,
            hovertemplate="<b>%{x}</b><br>R$ %{y:,.2f}<extra></extra>",
        )
        fig_pizza_des.update_layout(
            **_common_graph_layout(),
            xaxis_title="Grupo da Despesa",
            yaxis_title="Destaques Recebidos (R$)",
            yaxis_tickprefix="R$ ",
            yaxis_tickformat=",.2f",
            showlegend=False,
            title_y=0.95,
        )
    else:
        fig_pizza_des = px.bar(
            title="Sem dados para os filtros selecionados"
        )

    def texto_posicoes(valores):
        max_v = max(valores) if len(valores) else 0
        posicoes = []
        for v in valores:
            if max_v > 0 and v >= 0.3 * max_v:
                posicoes.append("inside")
            else:
                posicoes.append("outside")
        return posicoes

    # Barra – Dotação por Fonte
    if not dff.empty:
        grp_dot_fonte = dff.groupby(
            "Fonte Recursos Detalhada", as_index=False
        )["DOTACAO ATUALIZADA_VAL"].sum()
        fig_bar_dot = px.bar(
            grp_dot_fonte,
            x="DOTACAO ATUALIZADA_VAL",
            y="Fonte Recursos Detalhada",
            orientation="h",
            title="Dotação Atualizada por Fonte de Recursos Detalhada",
        )
        valores = grp_dot_fonte["DOTACAO ATUALIZADA_VAL"].tolist()
        posicoes = texto_posicoes(valores)
        fig_bar_dot.update_traces(
            marker_color="#003A70",
            hovertemplate="<b>%{y}</b><br>R$ %{x:,.2f}<extra></extra>",
            text=[fmt(v) for v in valores],
            textposition=posicoes,
            textfont_color="white",
        )
        fig_bar_dot.update_layout(
            **_common_graph_layout(),
            xaxis_title="Dotação Atualizada (R$)",
            yaxis_title="Fonte Recursos Detalhada",
            xaxis_tickprefix="R$ ",
            xaxis_tickformat=",.2f",
            title_y=0.95,
        )
    else:
        fig_bar_dot = px.bar(
            title="Sem dados para os filtros selecionados"
        )

    # Barra – Destaques por Fonte
    if not dff.empty:
        grp_des_fonte = dff.groupby(
            "Fonte Recursos Detalhada", as_index=False
        )["DESTAQUE RECEBIDO_VAL"].sum()
        fig_bar_des = px.bar(
            grp_des_fonte,
            x="DESTAQUE RECEBIDO_VAL",
            y="Fonte Recursos Detalhada",
            orientation="h",
            title="Destaques Recebidos por Fonte de Recursos Detalhada",
        )
        valores_des = grp_des_fonte["DESTAQUE RECEBIDO_VAL"].tolist()
        posicoes_des = texto_posicoes(valores_des)
        fig_bar_des.update_traces(
            marker_color="#DA291C",
            hovertemplate="<b>%{y}</b><br>R$ %{x:,.2f}<extra></extra>",
            text=[fmt(v) for v in valores_des],
            textposition=posicoes_des,
            textfont_color="white",
        )
        fig_bar_des.update_layout(
            **_common_graph_layout(),
            xaxis_title="Destaques Recebidos (R$)",
            yaxis_title="Fonte Recursos Detalhada",
            xaxis_tickprefix="R$ ",
            xaxis_tickformat=",.2f",
            title_y=0.95,
        )
    else:
        fig_bar_des = px.bar(
            title="Sem dados para os filtros selecionados"
        )

    dados_pdf = {
        "tabela": dff_display.to_dict("records"),
        "total_dotacao": float(total_dotacao),
        "total_destaque": float(total_destaque),
        "filtros": {
            "grupo": grupo,
            "ano": ano,
            "unidade": unidade,
            "fonte": fonte,
        },
    }

    return (
        dff_display.to_dict("records"),
        cards,
        info_msg,
        fig_pizza_dot,
        fig_pizza_des,
        fig_bar_dot,
        fig_bar_des,
        dados_pdf,
    )

# --------------------------------------------------
# 4. Filtros em cascata
# --------------------------------------------------
@dash.callback(
    Output("filtro_grupo_dotacao", "options"),
    Output("filtro_unidade_dotacao", "options"),
    Output("filtro_fonte_dotacao", "options"),
    Input("filtro_ano_dotacao", "value"),
    Input("filtro_grupo_dotacao", "value"),
    Input("filtro_unidade_dotacao", "value"),
    Input("filtro_fonte_dotacao", "value"),
)
def atualizar_opcoes_filtros_dotacao(ano, grupo, unidade, fonte):
    dff = df_base.copy()
    mask = pd.Series(True, index=dff.index)

    if ano:
        mask &= dff["ANO"] == ano
    if grupo:
        mask &= dff["GRUPO DA DESPESA"] == grupo
    if unidade:
        mask &= dff["UNIDADE ORÇAMENTÁRIA"] == unidade
    if fonte:
        mask &= dff["Fonte Recursos Detalhada"] == fonte

    dff = dff[mask]

    op_grupo = [
        {"label": g, "value": g}
        for g in sorted(dff["GRUPO DA DESPESA"].dropna().unique())
        if str(g) != ""
    ]

    op_unidade = [
        {"label": u, "value": u}
        for u in sorted(dff["UNIDADE ORÇAMENTÁRIA"].dropna().unique())
        if str(u) != ""
    ]

    op_fonte = [
        {"label": f, "value": f}
        for f in sorted(dff["Fonte Recursos Detalhada"].dropna().unique())
        if str(f) != ""
    ]

    return op_grupo, op_unidade, op_fonte

# --------------------------------------------------
# 5. Limpar filtros
# --------------------------------------------------
@dash.callback(
    Output("filtro_ano_dotacao", "value"),
    Output("filtro_grupo_dotacao", "value"),
    Output("filtro_unidade_dotacao", "value"),
    Output("filtro_fonte_dotacao", "value"),
    Input("btn_limpar_filtros_dotacao", "n_clicks"),
    prevent_initial_call=True,
)
def limpar_filtros(n):
    return ANO_PADRAO, None, None, None

# --------------------------------------------------
# 6. Estilos PDF + funções auxiliares
# --------------------------------------------------
def formatar_moeda_br(v):
    try:
        return format_brl(v)
    except (ValueError, TypeError):
        return str(v)

wrap_style_dot = ParagraphStyle(
    name="wrap_dot",
    fontSize=7,
    leading=9,
    spaceAfter=2,
    wordWrap="CJK",
)

simple_style_dot = ParagraphStyle(
    name="simple_dot",
    fontSize=7,
    alignment=TA_CENTER,
)

header_cell_style_dot = ParagraphStyle(
    name="header_cell_dot",
    fontSize=7,
    alignment=TA_CENTER,
    fontName="Helvetica-Bold",
    textColor=colors.white,
)

def wrap_pdf_dot(text):
    return Paragraph(str(text), wrap_style_dot)

def simple_pdf_dot(text):
    return Paragraph(str(text), simple_style_dot)

def header_pdf_dot(text):
    return Paragraph(str(text), header_cell_style_dot)

def criar_card_elemento_dot(titulo, valor, cor):
    card_content = [
        [
            Paragraph(
                f"{valor}",
                ParagraphStyle(
                    "card_valor_dot",
                    alignment=TA_CENTER,
                    spaceAfter=4,
                ),
            )
        ],
        [
            Paragraph(
                f"{titulo}",
                ParagraphStyle(
                    "card_titulo_dot",
                    alignment=TA_CENTER,
                    textColor="#666666",
                    spaceAfter=0,
                ),
            )
        ],
    ]

    card_table = Table(card_content, colWidths=[1.5 * inch])
    card_table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#F5F5F5")),
                ("BORDER", (0, 0), (-1, -1), 1, colors.HexColor("#DDDDDD")),
                ("ALIGN", (0, 0), (-1, -1), "CENTER"),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("TOPPADDING", (0, 0), (-1, -1), 6),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
                ("LEFTPADDING", (0, 0), (-1, -1), 4),
                ("RIGHTPADDING", (0, 0), (-1, -1), 4),
            ]
        )
    )
    return card_table

def criar_cards_resumo_dotacao_pdf(story, dados_pdf, pagesize):
    total_dotacao = dados_pdf.get("total_dotacao", 0.0)
    total_destaque = dados_pdf.get("total_destaque", 0.0)

    story.append(Spacer(1, 0.08 * inch))

    card_data = [
        [
            criar_card_elemento_dot(
                "Dotação Atualizada",
                formatar_moeda_br(total_dotacao),
                "#003A70",
            ),
            criar_card_elemento_dot(
                "Destaques Recebidos",
                formatar_moeda_br(total_destaque),
                "#DA291C",
            ),
        ]
    ]

    largura_util = pagesize[0] - 0.3 * inch
    card_width = largura_util / 2 - 0.05 * inch

    cards_table = Table(
        card_data,
        colWidths=[card_width, card_width],
    )
    cards_table.setStyle(
        TableStyle(
            [
                ("ALIGN", (0, 0), (-1, -1), "CENTER"),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("TOPPADDING", (0, 0), (-1, -1), 0),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 0),
                ("LEFTPADDING", (0, 0), (-1, -1), 0),
                ("RIGHTPADDING", (0, 0), (-1, -1), 0),
                ("GRID", (0, 0), (-1, -1), 0, colors.transparent),
            ]
        )
    )

    story.append(cards_table)
    story.append(Spacer(1, 0.15 * inch))

def adicionar_cabecalho_dotacao(story, df, styles, pagesize, dados_pdf):
    # Logos
    logo_esq = (
        Image("assets/brasaobrasil.png", 1.2 * inch, 1.2 * inch)
        if os.path.exists("assets/brasaobrasil.png")
        else ""
    )
    logo_dir = (
        Image("assets/simbolo_RGB.png", 1.2 * inch, 1.2 * inch)
        if os.path.exists("assets/simbolo_RGB.png")
        else ""
    )

    texto_instituicao = (
        "<b><font color='#0b2b57' size=13>Ministério da Educação</font></b><br/>"
        "<b><font color='#0b2b57' size=13>Universidade Federal de Itajubá</font></b><br/>"
        "<font color='#0b2b57' size=11>Diretoria de Contabilidade e Finanças</font>"
    )

    instituicao = Paragraph(
        texto_instituicao,
        ParagraphStyle(
            "instituicao_dotacao",
            alignment=TA_CENTER,
            leading=16,
        ),
    )

    # coluna central menor para aproximar os logos (como no modelo desejado)
    cabecalho = Table(
        [[logo_esq, instituicao, logo_dir]],
        colWidths=[
            1.4 * inch,
            4.2 * inch,
            1.4 * inch,
        ],
    )
    cabecalho.setStyle(
        TableStyle(
            [
                ("ALIGN", (0, 0), (-1, -1), "CENTER"),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("TOPPADDING", (0, 0), (-1, -1), 6),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
            ]
        )
    )
    story.append(cabecalho)
    story.append(Spacer(1, 0.15 * inch))

    # Título do relatório
    titulo = Paragraph(
        "RELATÓRIO DE DOTAÇÃO ATUALIZADA E DESTAQUES RECEBIDOS",
        ParagraphStyle(
            "titulo_dotacao",
            alignment=TA_CENTER,
            fontSize=10,
            leading=14,
            textColor=colors.black,
            fontName="Helvetica-Bold",
        ),
    )
    story.append(titulo)
    story.append(Spacer(1, 0.15 * inch))

    # Total de registros
    total_registros = len(df) if df is not None else 0
    story.append(
        Paragraph(f"Total de registros: {total_registros}", styles["Normal"])
    )
    story.append(Spacer(1, 0.15 * inch))

    # Filtros
    f = dados_pdf.get("filtros", {})
    story.append(
        Paragraph(
            f"Ano: {f.get('ano') if f.get('ano') else 'Todos'} — "
            f"Grupo: {f.get('grupo') if f.get('grupo') else 'Todos'} — "
            f"Unidade: {f.get('unidade') if f.get('unidade') else 'Todas'} — "
            f"Fonte: {f.get('fonte') if f.get('fonte') else 'Todas'}",
            styles["Normal"],
        )
    )
    story.append(Spacer(1, 0.15 * inch))

def criar_tabela_dados_dotacao(story, dados_pdf, pagesize):
    registros = dados_pdf["tabela"]
    if not registros:
        return

    df_pdf = pd.DataFrame(registros)

    cols = [
        "GRUPO DA DESPESA",
        "ANO",
        "UNIDADE ORÇAMENTÁRIA",
        "Fonte Recursos Detalhada",
        "DOTACAO ATUALIZADA",
        "DESTAQUE RECEBIDO",
    ]
    cols = [c for c in cols if c in df_pdf.columns]

    header = [header_pdf_dot(c) for c in cols]
    table_data = [header]

    for _, row in df_pdf[cols].iterrows():
        linha = []
        for c in cols:
            val = "" if pd.isna(row[c]) else str(row[c]).strip()
            if c in ["GRUPO DA DESPESA", "UNIDADE ORÇAMENTÁRIA", "Fonte Recursos Detalhada"]:
                linha.append(wrap_pdf_dot(val))
            else:
                linha.append(simple_pdf_dot(val))
        table_data.append(linha)

    col_widths = [
        1.2 * inch,  # GRUPO
        0.6 * inch,  # ANO
        2.0 * inch,  # UNIDADE
        2.5 * inch,  # FONTE
        1.0 * inch,  # DOTACAO
        1.0 * inch,  # DESTAQUE
    ]
    col_widths = col_widths[: len(cols)]

    tbl = Table(table_data, colWidths=col_widths, repeatRows=1)
    style_list = [
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#0b2b57")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("ALIGN", (0, 0), (-1, 0), "CENTER"),
        ("FONTSIZE", (0, 0), (-1, 0), 7),
        ("FONTWEIGHT", (0, 0), (-1, 0), "bold"),
        ("TOPPADDING", (0, 0), (-1, 0), 6),
        ("BOTTOMPADDING", (0, 0), (-1, 0), 6),
        ("LINEBELOW", (0, 0), (-1, 0), 1.2, colors.HexColor("#0b2b57")),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
        ("ALIGN", (0, 1), (-1, -1), "LEFT"),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("FONTSIZE", (0, 1), (-1, -1), 7),
        ("TOPPADDING", (0, 0), (-1, -1), 2),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 2),
        ("LEFTPADDING", (0, 0), (-1, -1), 2),
        ("RIGHTPADDING", (0, 0), (-1, -1), 2),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1),
         [colors.white, colors.HexColor("#f0f0f0")]),
        ("WORDWRAP", (0, 0), (-1, -1), True),
    ]
    tbl.setStyle(TableStyle(style_list))
    story.append(tbl)

# --------------------------------------------------
# 7. PDF (callback, modelo próximo ao UNIFEI)
# --------------------------------------------------
@dash.callback(
    Output("download_relatorio_dotacao", "data"),
    Input("btn_download_relatorio_dotacao", "n_clicks"),
    State("store_pdf_dotacao", "data"),
    prevent_initial_call=True,
)
def gerar_pdf(n, dados_pdf):
    if not n or not dados_pdf:
        raise PreventUpdate

    df_pdf = pd.DataFrame(dados_pdf["tabela"])

    buffer = BytesIO()
    pagesize = landscape(A4)
    doc = SimpleDocTemplate(
        buffer,
        pagesize=pagesize,
        rightMargin=0.15 * inch,
        leftMargin=0.15 * inch,
        topMargin=0.2 * inch,
        bottomMargin=0.4 * inch,
    )
    styles = getSampleStyleSheet()
    story = []

    # Data/hora topo (Brasília) – padrão UNIFEI
    data_hora_brasilia = format_datetime_sp(now_sp())
    data_top_table = Table(
        [[
            Paragraph(
                data_hora_brasilia,
                ParagraphStyle(
                    "data_topo_dotacao",
                    fontSize=9,
                    alignment=TA_RIGHT,
                    textColor="#333333",
                ),
            )
        ]],
        colWidths=[pagesize[0] - 0.3 * inch],
    )
    data_top_table.setStyle(
        TableStyle(
            [
                ("ALIGN", (0, 0), (-1, -1), "RIGHT"),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ]
        )
    )
    story.append(data_top_table)
    story.append(Spacer(1, 0.1 * inch))

    # Cabeçalho padrão
    adicionar_cabecalho_dotacao(story, df_pdf, styles, pagesize, dados_pdf)

    # Cards resumo
    criar_cards_resumo_dotacao_pdf(story, dados_pdf, pagesize)

    # Tabela de dados
    criar_tabela_dados_dotacao(story, dados_pdf, pagesize)

    doc.build(story)
    buffer.seek(0)

    from dash import dcc
    return dcc.send_bytes(
        buffer.getvalue(),
        f"dotacao_destaques_{now_sp().strftime('%Y%m%d%H%M%S')}.pdf",
    )
