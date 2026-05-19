"""Drill Down — Saldo Estático e Extrato de Movimentação por produto/categoria.

Aba 1 — Saldo Estático: o que existe hoje (aquisições - baixas associadas)
Aba 2 — Extrato: movimentações no período (aquisições + baixas)

Considera as baixas associadas na página 8 (Associar Baixas) para
deduzir corretamente o saldo dos itens baixados.
"""
import streamlit as st
import pandas as pd
import plotly.express as px
from datetime import date, timedelta
from app import sb

if "user" not in st.session_state:
    st.warning("Faça login primeiro.")
    st.stop()

st.title("🔎 Drill Down — Itens Imobilizados")
st.caption(
    "Explore os ativos por categoria → produto → nota fiscal. "
    "Considera as baixas associadas na página 'Associar Baixas'."
)

sup = sb()


# ============================================================
# FUNÇÕES DE CARGA DE DADOS
# ============================================================

@st.cache_data(ttl=60)
def carrega_aquisicoes():
    """Lançamentos contábeis a débito em contas de CUSTO, com produtos cruzados."""
    pc = pd.DataFrame(
        sup.table("plano_contas")
        .select("codctactb,descrcta,categoria_id")
        .eq("tipo", "CUSTO")
        .execute().data
    )
    if pc.empty:
        return pd.DataFrame()

    cats = pd.DataFrame(
        sup.table("categorias_contabeis").select("id,nome").execute().data
    ).rename(columns={"id": "categoria_id", "nome": "categoria"})

    # Lançamentos
    codctactbs = pc["codctactb"].tolist()
    lanc_list = []
    for i in range(0, len(codctactbs), 50):
        lote = codctactbs[i:i+50]
        resp = sup.table("lancamentos_contabeis").select(
            "id,nota_chave,numdoc,dtmov,codctactb,codemp,descrcencus,debito,parceiro_extraido"
        ).in_("codctactb", lote).gt("debito", 0).execute()
        if resp.data:
            lanc_list.append(pd.DataFrame(resp.data))

    if not lanc_list:
        return pd.DataFrame()

    lanc = pd.concat(lanc_list, ignore_index=True)
    lanc = lanc.merge(pc, on="codctactb", how="inner")
    lanc = lanc.merge(cats, on="categoria_id", how="left")

    # Itens de compra cruzados pela nota_chave
    chaves = lanc["nota_chave"].dropna().unique().tolist()
    itens_list = []
    for i in range(0, len(chaves), 50):
        lote = chaves[i:i+50]
        resp = sup.table("itens_compra").select(
            "id,nota_chave,codemp,codprod,produto_servico,qtdneg,un,vlrtot,parceiro,numnota,dtentsai"
        ).in_("nota_chave", lote).execute()
        if resp.data:
            itens_list.append(pd.DataFrame(resp.data))

    if itens_list:
        itens = pd.concat(itens_list, ignore_index=True)
        itens = itens.rename(columns={"id": "item_id"})
        cruzado = lanc.merge(itens, on=["nota_chave", "codemp"], how="left", suffixes=("_l", "_i"))
    else:
        cruzado = lanc.copy()
        for c in ["item_id", "codprod", "produto_servico", "qtdneg", "un", "vlrtot", "parceiro", "numnota", "dtentsai"]:
            cruzado[c] = None

    return cruzado


@st.cache_data(ttl=60)
def carrega_baixas_contabeis():
    """Lançamentos a crédito em contas de CUSTO (baixas)."""
    pc = pd.DataFrame(
        sup.table("plano_contas")
        .select("codctactb,categoria_id")
        .eq("tipo", "CUSTO")
        .execute().data
    )
    if pc.empty:
        return pd.DataFrame()

    cats = pd.DataFrame(
        sup.table("categorias_contabeis").select("id,nome").execute().data
    ).rename(columns={"id": "categoria_id", "nome": "categoria"})

    codctactbs = pc["codctactb"].tolist()
    baixas_list = []
    for i in range(0, len(codctactbs), 50):
        lote = codctactbs[i:i+50]
        resp = sup.table("lancamentos_contabeis").select(
            "id,dtmov,codctactb,codemp,descrcencus,credito,complhist,numdoc"
        ).in_("codctactb", lote).gt("credito", 0).execute()
        if resp.data:
            baixas_list.append(pd.DataFrame(resp.data))

    if not baixas_list:
        return pd.DataFrame()

    baixas = pd.concat(baixas_list, ignore_index=True)
    baixas = baixas.merge(pc, on="codctactb", how="inner")
    baixas = baixas.merge(cats, on="categoria_id", how="left")
    return baixas


