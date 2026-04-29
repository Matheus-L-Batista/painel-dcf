import dash
from dash import html, dcc, Input, Output, State, dash_table
from dash.exceptions import PreventUpdate
import plotly.express as px
import pandas as pd
from datetime import datetime
from io import BytesIO
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import inch
from reportlab.platypus import (
    SimpleDocTemplate,
    Image,
    Paragraph,
    Spacer,
    Table,
    TableStyle,
)
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_CENTER, TA_RIGHT, TA_LEFT
from reportlab.lib import colors
import os
from utils.formatting import format_brl, parse_brl_value
from utils.runtime import format_datetime_sp, get_default_year, now_sp
from utils.ui import BUTTON_CLEAR_STYLE, BUTTON_PDF_STYLE, BUTTON_REFRESH_STYLE

# --------------------------------------------------
# Registro da página
# --------------------------------------------------
dash.register_page(
    __name__,
    path="/passagens-dcf",
    name="Passagens DCF",
    title="Gastos com Viagens",
)

# --------------------------------------------------
# URL da planilha
# --------------------------------------------------
URL = (
    "https://docs.google.com/spreadsheets/d/"
    "1QJFSLpVO0bI-bsNdgiTWl8rOh1_h6_B7Q8F_SW66_yc/"
    "gviz/tq?tqx=out:csv&sheet=Passagens%20-%20DCF"
)

# --------------------------------------------------
# Carga e tratamento dos dados
# --------------------------------------------------
COLUNAS_PASSAGENS = [
    "Data Início da Viagem",
    "Valor das Diárias",
    "Valor da Viagem",
    "Valor da Passagem",
    "Valor Seguro Viagem",
    "Valor Restituição",
    "Custo com emissão de passagens dentro do prazo",
    "Custo com emissão de passagens em caráter de urgência",
    "Unidade (Viagem)",
    "Número da PCDP",
    "Ano",
    "Mes",
]


def _df_vazio_passagens():
    df = pd.DataFrame(columns=COLUNAS_PASSAGENS)
    df["Data Início da Viagem"] = pd.to_datetime(df["Data Início da Viagem"], errors="coerce")
    for col in [
        "Valor das Diárias",
        "Valor da Viagem",
        "Valor da Passagem",
        "Valor Seguro Viagem",
        "Valor Restituição",
        "Custo com emissão de passagens dentro do prazo",
        "Custo com emissão de passagens em caráter de urgência",
        "Ano",
        "Mes",
    ]:
        df[col] = pd.to_numeric(df[col], errors="coerce")
    return df


def carregar_dados():
    df = pd.read_csv(URL)
    df.columns = [c.strip() for c in df.columns]

    colunas_obrigatorias = [c for c in COLUNAS_PASSAGENS if c not in ["Ano", "Mes"]]
    faltantes = [c for c in colunas_obrigatorias if c not in df.columns]
    if faltantes:
        raise ValueError("Colunas ausentes na planilha de passagens: " + ", ".join(faltantes))

    df["Data Início da Viagem"] = pd.to_datetime(
        df["Data Início da Viagem"], format="%d/%m/%Y", errors="coerce"
    )

    col_moeda = [
        "Valor das Diárias",
        "Valor da Viagem",
        "Valor da Passagem",
        "Valor Seguro Viagem",
        "Valor Restituição",
        "Custo com emissão de passagens dentro do prazo",
        "Custo com emissão de passagens em caráter de urgência",
    ]

    for col in col_moeda:
        df[col] = df[col].apply(parse_brl_value)

    df["Ano"] = df["Data Início da Viagem"].dt.year
    df["Mes"] = df["Data Início da Viagem"].dt.month

    return df


_ULTIMO_ERRO_CARGA = None


def carregar_dados_seguro(df_atual=None):
    global _ULTIMO_ERRO_CARGA
    try:
        df = carregar_dados()
        _ULTIMO_ERRO_CARGA = None
        return df
    except Exception as exc:
        _ULTIMO_ERRO_CARGA = str(exc)
        if df_atual is not None and not df_atual.empty:
            return df_atual
        return _df_vazio_passagens()


