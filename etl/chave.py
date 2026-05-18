"""Geração da chave determinística de uma nota fiscal.

A chave combina NUMNOTA + CGC + DATA + EMPRESA em um SHA-256 truncado.
Isso permite diferenciar NFs com o mesmo número de fornecedores ou
períodos diferentes, e detectar duplicatas reais em re-importações.
"""
import hashlib


def chave_nf(numnota, cgc_cpf, dt_entsai, codemp) -> str | None:
    """Gera SHA-256 truncado em 16 caracteres a partir dos 4 campos.

    Retorna None se faltar algum campo essencial (NUMNOTA ou CODEMP).
    Quando CGC ou data faltam, usa placeholders ('SEMCGC' / 'SEMDATA')
    para ainda gerar uma chave estável.
    """
    if not numnota or codemp is None:
        return None
    cgc = cgc_cpf if cgc_cpf else "SEMCGC"
    if dt_entsai:
        try:
            dt = dt_entsai.isoformat()
        except AttributeError:
            dt = str(dt_entsai)
    else:
        dt = "SEMDATA"
    raw = f"{int(numnota)}|{cgc}|{dt}|{int(codemp)}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:16]
