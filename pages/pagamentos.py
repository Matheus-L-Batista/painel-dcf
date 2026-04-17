import dash
from dash import html, dcc, Input, Output, State, dash_table
from dash.exceptions import PreventUpdate
import pandas as pd
from datetime import datetime
from io import BytesIO
import plotly.express as px

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
    path="/pagamentos",
    name="Pagamentos Efetivados",
    title="Pagamentos Efetivados",
)


URL = (
    "https://docs.google.com/spreadsheets/d/"
    "1KEEohPamH36URHpPjFjpVmSNOoK3429erayoPv6fcDo/"
    "gviz/tq?tqx=out:csv&sheet=Pagamentos%20Efetivados"
)


# ----------------------------------------
# 2. CARGA E TRATAMENTO DOS DADOS
# ----------------------------------------
def carregar_dados():
    df = pd.read_csv(URL)
    df.columns = [c.strip() for c in df.columns]
    df = df.rename(
        columns={
            "Unnamed: 2": "DT ATESTE",
            "Unnamed: 3": "DT PGTO",
        }
    )

    df["DT ATESTE"] = pd.to_datetime(
        df["DT ATESTE"], format="%d/%m/%Y", errors="coerce"
    )
    df["DT PGTO"] = pd.to_datetime(
        df["DT PGTO"], format="%d/%m/%Y", errors="coerce"
    )

    df["Valor"] = df["Valor"].apply(parse_brl_value)

    mapa_meses = {
        "JANEIRO": 1,
        "FEVEREIRO": 2,
        "MARÇO": 3,
        "MARCO": 3,
        "ABRIL": 4,
        "MAIO": 5,
        "JUNHO": 6,
        "JULHO": 7,
        "AGOSTO": 8,
        "SETEMBRO": 9,
        "OUTUBRO": 10,
        "NOVEMBRO": 11,
        "DEZEMBRO": 12,
    }

    df["Ano"] = df["ANO"].astype(int)
    df["Mes"] = df["MÊS"].astype(str).str.upper().map(mapa_meses)
    return df


# DF base inicial
df_base = carregar_dados()
try:
    ANO_PADRAO = int(sorted(df_base["Ano"].dropna().unique())[-1])
except Exception:
    ANO_PADRAO = get_default_year()


# ----------------------------------------
# 3. LISTA DE MESES (para o dropdown)
# ----------------------------------------
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
}


