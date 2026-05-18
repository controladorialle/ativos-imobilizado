"""Mapeia CODCTACTB para (tipo, prefixo_categoria).

Tipos:
  - CUSTO: aquisição de imobilizado (entrada como débito)
  - DEPRECIACAO: depreciação acumulada
  - AMORTIZACAO: amortização (intangíveis, benfeitorias)
  - CIAP: ajuste fiscal CIAP

Prefixos casam com a coluna 'prefixo' da tabela categorias_contabeis.
"""

PLANO_CONTAS = {
    # Terrenos
    1230101: ("CUSTO", "1.2.03.01"),
    1230102: ("CUSTO", "1.2.03.01"),
    # Edificações
    1230205: ("CUSTO", "1.2.03.02"),
    1230206: ("DEPRECIACAO", "1.2.03.02"),
    # Móveis e Utensílios
    1230301: ("CUSTO", "1.2.03.03"),
    1230302: ("DEPRECIACAO", "1.2.03.03"),
    1230311: ("CIAP", "1.2.03.03"),
    # Máquinas e Equipamentos
    1230401: ("CUSTO", "1.2.03.04"),
    1230402: ("DEPRECIACAO", "1.2.03.04"),
    1230411: ("CIAP", "1.2.03.04"),
    # Equipamentos de Informática
    1230501: ("CUSTO", "1.2.03.05"),
    1230502: ("DEPRECIACAO", "1.2.03.05"),
    1230511: ("CIAP", "1.2.03.05"),
    # Equipamentos de Comunicação
    1230601: ("CUSTO", "1.2.03.06"),
    1230602: ("DEPRECIACAO", "1.2.03.06"),
    # Instalações
    1230701: ("CUSTO", "1.2.03.07"),
    1230702: ("DEPRECIACAO", "1.2.03.07"),
    1230711: ("CIAP", "1.2.03.07"),
    # Veículos e Caminhões
    1230801: ("CUSTO", "1.2.03.08"),
    1230802: ("DEPRECIACAO", "1.2.03.08"),
    1230803: ("CUSTO", "1.2.03.08"),
    1230804: ("DEPRECIACAO", "1.2.03.08"),
    1230811: ("CIAP", "1.2.03.08"),
    # Softwares
    1230901: ("CUSTO", "1.2.03.09"),
    1230902: ("AMORTIZACAO", "1.2.03.09"),
    # Benfeitorias
    1231502: ("AMORTIZACAO", "1.2.03.15"),
    1231503: ("CUSTO", "1.2.03.15"),
    1231504: ("AMORTIZACAO", "1.2.03.15"),
    1231511: ("CIAP", "1.2.03.15"),
    1231521: ("CIAP", "1.2.03.15"),
    # Imobilizado em Andamento (Projeto Novo CDK e Consórcios)
    1231640: ("CUSTO", "1.2.03.16"),
    1231641: ("CUSTO", "1.2.03.16"),
    1231649: ("CUSTO", "1.2.03.16"),
    1231650: ("CUSTO", "1.2.03.16"),
    1231651: ("CUSTO", "1.2.03.16"),
    1231653: ("CUSTO", "1.2.03.16"),
    1231654: ("CUSTO", "1.2.03.16"),
    1231655: ("CUSTO", "1.2.03.16"),
    1231656: ("CUSTO", "1.2.03.16"),
    1231664: ("CUSTO", "1.2.03.16"),
    1231665: ("CUSTO", "1.2.03.16"),
    1231666: ("CUSTO", "1.2.03.16"),
    1231667: ("CUSTO", "1.2.03.16"),
    1231668: ("CUSTO", "1.2.03.16"),
    1231669: ("CUSTO", "1.2.03.16"),
    1231670: ("CUSTO", "1.2.03.16"),
    1231671: ("CUSTO", "1.2.03.16"),
}


def classifica(codctactb):
    """Retorna (tipo, prefixo) para o CODCTACTB dado, ou (None, None) se desconhecido."""
    if codctactb is None:
        return (None, None)
    try:
        return PLANO_CONTAS.get(int(codctactb), (None, None))
    except (ValueError, TypeError):
        return (None, None)