@st.cache_data(ttl=60)
def carrega_associacoes():
    """Associações de baixa feitas na página 8."""
    resp = sup.table("baixas_associadas").select("*").execute()
    return pd.DataFrame(resp.data) if resp.data else pd.DataFrame()


# ============================================================
# CARREGA TUDO
# ============================================================

with st.spinner("Carregando dados..."):
    df_aquis = carrega_aquisicoes()
    df_baixas = carrega_baixas_contabeis()
    df_assoc = carrega_associacoes()

if df_aquis.empty:
    st.info("Sem dados de aquisição ainda. Importe as bases primeiro.")
    st.stop()

# Marca itens que foram baixados (via associação)
itens_baixados = set()
if not df_assoc.empty and "item_origem_id" in df_assoc.columns:
    itens_baixados = set(df_assoc["item_origem_id"].dropna().astype(int).tolist())

df_aquis["foi_baixado"] = df_aquis["item_id"].apply(
    lambda x: int(x) in itens_baixados if pd.notna(x) else False
)

# ============================================================
# FILTROS GERAIS (sidebar)
# ============================================================

st.sidebar.header("Filtros gerais")

empresas = sorted(df_aquis["codemp"].dropna().unique())
empresa_sel = st.sidebar.multiselect("Empresa", empresas, default=list(empresas))

centros = sorted(df_aquis["descrcencus"].dropna().unique())
centro_sel = st.sidebar.multiselect(
    "Centro de custo", centros, default=list(centros)
)

# Aplica filtros
df_aquis_f = df_aquis[
    df_aquis["codemp"].isin(empresa_sel) &
    df_aquis["descrcencus"].fillna("").isin(centro_sel + [""])
].copy()

df_baixas_f = pd.DataFrame()
if not df_baixas.empty:
    df_baixas_f = df_baixas[
        df_baixas["codemp"].isin(empresa_sel) &
        df_baixas["descrcencus"].fillna("").isin(centro_sel + [""])
    ].copy()


# ============================================================
# 2 ABAS
# ============================================================

tab_saldo, tab_extrato = st.tabs([
    "📋 Saldo Estático",
    "📊 Extrato de Movimentação"
])


