# pages/execucao_orcamento_unifei.py

import os
import threading
from io import BytesIO
from datetime import datetime, timedelta

import dash
from dash import html, dcc, Input, Output, State, dash_table
import pandas as pd
import plotly.express as px
from utils.formatting import format_brl, format_brl_series, parse_brl_series
from utils.runtime import format_datetime_sp, get_default_year, now_sp
from utils.ui import BUTTON_CLEAR_STYLE, BUTTON_PDF_STYLE, BUTTON_REFRESH_STYLE


dash.register_page(
    __name__,
    path="/execucao-orcamento-unifei",
    name="Execução Orçamento UNIFEI",
    title="Execução do Orçamento - UNIFEI",
)

URL = (
    "https://docs.google.com/spreadsheets/d/"
    "1MkiWDH-MBnLeSUlqV91qjzCVRTlTAVh9xYooENJ151o/"
    "gviz/tq?tqx=out:csv&sheet=Execucao%20do%20Orcamento%20Unifei"
)

# Cores
AZUL = "#003A70"
VERMELHO = "#DA291C"
CINZA = "#A2AAAD"
VERDE_PETROLEO = "#2A9D8F"
LARANJA_RPNP = "#F2994A"

# Zebra linhas (branco/laranja suave)
ZEBRA_LARANJA_BG = "#FFF3E6"

MESES_ORDEM = [
    "Janeiro", "Fevereiro", "Março", "Abril", "Maio", "Junho",
    "Julho", "Agosto", "Setembro", "Outubro", "Novembro", "Dezembro"
]
MAP_MES_NUM = {m: i + 1 for i, m in enumerate(MESES_ORDEM)}

dropdown_style = {
    "color": "black",
    "width": "100%",
    "marginBottom": "6px",
    "whiteSpace": "normal",
}

# ✅ Cartões menores
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

ANO_PADRAO = get_default_year()

COLS_TABELA = [
    "UG Executora",
    "Mês",
    "Fonte Recursos Detalhada",
    "Grupo Despesa",
    "DESPESAS INSCRITAS EM RP NAO PROCESSADOS",
    "DESPESAS EMPENHADAS (CONTROLE EMPENHO)",
    "DESPESAS LIQUIDADAS (CONTROLE EMPENHO)",
    "DESPESAS LIQUIDADAS A PAGAR(CONTROLE EMPENHO)",
    "DESPESAS PAGAS (CONTROLE EMPENHO)",
]

COLS_VALORES = [
    "DESPESAS INSCRITAS EM RP NAO PROCESSADOS",
    "DESPESAS EMPENHADAS (CONTROLE EMPENHO)",
    "DESPESAS LIQUIDADAS (CONTROLE EMPENHO)",
    "DESPESAS LIQUIDADAS A PAGAR(CONTROLE EMPENHO)",
    "DESPESAS PAGAS (CONTROLE EMPENHO)",
]


def fmt_brl(x: float) -> str:
    return format_brl(x)


def fmt_brl_series(s: pd.Series) -> pd.Series:
    return format_brl_series(s)


def get_agora_brasilia() -> str:
    return format_datetime_sp(now_sp())


def _safe_unique_sorted(df: pd.DataFrame, col: str):
    if df is None or df.empty or col not in df.columns:
        return []
    if col == "Mês":
        vals = [v for v in df[col].dropna().unique().tolist() if v in MAP_MES_NUM]
        return sorted(vals, key=lambda m: MAP_MES_NUM[m])
    if col == "Ano":
        vals = df[col].dropna().unique().tolist()
        try:
            return sorted([int(v) for v in vals])
        except Exception:
            return sorted(vals)
    return sorted(df[col].dropna().unique().tolist())


def _moeda_para_float_series(s: pd.Series) -> pd.Series:
    return parse_brl_series(s)


def carregar_dados() -> pd.DataFrame:
    df = pd.read_csv(URL, low_memory=False)
    df.columns = [c.strip() for c in df.columns]

    if "Mês" in df.columns:
        df["Mês"] = df["Mês"].astype(str).str.strip()
        df["Mês"] = pd.Categorical(df["Mês"], categories=MESES_ORDEM, ordered=True)

    for c in COLS_VALORES:
        if c in df.columns:
            df[c + "_VAL"] = _moeda_para_float_series(df[c])
        else:
            df[c + "_VAL"] = 0.0

    if "Ano" in df.columns:
        df["Ano"] = pd.to_numeric(df["Ano"], errors="coerce").fillna(ANO_PADRAO).astype(int)

    return df


