"""Lê a base de compras (XLSX cru) e prepara para inserção no Supabase.

A base de compras é processada PRIMEIRO porque ela alimenta o dicionário
de parceiros (CGC_CPF + nome) usado depois pelo parser contábil.
"""
import pandas as pd
from .limpeza import (
    validar_colunas, normaliza_texto, normaliza_cgc,
    to_int, to_num, to_date
)
from .chave import chave_nf

COLUNAS = [
    "CODEMP", "CODPARC", "PARCEIRO", "CGC_CPF", "NUMNOTA", "NUNOTA",
    "DTENTSAI", "DTMOV", "CONFIRMADA", "CODTIPOPER", "DESCROPER",
    "CODPROD", "PRODUTO_SERVICO", "QTDNEG", "UN", "VLRTOT", "SEGUIMENTO"
]

# Códigos de operação que representam compra de imobilizado
OPER_IMOBILIZADO = {46, 1402, 1416, 1433, 1435, 1551, 1552, 1554, 1555}


def parse(arquivo_xlsx):
    """Lê e limpa a base de compras.

    Retorna (df_valido, df_invalido):
      - df_valido: linhas com nota_chave gerada com sucesso
      - df_invalido: linhas descartadas (sem dados mínimos)
    """
    df = pd.read_excel(arquivo_xlsx, dtype=object)
    validar_colunas(df, COLUNAS, "base de compras")

    df = df[COLUNAS].copy()

    df["CODEMP"] = df["CODEMP"].apply(to_int)
    df["CODPARC"] = df["CODPARC"].apply(to_int)
    df["PARCEIRO"] = df["PARCEIRO"].apply(normaliza_texto)
    df["CGC_CPF"] = df["CGC_CPF"].apply(normaliza_cgc)
    df["NUMNOTA"] = df["NUMNOTA"].apply(to_int)
    df["NUNOTA"] = df["NUNOTA"].apply(to_int)
    df["DTENTSAI"] = df["DTENTSAI"].apply(to_date)
    df["DTMOV"] = df["DTMOV"].apply(to_date)
    df["CODTIPOPER"] = df["CODTIPOPER"].apply(to_int)
    df["DESCROPER"] = df["DESCROPER"].apply(normaliza_texto)
    df["CODPROD"] = df["CODPROD"].apply(to_int)
    df["PRODUTO_SERVICO"] = df["PRODUTO_SERVICO"].apply(normaliza_texto)
    df["QTDNEG"] = df["QTDNEG"].apply(to_num)
    df["UN"] = df["UN"].apply(normaliza_texto)
    df["VLRTOT"] = df["VLRTOT"].apply(to_num)
    df["SEGUIMENTO"] = df["SEGUIMENTO"].apply(normaliza_texto)
    df["CONFIRMADA"] = df["CONFIRMADA"].apply(
        lambda x: True if str(x).strip().lower() == "sim" else False
    )

    df["is_imobilizado"] = df["CODTIPOPER"].isin(OPER_IMOBILIZADO)
    df["nota_chave"] = df.apply(
        lambda r: chave_nf(r["NUMNOTA"], r["CGC_CPF"], r["DTENTSAI"], r["CODEMP"]),
        axis=1
    )

    # Linhas sem chave (faltam dados essenciais) são separadas
    invalidas = df[df["nota_chave"].isna()].copy()
    validas = df.dropna(subset=["nota_chave"]).copy()

    return validas, invalidas