# ----------------------------------------
# 4. LAYOUT DA PÁGINA
# ----------------------------------------
layout = html.Div(
    style={"padding": "10px 22px"},
    children=[
        # ===== Barra de filtros FIXA no topo =====
        html.Div(
            id="barra-filtros-pagamentos",
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
                                    id="filtro_ano_pagamentos",
                                    options=[
                                        {
                                            "label": int(a),
                                            "value": int(a),
                                        }
                                        for a in sorted(
                                            df_base["Ano"]
                                            .dropna()
                                            .unique()
                                        )
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
                                    id="filtro_mes_pagamentos",
                                    options=[
                                        {
                                            "label": m.capitalize(),
                                            "value": i,
                                        }
                                        for i, m in enumerate(
                                            nomes_meses, start=1
                                        )
                                    ],
                                    value=None,
                                    placeholder="Todos",
                                    clearable=True,
                                    style={
                                        **dropdown_style,
                                        "maxHeight": 260,
                                    },
                                    optionHeight=35,
                                    maxHeight=260,
                                ),
                            ],
                        ),
                        # Lista
                        html.Div(
                            style={
                                "minWidth": "240px",
                                "flex": "1 1 280px",
                                "maxWidth": "480px",
                            },
                            children=[
                                html.Label("Lista"),
                                dcc.Dropdown(
                                    id="filtro_lista_pagamentos",
                                    options=[
                                        {"label": u, "value": u}
                                        for u in sorted(
                                            df_base["LISTAS"]
                                            .dropna()
                                            .unique()
                                        )
                                    ],
                                    value=None,
                                    placeholder="Todas",
                                    clearable=True,
                                    style=dropdown_style,
                                    optionHeight=35,
                                ),
                            ],
                        ),
                        # Fonte
                        html.Div(
                            style={
                                "minWidth": "220px",
                                "flex": "1 1 260px",
                                "maxWidth": "420px",
                            },
                            children=[
                                html.Label("Fonte"),
                                dcc.Dropdown(
                                    id="filtro_fonte_pagamentos",
                                    options=[
                                        {"label": u, "value": u}
                                        for u in sorted(
                                            df_base["FONTE"]
                                            .dropna()
                                            .unique()
                                        )
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
                    style={"display": "flex", "gap": "8px", "flexWrap": "wrap", "justifyContent": "flex-end"},
                    children=[
                        html.Button(
                            "Limpar filtros",
                            id="btn_limpar_filtros_pagamentos",
                            n_clicks=0,
                            style=BUTTON_CLEAR_STYLE,
                        ),
                        html.Button(
                            "Atualizar Dados",
                            id="btn_reload_pagamentos",
                            n_clicks=0,
                            style=BUTTON_REFRESH_STYLE,
                        ),
                        html.Button(
                            "Baixar Relatório PDF",
                            id="btn_download_relatorio_pagamentos",
                            n_clicks=0,
                            style={**BUTTON_PDF_STYLE, "marginLeft": "10px"},
                        ),
                        dcc.Download(id="download_relatorio_pagamentos"),
                    ],
                ),
            ],
        ),

        # Linha de gráficos
        html.Div(
            id="info-atualizacao-pagamentos",
            style={"marginBottom": "10px"},
            children=html.Div(
                [html.B("Dados disponiveis. "), html.Span(f"Ultima visualizacao em {format_datetime_sp(now_sp())}.")]
            ),
        ),

        html.Div(
            style={"display": "grid", "gridTemplateColumns": "repeat(auto-fit, minmax(360px, 1fr))", "gap": "12px", "marginBottom": "12px"},
            children=[
                dcc.Graph(id="grafico_lista_pagamentos"),
                dcc.Graph(id="grafico_fonte_pagamentos"),
            ],
        ),

        html.H4("Detalhamento de Pagamentos", style={"marginTop": "8px"}),
        html.Div(
            style={"width": "100%", "overflowX": "auto", "border": "1px solid #A2AAAD", "borderRadius": "10px", "paddingBottom": "8px"},
            children=dash_table.DataTable(
            id="tabela_pagamentos",
            row_selectable=False,
            cell_selectable=False,
            active_cell=None,
            selected_cells=[],
            selected_rows=[],
            columns=[
                {"name": "DT ATESTE", "id": "DT ATESTE"},
                {"name": "DT PGTO", "id": "DT PGTO"},
                {"name": "Valor", "id": "Valor"},
                {"name": "FONTE", "id": "FONTE"},
                {"name": "LISTAS", "id": "LISTAS"},
                {"name": "RAZÃO SOCIAL", "id": "RAZÃO SOCIAL"},
            ],
            data=[],
            style_as_list_view=True,
            style_table={"minWidth": "100%", "overflowX": "auto", "maxHeight": "520px", "overflowY": "auto"},
            style_cell={"textAlign": "left", "padding": "8px", "fontSize": "12px", "whiteSpace": "normal", "height": "auto", "border": "1px solid #A2AAAD"},
            style_data_conditional=[
                {"if": {"row_index": "odd"}, "backgroundColor": "#FFF3E6"},
                {
                    "if": {"column_id": "Valor"},
                    "color": "#0b2b57",
                    "fontWeight": "bold",
                    "textAlign": "right",
                }
            ],
            style_header={
                "fontWeight": "bold",
                "backgroundColor": "#003A70",
                "color": "white",
                "textAlign": "left",
                "position": "sticky",
                "top": 0,
                "zIndex": 10,
            },
        )),
        dcc.Store(id="store_dados_pagamentos"),
    ],
)