# ============================================================
# ABA 1 — SALDO ESTÁTICO
# ============================================================
with tab_saldo:
    st.markdown(
        "**O que existe hoje** — aquisições acumuladas, descontando o que foi "
        "baixado (somente baixas com vínculo de item feito na página 'Associar Baixas')."
    )

    # Aquisições ativas (não baixadas)
    df_ativos = df_aquis_f[~df_aquis_f["foi_baixado"]].copy()
    df_baixados = df_aquis_f[df_aquis_f["foi_baixado"]].copy()

    # KPIs
    c1, c2, c3, c4 = st.columns(4)
    c1.metric(
        "Valor ativo (aquisição)",
        f"R$ {df_ativos['debito'].sum():,.0f}".replace(",", ".")
    )
    c2.metric(
        "Valor baixado (associado)",
        f"R$ {df_baixados['debito'].sum():,.0f}".replace(",", ".")
    )

    # Baixas contábeis ainda não associadas a item
    valor_baixas_nao_associadas = 0.0
    if not df_baixas_f.empty:
        baixas_associadas_ids = set(df_assoc["lanc_baixa_id"].tolist()) if not df_assoc.empty else set()
        nao_assoc = df_baixas_f[~df_baixas_f["id"].isin(baixas_associadas_ids)]
        valor_baixas_nao_associadas = nao_assoc["credito"].sum()
    c3.metric(
        "Baixas pendentes assoc.",
        f"R$ {valor_baixas_nao_associadas:,.0f}".replace(",", ".")
    )

    c4.metric("Lançamentos ativos", len(df_ativos))

    if valor_baixas_nao_associadas > 0:
        st.warning(
            f"⚠️ Existem R$ {valor_baixas_nao_associadas:,.2f} em baixas contábeis "
            "ainda **não associadas** a itens específicos. Vá em **Associar Baixas** "
            "para vincular essas baixas e ter o saldo correto."
        )

    st.divider()

    # NÍVEL 1 — Categorias
    st.subheader("📊 Nível 1 — Categorias")

    resumo_cat = (
        df_ativos.groupby("categoria", as_index=False)
        .agg(
            qtd_itens=("item_id", "count"),
            produtos_unicos=("codprod", "nunique"),
            valor_total=("debito", "sum"),
        )
        .sort_values("valor_total", ascending=False)
    )

    if resumo_cat.empty:
        st.info("Sem dados para os filtros.")
        st.stop()

    col_g, col_t = st.columns([2, 1])
    with col_g:
        fig = px.bar(
            resumo_cat.sort_values("valor_total"),
            x="valor_total", y="categoria", orientation="h",
            title="Valor ativo por categoria (R$)",
            labels={"valor_total": "Valor (R$)", "categoria": ""}
        )
        fig.update_layout(height=400)
        st.plotly_chart(fig, use_container_width=True)
    with col_t:
        st.dataframe(
            resumo_cat.style.format({"valor_total": "R$ {:,.2f}".format}),
            use_container_width=True, hide_index=True
        )

    st.divider()

    # NÍVEL 2 — Produtos da categoria
    st.subheader("📦 Nível 2 — Produtos da categoria")

    categoria_escolhida = st.selectbox(
        "Categoria", options=resumo_cat["categoria"].tolist(), key="cat_saldo"
    )

    df_cat_ativos = df_ativos[df_ativos["categoria"] == categoria_escolhida].copy()
    df_cat_baixados = df_baixados[df_baixados["categoria"] == categoria_escolhida].copy()

    # Sem cruzamento em compras
    sem_detalhe = df_cat_ativos[df_cat_ativos["codprod"].isna()]
    if not sem_detalhe.empty:
        st.info(
            f"💡 {len(sem_detalhe)} lançamentos sem detalhe na base de compras "
            f"(R$ {sem_detalhe['debito'].sum():,.2f}). "
            "Geralmente provisões, juros capitalizados ou transferências de obra."
        )

    resumo_prod = (
        df_cat_ativos[df_cat_ativos["codprod"].notna()]
        .groupby(["codprod", "produto_servico"], as_index=False)
        .agg(
            qtd_total=("qtdneg", "sum"),
            valor_total=("vlrtot", "sum"),
            qtd_notas=("numnota", "nunique"),
            un=("un", "first"),
        )
        .sort_values("valor_total", ascending=False)
    )

    # Conta quantos foram baixados desse produto
    if not df_cat_baixados.empty:
        baixados_count = df_cat_baixados.groupby("codprod").size().rename("qtd_baixados")
        resumo_prod = resumo_prod.merge(baixados_count, on="codprod", how="left")
        resumo_prod["qtd_baixados"] = resumo_prod["qtd_baixados"].fillna(0).astype(int)
    else:
        resumo_prod["qtd_baixados"] = 0

    st.write(f"**{len(resumo_prod)} produtos ativos** em **{categoria_escolhida}**")

    busca = st.text_input(
        "🔍 Buscar produto",
        placeholder="Ex: monitor, notebook, impressora...",
        key="busca_saldo"
    )
    if busca:
        resumo_prod = resumo_prod[
            resumo_prod["produto_servico"].str.contains(busca, case=False, na=False)
        ]

    ca, cb = st.columns(2)
    ca.metric(
        "Quantidade ativa",
        f"{int(resumo_prod['qtd_total'].sum()):,}".replace(",", ".")
    )
    cb.metric(
        "Valor ativo",
        f"R$ {resumo_prod['valor_total'].sum():,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    )

    st.dataframe(
        resumo_prod.rename(columns={
            "codprod": "Cód.",
            "produto_servico": "Produto",
            "qtd_total": "Qtd Ativa",
            "qtd_baixados": "Já Baixados",
            "un": "Un",
            "valor_total": "Valor R$",
            "qtd_notas": "Nº Notas",
        }).style.format({
            "Qtd Ativa": "{:,.0f}".format,
            "Já Baixados": "{:,.0f}".format,
            "Valor R$": "R$ {:,.2f}".format,
        }),
        use_container_width=True, hide_index=True, height=400
    )

    st.divider()

    # NÍVEL 3 — Notas fiscais do produto
    st.subheader("📝 Nível 3 — Notas fiscais do produto")

    if resumo_prod.empty:
        st.info("Sem produtos.")
    else:
        opcoes = {
            f"{r['codprod']} — {r['produto_servico']}": r['codprod']
            for _, r in resumo_prod.iterrows()
        }
        prod_label = st.selectbox(
            "Produto", options=list(opcoes.keys()), key="prod_saldo"
        )
        codprod_esc = opcoes[prod_label]

        # Mostra itens (ativos e baixados separados)
        df_prod_at = df_cat_ativos[df_cat_ativos["codprod"] == codprod_esc].copy()
        df_prod_bx = df_cat_baixados[df_cat_baixados["codprod"] == codprod_esc].copy()

        df_prod_at["Status"] = "✅ Ativo"
        df_prod_bx["Status"] = "❌ Baixado"

        detalhe = pd.concat([df_prod_at, df_prod_bx])[
            ["Status", "numnota", "dtentsai", "parceiro", "qtdneg", "un", "vlrtot", "descrcencus", "codemp"]
        ].sort_values("dtentsai", ascending=False)

        c_a, c_b, c_c = st.columns(3)
        c_a.metric("Ativos", len(df_prod_at))
        c_b.metric("Baixados", len(df_prod_bx))
        c_c.metric(
            "Valor ativo",
            f"R$ {df_prod_at['vlrtot'].sum():,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
        )

        st.dataframe(
            detalhe.rename(columns={
                "numnota": "NF", "dtentsai": "Data", "parceiro": "Fornecedor",
                "qtdneg": "Qtd", "un": "Un", "vlrtot": "Valor",
                "descrcencus": "Centro de Custo", "codemp": "Empresa",
            }).style.format({
                "Qtd": "{:,.0f}".format,
                "Valor": "R$ {:,.2f}".format,
            }),
            use_container_width=True, hide_index=True,
        )

        csv = detalhe.to_csv(index=False).encode("utf-8")
        st.download_button(
            "📥 Exportar CSV",
            csv,
            f"saldo_{codprod_esc}.csv",
            "text/csv"
        )


# ============================================================
# ABA 2 — EXTRATO DE MOVIMENTAÇÃO
# ============================================================
with tab_extrato:
    st.markdown(
        "**Movimentação no período** — aquisições (entradas) e baixas (saídas) "
        "lançadas em cada categoria/produto."
    )

    # Filtro de período
    st.markdown("##### Período")

    # Determina range
    datas_aquis = df_aquis_f["dtmov"].dropna()
    datas_baixas = df_baixas_f["dtmov"].dropna() if not df_baixas_f.empty else pd.Series([])

    todas_datas = pd.concat([
        pd.to_datetime(datas_aquis, errors="coerce"),
        pd.to_datetime(datas_baixas, errors="coerce")
    ]).dropna()

    if todas_datas.empty:
        st.info("Sem dados.")
        st.stop()

    data_min = todas_datas.min().date()
    data_max = todas_datas.max().date()

    cp1, cp2 = st.columns(2)
    dt_ini = cp1.date_input("De", value=data_min, min_value=data_min, max_value=data_max)
    dt_fim = cp2.date_input("Até", value=data_max, min_value=data_min, max_value=data_max)

    tipo_mov = st.multiselect(
        "Tipo de movimentação",
        ["AQUISICAO", "BAIXA"],
        default=["AQUISICAO", "BAIXA"]
    )

    # Filtra aquisições por período
    df_aquis_p = df_aquis_f[
        (pd.to_datetime(df_aquis_f["dtmov"], errors="coerce").dt.date >= dt_ini) &
        (pd.to_datetime(df_aquis_f["dtmov"], errors="coerce").dt.date <= dt_fim)
    ].copy()

    # Filtra baixas por período
    df_baixas_p = pd.DataFrame()
    if not df_baixas_f.empty:
        df_baixas_p = df_baixas_f[
            (pd.to_datetime(df_baixas_f["dtmov"], errors="coerce").dt.date >= dt_ini) &
            (pd.to_datetime(df_baixas_f["dtmov"], errors="coerce").dt.date <= dt_fim)
        ].copy()

    # KPIs
    c1, c2, c3 = st.columns(3)
    val_aq = df_aquis_p["debito"].sum() if "AQUISICAO" in tipo_mov else 0
    val_bx = df_baixas_p["credito"].sum() if not df_baixas_p.empty and "BAIXA" in tipo_mov else 0

    c1.metric(
        "Aquisições no período",
        f"R$ {val_aq:,.0f}".replace(",", ".")
    )
    c2.metric(
        "Baixas no período",
        f"R$ {val_bx:,.0f}".replace(",", ".")
    )
    c3.metric(
        "Movimento líquido",
        f"R$ {val_aq - val_bx:,.0f}".replace(",", ".")
    )

    st.divider()

    # NÍVEL 1 — Movimentação por categoria
    st.subheader("📊 Movimentação por categoria")

    aq_cat = (
        df_aquis_p.groupby("categoria", as_index=False)["debito"].sum()
        .rename(columns={"debito": "aquisicao"})
    ) if "AQUISICAO" in tipo_mov else pd.DataFrame(columns=["categoria", "aquisicao"])

    bx_cat = (
        df_baixas_p.groupby("categoria", as_index=False)["credito"].sum()
        .rename(columns={"credito": "baixa"})
    ) if (not df_baixas_p.empty and "BAIXA" in tipo_mov) else pd.DataFrame(columns=["categoria", "baixa"])

    mov_cat = aq_cat.merge(bx_cat, on="categoria", how="outer").fillna(0)
    mov_cat["liquido"] = mov_cat["aquisicao"] - mov_cat["baixa"]
    mov_cat = mov_cat.sort_values("aquisicao", ascending=True)

    if not mov_cat.empty:
        fig = px.bar(
            mov_cat,
            x=["aquisicao", "baixa"], y="categoria",
            orientation="h",
            title="Aquisições vs Baixas por categoria no período",
            labels={"value": "R$", "variable": "Tipo", "categoria": ""},
            barmode="group"
        )
        fig.update_layout(height=400)
        st.plotly_chart(fig, use_container_width=True)

        st.dataframe(
            mov_cat.style.format({
                "aquisicao": "R$ {:,.2f}".format,
                "baixa": "R$ {:,.2f}".format,
                "liquido": "R$ {:,.2f}".format,
            }),
            use_container_width=True, hide_index=True
        )

    st.divider()

    # NÍVEL 2 — Extrato detalhado
    st.subheader("📝 Extrato detalhado por categoria")

    cat_esc_ext = st.selectbox(
        "Categoria",
        options=mov_cat["categoria"].tolist() if not mov_cat.empty else [],
        key="cat_ext"
    )

    # Aquisições da categoria
    aq_det = df_aquis_p[df_aquis_p["categoria"] == cat_esc_ext].copy()
    aq_det["Movimento"] = "🟢 AQUISIÇÃO"
    aq_det["Valor"] = aq_det["debito"]
    aq_det["Data"] = aq_det["dtmov"]
    aq_det["Detalhe"] = aq_det["produto_servico"].fillna("(sem detalhe em compras)")
    aq_det["NF"] = aq_det["numdoc"]
    aq_det["Parceiro"] = aq_det["parceiro"].fillna(aq_det["parceiro_extraido"])

    # Baixas da categoria
    if not df_baixas_p.empty and "BAIXA" in tipo_mov:
        bx_det = df_baixas_p[df_baixas_p["categoria"] == cat_esc_ext].copy()
        bx_det["Movimento"] = "🔴 BAIXA"
        bx_det["Valor"] = bx_det["credito"]
        bx_det["Data"] = bx_det["dtmov"]
        bx_det["Detalhe"] = bx_det["complhist"].fillna("(sem histórico)")
        bx_det["NF"] = bx_det["numdoc"]
        bx_det["Parceiro"] = "—"
        bx_det["Qtd"] = None
        bx_det["un"] = None
        bx_det["descrcencus"] = bx_det.get("descrcencus")
    else:
        bx_det = pd.DataFrame()

    if "AQUISICAO" not in tipo_mov:
        aq_det = pd.DataFrame()

    cols_extrato = ["Data", "Movimento", "Detalhe", "NF", "Parceiro", "qtdneg", "un", "Valor", "descrcencus", "codemp"]

    if aq_det.empty:
        aq_visivel = pd.DataFrame(columns=cols_extrato)
    else:
        aq_visivel = aq_det.rename(columns={"qtdneg": "qtdneg"})[cols_extrato]

    if bx_det.empty:
        bx_visivel = pd.DataFrame(columns=cols_extrato)
    else:
        bx_visivel = bx_det[cols_extrato]

    extrato = pd.concat([aq_visivel, bx_visivel], ignore_index=True)
    extrato = extrato.sort_values("Data", ascending=False)

    st.write(f"**{len(extrato)} movimentações** em **{cat_esc_ext}** entre {dt_ini} e {dt_fim}")

    st.dataframe(
        extrato.rename(columns={
            "qtdneg": "Qtd", "un": "Un",
            "descrcencus": "Centro de Custo", "codemp": "Empresa",
        }).style.format({
            "Qtd": "{:,.0f}".format,
            "Valor": "R$ {:,.2f}".format,
        }),
        use_container_width=True, hide_index=True, height=500
    )

    csv = extrato.to_csv(index=False).encode("utf-8")
    st.download_button(
        "📥 Exportar extrato CSV",
        csv,
        f"extrato_{cat_esc_ext}_{dt_ini}_{dt_fim}.csv",
        "text/csv"
    )
