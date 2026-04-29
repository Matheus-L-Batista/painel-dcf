# pages/execucao_ted.py

# Painel: Execução do Orçamento - TED

import os
import threading
from io import BytesIO
from datetime import datetime, timedelta

import dash
from dash import html, dcc, Input, Output, State, dash_table
from dash.exceptions import PreventUpdate
import pandas as pd
import plotly.express as px
import numpy as np
from reportlab.lib.pagesizes import letter, landscape
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
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT
from reportlab.lib import colors
import datetime as dt
from utils.formatting import format_brl, format_brl_series, parse_brl_series
from utils.runtime import format_datetime_sp, get_default_year, now_sp
from utils.ui import BUTTON_CLEAR_STYLE, BUTTON_PDF_STYLE, BUTTON_REFRESH_STYLE


# --------------------------------------------------
# Registro da página
# --------------------------------------------------
dash.register_page(
    __name__,
    path="/execucao-ted",
    name="Execução TED",
    title="Execução do Orçamento - TED",
)


# --------------------------------------------------
# URL da planilha (TED)
# --------------------------------------------------
URL = (
    "https://docs.google.com/spreadsheets/d/"
    "1MkiWDH-MBnLeSUlqV91qjzCVRTlTAVh9xYooENJ151o/"
    "gviz/tq?tqx=out:csv&sheet=Execucao%20do%20Orcamento%20TED"
)

# --------------------------------------------------
# Cores (mesmo padrão UNIFEI)
# --------------------------------------------------
AZUL = "#003A70"
VERMELHO = "#DA291C"
CINZA = "#A2AAAD"
VERDE_PETROLEO = "#2A9D8F"
LARANJA_RPNP = "#F2994A"
ZEBRA_LARANJA_BG = "#FFF3E6"

# --------------------------------------------------
# Estilo unificado dos botões (padrão azul)
# --------------------------------------------------
dropdown_style = {
    "color": "black",
    "width": "100%",
    "marginBottom": "6px",
    "whiteSpace": "normal",
}

# ✅ Cartões no padrão UNIFEI
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

# Ordem dos meses para o filtro
MESES_ORDEM = [
    "Janeiro", "Fevereiro", "Março", "Abril", "Maio", "Junho",
    "Julho", "Agosto", "Setembro", "Outubro", "Novembro", "Dezembro"
]
MAP_MES_NUM = {m: i + 1 for i, m in enumerate(MESES_ORDEM)}

# Colunas monetárias
COLS_VALORES = [
    "DESPESAS INSCRITAS EM RP NAO PROCESSADOS",
    "DESPESAS EMPENHADAS (CONTROLE EMPENHO)",
    "DESPESAS LIQUIDADAS (CONTROLE EMPENHO)",
    "DESPESAS LIQUIDADAS A PAGAR(CONTROLE EMPENHO)",
    "DESPESAS PAGAS (CONTROLE EMPENHO)",
]

