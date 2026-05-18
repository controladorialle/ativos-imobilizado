"""Limpeza genérica de um DataFrame vindo de XLSX cru.

Lida com tipos errados, datas como string, números com vírgula,
células vazias representadas de várias formas, espaços e encoding.
"""
import pandas as pd
import numpy as np
from unidecode import unidecode

NULOS = {"", "nan", "NaN", "NULL", "null", "None", "-", "N/A", "n/a", "#N/D"}


def normaliza_texto(s):
    """Converte para string, remove espaços extras, devolve None se vazio."""
    if pd.isna(s):
        return None
    s = str(s).strip()
    return None if s in NULOS else s


def normaliza_cgc(v):
    """Remove tudo que não é dígito; padroniza CGC/CPF."""
    if pd.isna(v):
        return None
    s = "".join(ch for ch in str(v) if ch.isdigit())
    return s or None


def to_int(v):
    """Converte para int. Lida com strings com pontos/vírgulas."""
    if pd.isna(v):
        return None
    try:
        if isinstance(v, str):
            v = v.replace(".", "").replace(",", "")
        return int(float(v))
    except (ValueError, TypeError):
        return None


def to_num(v):
    """Converte para float. Lida com formato brasileiro (1.234,56)."""
    if pd.isna(v):
        return 0.0
    if isinstance(v, str):
        v = v.replace(".", "").replace(",", ".").strip()
        if not v:
            return 0.0
    try:
        return float(v)
    except (ValueError, TypeError):
        return 0.0


def to_date(v):
    """Converte para date. dayfirst=True para formato brasileiro."""
    if pd.isna(v):
        return None
    try:
        d = pd.to_datetime(v, dayfirst=True, errors="coerce")
        return None if pd.isna(d) else d.date()
    except Exception:
        return None


def normaliza_nome(s):
    """Para comparação: minúsculo, sem acento, sem pontuação extra."""
    if not s:
        return ""
    s = unidecode(str(s)).lower()
    # Remove caracteres não alfanuméricos exceto espaço
    s = "".join(ch if ch.isalnum() or ch == " " else " " for ch in s)
    return " ".join(s.split())


def validar_colunas(df, esperadas, contexto):
    """Verifica se todas as colunas esperadas estão no DataFrame.
    Normaliza nomes de colunas para maiúsculas e sem espaços."""
    df.columns = [str(c).strip().upper() for c in df.columns]
    faltam = [c for c in esperadas if c not in df.columns]
    if faltam:
        raise ValueError(
            f"Arquivo {contexto} sem as colunas obrigatórias: {faltam}. "
            f"Colunas encontradas: {list(df.columns)}"
        )
