"""Lê a base contábil (XLSX cru), extrai o parceiro do COMPLHIST e cruza
com o dicionário de parceiros (vindo da base de compras).

Estratégia de matching:
  1. Extrai o nome do parceiro do COMPLHIST via regex
  2. Procura match exato (após normalização) no dicionário
  3. Se não achar, calcula similaridade (SequenceMatcher)
  4. Score >= 0.85 → grava como APROXIMADO com CGC resolvido
  5. Score entre 0.60 e 0.85 → grava como APROXIMADO sem CGC e cria revisão
  6. Score < 0.60 → grava como SEM_MATCH (sem CGC)
"""
import pandas as pd
import re
from difflib import SequenceMatcher
from .limpeza import (
    validar_colunas, normaliza_texto, normaliza_nome,
    to_int, to_num, to_date
)
from .chave import chave_nf

COLUNAS = [
    "CODEMP", "REFERENCIA", "DTMOV", "CODCTACTB", "DESCRCTA", "NUMDOC",
    "COMPLHIST", "DEBITO", "CREDITO", "NUMLOTE", "NUMLANC",
    "CODCENCUS", "DESCRCENCUS", "TIPOLANCAMENTO", "USADO"
]

# Pega o nome do parceiro entre "NF NNNNN " e o sufixo "-NNNN.N"
RX_PARCEIRO = re.compile(r"NF\s+\d+\s+(.+?)\s*-\s*\d+\.?\d*\s*$", re.IGNORECASE)


def _extrai_parceiro(complhist):
    """Extrai o nome do parceiro de um histórico contábil padrão."""
    if not complhist:
        return None
    m = RX_PARCEIRO.search(complhist)
    if m:
        return m.group(1).strip()
    return None


def _eh_nf_real(numdoc):
    """Heurística: distingue uma NF real de uma data disfarçada como número.

    Casos:
      - 87704490 → NF real (8 dígitos, mas sufixo não é ano válido)
      - 1082025  → 1/8/2025 (data disfarçada)
      - 30112025 → 30/11/2025 (data disfarçada)
    """
    if not numdoc:
        return False
    try:
        n = int(numdoc)
    except (ValueError, TypeError):
        return False
    s = str(n)
    # Se termina com ano e o número anterior é mês válido, provavelmente é data
    if len(s) in (7, 8) and s[-4:] in ("2023", "2024", "2025", "2026", "2027", "2028"):
        try:
            mes = int(s[-6:-4]) if len(s) == 8 else int(s[-5:-4])
            if 1 <= mes <= 12:
                return False
        except ValueError:
            pass
    return n > 1000


def _melhor_match(alvo, nomes_norm, parc_idx):
    """Calcula similaridade contra todos os parceiros e retorna o melhor + top3."""
    scores = []
    for n in nomes_norm:
        s = SequenceMatcher(None, alvo, n).ratio()
        scores.append((s, n))
    scores.sort(reverse=True)
    if not scores:
        return None, 0.0, []
    melhor_score, melhor_nome = scores[0]
    top3 = [
        {
            "nome": parc_idx[n]["nome"],
            "codparc": int(parc_idx[n]["codparc"]),
            "score": round(s, 3)
        }
        for s, n in scores[:3]
    ]
    return melhor_nome, melhor_score, top3