# ----------------------------------------
# 5. CALLBACK — Atualização tabela + gráficos
# ----------------------------------------
@dash.callback(
    Output("tabela_pagamentos", "data"),
    Output("store_dados_pagamentos", "data"),
    Output("grafico_lista_pagamentos", "figure"),
    Output("grafico_fonte_pagamentos", "figure"),
    Input("filtro_ano_pagamentos", "value"),
    Input("filtro_mes_pagamentos", "value"),
    Input("filtro_lista_pagamentos", "value"),
    Input("filtro_fonte_pagamentos", "value"),
    Input("btn_reload_pagamentos", "n_clicks"),
)
def atualizar_tabela(ano, mes, lista, fonte, n_reload):
    global df_base

    if getattr(dash.ctx, "triggered_id", None) == "btn_reload_pagamentos":
        df_base = carregar_dados()

    dff = df_base.copy()

    if ano:
        dff = dff[dff["Ano"] == ano]
    if mes:
        dff = dff[dff["Mes"] == mes]
    if lista:
        dff = dff[dff["LISTAS"] == lista]
    if fonte:
        dff = dff[dff["FONTE"].astype(str) == str(fonte)]

    dff_display = dff.copy()
    dff_display["DT ATESTE"] = dff_display["DT ATESTE"].dt.strftime("%d/%m/%Y")
    dff_display["DT PGTO"] = dff_display["DT PGTO"].dt.strftime("%d/%m/%Y")

    dff_display["Valor"] = dff_display["Valor"].apply(format_brl)

    colunas_exibir = [
        "DT ATESTE",
        "DT PGTO",
        "Valor",
        "FONTE",
        "LISTAS",
        "RAZÃO SOCIAL",
    ]
    dff_display = dff_display[colunas_exibir]

    dados_pdf = {
        "tabela": dff_display.to_dict("records"),
        "filtros": {"ano": ano, "mes": mes, "lista": lista, "fonte": fonte},
        "total_geral": dff["Valor"].sum() if not dff.empty else 0.0,
    }

    # Gráfico por lista
    if not dff.empty:
        grp_lista = dff.groupby("LISTAS", as_index=False)["Valor"].sum()
    else:
        grp_lista = pd.DataFrame({"LISTAS": [], "Valor": []})

    fig_lista = px.line(
        grp_lista,
        x="LISTAS",
        y="Valor",
        markers=True,
        title="Total Pago por Lista",
    )
    fig_lista.update_traces(
        line_color="#003A70",
        hovertemplate="<b>%{x}</b><br>R$ %{y:,.2f}<extra></extra>",
    )
    fig_lista.update_layout(
        xaxis_title="Lista",
        yaxis_title="Valor (R$)",
        yaxis_tickprefix="R$ ",
        yaxis_tickformat=",.2f",
        hovermode="x unified",
    )

    # Gráfico por fonte
    if not dff.empty:
        grp_fonte = dff.groupby("FONTE", as_index=False)["Valor"].sum()
    else:
        grp_fonte = pd.DataFrame({"FONTE": [], "Valor": []})

    fig_fonte = px.line(
        grp_fonte,
        x="FONTE",
        y="Valor",
        markers=True,
        title="Total por Fonte de Recurso",
    )
    fig_fonte.update_traces(
        line_color="#DA291C",
        hovertemplate="<b>%{x}</b><br>R$ %{y:,.2f}<extra></extra>",
    )
    fig_fonte.update_layout(
        xaxis_title="Fonte",
        yaxis_title="Valor (R$)",
        yaxis_tickprefix="R$ ",
        yaxis_tickformat=",.2f",
        hovermode="x unified",
    )

    return dff_display.to_dict("records"), dados_pdf, fig_lista, fig_fonte


# ----------------------------------------
# 6. CALLBACK — Filtros em cascata
# ----------------------------------------
@dash.callback(
    Output("filtro_mes_pagamentos", "options"),
    Output("filtro_lista_pagamentos", "options"),
    Output("filtro_fonte_pagamentos", "options"),
    Input("filtro_ano_pagamentos", "value"),
    Input("filtro_mes_pagamentos", "value"),
    Input("filtro_lista_pagamentos", "value"),
    Input("filtro_fonte_pagamentos", "value"),
    Input("btn_reload_pagamentos", "n_clicks"),
)
def atualizar_opcoes_filtros_pagamentos(ano, mes, lista, fonte, n_reload):
    global df_base

    if getattr(dash.ctx, "triggered_id", None) == "btn_reload_pagamentos":
        df_base = carregar_dados()

    dff = df_base.copy()
    mask = pd.Series(True, index=dff.index)

    if ano:
        mask &= dff["Ano"] == ano
    if mes:
        mask &= dff["Mes"] == mes
    if lista:
        mask &= dff["LISTAS"] == lista
    if fonte:
        mask &= dff["FONTE"].astype(str) == str(fonte)

    dff = dff[mask]

    meses_disponiveis = sorted(dff["Mes"].dropna().unique().tolist())
    op_mes = [
        {"label": nomes_meses[m - 1].capitalize(), "value": m}
        for m in meses_disponiveis
        if 1 <= m <= 12
    ]

    op_lista = [
        {"label": u, "value": u}
        for u in sorted(dff["LISTAS"].dropna().unique())
        if str(u) != ""
    ]

    op_fonte = [
        {"label": u, "value": u}
        for u in sorted(dff["FONTE"].dropna().unique())
        if str(u) != ""
    ]

    return op_mes, op_lista, op_fonte


# ----------------------------------------
# 7. CALLBACK — Limpar filtros
# ----------------------------------------
@dash.callback(
    Output("filtro_ano_pagamentos", "value"),
    Output("filtro_mes_pagamentos", "value"),
    Output("filtro_lista_pagamentos", "value"),
    Output("filtro_fonte_pagamentos", "value"),
    Input("btn_limpar_filtros_pagamentos", "n_clicks"),
    prevent_initial_call=True,
)
def limpar(n):
    return ANO_PADRAO, None, None, None


# ----------------------------------------
# 8. Estilos PDF para Pagamentos
# ----------------------------------------
wrap_style_pag = ParagraphStyle(
    name="wrap_pag",
    fontSize=7,
    leading=9,
    spaceAfter=2,
    wordWrap="CJK",
)