# Base inicial: não deixa falha externa de rede/planilha derrubar o app.
df_base = carregar_dados_seguro()
try:
    ANO_PADRAO = int(sorted(df_base["Ano"].dropna().unique())[-1])
except Exception:
    ANO_PADRAO = get_default_year()

# evita recarregar a planilha mais de uma vez no mesmo tick do Interval global
_LAST_INTERVAL_N = None

def _maybe_reload_df(n_intervals):
    global df_base, _LAST_INTERVAL_N
    if n_intervals is None:
        return
    if _LAST_INTERVAL_N == n_intervals:
        return
    _LAST_INTERVAL_N = n_intervals

    # recarrega apenas em horário comercial (Brasília)
    hora = now_sp().hour
    if 8 <= hora < 18:
        df_base = carregar_dados_seguro(df_base)

nomes_meses = [
    "janeiro",
    "fevereiro",
    "março",
    "abril",
    "maio",
    "junho",
    "julho",
    "agosto",
    "setembro",
    "outubro",
    "novembro",
    "dezembro",
]

dropdown_style = {
    "color": "black",
    "width": "100%",
    "marginBottom": "6px",
    "whiteSpace": "normal",
    "position": "relative",
    "zIndex": 1000,
}

# ----------------------------------------
# Layout (conteúdo da página)
# ----------------------------------------
layout = html.Div(
    style={"padding": "10px 22px"},
    children=[
        dcc.Location(id="url-passagens"),
        # ===== Barra de filtros FIXA no topo =====
        html.Div(
            id="barra-filtros-passagens",
            className="filtros-sticky",
            children=[
                html.H3("Filtros", className="sidebar-title"),
                html.Div(
                    style={
                        "display": "flex",
                        "flexWrap": "wrap",
                        "gap": "10px",
                        "alignItems": "flex-start",
                    },
                    children=[
                        # Ano
                        html.Div(
                            style={"minWidth": "140px", "flex": "0 0 160px"},
                            children=[
                                html.Label("Ano"),
                                dcc.Dropdown(
                                    id="filtro_ano_passagens",
                                    options=[
                                        {"label": int(a), "value": int(a)}
                                        for a in sorted(df_base["Ano"].dropna().unique())
                                    ],
                                    value=ANO_PADRAO,
                                    clearable=False,
                                    style=dropdown_style,
                                    optionHeight=40,
                                ),
                            ],
                        ),

                        # Mês
                        html.Div(
                            style={"minWidth": "140px", "flex": "0 0 160px"},
                            children=[
                                html.Label("Mês"),
                                dcc.Dropdown(
                                    id="filtro_mes_passagens",
                                    options=[
                                        {"label": m.capitalize(), "value": i}
                                        for i, m in enumerate(nomes_meses, start=1)
                                    ],
                                    value=None,
                                    placeholder="Todos",
                                    clearable=True,
                                    style={**dropdown_style, "maxHeight": 260},
                                    optionHeight=35,
                                    maxHeight=260,
                                ),
                            ],
                        ),

                        # Unidade
                        html.Div(
                            style={"minWidth": "260px", "flex": "1 1 320px", "maxWidth": "520px"},
                            children=[
                                html.Label("Unidade"),
                                dcc.Dropdown(
                                    id="filtro_unidade_passagens",
                                    options=[
                                        {"label": u, "value": u}
                                        for u in sorted(df_base["Unidade (Viagem)"].dropna().unique())
                                    ],
                                    value=None,
                                    placeholder="Todas",
                                    clearable=True,
                                    style=dropdown_style,
                                    optionHeight=35,
                                ),
                            ],
                        ),
                    ],
                ),

                html.Div(
                    style={"marginTop": "10px", "display": "flex", "alignItems": "center", "gap": "10px", "flexWrap": "wrap"},
                    children=[
                        html.Button(
                            "Limpar filtros",
                            id="btn_limpar_filtros_passagens",
                            n_clicks=0,
                            style=BUTTON_CLEAR_STYLE,
                        ),
                        html.Button(
                            "Atualizar Dados",
                            id="btn_reload_passagens",
                            n_clicks=0,
                            style=BUTTON_REFRESH_STYLE,
                        ),
                        html.Button(
                            "Baixar Relatório PDF",
                            id="btn_download_relatorio_passagens",
                            n_clicks=0,
                            style={**BUTTON_PDF_STYLE, "marginLeft": "10px"},
                        ),
                        html.Div(
                            id="info-atualizacao-passagens",
                            style={"fontSize": "14px", "lineHeight": "1.35"},
                            children=html.Div(
                                [html.B("Dados disponiveis. "), html.Span(f"Ultima visualizacao em {format_datetime_sp(now_sp())}.")]
                            ),
                        ),
                        dcc.Download(id="download_relatorio_passagens"),
                    ],
                ),
            ],
        ),

        html.Div(
            id="cards_container_passagens",
            style={
                "display": "grid",
                "gridTemplateColumns": "repeat(auto-fit, minmax(165px, 1fr))",
                "gap": "8px",
                "margin": "8px 0 10px 0",
            },
        ),

        # ===== Gráficos =====
        html.Div(
            style={"display": "grid", "gridTemplateColumns": "repeat(auto-fit, minmax(360px, 1fr))", "gap": "12px", "marginBottom": "12px"},
            children=[
                dcc.Graph(id="grafico_pizza_passagens"),
                dcc.Graph(id="grafico_barras_passagens"),
            ],
        ),

        html.H4("Resumo por Unidade", style={"marginTop": "8px", "display": "none"}),
        html.Div(
            style={"display": "none"},
            children=dash_table.DataTable(
            id="tabela_unidades_passagens",
            columns=[
                {"name": "Unidade (Viagem)", "id": "Unidade (Viagem)"},
                {"name": "Valor Total", "id": "Valor Total"},
                {"name": "Dentro do Prazo", "id": "Dentro do Prazo"},
                {"name": "Urgência", "id": "Urgência"},
                {"name": "Valor Total", "id": "Valor Total"},
                {"name": "Dentro do Prazo", "id": "Dentro do Prazo"},
                {"name": "Urgência", "id": "Urgência"},
                {"name": "Valor Total", "id": "Valor Total"},
                {"name": "Dentro do Prazo", "id": "Dentro do Prazo"},
                {"name": "Urgência", "id": "Urgência"},
            ],
            data=[],
            style_as_list_view=True,
            style_table={"minWidth": "100%", "overflowX": "auto", "maxHeight": "260px", "overflowY": "auto"},
            style_cell={"textAlign": "left", "padding": "8px", "fontSize": "12px", "whiteSpace": "normal", "height": "auto", "border": "1px solid #A2AAAD"},
            style_header={
                "fontWeight": "bold",
                "backgroundColor": "#003A70",
                "color": "white",
                "textAlign": "left",
                "zIndex": 0,
            },
            style_data_conditional=[
                {"if": {"row_index": "odd"}, "backgroundColor": "#FFF3E6"},
                {"if": {"column_id": "Valor Total"}, "textAlign": "right"},
                {"if": {"column_id": "Dentro do Prazo"}, "textAlign": "right"},
                {"if": {"column_id": "UrgÃªncia"}, "textAlign": "right"},
            ],
        )),

        html.H4("Detalhamento por Unidade e PCDP", style={"marginTop": "8px"}),
        html.Div(
            style={"width": "100%", "overflowX": "auto", "border": "1px solid #A2AAAD", "borderRadius": "10px", "paddingBottom": "8px"},
            children=dash_table.DataTable(
            id="tabela_detalhe_passagens",
            columns=[
                {"name": "Unidade (Viagem)", "id": "Unidade (Viagem)"},
                {"name": "Valor Total", "id": "Valor Total"},
                {"name": "Dentro do Prazo", "id": "Dentro do Prazo"},
                {"name": "Urgência", "id": "Urgência"},
                {"name": "Número da PCDP", "id": "Número da PCDP"},
                {"name": "Data Início da Viagem", "id": "Data Início da Viagem"},
            ],
            data=[],
            page_size=12,
            style_as_list_view=True,
            style_table={"minWidth": "100%", "overflowX": "auto", "maxHeight": "420px", "overflowY": "auto"},
            style_cell={"textAlign": "left", "padding": "8px", "fontSize": "12px", "whiteSpace": "normal", "height": "auto", "border": "1px solid #A2AAAD"},
            style_header={
                "fontWeight": "bold",
                "backgroundColor": "#003A70",
                "color": "white",
                "textAlign": "left",
                "position": "sticky",
                "top": 0,
                "zIndex": 10,
            },
            style_data_conditional=[
                {"if": {"row_index": "odd"}, "backgroundColor": "#FFF3E6"},
                {"if": {"column_id": "Custo com emissÃ£o de passagens dentro do prazo"}, "textAlign": "right"},
                {"if": {"column_id": "Custo com emissÃ£o de passagens em carÃ¡ter de urgÃªncia"}, "textAlign": "right"},
            ],
        )),

        dcc.Store(id="store_graficos_passagens"),
        dcc.Store(id="store_tabela_passagens_legacy"),
    ]
)