def parse(arquivo_xlsx, parceiros_df):
    """Lê e processa a base contábil.

    parceiros_df: DataFrame com colunas codparc, nome, cgc_cpf, nome_norm
                  (vem do Supabase, alimentado pela base de compras).

    Retorna DataFrame com colunas adicionais:
      - tem_nf, parceiro_extraido
      - codparc_resolvido, cgc_cpf_resolvido
      - match_status (OK, APROXIMADO, SEM_MATCH, SEM_NF)
      - match_score, candidatos (top3 quando precisa revisão)
      - nota_chave
    """
    df = pd.read_excel(arquivo_xlsx, dtype=object)
    validar_colunas(df, COLUNAS, "base contábil")

    df = df[COLUNAS].copy()

    df["CODEMP"] = df["CODEMP"].apply(to_int)
    df["REFERENCIA"] = df["REFERENCIA"].apply(to_date)
    df["DTMOV"] = df["DTMOV"].apply(to_date)
    df["CODCTACTB"] = df["CODCTACTB"].apply(to_int)
    df["DESCRCTA"] = df["DESCRCTA"].apply(normaliza_texto)
    df["NUMDOC"] = df["NUMDOC"].apply(to_int)
    df["COMPLHIST"] = df["COMPLHIST"].apply(normaliza_texto)
    df["DEBITO"] = df["DEBITO"].apply(to_num)
    df["CREDITO"] = df["CREDITO"].apply(to_num)
    df["NUMLOTE"] = df["NUMLOTE"].apply(to_int)
    df["NUMLANC"] = df["NUMLANC"].apply(to_int)
    df["CODCENCUS"] = df["CODCENCUS"].apply(to_int)
    df["DESCRCENCUS"] = df["DESCRCENCUS"].apply(normaliza_texto)
    df["TIPOLANCAMENTO"] = df["TIPOLANCAMENTO"].apply(normaliza_texto)
    df["USADO"] = df["USADO"].apply(normaliza_texto)

    df["tem_nf"] = df["NUMDOC"].apply(_eh_nf_real)
    df["parceiro_extraido"] = df["COMPLHIST"].apply(_extrai_parceiro)

    # Monta o índice de parceiros (normalizado)
    if parceiros_df is None or parceiros_df.empty:
        parc_idx = {}
        nomes_norm = []
    else:
        parc_idx = {row["nome_norm"]: row for _, row in parceiros_df.iterrows()}
        nomes_norm = list(parc_idx.keys())

    resultados = []
    for _, row in df.iterrows():
        if not row["tem_nf"]:
            resultados.append({
                "codparc": None, "cgc_cpf": None,
                "status": "SEM_NF", "score": None, "candidatos": None
            })
            continue

        alvo_raw = row["parceiro_extraido"]
        if not alvo_raw:
            resultados.append({
                "codparc": None, "cgc_cpf": None,
                "status": "SEM_MATCH", "score": None, "candidatos": None
            })
            continue

        alvo = normaliza_nome(alvo_raw)

        # Match exato
        if alvo in parc_idx:
            p = parc_idx[alvo]
            resultados.append({
                "codparc": int(p["codparc"]) if pd.notna(p["codparc"]) else None,
                "cgc_cpf": p["cgc_cpf"],
                "status": "OK", "score": 1.0, "candidatos": None
            })
            continue

        # Similaridade
        if not nomes_norm:
            resultados.append({
                "codparc": None, "cgc_cpf": None,
                "status": "SEM_MATCH", "score": 0.0, "candidatos": None
            })
            continue

        melhor_nome, score, top3 = _melhor_match(alvo, nomes_norm, parc_idx)

        if score >= 0.85:
            p = parc_idx[melhor_nome]
            resultados.append({
                "codparc": int(p["codparc"]) if pd.notna(p["codparc"]) else None,
                "cgc_cpf": p["cgc_cpf"],
                "status": "APROXIMADO", "score": round(score, 3),
                "candidatos": None
            })
        elif score >= 0.60:
            resultados.append({
                "codparc": None, "cgc_cpf": None,
                "status": "APROXIMADO", "score": round(score, 3),
                "candidatos": top3
            })
        else:
            resultados.append({
                "codparc": None, "cgc_cpf": None,
                "status": "SEM_MATCH", "score": round(score, 3),
                "candidatos": None
            })

    df["codparc_resolvido"] = [r["codparc"] for r in resultados]
    df["cgc_cpf_resolvido"] = [r["cgc_cpf"] for r in resultados]
    df["match_status"] = [r["status"] for r in resultados]
    df["match_score"] = [r["score"] for r in resultados]
    df["candidatos"] = [r["candidatos"] for r in resultados]

    # Gera a chave de cruzamento usando o CGC resolvido
    df["nota_chave"] = df.apply(
        lambda r: chave_nf(
            r["NUMDOC"], r["cgc_cpf_resolvido"], r["DTMOV"], r["CODEMP"]
        ) if r["tem_nf"] else None,
        axis=1
    )

    return df