simple_style_pag = ParagraphStyle(
    name="simple_pag",
    fontSize=7,
    alignment=TA_CENTER,
)

header_cell_style_pag = ParagraphStyle(
    name="header_cell_pag",
    fontSize=7,
    alignment=TA_CENTER,
    fontName="Helvetica-Bold",
    textColor=colors.white,
)


def wrap_pdf_pag(text):
    return Paragraph(str(text), wrap_style_pag)


def simple_pdf_pag(text):
    return Paragraph(str(text), simple_style_pag)


def header_pdf_pag(text):
    return Paragraph(str(text), header_cell_style_pag)


def criar_tabela_dados_pagamentos(story, dados_pdf, pagesize):
    registros = dados_pdf["tabela"]
    if not registros:
        return

    df_pdf = pd.DataFrame(registros)

    cols = [
        "DT ATESTE",
        "DT PGTO",
        "Valor",
        "FONTE",
        "LISTAS",
        "RAZÃO SOCIAL",
    ]
    cols = [c for c in cols if c in df_pdf.columns]

    header = [header_pdf_pag(c) for c in cols]
    table_data = [header]

    for _, row in df_pdf[cols].iterrows():
        linha = []
        for c in cols:
            val = "" if pd.isna(row[c]) else str(row[c]).strip()
            if c == "RAZÃO SOCIAL":
                linha.append(wrap_pdf_pag(val))
            else:
                linha.append(simple_pdf_pag(val))
        table_data.append(linha)

    col_widths = [
        0.9 * inch,  # DT ATESTE
        0.9 * inch,  # DT PGTO
        1.0 * inch,  # Valor
        1.2 * inch,  # FONTE
        1.2 * inch,  # LISTAS
        1.6 * inch,  # RAZÃO SOCIAL
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
        (
            "ROWBACKGROUNDS",
            (0, 1),
            (-1, -1),
            [colors.white, colors.HexColor("#f0f0f0")],
        ),
        ("WORDWRAP", (0, 0), (-1, -1), True),
    ]
    tbl.setStyle(TableStyle(style_list))
    story.append(tbl)


# ----------------------------------------
# 9. CALLBACK — Geração do PDF (cabeçalho padrão)
# ----------------------------------------
@dash.callback(
    Output("download_relatorio_pagamentos", "data"),
    Input("btn_download_relatorio_pagamentos", "n_clicks"),
    State("store_dados_pagamentos", "data"),
    prevent_initial_call=True,
)
def gerar_pdf_pagamentos(n, dados_pdf):
    if not n or not dados_pdf:
        raise PreventUpdate

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

    # Data/hora topo (Brasília)
    data_hora_brasilia = format_datetime_sp(now_sp())
    data_top_table = Table(
        [[
            Paragraph(
                data_hora_brasilia,
                ParagraphStyle(
                    "data_topo_pag",
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

    # Logos esquerda/direita + instituição ao centro (padrão passagens/compras)
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
            "instituicao_pag",
            alignment=TA_CENTER,
            leading=16,
        ),
    )

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

    # Título principal
    titulo = Paragraph(
        "RELATÓRIO DE PAGAMENTOS EFETIVADOS",
        ParagraphStyle(
            "titulo_pag",
            alignment=TA_CENTER,
            fontSize=10,
            leading=14,
            textColor=colors.black,
            fontName="Helvetica-Bold",
        ),
    )
    story.append(titulo)
    story.append(Spacer(1, 0.15 * inch))

    # Filtros e total geral
    filtros = dados_pdf["filtros"]
    total_geral = dados_pdf["total_geral"]

    story.append(
        Paragraph(
            f"Ano: {filtros['ano']} — "
            f"Mês: {filtros['mes'] if filtros['mes'] else 'Todos'} — "
            f"Lista: {filtros['lista'] if filtros['lista'] else 'Todas'} — "
            f"Fonte: {filtros['fonte'] if filtros['fonte'] else 'Todas'}",
            styles["Normal"],
        )
    )
    story.append(Spacer(1, 0.1 * inch))

    story.append(
        Paragraph(
            f"Total Geral: {format_brl(total_geral)}",
            styles["Normal"],
        )
    )
    story.append(Spacer(1, 0.15 * inch))

    # Tabela de dados com cabeçalho azul
    criar_tabela_dados_pagamentos(story, dados_pdf, pagesize)

    doc.build(story)
    buffer.seek(0)
    return dcc.send_bytes(
        buffer.getvalue(),
        f"pagamentos_efetivados_{now_sp().strftime('%Y%m%d%H%M%S')}.pdf",
    )