# ----------------------------------------
# CALLBACK 1 — Atualizar opções do filtro de Unidade (CASCATA)
# ----------------------------------------
@dash.callback(
    Output("filtro_unidade_passagens", "options"),
    Input("filtro_ano_passagens", "value"),
    Input("filtro_mes_passagens", "value"),
    Input("url-passagens", "pathname"),
    Input("btn_reload_passagens", "n_clicks"),
)
def atualizar_opcoes_unidade(ano, mes, pathname, n_reload):
    global df_base

    if pathname != "/passagens-dcf":
        raise PreventUpdate

    if getattr(dash.ctx, "triggered_id", None) in ("btn_reload_passagens", "url-passagens"):
        df_base = carregar_dados_seguro(df_base)

    dff = df_base.copy()

    if ano:
        dff = dff[dff["Ano"] == ano]
    if mes:
        dff = dff[dff["Mes"] == mes]

    unidades = sorted(dff["Unidade (Viagem)"].dropna().unique())
    opcoes = [{"label": u, "value": u} for u in unidades]
    return opcoes

# ----------------------------------------
# CALLBACK 2 — Atualização geral (cards + gráficos + resumo)
# ----------------------------------------
@dash.callback(
    Output("cards_container_passagens", "children"),
    Output("grafico_pizza_passagens", "figure"),
    Output("grafico_barras_passagens", "figure"),
    Output("tabela_detalhe_passagens", "data"),
    Output("store_graficos_passagens", "data"),
    Input("filtro_ano_passagens", "value"),
    Input("filtro_mes_passagens", "value"),
    Input("filtro_unidade_passagens", "value"),
    Input("url-passagens", "pathname"),
    Input("btn_reload_passagens", "n_clicks"),
    Input("interval-atualizacao", "n_intervals"),
)
def atualizar_pagina(ano, mes, unidade, pathname, n_reload, n_intervals):
    global df_base

    if pathname != "/passagens-dcf":
        raise PreventUpdate

    if getattr(dash.ctx, "triggered_id", None) in ("btn_reload_passagens", "url-passagens"):
        df_base = carregar_dados_seguro(df_base)
    else:
        _maybe_reload_df(n_intervals)

    dff = df_base.copy()

    if ano:
        dff = dff[dff["Ano"] == ano]
    if mes:
        dff = dff[dff["Mes"] == mes]
    if unidade:
        dff = dff[dff["Unidade (Viagem)"] == unidade]

    total_viagem = dff["Valor da Viagem"].sum()
    total_prazo = dff["Custo com emissão de passagens dentro do prazo"].sum()
    total_urgencia = dff["Custo com emissão de passagens em caráter de urgência"].sum()
    total_diarias = dff["Valor das Diárias"].sum()
    total_seguro = dff["Valor Seguro Viagem"].sum()
    total_restit = dff["Valor Restituição"].sum()
    total_passagem = dff["Valor da Passagem"].sum()

    def f(v):
        return (
            f"R$ {v:,.2f}"
            .replace(",", "X")
            .replace(".", ",")
            .replace("X", ".")
        )

    card_style = {
        "background": "#ffffff",
        "border": "1px solid #A2AAAD",
        "borderRadius": "14px",
        "padding": "6px 8px",
        "textAlign": "center",
        "boxShadow": "0 1px 3px rgba(0,0,0,0.06)",
        "minHeight": "46px",
        "display": "flex",
        "flexDirection": "column",
        "justifyContent": "center",
    }

    def card(titulo, valor, cor=None):
        cor_card = cor or "#003A70"
        estilo_valor = {
            "margin": "0",
            "fontSize": "16px",
            "fontWeight": "900",
            "letterSpacing": "0.2px",
            "lineHeight": "1.05",
            "color": cor_card,
        }
        return html.Div(
            style={**card_style, "borderTop": f"4px solid {cor_card}"},
            children=[
                html.P(
                    titulo,
                    style={
                        "margin": "0 0 2px",
                        "fontSize": "10px",
                        "fontWeight": "800",
                        "color": cor_card,
                        "textTransform": "uppercase",
                        "lineHeight": "1.05",
                    },
                ),
                html.P(valor, style=estilo_valor),
            ],
        )

    cards = [
        card("Valor Total da Viagem", f(total_viagem), "#F2994A"),
        card("Passagens (Dentro do Prazo)", f(total_prazo), "#003A70"),
        card("Passagens (Urgência)", f(total_urgencia), "#DA291C"),
        card("Valor das Diárias", f(total_diarias), "#003A70"),
        card("Valor Seguro Viagem", f(total_seguro), "#A2AAAD"),
        card("Valor Restituição", f(total_restit), "#2A9D8F"),
        card("Valor da Passagem", f(total_passagem), "#7A3E9D"),
    ]

    # Gráfico pizza: prazo x urgência
    df_pizza = pd.DataFrame(
        {
            "Tipo": ["Dentro do Prazo", "Urgência"],
            "Valor": [total_prazo, total_urgencia],
        }
    )
    fig_pizza = px.pie(
        df_pizza,
        names="Tipo",
        values="Valor",
        title="Emissão de Passagens: Prazo x Urgência",
        hole=0.35,
        color="Tipo",
        color_discrete_map={"Dentro do Prazo": "#003A70", "Urgência": "#DA291C"},
    )
    fig_pizza.update_traces(
        textposition="outside",
        textinfo="label+percent",
        hovertemplate="%{label}<br>R$ %{value:,.2f}<extra></extra>",
    )
    fig_pizza.update_layout(
        legend_title="",
        legend_orientation="v",
        legend_x=1.02,
        legend_y=0.95,
    )

    # Gráfico barras: valores principais
    df_barras = pd.DataFrame(
        {
            "Categoria": ["Viagem", "Diárias", "Passagem", "Seguro", "Restituição"],
            "Valor": [total_viagem, total_diarias, total_passagem, total_seguro, total_restit],
        }
    )
    fig_barras = px.bar(
        df_barras,
        x="Categoria",
        y="Valor",
        title="Totais por Categoria",
        text="Valor",
    )
    fig_barras.update_traces(
        marker_color=["#F2994A", "#003A70", "#7A3E9D", "#A2AAAD", "#2A9D8F"],
        texttemplate="R$ %{y:,.2f}",
        textposition="outside",
        cliponaxis=False,
        hovertemplate="%{x}<br>Valor=R$ %{y:,.2f}<extra></extra>",
    )
    fig_barras.update_layout(
        yaxis_title="Valor (R$)",
        yaxis_tickprefix="R$ ",
        yaxis_tickformat=",.2f",
        hovermode="x unified",
    )

    # Resumo por unidade
    if dff.empty:
        resumo = pd.DataFrame(columns=["Unidade (Viagem)", "Valor Total", "Dentro do Prazo", "Urgência"])
    else:
        resumo = (
            dff.groupby("Unidade (Viagem)", as_index=False)
            .agg(
                {
                    "Valor da Viagem": "sum",
                    "Custo com emissão de passagens dentro do prazo": "sum",
                    "Custo com emissão de passagens em caráter de urgência": "sum",
                }
            )
            .rename(
                columns={
                    "Valor da Viagem": "Valor Total",
                    "Custo com emissão de passagens dentro do prazo": "Dentro do Prazo",
                    "Custo com emissão de passagens em caráter de urgência": "Urgência",
                }
            )
        )

    detalhe = dff[
        [
            "Unidade (Viagem)",
            "Número da PCDP",
            "Data Início da Viagem",
            "Custo com emissão de passagens dentro do prazo",
            "Custo com emissão de passagens em caráter de urgência",
        ]
    ].copy()

    if not detalhe.empty:
        detalhe["Data Início da Viagem"] = detalhe["Data Início da Viagem"].dt.strftime("%d/%m/%Y")
        detalhe = detalhe.merge(resumo, on="Unidade (Viagem)", how="left")
        detalhe["Valor Total"] = detalhe["Valor Total"].apply(f)
        detalhe["Dentro do Prazo"] = detalhe["Dentro do Prazo"].apply(f)
        detalhe["Urgência"] = detalhe["Urgência"].apply(f)
        detalhe = detalhe[
            [
                "Unidade (Viagem)",
                "Valor Total",
                "Dentro do Prazo",
                "Urgência",
                "Número da PCDP",
                "Data Início da Viagem",
            ]
        ]
    else:
        detalhe = pd.DataFrame(
            columns=[
                "Unidade (Viagem)",
                "Valor Total",
                "Dentro do Prazo",
                "Urgência",
                "Número da PCDP",
                "Data Início da Viagem",
            ]
        )

    dados_pdf = {
        "filtros": {"ano": ano, "mes": mes, "unidade": unidade},
        "totais": {
            "total_viagem": total_viagem,
            "total_prazo": total_prazo,
            "total_urgencia": total_urgencia,
            "total_diarias": total_diarias,
            "total_seguro": total_seguro,
            "total_restit": total_restit,
        },
    }

    return cards, fig_pizza, fig_barras, detalhe.to_dict("records"), dados_pdf

