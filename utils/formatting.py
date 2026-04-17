from __future__ import annotations

import pandas as pd


def parse_brl_value(value) -> float:
    if isinstance(value, str):
        normalized = value.replace("R$", "", 1).strip()
        normalized = normalized.replace("\u00A0", " ").strip()
        normalized = normalized.replace(".", "").replace(",", ".")
        return float(normalized) if normalized not in ["", "-"] else 0.0
    return float(value) if pd.notna(value) else 0.0


def parse_brl_series(series: pd.Series | None) -> pd.Series:
    if series is None:
        return pd.Series(dtype="float64")

    out = series.astype(str)
    out = out.str.replace("R$", "", regex=False).str.strip()
    out = out.str.replace("\u00A0", " ", regex=False).str.strip()
    out = out.replace({"": "0", "-": "0", "nan": "0", "None": "0"})
    out = out.str.extract(r"([-+]?\d[\d\.,]*)", expand=False).fillna("0")

    mask_duplo = out.str.contains(r"\.") & out.str.contains(r",")
    out.loc[mask_duplo] = (
        out.loc[mask_duplo]
        .str.replace(".", "", regex=False)
        .str.replace(",", ".", regex=False)
    )

    mask_virg = (~mask_duplo) & out.str.contains(",")
    out.loc[mask_virg] = out.loc[mask_virg].str.replace(",", ".", regex=False)

    return pd.to_numeric(out, errors="coerce").fillna(0.0).astype("float64")


def format_brl(value) -> str:
    try:
        numeric = float(value)
    except Exception:
        numeric = 0.0
    return f"R$ {numeric:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


def format_brl_series(series: pd.Series) -> pd.Series:
    normalized = pd.to_numeric(series, errors="coerce").fillna(0.0)
    out = normalized.map(lambda v: f"{v:,.2f}")
    out = (
        out.str.replace(",", "X", regex=False)
        .str.replace(".", ",", regex=False)
        .str.replace("X", ".", regex=False)
    )
    return "R$ " + out