def filtrar_df(df: pd.DataFrame, ug, mes, ano, fonte, grupo, natureza) -> pd.DataFrame:
    if df is None or df.empty:
        return pd.DataFrame()

    dff = df
    if ano is not None and "Ano" in dff.columns:
        dff = dff[dff["Ano"] == int(ano)]
    if ug and "UG Executora" in dff.columns:
        dff = dff[dff["UG Executora"] == ug]
    if mes and "Mês" in dff.columns:
        dff = dff[dff["Mês"] == mes]
    if fonte and "Fonte Recursos Detalhada" in dff.columns:
        dff = dff[dff["Fonte Recursos Detalhada"] == fonte]
    if grupo and "Grupo Despesa" in dff.columns:
        dff = dff[dff["Grupo Despesa"] == grupo]
    if natureza and "NAT DESP" in dff.columns:
        dff = dff[dff["NAT DESP"] == natureza]
    return dff


def calcular_kpis(dff: pd.DataFrame) -> dict:
    if dff is None or dff.empty:
        return {"rpnpp": 0.0, "empenhadas": 0.0, "liquidadas": 0.0, "liq_a_pagar": 0.0, "pagas": 0.0}
    return {
        "rpnpp": float(dff.get("DESPESAS INSCRITAS EM RP NAO PROCESSADOS_VAL", 0).sum()),
        "empenhadas": float(dff.get("DESPESAS EMPENHADAS (CONTROLE EMPENHO)_VAL", 0).sum()),
        "liquidadas": float(dff.get("DESPESAS LIQUIDADAS (CONTROLE EMPENHO)_VAL", 0).sum()),
        "liq_a_pagar": float(dff.get("DESPESAS LIQUIDADAS A PAGAR(CONTROLE EMPENHO)_VAL", 0).sum()),
        "pagas": float(dff.get("DESPESAS PAGAS (CONTROLE EMPENHO)_VAL", 0).sum()),
    }


# Cache
_DF_CACHE = None
_DF_CACHE_AT = None
_CACHE_LOCK = threading.Lock()
CACHE_TTL_MINUTOS = 15


def get_df(force: bool = False) -> tuple[pd.DataFrame, str]:
    global _DF_CACHE, _DF_CACHE_AT

    now = datetime.now()
    stale = (_DF_CACHE is None) or (_DF_CACHE_AT is None) or (now - _DF_CACHE_AT > timedelta(minutes=CACHE_TTL_MINUTOS))

    if force or stale:
        with _CACHE_LOCK:
            now2 = datetime.now()
            stale2 = (_DF_CACHE is None) or (_DF_CACHE_AT is None) or (now2 - _DF_CACHE_AT > timedelta(minutes=CACHE_TTL_MINUTOS))
            if force or stale2:
                _DF_CACHE = carregar_dados()
                _DF_CACHE_AT = now2
                return _DF_CACHE, f"Dados recarregados em {get_agora_brasilia()}."
    return _DF_CACHE, f"Dados em cache (último carregamento: {_DF_CACHE_AT.strftime('%d/%m/%Y %H:%M:%S')})."