# ----------------------------------------
# CALLBACK 3 — Tabela de Detalhamento
# ----------------------------------------
@dash.callback(
    Output("store_tabela_passagens_legacy", "data"),
    Input("filtro_ano_passagens", "value"),
    Input("filtro_mes_passagens", "value"),
    Input("filtro_unidade_passagens", "value"),
    Input("url-passagens", "pathname"),
    Input("btn_reload_passagens", "n_clicks"),
    Input("interval-atualizacao", "n_intervals"),
)
def atualizar_detalhe(ano, mes, unidade, pathname, n_reload, n_intervals):
    global df_base

    if pathname != "/passagens-dcf":
        raise PreventUpdate

    if getattr(dash.ctx, "triggered_id", None) in ("btn_reload_passagens", "url-passagens"):
        df_base = carregar_dados_seguro(df_base)
    else:
        _maybe_reload_df(n_intervals)

    dff = df_base.copy()

    if ano:
        dff = dff[dff["Ano"] == ano]
    if mes:
        dff = dff[dff["Mes"] == mes]
    if unidade:
        dff = dff[dff["Unidade (Viagem)"] == unidade]

    dff = dff[
        [
            "Unidade (Viagem)",
            "Número da PCDP",
            "Data Início da Viagem",
            "Custo com emissão de passagens dentro do prazo",
            "Custo com emissão de passagens em caráter de urgência",
        ]
    ].copy()

    dff["Data Início da Viagem"] = dff["Data Início da Viagem"].dt.strftime("%d/%m/%Y")

    def f(v):
        return (
            f"R$ {v:,.2f}"
            .replace(",", "X")
            .replace(".", ",")
            .replace("X", ".")
        )

    dff["Custo com emissão de passagens dentro do prazo"] = dff[
        "Custo com emissão de passagens dentro do prazo"
    ].apply(f)

    dff["Custo com emissão de passagens em caráter de urgência"] = dff[
        "Custo com emissão de passagens em caráter de urgência"
    ].apply(f)

    return dff.to_dict("records")