# Colunas da tabela (mantém “Fonte Recursos Detalhada”/“Natureza Despesa” como no TED atual)
COLS_TABELA = [
    "Unidade Orçamentária",
    "Fonte Recursos Detalhada",
    "GRUPO DESP",
    "Natureza Despesa",
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
        vals = [str(v).strip() for v in df[col].dropna().unique().tolist()]
        vals = [v for v in vals if v in MAP_MES_NUM]
        return sorted(vals, key=lambda m: MAP_MES_NUM[m])
    if col == "Ano":
        vals = df[col].dropna().unique().tolist()
        try:
            return sorted([int(v) for v in vals])
        except Exception:
            return sorted(vals)
    return sorted(df[col].dropna().astype(str).unique().tolist())


def _moeda_para_float_series(s: pd.Series) -> pd.Series:
    """Robusto para R$ 1.234,56 / 1234,56 / 1234.56 / '-' / vazio."""
    return parse_brl_series(s)


# --------------------------------------------------
# Carga e tratamento dos dados
# --------------------------------------------------
def carregar_dados():
    df = pd.read_csv(URL, low_memory=False)
    df.columns = [c.strip() for c in df.columns]

    # Normalizações/aliases para manter compatibilidade
    if "FRD" in df.columns and "Fonte Recursos Detalhada" not in df.columns:
        df["Fonte Recursos Detalhada"] = df["FRD"].astype(str)

    if "NAT DESP" in df.columns and "Natureza Despesa" not in df.columns:
        df["Natureza Despesa"] = df["NAT DESP"].astype(str)

    if "UG EXEC" in df.columns and "UG Executora" not in df.columns:
        df["UG Executora"] = df["UG EXEC"].astype(str)

    if "Mês" in df.columns:
        df["Mês"] = df["Mês"].astype(str).str.strip()
        # ajuda em ordenação
        df["Mês"] = pd.Categorical(df["Mês"], categories=MESES_ORDEM, ordered=True)

    for c in COLS_VALORES:
        if c in df.columns:
            df[c + "_VAL"] = _moeda_para_float_series(df[c])
        else:
            df[c + "_VAL"] = 0.0

    # Ano robusto
    if "Ano" in df.columns:
        df["Ano"] = pd.to_numeric(df["Ano"], errors="coerce")

    return df


# --------------------------------------------------
# Cache / atualização (mesma estrutura do UNIFEI)
# --------------------------------------------------
_DF_CACHE = None
_DF_CACHE_AT = None
_CACHE_LOCK = threading.Lock()
CACHE_TTL_MINUTOS = 15


def get_df(force: bool = False):
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


# DF base inicial
df_base, _ = get_df(force=True)
try:
    ANO_PADRAO = int(sorted(pd.to_numeric(df_base["Ano"], errors="coerce").dropna().unique())[-1])
except Exception:
    ANO_PADRAO = get_default_year()


def filtrar_df(df: pd.DataFrame, uo, ugexec, ano, mes, fonte, grupo, nat) -> pd.DataFrame:
    if df is None or df.empty:
        return pd.DataFrame()

    dff = df

    if ano is not None and "Ano" in dff.columns:
        dff = dff[pd.to_numeric(dff["Ano"], errors="coerce").fillna(0).astype(int) == int(ano)]

    if uo and "Unidade Orçamentária" in dff.columns:
        dff = dff[dff["Unidade Orçamentária"].astype(str) == str(uo)]

    if ugexec:
        if "UG EXEC" in dff.columns:
            dff = dff[dff["UG EXEC"].astype(str) == str(ugexec)]
        elif "UG Executora" in dff.columns:
            dff = dff[dff["UG Executora"].astype(str) == str(ugexec)]

    if mes and "Mês" in dff.columns:
        dff = dff[dff["Mês"] == mes]

    if fonte:
        if "FRD" in dff.columns:
            dff = dff[dff["FRD"].astype(str) == str(fonte)]
        elif "Fonte Recursos Detalhada" in dff.columns:
            dff = dff[dff["Fonte Recursos Detalhada"].astype(str) == str(fonte)]

    if grupo and "GRUPO DESP" in dff.columns:
        dff = dff[dff["GRUPO DESP"].astype(str) == str(grupo)]

    if nat and "NAT DESP" in dff.columns:
        dff = dff[dff["NAT DESP"].astype(str) == str(nat)]
    elif nat and "Natureza Despesa" in dff.columns:
        dff = dff[dff["Natureza Despesa"].astype(str) == str(nat)]

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


def _common_graph_layout():
    return dict(
        plot_bgcolor="white",
        paper_bgcolor="white",
        font=dict(color=AZUL),
        xaxis=dict(showgrid=False),
        yaxis=dict(gridcolor=CINZA),
        hovermode="x unified",
        showlegend=False,
        height=420,
        bargap=0.25,
        bargroupgap=0.05,
        margin=dict(t=55, r=20, b=60, l=60),
    )


# --------------------------------------------------
# Layout
# --------------------------------------------------
layout = html.Div(
    children=[
        # Location exclusivo (evita colisão com app.py)
        dcc.Location(id="url-ted"),

        # Barra de filtros fixa
        html.Div(
            id="barra-filtros-ted",
            className="filtros-sticky",
            children=[
                html.H3("Filtros", className="sidebar-title"),

                # 1ª linha: UO, UG, Ano, Mês
                html.Div(
                    style={
                        "display": "flex",
                        "flexWrap": "wrap",
                        "gap": "10px",
                        "marginBottom": "8px",
                    },
                    children=[
                        html.Div(
                            style={"minWidth": "220px", "flex": "1"},
                            children=[
                                html.Label("Unidade Orçamentária"),
                                dcc.Dropdown(
                                    id="filtro_uo_ted",
                                    options=[],
                                    value=None,
                                    placeholder="Selecione uma UO...",
                                    clearable=True,
                                    searchable=True,
                                    style=dropdown_style,
                                ),
                            ],
                        ),
                        html.Div(
                            style={"minWidth": "220px", "flex": "1"},
                            children=[
                                html.Label("UG Executora"),
                                dcc.Dropdown(
                                    id="filtro_ug_exec_ted",
                                    options=[],
                                    value=None,
                                    placeholder="Selecione uma UG...",
                                    clearable=True,
                                    searchable=True,
                                    style=dropdown_style,
                                ),
                            ],
                        ),
                        html.Div(
                            style={"minWidth": "120px", "flex": "0 0 150px"},
                            children=[
                                html.Label("Ano"),
                                dcc.Dropdown(
                                    id="filtro_ano_ted",
                                    options=[{"label": str(int(ANO_PADRAO)), "value": int(ANO_PADRAO)}],
                                    value=int(ANO_PADRAO),
                                    clearable=False,
                                    style=dropdown_style,
                                ),
                            ],
                        ),
                        html.Div(
                            style={"minWidth": "150px", "flex": "0 0 180px"},
                            children=[
                                html.Label("Mês"),
                                dcc.Dropdown(
                                    id="filtro_mes_ted",
                                    options=[],
                                    value=None,
                                    placeholder="Selecione um mês...",
                                    clearable=True,
                                    searchable=True,
                                    style=dropdown_style,
                                ),
                            ],
                        ),
                    ],
                ),

                # 2ª linha: Fonte, Grupo, Natureza + botões
                html.Div(
                    style={
                        "display": "flex",
                        "flexWrap": "wrap",
                        "gap": "10px",
                        "alignItems": "flex-end",
                    },
                    children=[
                        html.Div(
                            style={"minWidth": "220px", "flex": "1"},
                            children=[
                                html.Label("Fonte Recursos Detalhada"),
                                dcc.Dropdown(
                                    id="filtro_fonte_ted",
                                    options=[],
                                    value=None,
                                    placeholder="Selecione uma fonte...",
                                    clearable=True,
                                    searchable=True,
                                    style=dropdown_style,
                                ),
                            ],
                        ),
                        html.Div(
                            style={"minWidth": "220px", "flex": "1"},
                            children=[
                                html.Label("Grupo da Despesa"),
                                dcc.Dropdown(
                                    id="filtro_grupo_ted",
                                    options=[],
                                    value=None,
                                    placeholder="Selecione um grupo...",
                                    clearable=True,
                                    searchable=True,
                                    style=dropdown_style,
                                ),
                            ],
                        ),
                        html.Div(
                            style={"minWidth": "220px", "flex": "1"},
                            children=[
                                html.Label("Natureza Despesa"),
                                dcc.Dropdown(
                                    id="filtro_nat_ted",
                                    options=[],
                                    value=None,
                                    placeholder="Selecione uma natureza...",
                                    clearable=True,
                                    searchable=True,
                                    style=dropdown_style,
                                ),
                            ],
                        ),
                        html.Div(
                            style={
                                "display": "flex",
                                "gap": "10px",
                                "marginTop": "24px",
                                "flexWrap": "wrap",
                                "justifyContent": "flex-end",
                            },
                            children=[
                                html.Button(
                                    "Limpar filtros",
                                    id="btn_limpar_filtros_ted",
                                    n_clicks=0,
                                    style=BUTTON_CLEAR_STYLE,
                                ),
                                html.Button(
                                    "Recarregar Dados",
                                    id="btn_reload_ted",
                                    n_clicks=0,
                                    style=BUTTON_REFRESH_STYLE,
                                ),
                                html.Button(
                                    "Baixar Relatório PDF",
                                    id="btn_download_relatorio_ted",
                                    n_clicks=0,
                                    style=BUTTON_PDF_STYLE,
                                ),
                                dcc.Download(id="download_relatorio_ted"),
                            ],
                        ),
                    ],
                ),
            ],
        ),

        html.Div(id="info-atualizacao-ted", style={"marginBottom": "10px"}),

        html.Div(
            style={
                "display": "grid",
                "gridTemplateColumns": "repeat(auto-fit, minmax(210px, 1fr))",
                "gap": "10px",
                "marginBottom": "10px",
            },
            children=[
                html.Div(id="card-rpnpp-ted"),
                html.Div(id="card-empenhado-ted"),
                html.Div(id="card-liquidado-ted"),
                html.Div(id="card-liq-a-pagar-ted"),
                html.Div(id="card-pago-ted"),
            ],
        ),

        html.Div(
            style={
                "display": "grid",
                "gridTemplateColumns": "repeat(auto-fit, minmax(360px, 1fr))",
                "gap": "12px",
                "marginBottom": "12px",
            },
            children=[
                dcc.Graph(id="grafico_barras_grupo_ted", config={"displayModeBar": True}),
                dcc.Graph(id="grafico_pizza_status_ted", config={"displayModeBar": True}),
            ],
        ),

        html.H4("Detalhamento"),

        html.Div(
            style={"width": "100%", "overflowX": "hidden", "border": f"1px solid {CINZA}", "borderRadius": "10px", "paddingBottom": "8px"},
            children=[
                dash_table.DataTable(
                    id="tabela_execucao_ted",
                    columns=[{"name": c, "id": c} for c in COLS_TABELA],
                    data=[],
                    sort_action="custom",
                    sort_mode="single",
                    page_action="custom",
                    page_current=0,
                    page_size=10,
                    fixed_rows={"headers": True},

                    cell_selectable=False,
                    row_selectable=False,
                    column_selectable=False,
                    editable=False,
                    style_as_list_view=True,

                    fill_width=False,
                    style_table={"minWidth": "max-content", "overflowX": "auto", "maxHeight": "520px", "overflowY": "auto"},
                    style_header={
                        "backgroundColor": AZUL,
                        "color": "white",
                        "fontWeight": "bold",
                        "fontSize": "12px",
                        "textAlign": "left",
                        "padding": "10px",
                        "border": "0px",
                        "whiteSpace": "normal",
                        "height": "auto",
                    },
                    style_cell={
                        "fontSize": "12px",
                        "padding": "10px",
                        "textAlign": "left",
                        "border": "0px",
                        "whiteSpace": "normal",
                        "height": "auto",
                        "lineHeight": "1.25",
                    },
                    # ✅ zebra branco/laranja
                    style_data_conditional=[
                        {"if": {"row_index": "odd"}, "backgroundColor": ZEBRA_LARANJA_BG},
                    ],
                    style_cell_conditional=[
                        {"if": {"column_id": "Unidade Orçamentária"}, "minWidth": "210px", "width": "210px"},
                        {"if": {"column_id": "Fonte Recursos Detalhada"}, "minWidth": "190px", "width": "190px"},
                        {"if": {"column_id": "GRUPO DESP"}, "minWidth": "190px", "width": "190px"},
                        {"if": {"column_id": "Natureza Despesa"}, "minWidth": "220px", "width": "220px"},
                        {"if": {"column_id": "DESPESAS INSCRITAS EM RP NAO PROCESSADOS"}, "minWidth": "230px", "width": "230px", "textAlign": "right"},
                        {"if": {"column_id": "DESPESAS EMPENHADAS (CONTROLE EMPENHO)"}, "minWidth": "160px", "width": "160px", "textAlign": "right"},
                        {"if": {"column_id": "DESPESAS LIQUIDADAS (CONTROLE EMPENHO)"}, "minWidth": "160px", "width": "160px", "textAlign": "right"},
                        {"if": {"column_id": "DESPESAS LIQUIDADAS A PAGAR(CONTROLE EMPENHO)"}, "minWidth": "175px", "width": "175px", "textAlign": "right"},
                        {"if": {"column_id": "DESPESAS PAGAS (CONTROLE EMPENHO)"}, "minWidth": "160px", "width": "160px", "textAlign": "right"},
                    ],
                    css=[
                        {"selector": ".dash-spreadsheet-container th", "rule": "white-space: normal !important; height: auto !important;"},
                        {"selector": ".dash-spreadsheet-container td", "rule": "white-space: normal !important; height: auto !important;"},
                        {"selector": ".dash-cell.focused", "rule": "outline: none !important;"},
                        {"selector": "td.dash-cell", "rule": "cursor: default;"},
                    ],
                )
            ],
        ),

        dcc.Store(id="store_reload_ted"),
        dcc.Store(id="store_pdf_ted"),
    ],
)


# --------------------------------------------------
# Limpar filtros
# --------------------------------------------------
@dash.callback(
    Output("filtro_uo_ted", "value"),
    Output("filtro_ug_exec_ted", "value"),
    Output("filtro_ano_ted", "value"),
    Output("filtro_mes_ted", "value"),
    Output("filtro_fonte_ted", "value"),
    Output("filtro_grupo_ted", "value"),
    Output("filtro_nat_ted", "value"),
    Input("btn_limpar_filtros_ted", "n_clicks"),
    prevent_initial_call=True,
)
def limpar_filtros(n):
    return None, None, int(ANO_PADRAO), None, None, None, None


# --------------------------------------------------
# Estrutura de atualização (carrega ao abrir / recarrega manualmente)
# --------------------------------------------------
@dash.callback(
    Output("store_reload_ted", "data"),
    Output("info-atualizacao-ted", "children"),
    Output("filtro_uo_ted", "options"),
    Output("filtro_ug_exec_ted", "options"),
    Output("filtro_ano_ted", "options"),
    Output("filtro_mes_ted", "options"),
    Output("filtro_fonte_ted", "options"),
    Output("filtro_grupo_ted", "options"),
    Output("filtro_nat_ted", "options"),
    Input("url-ted", "pathname"),
    Input("btn_reload_ted", "n_clicks"),
)
def carregar_ao_abrir_ou_recarregar(pathname, n_reload):
    if pathname != "/execucao-ted":
        raise PreventUpdate

    force = bool(n_reload) and n_reload > 0
    try:
        df, status = get_df(force=force)

        # opções
        op_uo = [{"label": u, "value": u} for u in _safe_unique_sorted(df, "Unidade Orçamentária")]

        # UG (UG EXEC é o “original”)
        if "UG EXEC" in df.columns:
            op_ug = [{"label": u, "value": u} for u in sorted(df["UG EXEC"].dropna().astype(str).unique().tolist())]
        else:
            op_ug = [{"label": u, "value": u} for u in _safe_unique_sorted(df, "UG Executora")]

        anos = _safe_unique_sorted(df, "Ano")
        op_ano = [{"label": str(int(a)), "value": int(a)} for a in anos] if anos else [{"label": str(int(ANO_PADRAO)), "value": int(ANO_PADRAO)}]

        op_mes = [{"label": m, "value": m} for m in _safe_unique_sorted(df, "Mês")]

        # Fonte (FRD original)
        if "FRD" in df.columns:
            op_fonte = [{"label": f, "value": f} for f in sorted(df["FRD"].dropna().astype(str).unique().tolist())]
        else:
            op_fonte = [{"label": f, "value": f} for f in _safe_unique_sorted(df, "Fonte Recursos Detalhada")]

        op_grupo = [{"label": g, "value": g} for g in _safe_unique_sorted(df, "GRUPO DESP")]

        # Nat (NAT DESP original)
        if "NAT DESP" in df.columns:
            op_nat = [{"label": n, "value": n} for n in sorted(df["NAT DESP"].dropna().astype(str).unique().tolist())]
        else:
            op_nat = [{"label": n, "value": n} for n in _safe_unique_sorted(df, "Natureza Despesa")]

        msg = html.Div([html.B("Dados disponíveis. "), html.Span(status)])
        return (
            {"ts": datetime.now().isoformat()},
            msg,
            op_uo,
            op_ug,
            op_ano,
            op_mes,
            op_fonte,
            op_grupo,
            op_nat,
        )
    except Exception as e:
        msg = html.Div([html.B("Falha ao carregar dados: "), html.Span(str(e))], style={"color": "crimson"})
        return dash.no_update, msg, dash.no_update, dash.no_update, dash.no_update, dash.no_update, dash.no_update, dash.no_update, dash.no_update


# --------------------------------------------------
# Callback principal (KPIs + gráficos + tabela)
# --------------------------------------------------
@dash.callback(
    Output("card-rpnpp-ted", "children"),
    Output("card-empenhado-ted", "children"),
    Output("card-liquidado-ted", "children"),
    Output("card-liq-a-pagar-ted", "children"),
    Output("card-pago-ted", "children"),
    Output("grafico_barras_grupo_ted", "figure"),
    Output("grafico_pizza_status_ted", "figure"),
    Output("tabela_execucao_ted", "data"),
    Output("tabela_execucao_ted", "page_count"),
    Output("store_pdf_ted", "data"),
    Input("store_reload_ted", "data"),
    Input("filtro_uo_ted", "value"),
    Input("filtro_ug_exec_ted", "value"),
    Input("filtro_ano_ted", "value"),
    Input("filtro_mes_ted", "value"),
    Input("filtro_fonte_ted", "value"),
    Input("filtro_grupo_ted", "value"),
    Input("filtro_nat_ted", "value"),
    Input("interval-atualizacao", "n_intervals"),
    Input("tabela_execucao_ted", "page_current"),
    Input("tabela_execucao_ted", "page_size"),
    Input("tabela_execucao_ted", "sort_by"),
)
def atualizar_painel(_reload, uo, ugexec, ano, mes, fonte, grupo, nat, n_intervals, page_current, page_size, sort_by):
    global df_base

    # Atualiza cache somente em horário permitido (08h–18h) quando o Interval dispara
    hora = dt.datetime.now().hour
    if 8 <= hora < 18 and n_intervals is not None:
        df_base, _ = get_df(force=True)
    else:
        df_base, _ = get_df(force=False)

    dff = filtrar_df(df_base, uo, ugexec, ano, mes, fonte, grupo, nat)

    # Ordenar por mês se existir
    if not dff.empty and "Mês" in dff.columns:
        try:
            dff = dff.sort_values("Mês")
        except Exception:
            pass

    kpis = calcular_kpis(dff)

    def kpi_value_style(color_hex: str):
        s = dict(KPI_VALUE_STYLE_BASE)
        s["color"] = color_hex
        return s

    def kpi_title_style(color_hex: str):
        s = dict(KPI_TITLE_STYLE)
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

    # Gráfico 1: barras (totais) no padrão UNIFEI
    totais_df = pd.DataFrame(
        {
            "Tipo": ["Inscritas em RP Não Processados", "Empenhadas", "Liquidadas", "Liq. a Pagar", "Pagas"],
            "Valor": [kpis["rpnpp"], kpis["empenhadas"], kpis["liquidadas"], kpis["liq_a_pagar"], kpis["pagas"]],
        }
    )
    color_map = {
        "Inscritas em RP Não Processados": LARANJA_RPNP,
        "Empenhadas": AZUL,
        "Liquidadas": VERMELHO,
        "Liq. a Pagar": CINZA,
        "Pagas": VERDE_PETROLEO,
    }
    fig_totais = px.bar(totais_df, x="Tipo", y="Valor", color="Tipo", color_discrete_map=color_map, text="Valor")
    fig_totais.update_traces(
        hovertemplate="<b>%{x}</b><br>R$ %{y:,.2f}<extra></extra>",
        texttemplate="R$ %{y:,.2f}",
        textposition="outside",
        cliponaxis=False,
    )
    fig_totais.update_layout(title="Despesas (TED)", xaxis_title="", yaxis_title="Valor (R$)", **_common_graph_layout())

    # Gráfico 2: barras por grupo (Pagas) no padrão UNIFEI
    if not dff.empty and "GRUPO DESP" in dff.columns and "DESPESAS PAGAS (CONTROLE EMPENHO)_VAL" in dff.columns:
        grp = (
            dff.groupby("GRUPO DESP", observed=True)["DESPESAS PAGAS (CONTROLE EMPENHO)_VAL"]
            .sum()
            .reset_index()
            .sort_values("DESPESAS PAGAS (CONTROLE EMPENHO)_VAL", ascending=False)
        )
        fig_grupo = px.bar(grp, x="GRUPO DESP", y="DESPESAS PAGAS (CONTROLE EMPENHO)_VAL", text="DESPESAS PAGAS (CONTROLE EMPENHO)_VAL")
        paleta_3 = [AZUL, VERMELHO, CINZA]
        fig_grupo.update_traces(
            marker_color=[paleta_3[i % 3] for i in range(len(grp))],
            hovertemplate="<b>%{x}</b><br>R$ %{y:,.2f}<extra></extra>",
            texttemplate="R$ %{y:,.2f}",
            textposition="outside",
            cliponaxis=False,
        )
        fig_grupo.update_layout(
            title="Despesas pagas por grupo de despesa (TED)",
            xaxis_title="Grupo",
            yaxis_title="Valor (R$)",
            **_common_graph_layout(),
        )
    else:
        fig_grupo = px.bar(title="Despesas pagas por grupo de despesa (TED)")
        fig_grupo.update_layout(**_common_graph_layout())

    # Tabela (formatação + paginação + ordenação)
    dff_display = dff.copy()

    for c in COLS_VALORES:
        if c + "_VAL" in dff_display.columns and c in dff_display.columns:
            dff_display[c] = fmt_brl_series(dff_display[c + "_VAL"])

    # Garantir colunas “alias”
    if "Fonte Recursos Detalhada" not in dff_display.columns and "FRD" in dff_display.columns:
        dff_display["Fonte Recursos Detalhada"] = dff_display["FRD"].astype(str)
    if "Natureza Despesa" not in dff_display.columns and "NAT DESP" in dff_display.columns:
        dff_display["Natureza Despesa"] = dff_display["NAT DESP"].astype(str)

    cols_ok = [c for c in COLS_TABELA if c in dff_display.columns]
    if cols_ok:
        dff_display = dff_display[cols_ok]
    else:
        dff_display = pd.DataFrame()

    # Ordenação custom
    if sort_by and isinstance(sort_by, list) and len(sort_by) > 0 and not dff.empty:
        col_sort = sort_by[0].get("column_id")
        direction = sort_by[0].get("direction", "asc")

        sort_key = col_sort
        if col_sort in COLS_VALORES and (col_sort + "_VAL") in dff.columns:
            sort_key = col_sort + "_VAL"

        if sort_key in dff.columns:
            dff = dff.sort_values(sort_key, ascending=(direction == "asc"), kind="mergesort")
            # reconstroi display após sort
            dff_display = dff.copy()
            for c in COLS_VALORES:
                if c + "_VAL" in dff_display.columns and c in dff_display.columns:
                    dff_display[c] = fmt_brl_series(dff_display[c + "_VAL"])
            if "Fonte Recursos Detalhada" not in dff_display.columns and "FRD" in dff_display.columns:
                dff_display["Fonte Recursos Detalhada"] = dff_display["FRD"].astype(str)
            if "Natureza Despesa" not in dff_display.columns and "NAT DESP" in dff_display.columns:
                dff_display["Natureza Despesa"] = dff_display["NAT DESP"].astype(str)
            cols_ok = [c for c in COLS_TABELA if c in dff_display.columns]
            dff_display = dff_display[cols_ok] if cols_ok else pd.DataFrame()

    total_rows = len(dff_display)
    page_size = int(page_size or 10)
    page_current = int(page_current or 0)
    page_count = max(1, (total_rows + page_size - 1) // page_size) if total_rows else 1

    start = page_current * page_size
    end = start + page_size
    data_table = dff_display.iloc[start:end].to_dict("records") if total_rows else []

    dados_pdf = {
        "tabela": dff_display.to_dict("records"),
        "totais": {
            "rp": float(kpis["rpnpp"]),
            "emp": float(kpis["empenhadas"]),
            "liq": float(kpis["liquidadas"]),
            "liq_pagar": float(kpis["liq_a_pagar"]),
            "pagas": float(kpis["pagas"]),
        },
        "filtros": {
            "uo": uo,
            "ugexec": ugexec,
            "ano": ano,
            "mes": mes,
            "fonte": fonte,
            "grupo": grupo,
            "nat": nat,
        },
    }

    return (
        card_rpnpp,
        card_empenhado,
        card_liquidado,
        card_liq_a_pagar,
        card_pago,
        fig_totais,
        fig_grupo,
        data_table,
        page_count,
        dados_pdf,
    )


# --------------------------------------------------
# PDF (mantém estrutura original, só consome store_pdf_ted)
# --------------------------------------------------
wrap_style = ParagraphStyle(
    name="wrap",
    fontSize=5,
    leading=6,
    spaceAfter=0,
    alignment=TA_LEFT,
)


def wrap(text):
    return Paragraph(str(text)[:150], wrap_style)


@dash.callback(
    Output("download_relatorio_ted", "data"),
    Input("btn_download_relatorio_ted", "n_clicks"),
    State("store_pdf_ted", "data"),
    prevent_initial_call=True,
)
def gerar_pdf(n, dados_pdf):
    if not n or not dados_pdf:
        raise PreventUpdate

    buffer = BytesIO()
    pagesize = landscape(letter)
    doc = SimpleDocTemplate(
        buffer,
        pagesize=pagesize,
        topMargin=0.2 * inch,
        bottomMargin=0.4 * inch,
        leftMargin=0.3 * inch,
        rightMargin=0.3 * inch,
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
                    "data_topo_ted",
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

    # Cabeçalho com logos e instituição (padrão unificado)
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
            "instituicao_ted",
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

    # Título
    titulo = Paragraph(
        "RELATÓRIO DE EXECUÇÃO DO ORÇAMENTO - TED",
        ParagraphStyle(
            "titulo_ted",
            fontSize=10,
            alignment=TA_CENTER,
            textColor="#0b2b57",
            leading=14,
            fontName="Helvetica-Bold",
        ),
    )
    story.append(titulo)
    story.append(Spacer(1, 0.1 * inch))

    # Filtros
    f = dados_pdf["filtros"]
    story.append(
        Paragraph(
            f"UO: {f['uo'] if f['uo'] else 'Todas'} | "
            f"UG Exec: {f['ugexec'] if f['ugexec'] else 'Todas'} | "
            f"Ano: {f['ano'] if f['ano'] else 'Todos'} | "
            f"Mês: {f['mes'] if f['mes'] else 'Todos'}",
            ParagraphStyle("filtros1_ted", fontSize=7, alignment=TA_LEFT),
        )
    )
    story.append(
        Paragraph(
            f"Fonte: {f['fonte'] if f['fonte'] else 'Todas'} | "
            f"Grupo: {f['grupo'] if f['grupo'] else 'Todos'} | "
            f"Natureza: {f['nat'] if f['nat'] else 'Todas'}",
            ParagraphStyle("filtros2_ted", fontSize=7, alignment=TA_LEFT),
        )
    )
    story.append(Spacer(1, 0.08 * inch))

    def fmt(v):
        return (
            f"R$ {v:,.2f}"
            .replace(",", "X")
            .replace(".", ",")
            .replace("X", ".")
        )

    tot = dados_pdf["totais"]

    # Cartões na mesma linha (5 cartões)
    cards_data = [
        ["RP Não Proc.", "Empenhadas", "Liquidadas", "Liq. a Pagar", "Pagas"],
        [
            fmt(tot["rp"]),
            fmt(tot["emp"]),
            fmt(tot["liq"]),
            fmt(tot["liq_pagar"]),
            fmt(tot["pagas"])
        ]
    ]

    tbl_cards = Table(cards_data, colWidths=[1.5 * inch] * 5)
    tbl_cards.setStyle(
        TableStyle(
            [
                ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
                ("ALIGN", (0, 0), (-1, -1), "CENTER"),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#0b2b57")),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                ("BACKGROUND", (0, 1), (-1, 1), colors.whitesmoke),
                ("TEXTCOLOR", (0, 1), (-1, 1), colors.HexColor("#0b2b57")),
                ("FONTSIZE", (0, 0), (-1, -1), 7),
                ("FONTSIZE", (0, 1), (-1, 1), 8),
                ("LEFTPADDING", (0, 0), (-1, -1), 4),
                ("RIGHTPADDING", (0, 0), (-1, -1), 4),
                ("TOPPADDING", (0, 0), (-1, -1), 6),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
            ]
        )
    )
    story.append(tbl_cards)
    story.append(Spacer(1, 0.15 * inch))

    table_data = [
        [
            "UO",
            "Fonte\nRecursos",
            "Grupo\nDespesa",
            "Natureza\nDespesa",
            "RP N.P.",
            "Empenha.",
            "Liquida.",
            "Liq. Pagar",
            "Pagas",
        ]
    ]

    for r in dados_pdf["tabela"]:
        table_data.append(
            [
                wrap(r.get("Unidade Orçamentária", "")),
                wrap(r.get("Fonte Recursos Detalhada", "")),
                wrap(r.get("GRUPO DESP", "")),
                wrap(r.get("Natureza Despesa", "")),
                wrap(r.get("DESPESAS INSCRITAS EM RP NAO PROCESSADOS", "")),
                wrap(r.get("DESPESAS EMPENHADAS (CONTROLE EMPENHO)", "")),
                wrap(r.get("DESPESAS LIQUIDADAS (CONTROLE EMPENHO)", "")),
                wrap(r.get("DESPESAS LIQUIDADAS A PAGAR(CONTROLE EMPENHO)", "")),
                wrap(r.get("DESPESAS PAGAS (CONTROLE EMPENHO)", "")),
            ]
        )

    col_widths = [
        1.2 * inch,
        1.4 * inch,
        1.1 * inch,
        1.3 * inch,
        0.75 * inch,
        0.75 * inch,
        0.75 * inch,
        0.8 * inch,
        0.75 * inch,
    ]

    tbl = Table(table_data, colWidths=col_widths)
    tbl.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#0b2b57")),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                ("GRID", (0, 0), (-1, -1), 0.3, colors.grey),
                ("ALIGN", (0, 0), (-1, -1), "LEFT"),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("WORDWRAP", (0, 0), (-1, -1), True),
                ("FONTSIZE", (0, 0), (-1, 0), 5),
                ("FONTSIZE", (0, 1), (-1, -1), 5),
                (
                    "ROWBACKGROUNDS",
                    (0, 1),
                    (-1, -1),
                    [colors.white, colors.HexColor("#FFF3E6")],
                ),
                ("LEFTPADDING", (0, 0), (-1, -1), 1),
                ("RIGHTPADDING", (0, 0), (-1, -1), 1),
                ("TOPPADDING", (0, 0), (-1, -1), 1),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 1),
            ]
        )
    )

    story.append(tbl)
    doc.build(story)
    buffer.seek(0)

    return dcc.send_bytes(buffer.getvalue(), "execucao_orcamento_ted.pdf")