# PDF: mantém igual (não mexer no que já está bom)
def gerar_pdf_padrao(dff: pd.DataFrame, filtros: dict, totais: dict, titulo_rel: str) -> bytes:
    from reportlab.lib.pagesizes import landscape, letter
    from reportlab.lib.units import inch
    from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, Image
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT
    from reportlab.lib import colors as rl_colors
    import datetime as dt

    buffer = BytesIO()
    pagesize = landscape(letter)
    usable_w = pagesize[0] - 0.6 * inch

    doc = SimpleDocTemplate(
        buffer,
        pagesize=pagesize,
        topMargin=0.2 * inch,
        bottomMargin=0.35 * inch,
        leftMargin=0.3 * inch,
        rightMargin=0.3 * inch,
    )

    styles = getSampleStyleSheet()
    story = []

    data_hora_brasilia = format_datetime_sp(now_sp())
    story.append(Table([[Paragraph(data_hora_brasilia, ParagraphStyle("data_topo", fontSize=9, alignment=TA_RIGHT, textColor="#333333"))]], colWidths=[usable_w]))
    story.append(Spacer(1, 0.08 * inch))

    logo_esq_path = os.path.join("assets", "brasaobrasil.png")
    logo_dir_path = os.path.join("assets", "simbolo_RGB.png")
    logo_esq = Image(logo_esq_path, 1.1 * inch, 1.1 * inch) if os.path.exists(logo_esq_path) else ""
    logo_dir = Image(logo_dir_path, 1.1 * inch, 1.1 * inch) if os.path.exists(logo_dir_path) else ""

    texto_instituicao = (
        "<b><font color='#0b2b57' size=13>Ministério da Educação</font></b><br/>"
        "<b><font color='#0b2b57' size=13>Universidade Federal de Itajubá</font></b><br/>"
        "<font color='#0b2b57' size=11>Diretoria de Contabilidade e Finanças</font>"
    )
    instituicao = Paragraph(texto_instituicao, ParagraphStyle("inst", alignment=TA_CENTER, leading=16))
    cabecalho = Table([[logo_esq, instituicao, logo_dir]], colWidths=[1.2 * inch, usable_w - 2.4 * inch, 1.2 * inch])
    cabecalho.setStyle(TableStyle([("ALIGN", (0, 0), (-1, -1), "CENTER"), ("VALIGN", (0, 0), (-1, -1), "MIDDLE")]))
    story.append(cabecalho)
    story.append(Spacer(1, 0.10 * inch))

    story.append(Paragraph(titulo_rel, ParagraphStyle("titulo", fontSize=10, alignment=TA_CENTER, textColor="#0b2b57", leading=14, fontName="Helvetica-Bold")))
    story.append(Spacer(1, 0.08 * inch))

    f = filtros or {}
    story.append(Paragraph(f"UG Exec: {f.get('ug') or 'Todas'} | Ano: {f.get('ano') or 'Todos'} | Mês: {f.get('mes') or 'Todos'}", ParagraphStyle("f1", fontSize=7, alignment=TA_LEFT)))
    story.append(Paragraph(f"Fonte: {f.get('fonte') or 'Todas'} | Grupo: {f.get('grupo') or 'Todos'} | Natureza: {f.get('nat') or 'Todas'}", ParagraphStyle("f2", fontSize=7, alignment=TA_LEFT)))
    story.append(Spacer(1, 0.10 * inch))

    card_label = ParagraphStyle("cl", fontSize=6.2, leading=7.2, alignment=TA_CENTER, textColor="#0b2b57", fontName="Helvetica-Bold")
    card_value = ParagraphStyle("cv", fontSize=8.2, leading=9.0, alignment=TA_CENTER, textColor="#111111", fontName="Helvetica")

    def card_vertical(label: str, value: float):
        t = Table([[Paragraph(label, card_label)], [Paragraph(fmt_brl(value), card_value)]], colWidths=[(usable_w / 5.0) - 2])
        t.setStyle(TableStyle([("BOX", (0, 0), (-1, -1), 0.25, rl_colors.HexColor("#C9CED6"))]))
        return t

    cards = [
        card_vertical("DESPESAS INSCRITAS EM RP NÃO PROCESSADOS", totais.get("rpnpp", 0.0)),
        card_vertical("DESPESAS EMPENHADAS (CONTROLE EMPENHO)", totais.get("empenhadas", 0.0)),
        card_vertical("DESPESAS LIQUIDADAS (CONTROLE EMPENHO)", totais.get("liquidadas", 0.0)),
        card_vertical("DESPESAS LIQUIDADAS A PAGAR (CONTROLE EMPENHO)", totais.get("liq_a_pagar", 0.0)),
        card_vertical("DESPESAS PAGAS (CONTROLE EMPENHO)", totais.get("pagas", 0.0)),
    ]
    story.append(Table([cards], colWidths=[usable_w / 5.0] * 5))
    story.append(Spacer(1, 0.10 * inch))

    if dff is None or dff.empty:
        story.append(Paragraph("Sem dados para exibir.", styles["Normal"]))
        doc.build(story)
        buffer.seek(0)
        return buffer.read()

    wrap_style = ParagraphStyle("wrap", fontSize=5, leading=6, alignment=TA_LEFT)
    def wrap(x):
        return Paragraph(str(x)[:150], wrap_style)

    cols_export = [c for c in COLS_TABELA if c in dff.columns]
    df_small = dff[cols_export].copy()
    if len(df_small) > 130:
        df_small = df_small.iloc[:130]

    for col in COLS_VALORES:
        col_val = col + "_VAL"
        if col in df_small.columns and col_val in dff.columns:
            df_small[col] = fmt_brl_series(dff.loc[df_small.index, col_val])

    header_style = ParagraphStyle("h", fontSize=6, leading=7, alignment=TA_CENTER, textColor=rl_colors.HexColor("#0b2b57"), fontName="Helvetica-Bold")
    header = [Paragraph(str(c), header_style) for c in cols_export]
    body = [[wrap(v) for v in row] for row in df_small.astype(str).values.tolist()]
    data = [header] + body

    from reportlab.lib.units import inch
    width_map_in = {
        "UG Executora": 1.35,
        "Mês": 0.55,
        "Fonte Recursos Detalhada": 1.35,
        "Grupo Despesa": 1.10,
        "DESPESAS INSCRITAS EM RP NAO PROCESSADOS": 1.20,
        "DESPESAS EMPENHADAS (CONTROLE EMPENHO)": 1.05,
        "DESPESAS LIQUIDADAS (CONTROLE EMPENHO)": 1.05,
        "DESPESAS LIQUIDADAS A PAGAR(CONTROLE EMPENHO)": 1.15,
        "DESPESAS PAGAS (CONTROLE EMPENHO)": 1.05,
    }
    col_widths = [(width_map_in.get(c, 1.0) * inch) for c in cols_export]

    tabela = Table(data, repeatRows=1, colWidths=col_widths)

    money_cols = set(COLS_VALORES)
    money_indices = [i for i, c in enumerate(cols_export) if c in money_cols]

    ts = [
        ("BACKGROUND", (0, 0), (-1, 0), rl_colors.white),
        ("TEXTCOLOR", (0, 0), (-1, 0), rl_colors.HexColor("#0b2b57")),
        ("ALIGN", (0, 0), (-1, 0), "CENTER"),
        ("VALIGN", (0, 0), (-1, 0), "MIDDLE"),
        ("GRID", (0, 0), (-1, -1), 0.25, rl_colors.HexColor("#C9CED6")),
        ("LEFTPADDING", (0, 0), (-1, -1), 2),
        ("RIGHTPADDING", (0, 0), (-1, -1), 2),
        ("TOPPADDING", (0, 0), (-1, -1), 1),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 1),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
    ]
    for idx in money_indices:
        ts.append(("ALIGN", (idx, 1), (idx, -1), "RIGHT"))

    tabela.setStyle(TableStyle(ts))
    story.append(tabela)

    doc.build(story)
    buffer.seek(0)
    return buffer.read()