# ----------------------------------------
# CALLBACK 4 — Limpar filtros
# ----------------------------------------
@dash.callback(
    Output("filtro_ano_passagens", "value"),
    Output("filtro_mes_passagens", "value"),
    Output("filtro_unidade_passagens", "value"),
    Input("btn_limpar_filtros_passagens", "n_clicks"),
    prevent_initial_call=True,
)
def limpar(n):
    return ANO_PADRAO, None, None

# ==================================================
# PADRÃO DE PDF (reutilizando estilo de processos)
# ==================================================

def formatar_moeda(v):
    if v is None or (isinstance(v, float) and pd.isna(v)):
        return ""
    try:
        return format_brl(v)
    except (TypeError, ValueError):
        return ""

# Estilos de texto para PDF – Passagens
wrap_style_pass = ParagraphStyle(
    name="wrap_passagens",
    fontSize=7,
    leading=9,
    spaceAfter=2,
    wordWrap="CJK",
)

simple_style_pass = ParagraphStyle(
    name="simple_passagens",
    fontSize=7,
    alignment=TA_CENTER,
)

header_cell_style_pass = ParagraphStyle(
    name="header_cell_passagens",
    fontSize=7,
    alignment=TA_CENTER,
    fontName="Helvetica-Bold",
    textColor=colors.white,
)