layout = html.Div(
    style={"padding": "10px 22px"},
    children=[
        # ✅ mantém o Location, mas com id único para não colidir com o app.py
        dcc.Location(id="url-unifei"),

        html.Div(
            id="barra-filtros-unifei",
            className="filtros-sticky",
            children=[
                html.Div(
                    style={"display": "grid", "gridTemplateColumns": "2fr 220px 1fr 160px", "gap": "12px", "alignItems": "end", "marginBottom": "8px"},
                    children=[
                        html.Div([html.Label("UG Executora"), dcc.Dropdown(id="filtro_ug_exec_unifei", options=[], value=None, placeholder="Todas", clearable=True, style=dropdown_style)]),
                        html.Div([html.Label("Mês"), dcc.Dropdown(id="filtro_mes_unifei", options=[], value=None, placeholder="Todos", clearable=True, style=dropdown_style)]),
                        html.Div([html.Label("Fonte Recursos Detalhada"), dcc.Dropdown(id="filtro_fonte_unifei", options=[], value=None, placeholder="Todas", clearable=True, style=dropdown_style)]),
                        html.Div([html.Label("Ano"), dcc.Dropdown(id="filtro_ano_unifei", options=[{"label": ANO_PADRAO, "value": ANO_PADRAO}], value=ANO_PADRAO, clearable=False, style=dropdown_style)]),
                    ],
                ),
                html.Div(
                    style={"display": "grid", "gridTemplateColumns": "1fr 1fr auto", "gap": "12px", "alignItems": "end", "marginBottom": "10px"},
                    children=[
                        html.Div([html.Label("Grupo Despesa"), dcc.Dropdown(id="filtro_grupo_unifei", options=[], value=None, placeholder="Todos", clearable=True, style=dropdown_style)]),
                        html.Div([html.Label("Natureza da Despesa"), dcc.Dropdown(id="filtro_natureza_unifei", options=[], value=None, placeholder="Todas", clearable=True, style=dropdown_style)]),
                        html.Div(
                            style={"display": "flex", "gap": "8px", "flexWrap": "wrap", "justifyContent": "flex-end"},
                            children=[
                                html.Button("Limpar Filtros", id="btn-limpar-unifei", n_clicks=0, style=BUTTON_CLEAR_STYLE),
                                html.Button("Recarregar Dados", id="btn-reload-unifei", n_clicks=0, style=BUTTON_REFRESH_STYLE),
                                html.Button("Baixar PDF", id="btn-pdf-unifei", n_clicks=0, style=BUTTON_PDF_STYLE),
                                dcc.Download(id="download-pdf-unifei"),
                            ],
                        ),
                    ],
                ),
            ],
        ),

        html.Div(id="info-atualizacao-unifei", style={"marginBottom": "10px"}),

        html.Div(
            style={"display": "grid", "gridTemplateColumns": "repeat(auto-fit, minmax(210px, 1fr))", "gap": "10px", "marginBottom": "10px"},
            children=[
                html.Div(id="card-rpnpp-unifei"),
                html.Div(id="card-empenhado-unifei"),
                html.Div(id="card-liquidado-unifei"),
                html.Div(id="card-liq-a-pagar-unifei"),
                html.Div(id="card-pago-unifei"),
            ],
        ),

        html.Div(
            style={"display": "grid", "gridTemplateColumns": "repeat(auto-fit, minmax(360px, 1fr))", "gap": "12px", "marginBottom": "12px"},
            children=[
                dcc.Graph(id="grafico-mensal-unifei", config={"displayModeBar": True}),
                dcc.Graph(id="grafico-por-grupo-unifei", config={"displayModeBar": True}),
            ],
        ),

        html.H4("Detalhamento", style={"marginTop": "8px"}),

        html.Div(
            style={"width": "100%", "overflowX": "hidden", "border": f"1px solid {CINZA}", "borderRadius": "10px", "paddingBottom": "8px"},
            children=[
                dash_table.DataTable(
                    id="tabela-unifei",
                    columns=[],
                    data=[],
                    sort_action="custom",
                    sort_mode="single",
                    page_action="custom",
                    page_current=0,
                    page_size=8,  # ✅ exibe só 10 linhas

                    fixed_rows={"headers": True},  # ✅ cabeçalho fixo

                    cell_selectable=False,
                    row_selectable=False,
                    column_selectable=False,
                    editable=False,
                    style_as_list_view=True,

                    fill_width=False,
                    style_table={
                        "width": "100%",
                        "overflowX": "hidden",
                        "maxHeight": "520px",   # ✅ necessário p/ header fixo funcionar com scroll
                        "overflowY": "auto",
                    },
                    style_header={
                        "backgroundColor": AZUL,
                        "color": "white",
                        "fontWeight": "bold",
                        "fontSize": "11px",
                        "textAlign": "left",
                        "whiteSpace": "normal",
                        "height": "auto",
                        "padding": "6px",
                    },
                    style_cell={
                        "fontSize": "11px",
                        "padding": "6px",
                        "whiteSpace": "normal",
                        "height": "auto",
                        "textAlign": "left",
                        "border": f"1px solid {CINZA}",
                        "lineHeight": "1.25",
                        "backgroundColor": "white",
                        "color": "#111",
                        "overflow": "hidden",
                        "textOverflow": "clip",
                    },

                    # ✅ remove cores por coluna; aplica zebra branco/laranja
                    style_data_conditional=[
                        {"if": {"row_index": "odd"}, "backgroundColor": ZEBRA_LARANJA_BG},
                    ],

                    style_cell_conditional=[
                        {"if": {"column_id": "UG Executora"}, "minWidth": "170px", "width": "170px", "maxWidth": "170px"},
                        {"if": {"column_id": "Mês"}, "minWidth": "70px", "width": "70px", "maxWidth": "70px"},
                        {"if": {"column_id": "Fonte Recursos Detalhada"}, "minWidth": "190px", "width": "190px", "maxWidth": "190px"},
                        {"if": {"column_id": "Grupo Despesa"}, "minWidth": "170px", "width": "170px", "maxWidth": "170px"},
                        {"if": {"column_id": "DESPESAS INSCRITAS EM RP NAO PROCESSADOS"}, "minWidth": "185px", "width": "185px", "maxWidth": "185px", "textAlign": "right"},
                        {"if": {"column_id": "DESPESAS EMPENHADAS (CONTROLE EMPENHO)"}, "minWidth": "150px", "width": "150px", "maxWidth": "150px", "textAlign": "right"},
                        {"if": {"column_id": "DESPESAS LIQUIDADAS (CONTROLE EMPENHO)"}, "minWidth": "150px", "width": "150px", "maxWidth": "150px", "textAlign": "right"},
                        {"if": {"column_id": "DESPESAS LIQUIDADAS A PAGAR(CONTROLE EMPENHO)"}, "minWidth": "165px", "width": "165px", "maxWidth": "165px", "textAlign": "right"},
                        {"if": {"column_id": "DESPESAS PAGAS (CONTROLE EMPENHO)"}, "minWidth": "150px", "width": "150px", "maxWidth": "150px", "textAlign": "right"},
                    ],

                    css=[
                        {"selector": ".dash-spreadsheet-container th", "rule": "white-space: normal !important; height: auto !important; overflow-wrap: anywhere;"},
                        {"selector": ".dash-spreadsheet-container td", "rule": "white-space: normal !important; height: auto !important; overflow-wrap: anywhere;"},
                        {"selector": ".dash-cell.focused", "rule": "outline: none !important;"},
                        {"selector": "td.dash-cell", "rule": "cursor: default;"},
                    ],
                )
            ],
        ),

        dcc.Store(id="store-reload-unifei"),
    ],
)