def wrap_pdf_pass(text):
    return Paragraph(str(text), wrap_style_pass)

def simple_pdf_pass(text):
    return Paragraph(str(text), simple_style_pass)

def header_pdf_pass(text):
    return Paragraph(str(text), header_cell_style_pass)

def adicionar_cabecalho_passagens(story, styles, total_registros):
    data_hora_brasilia = format_datetime_sp(now_sp())

    pagesize = A4
    data_top_table = Table(
        [[
            Paragraph(
                data_hora_brasilia,
                ParagraphStyle(
                    "data_topo_pass",
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
        ParagraphStyle("instituicao_pass", alignment=TA_CENTER, leading=16),
    )

    cabecalho = Table(
        [[logo_esq, instituicao, logo_dir]],
        colWidths=[1.1 * inch, 4.9 * inch, 1.1 * inch],
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

    titulo = Paragraph(
        "RELATÓRIO DE GASTOS COM PASSAGENS (DCF)",
        ParagraphStyle(
            "titulo_pass",
            alignment=TA_CENTER,
            fontSize=10,
            leading=14,
            textColor=colors.black,
            fontName="Helvetica-Bold",
        ),
    )
    story.append(titulo)
    story.append(Spacer(1, 0.08 * inch))

    story.append(
        Paragraph(
            f"Total de registros (detalhamento): <b>{total_registros}</b>",
            styles["Normal"],
        )
    )
    story.append(Spacer(1, 0.12 * inch))

def _fig_to_image(fig, width=5.2 * inch, height=3.0 * inch):
    import plotly.io as pio
    img_bytes = pio.to_image(fig, format="png", scale=2)
    return Image(BytesIO(img_bytes), width=width, height=height)

def criar_tabelas_passagens_pdf(story, resumo, detalhe):
    # --------- resumo
    if resumo:
        df_resumo = pd.DataFrame(resumo)
        cols = df_resumo.columns.tolist()
        header = [header_pdf_pass(c) for c in cols]
        table_data = [header]
        for _, row in df_resumo.iterrows():
            linha = [simple_pdf_pass("" if pd.isna(row[c]) else str(row[c])) for c in cols]
            table_data.append(linha)

        colw = [2.6 * inch, 1.3 * inch, 1.3 * inch, 1.3 * inch]
        colw = colw[: len(cols)]
        tbl = Table(table_data, colWidths=colw, repeatRows=1)
        tbl.setStyle(
            TableStyle(
                [
                    ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#0b2b57")),
                    ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                    ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
                    ("VALIGN", (0, 0), (-1, -1), "TOP"),
                    ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f0f0f0")]),
                    ("LEFTPADDING", (0, 0), (-1, -1), 2),
                    ("RIGHTPADDING", (0, 0), (-1, -1), 2),
                    ("TOPPADDING", (0, 0), (-1, -1), 2),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 2),
                ]
            )
        )
        story.append(Paragraph("<b>Resumo por Unidade</b>", getSampleStyleSheet()["Normal"]))
        story.append(Spacer(1, 0.08 * inch))
        story.append(tbl)
        story.append(Spacer(1, 0.18 * inch))

    # --------- detalhe
    if detalhe:
        df_det = pd.DataFrame(detalhe)
        cols2 = df_det.columns.tolist()

        header2 = [header_pdf_pass(c) for c in cols2]
        table_data2 = [header2]
        for _, row in df_det.iterrows():
            linha = []
            for c in cols2:
                val = "" if pd.isna(row[c]) else str(row[c]).strip()
                # quebra melhor para unidade/PCDP
                if c in ["Unidade (Viagem)", "Número da PCDP"]:
                    linha.append(wrap_pdf_pass(val))
                else:
                    linha.append(simple_pdf_pass(val))
            table_data2.append(linha)

        width_map = {
            "Unidade (Viagem)": 2.15 * inch,
            "Valor Total": 1.0 * inch,
            "Dentro do Prazo": 1.0 * inch,
            "UrgÃªncia": 1.0 * inch,
            "NÃºmero da PCDP": 1.2 * inch,
            "Data InÃ­cio da Viagem": 1.1 * inch,
        }
        colw2 = [width_map.get(col, 1.0 * inch) for col in cols2]
        tbl2 = Table(table_data2, colWidths=colw2, repeatRows=1)
        tbl2.setStyle(
            TableStyle(
                [
                    ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#0b2b57")),
                    ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                    ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
                    ("VALIGN", (0, 0), (-1, -1), "TOP"),
                    ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f0f0f0")]),
                    ("LEFTPADDING", (0, 0), (-1, -1), 2),
                    ("RIGHTPADDING", (0, 0), (-1, -1), 2),
                    ("TOPPADDING", (0, 0), (-1, -1), 2),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 2),
                ]
            )
        )
        story.append(Paragraph("<b>Detalhamento (PCDP)</b>", getSampleStyleSheet()["Normal"]))
        story.append(Spacer(1, 0.08 * inch))
        story.append(tbl2)

# ----------------------------------------
# CALLBACK 5 — Geração do PDF
# ----------------------------------------
@dash.callback(
    Output("download_relatorio_passagens", "data"),
    Input("btn_download_relatorio_passagens", "n_clicks"),
    State("grafico_pizza_passagens", "figure"),
    State("grafico_barras_passagens", "figure"),
    State("tabela_unidades_passagens", "data"),
    State("tabela_detalhe_passagens", "data"),
    State("store_graficos_passagens", "data"),
    prevent_initial_call=True,
)
def gerar_pdf(n, fig_pizza, fig_barras, resumo, detalhe, dados_pdf):
    if not n or not dados_pdf:
        return None

    buffer = BytesIO()
    pagesize = A4
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

    total_registros = len(detalhe) if detalhe else 0
    adicionar_cabecalho_passagens(story, styles, total_registros)

    filtros = dados_pdf["filtros"]
    mes_nome = (
        nomes_meses[filtros["mes"] - 1].capitalize()
        if filtros["mes"]
        else "Todos"
    )
    filtro_texto = (
        f"Ano: {filtros['ano']} | "
        f"Mês: {mes_nome} | "
        f"Unidade: {filtros['unidade'] if filtros['unidade'] else 'Todas'}"
    )
    story.append(
        Paragraph(
            filtro_texto,
            ParagraphStyle("filtros_pass", fontSize=9, leading=12, alignment=TA_LEFT),
        )
    )
    story.append(Spacer(1, 0.12 * inch))

    # Gráficos no PDF
    try:
        fig_pizza_obj = px.Figure(fig_pizza)
        fig_barras_obj = px.Figure(fig_barras)
        story.append(_fig_to_image(fig_pizza_obj, width=5.0 * inch, height=2.8 * inch))
        story.append(Spacer(1, 0.12 * inch))
        story.append(_fig_to_image(fig_barras_obj, width=5.3 * inch, height=2.9 * inch))
        story.append(Spacer(1, 0.18 * inch))
    except Exception:
        # se faltar kaleido, não interrompe geração
        pass

    criar_tabelas_passagens_pdf(story, resumo, detalhe)

    doc.build(story)
    buffer.seek(0)
    return dcc.send_bytes(
        buffer.getvalue(),
        f"passagens_dcf_{now_sp().strftime('%Y%m%d%H%M%S')}.pdf",
    )