@dash.callback(
    Output("filtro_ug_exec_unifei", "value"),
    Output("filtro_mes_unifei", "value"),
    Output("filtro_ano_unifei", "value"),
    Output("filtro_fonte_unifei", "value"),
    Output("filtro_grupo_unifei", "value"),
    Output("filtro_natureza_unifei", "value"),
    Input("btn-limpar-unifei", "n_clicks"),
    prevent_initial_call=True,
)
def limpar_filtros(_):
    return None, None, ANO_PADRAO, None, None, None


@dash.callback(
    Output("store-reload-unifei", "data"),
    Output("info-atualizacao-unifei", "children"),
    Output("filtro_ug_exec_unifei", "options"),
    Output("filtro_mes_unifei", "options"),
    Output("filtro_ano_unifei", "options"),
    Output("filtro_fonte_unifei", "options"),
    Output("filtro_grupo_unifei", "options"),
    Output("filtro_natureza_unifei", "options"),
    Input("url-unifei", "pathname"),
    Input("btn-reload-unifei", "n_clicks"),
)
def carregar_ao_abrir_ou_recarregar(pathname, n_reload):
    if pathname != "/execucao-orcamento-unifei":
        raise dash.exceptions.PreventUpdate

    force = bool(n_reload) and n_reload > 0
    try:
        df, status = get_df(force=force)

        ug_opts = [{"label": u, "value": u} for u in _safe_unique_sorted(df, "UG Executora")]
        mes_opts = [{"label": m, "value": m} for m in _safe_unique_sorted(df, "Mês")]

        ano_vals = _safe_unique_sorted(df, "Ano")
        ano_opts = [{"label": int(a), "value": int(a)} for a in ano_vals] if ano_vals else [{"label": ANO_PADRAO, "value": ANO_PADRAO}]

        fonte_opts = [{"label": f, "value": f} for f in _safe_unique_sorted(df, "Fonte Recursos Detalhada")]
        grupo_opts = [{"label": g, "value": g} for g in _safe_unique_sorted(df, "Grupo Despesa")]
        nat_opts = [{"label": n, "value": n} for n in _safe_unique_sorted(df, "NAT DESP")]

        msg = html.Div([html.B("Dados disponíveis. "), html.Span(status)])
        return (
            {"ts": datetime.now().isoformat()},
            msg,
            ug_opts,
            mes_opts,
            ano_opts,
            fonte_opts,
            grupo_opts,
            nat_opts,
        )
    except Exception as e:
        msg = html.Div([html.B("Falha ao carregar dados: "), html.Span(str(e))], style={"color": "crimson"})
        return dash.no_update, msg, dash.no_update, dash.no_update, dash.no_update, dash.no_update, dash.no_update, dash.no_update


@dash.callback(
    Output("card-rpnpp-unifei", "children"),
    Output("card-empenhado-unifei", "children"),
    Output("card-liquidado-unifei", "children"),
    Output("card-liq-a-pagar-unifei", "children"),
    Output("card-pago-unifei", "children"),
    Output("grafico-mensal-unifei", "figure"),
    Output("grafico-por-grupo-unifei", "figure"),
    Output("tabela-unifei", "columns"),
    Output("tabela-unifei", "data"),
    Output("tabela-unifei", "page_count"),
    Input("store-reload-unifei", "data"),
    Input("filtro_ug_exec_unifei", "value"),
    Input("filtro_mes_unifei", "value"),
    Input("filtro_ano_unifei", "value"),
    Input("filtro_fonte_unifei", "value"),
    Input("filtro_grupo_unifei", "value"),
    Input("filtro_natureza_unifei", "value"),
    Input("tabela-unifei", "page_current"),
    Input("tabela-unifei", "page_size"),
    Input("tabela-unifei", "sort_by"),
)
def atualizar_painel(_reload, ug, mes, ano, fonte, grupo, natureza, page_current, page_size, sort_by):
    df, _ = get_df(force=False)
    dff = filtrar_df(df, ug, mes, ano, fonte, grupo, natureza)

    if not dff.empty and "Mês" in dff.columns:
        dff = dff.sort_values("Mês")

    kpis = calcular_kpis(dff)

    def kpi_value_style(color_hex: str):
        s = dict(KPI_VALUE_STYLE_BASE)
        s["color"] = color_hex
        return s

    def kpi_card_style(color_hex: str):
        s = dict(KPI_CARD_STYLE)
        s["borderTop"] = f"4px solid {color_hex}"
        return s

    card_rpnpp = html.Div(
        [html.Div("INSCRITAS EM RP NÃO PROCESSADOS", style={**KPI_TITLE_STYLE, "color": LARANJA_RPNP}),
         html.Div(fmt_brl(kpis["rpnpp"]), style=kpi_value_style(LARANJA_RPNP))],
        style=kpi_card_style(LARANJA_RPNP),
    )
    card_empenhado = html.Div(
        [html.Div("DESPESAS EMPENHADAS", style={**KPI_TITLE_STYLE, "color": AZUL}),
         html.Div(fmt_brl(kpis["empenhadas"]), style=kpi_value_style(AZUL))],
        style=kpi_card_style(AZUL),
    )
    card_liquidado = html.Div(
        [html.Div("DESPESAS LIQUIDADAS", style={**KPI_TITLE_STYLE, "color": VERMELHO}),
         html.Div(fmt_brl(kpis["liquidadas"]), style=kpi_value_style(VERMELHO))],
        style=kpi_card_style(VERMELHO),
    )
    card_liq_a_pagar = html.Div(
        [html.Div("DESPESAS LIQUIDADAS A PAGAR", style={**KPI_TITLE_STYLE, "color": CINZA}),
         html.Div(fmt_brl(kpis["liq_a_pagar"]), style=kpi_value_style(CINZA))],
        style=kpi_card_style(CINZA),
    )
    card_pago = html.Div(
        [html.Div("DESPESAS PAGAS", style={**KPI_TITLE_STYLE, "color": VERDE_PETROLEO}),
         html.Div(fmt_brl(kpis["pagas"]), style=kpi_value_style(VERDE_PETROLEO))],
        style=kpi_card_style(VERDE_PETROLEO),
    )

    # ✅ parâmetros para “alinhar” aparência de largura de barras nos 2 gráficos
    COMMON_GRAPH_LAYOUT = dict(
        plot_bgcolor="white",
        paper_bgcolor="white",
        font=dict(color=AZUL),
        xaxis=dict(showgrid=False),
        yaxis=dict(gridcolor=CINZA),
        hovermode="x unified",
        showlegend=False,
        height=420,          # mesma altura
        bargap=0.25,         # mesma “sensação” de largura
        bargroupgap=0.05,
        margin=dict(t=55, r=20, b=60, l=60),
    )

    # Gráfico 1
    if not dff.empty:
        totais_df = pd.DataFrame(
            {
                "Tipo": ["Inscritas em RP Não Processados", "Empenhadas", "Liquidadas", "Liq. a Pagar", "Pagas"],
                "Valor": [
                    float(dff.get("DESPESAS INSCRITAS EM RP NAO PROCESSADOS_VAL", 0).sum()),
                    float(dff.get("DESPESAS EMPENHADAS (CONTROLE EMPENHO)_VAL", 0).sum()),
                    float(dff.get("DESPESAS LIQUIDADAS (CONTROLE EMPENHO)_VAL", 0).sum()),
                    float(dff.get("DESPESAS LIQUIDADAS A PAGAR(CONTROLE EMPENHO)_VAL", 0).sum()),
                    float(dff.get("DESPESAS PAGAS (CONTROLE EMPENHO)_VAL", 0).sum()),
                ],
            }
        )
        color_map = {
            "Inscritas em RP Não Processados": LARANJA_RPNP,
            "Empenhadas": AZUL,
            "Liquidadas": VERMELHO,
            "Liq. a Pagar": CINZA,
            "Pagas": VERDE_PETROLEO,
        }
        fig_mensal = px.bar(totais_df, x="Tipo", y="Valor", color="Tipo", color_discrete_map=color_map, text="Valor")
        fig_mensal.update_traces(
            hovertemplate="<b>%{x}</b><br>R$ %{y:,.2f}<extra></extra>",
            texttemplate="R$ %{y:,.2f}",
            textposition="outside",
            cliponaxis=False,
        )
        fig_mensal.update_layout(title="Despesas", xaxis_title="", yaxis_title="Valor (R$)", **COMMON_GRAPH_LAYOUT)
    else:
        fig_mensal = px.bar(title="Despesas")
        fig_mensal.update_layout(**COMMON_GRAPH_LAYOUT)

    # Gráfico 2
    if not dff.empty and "Grupo Despesa" in dff.columns and "DESPESAS PAGAS (CONTROLE EMPENHO)_VAL" in dff.columns:
        grp = (
            dff.groupby("Grupo Despesa", observed=True)["DESPESAS PAGAS (CONTROLE EMPENHO)_VAL"]
            .sum()
            .reset_index()
            .sort_values("DESPESAS PAGAS (CONTROLE EMPENHO)_VAL", ascending=False)
        )
        fig_grupo = px.bar(
            grp,
            x="Grupo Despesa",
            y="DESPESAS PAGAS (CONTROLE EMPENHO)_VAL",
            text="DESPESAS PAGAS (CONTROLE EMPENHO)_VAL",
        )
        paleta_3 = [AZUL, VERMELHO, CINZA]
        fig_grupo.update_traces(
            marker_color=[paleta_3[i % 3] for i in range(len(grp))],
            hovertemplate="<b>%{x}</b><br>R$ %{y:,.2f}<extra></extra>",
            texttemplate="R$ %{y:,.2f}",
            textposition="outside",
            cliponaxis=False,
        )
        fig_grupo.update_layout(
            title="Despesas pagas por grupo de despesa",
            xaxis_title="Grupo",
            yaxis_title="Valor (R$)",
            **COMMON_GRAPH_LAYOUT,
        )
    else:
        fig_grupo = px.bar(title="Despesas pagas por grupo de despesa")
        fig_grupo.update_layout(**COMMON_GRAPH_LAYOUT)

    # Tabela
    cols_ok = [c for c in COLS_TABELA if c in dff.columns]
    columns = [{"name": c, "id": c} for c in cols_ok]

    if sort_by and isinstance(sort_by, list) and len(sort_by) > 0:
        col_sort = sort_by[0].get("column_id")
        direction = sort_by[0].get("direction", "asc")
        if col_sort in COLS_VALORES and (col_sort + "_VAL") in dff.columns:
            sort_key = col_sort + "_VAL"
        else:
            sort_key = col_sort
        if sort_key in dff.columns:
            dff = dff.sort_values(sort_key, ascending=(direction == "asc"), kind="mergesort")

    total_rows = len(dff)
    page_size = int(page_size or 10)      # ✅ default 10
    page_current = int(page_current or 0)
    page_count = max(1, (total_rows + page_size - 1) // page_size) if total_rows else 1

    start = page_current * page_size
    end = start + page_size

    if cols_ok and total_rows:
        page_df = dff.iloc[start:end][cols_ok].copy()
        for col in COLS_VALORES:
            col_val = col + "_VAL"
            if col in page_df.columns and col_val in dff.columns:
                page_df[col] = fmt_brl_series(dff.iloc[start:end][col_val])
        data_table = page_df.to_dict("records")
    else:
        data_table = []

    return (
        card_rpnpp,
        card_empenhado,
        card_liquidado,
        card_liq_a_pagar,
        card_pago,
        fig_mensal,
        fig_grupo,
        columns,
        data_table,
        page_count,
    )


@dash.callback(
    Output("download-pdf-unifei", "data"),
    Input("btn-pdf-unifei", "n_clicks"),
    State("filtro_ug_exec_unifei", "value"),
    State("filtro_mes_unifei", "value"),
    State("filtro_ano_unifei", "value"),
    State("filtro_fonte_unifei", "value"),
    State("filtro_grupo_unifei", "value"),
    State("filtro_natureza_unifei", "value"),
    prevent_initial_call=True,
)
def baixar_pdf(_, ug, mes, ano, fonte, grupo, natureza):
    df, _ = get_df(force=False)
    dff = filtrar_df(df, ug, mes, ano, fonte, grupo, natureza)

    totais = calcular_kpis(dff)
    filtros = {"ug": ug, "ano": ano, "mes": mes, "fonte": fonte, "grupo": grupo, "nat": natureza}

    titulo_rel = "RELATÓRIO DE EXECUÇÃO DO ORÇAMENTO - UNIFEI"
    conteudo = gerar_pdf_padrao(dff, filtros, totais, titulo_rel)

    nome = f"execucao_orcamento_unifei_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf"
    return dcc.send_bytes(conteudo, nome)
