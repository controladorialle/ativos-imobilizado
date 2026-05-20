"""Consulta Rápida — busca operacional do dia a dia.

3 modos selecionáveis:
- 🔎 Por Produto: busca por nome/código, quantidade total
- 📅 Por Período: aquisições em um intervalo de datas
- 🏢 Por Centro de Resultado: ativos alocados por centro
"""
import streamlit as st
import pandas as pd
import plotly.express as px
from datetime import date
from app import sb

if "user" not in st.session_state:
    st.warning("Faça login primeiro.")
    st.stop()

st.title("🔍 Consulta Rápida")
st.caption(
    "Consulta operacional dos ativos imobilizados. "
    "Escolha o modo de busca abaixo."
)

sup = sb()

# ============================================================
# CARGA DE DADOS (cache de 60s)
# ============================================================

@st.cache_data(ttl=60)
def carrega_base():
    """Cruza lançamentos contábeis de CUSTO (débito) com itens de compra.

    Retorna DataFrame único com tudo que precisamos para os 3 modos.
    """
    # Contas de CUSTO
    pc = pd.DataFrame(
        sup.table("plano_contas")
        .select("codctactb,descrcta,categoria_id")
        .eq("tipo", "CUSTO")
        .execute().data
    )
    if pc.empty:
        return pd.DataFrame()

    # Categorias
    cats = pd.DataFrame(
        sup.table("categorias_contabeis").select("id,nome").execute().data
    ).rename(columns={"id": "categoria_id", "nome": "categoria"})

    # Lançamentos a débito (aquisições)
    codctactbs = pc["codctactb"].tolist()
    lanc_list = []
    for i in range(0, len(codctactbs), 50):
        lote = codctactbs[i:i+50]
        resp = sup.table("lancamentos_contabeis").select(
            "id,nota_chave,numdoc,dtmov,codctactb,codemp,codcencus,descrcencus,debito,parceiro_extraido"
        ).in_("codctactb", lote).gt("debito", 0).execute()
        if resp.data:
            lanc_list.append(pd.DataFrame(resp.data))

    if not lanc_list:
        return pd.DataFrame()

    lanc = pd.concat(lanc_list, ignore_index=True)
    lanc = lanc.merge(pc, on="codctactb", how="inner")
    lanc = lanc.merge(cats, on="categoria_id", how="left")

    # Itens de compra
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
        df = lanc.merge(itens, on=["nota_chave", "codemp"], how="left", suffixes=("_l", "_i"))
    else:
        df = lanc.copy()
        for c in ["item_id", "codprod", "produto_servico", "qtdneg", "un", "vlrtot",
                  "parceiro", "numnota", "dtentsai"]:
            df[c] = None

    # Converte datas
    df["dtmov"] = pd.to_datetime(df["dtmov"], errors="coerce")
    df["dtentsai"] = pd.to_datetime(df["dtentsai"], errors="coerce")
    df["data_efetiva"] = df["dtentsai"].fillna(df["dtmov"])

    return df


with st.spinner("Carregando base..."):
    df = carrega_base()

if df.empty:
    st.info("Sem dados para consultar. Importe as bases primeiro.")
    st.stop()


# ============================================================
# SELETOR DE MODO
# ============================================================

modo = st.radio(
    "**Selecione o modo de consulta:**",
    options=["🔎 Por Produto", "📅 Por Período", "🏢 Por Centro de Resultado"],
    horizontal=True,
    label_visibility="visible"
)

st.divider()


# ============================================================
# FILTROS COMUNS NA SIDEBAR
# ============================================================

st.sidebar.header("Filtros globais")

empresas_opts = sorted(df["codemp"].dropna().unique().astype(int).tolist())
empresa_sel = st.sidebar.multiselect(
    "Empresa", empresas_opts, default=empresas_opts
)

df_base = df[df["codemp"].isin(empresa_sel)].copy()


# ============================================================
# MODO 1 — POR PRODUTO
# ============================================================
if modo == "🔎 Por Produto":
    st.subheader("🔎 Busca por Produto")
    st.caption(
        "Busque um produto pelo nome ou código. Veja a quantidade total adquirida."
    )

    col_b, col_c = st.columns([3, 1])
    with col_b:
        busca = st.text_input(
            "Buscar produto (nome ou código)",
            placeholder="Ex: notebook, monitor, 28031, computador...",
            key="busca_prod"
        )
    with col_c:
        ordenar_por = st.selectbox(
            "Ordenar por",
            ["Quantidade ↓", "Valor ↓", "Nome A→Z"],
            key="ord_prod"
        )

    if not busca:
        st.info("👆 Digite algo para começar a busca.")
    else:
        # Filtra
        mask = (
            df_base["produto_servico"].str.contains(busca, case=False, na=False) |
            df_base["codprod"].astype(str).str.contains(busca, na=False)
        )
        df_busca = df_base[mask & df_base["codprod"].notna()].copy()

        if df_busca.empty:
            st.warning(f"Nenhum produto encontrado para '{busca}'.")
        else:
            # Agrupa por produto
            resumo = (
                df_busca.groupby(["codprod", "produto_servico", "un"], as_index=False)
                .agg(
                    qtd_total=("qtdneg", "sum"),
                    valor_total=("vlrtot", "sum"),
                    qtd_notas=("numnota", "nunique"),
                )
            )

            # Ordena
            if ordenar_por == "Quantidade ↓":
                resumo = resumo.sort_values("qtd_total", ascending=False)
            elif ordenar_por == "Valor ↓":
                resumo = resumo.sort_values("valor_total", ascending=False)
            else:
                resumo = resumo.sort_values("produto_servico")

            # KPIs
            k1, k2, k3 = st.columns(3)
            k1.metric(
                "Produtos encontrados",
                f"{len(resumo):,}".replace(",", ".")
            )
            k2.metric(
                "Quantidade total",
                f"{int(resumo['qtd_total'].sum()):,}".replace(",", ".")
            )
            k3.metric(
                "Valor total",
                f"R$ {resumo['valor_total'].sum():,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
            )

            st.divider()

            # Tabela
            st.dataframe(
                resumo.rename(columns={
                    "codprod": "Cód",
                    "produto_servico": "Produto",
                    "un": "Un",
                    "qtd_total": "Qtd Total",
                    "valor_total": "Valor R$",
                    "qtd_notas": "Nº Notas",
                }).style.format({
                    "Qtd Total": "{:,.0f}".format,
                    "Valor R$": "R$ {:,.2f}".format,
                }),
                use_container_width=True,
                hide_index=True,
                height=400
            )

            # Detalhamento de NFs ao escolher um produto
            st.divider()
            st.markdown("##### 🧾 Ver notas fiscais de um produto")

            opcoes = {
                f"{r['codprod']} — {r['produto_servico'][:60]}": r['codprod']
                for _, r in resumo.iterrows()
            }
            label_esc = st.selectbox(
                "Produto", options=list(opcoes.keys()), key="prod_detalhe"
            )
            codprod_esc = opcoes[label_esc]

            df_prod = df_busca[df_busca["codprod"] == codprod_esc].copy()
            detalhe = df_prod[[
                "numnota", "data_efetiva", "parceiro", "qtdneg", "un",
                "vlrtot", "descrcencus", "categoria", "codemp"
            ]].sort_values("data_efetiva", ascending=False)

            st.dataframe(
                detalhe.rename(columns={
                    "numnota": "NF",
                    "data_efetiva": "Data",
                    "parceiro": "Fornecedor",
                    "qtdneg": "Qtd",
                    "un": "Un",
                    "vlrtot": "Valor",
                    "descrcencus": "Centro de Custo",
                    "categoria": "Categoria",
                    "codemp": "Empresa",
                }).style.format({
                    "Qtd": "{:,.0f}".format,
                    "Valor": "R$ {:,.2f}".format,
                }),
                use_container_width=True,
                hide_index=True,
                height=350
            )

            # Export
            csv = resumo.to_csv(index=False).encode("utf-8")
            st.download_button(
                "📥 Exportar resumo CSV",
                csv,
                f"consulta_produto_{busca}.csv",
                "text/csv"
            )


# ============================================================
# MODO 2 — POR PERÍODO
# ============================================================
elif modo == "📅 Por Período":
    st.subheader("📅 Aquisições por Período")
    st.caption(
        "Veja tudo que foi adquirido em um intervalo de datas específico."
    )

    # Range de datas
    data_min = df_base["data_efetiva"].min().date() if pd.notna(df_base["data_efetiva"].min()) else date.today()
    data_max = df_base["data_efetiva"].max().date() if pd.notna(df_base["data_efetiva"].max()) else date.today()

    cp1, cp2, cp3 = st.columns([2, 2, 2])
    dt_ini = cp1.date_input(
        "De", value=data_min, min_value=data_min, max_value=data_max, key="dt_ini_p"
    )
    dt_fim = cp2.date_input(
        "Até", value=data_max, min_value=data_min, max_value=data_max, key="dt_fim_p"
    )

    cats_opts = sorted(df_base["categoria"].dropna().unique().tolist())
    cat_filtro = cp3.multiselect(
        "Categoria(s)", cats_opts, default=cats_opts, key="cat_filt_p"
    )

    # Filtra
    df_per = df_base[
        (df_base["data_efetiva"].dt.date >= dt_ini) &
        (df_base["data_efetiva"].dt.date <= dt_fim) &
        (df_base["categoria"].isin(cat_filtro))
    ].copy()

    if df_per.empty:
        st.warning("Sem aquisições no período/filtros selecionados.")
    else:
        # KPIs
        k1, k2, k3, k4 = st.columns(4)
        k1.metric(
            "Valor total",
            f"R$ {df_per['debito'].sum():,.0f}".replace(",", ".")
        )
        k2.metric(
            "Quantidade itens",
            f"{int(df_per['qtdneg'].fillna(0).sum()):,}".replace(",", ".")
        )
        k3.metric(
            "Notas fiscais",
            f"{df_per['numnota'].nunique():,}".replace(",", ".")
        )
        k4.metric(
            "Produtos distintos",
            f"{df_per['codprod'].nunique():,}".replace(",", ".")
        )

        st.divider()

        # Gráfico por categoria
        resumo_cat = (
            df_per.groupby("categoria", as_index=False)
            .agg(valor=("debito", "sum"))
            .sort_values("valor", ascending=True)
        )
        fig = px.bar(
            resumo_cat, x="valor", y="categoria", orientation="h",
            title=f"Aquisições por categoria ({dt_ini.strftime('%d/%m/%Y')} a {dt_fim.strftime('%d/%m/%Y')})",
            labels={"valor": "R$", "categoria": ""}
        )
        fig.update_layout(height=400)
        st.plotly_chart(fig, use_container_width=True)

        # Tabela detalhada
        st.markdown("##### Detalhamento das aquisições")
        detalhe = df_per[[
            "data_efetiva", "categoria", "numnota", "parceiro",
            "produto_servico", "qtdneg", "un", "vlrtot",
            "descrcencus", "codemp"
        ]].sort_values("data_efetiva", ascending=False)

        st.dataframe(
            detalhe.rename(columns={
                "data_efetiva": "Data",
                "categoria": "Categoria",
                "numnota": "NF",
                "parceiro": "Fornecedor",
                "produto_servico": "Produto",
                "qtdneg": "Qtd",
                "un": "Un",
                "vlrtot": "Valor",
                "descrcencus": "Centro de Custo",
                "codemp": "Emp",
            }).style.format({
                "Qtd": "{:,.0f}".format,
                "Valor": "R$ {:,.2f}".format,
            }),
            use_container_width=True,
            hide_index=True,
            height=400
        )

        # Export
        csv = detalhe.to_csv(index=False).encode("utf-8")
        st.download_button(
            "📥 Exportar período CSV",
            csv,
            f"aquisicoes_{dt_ini}_a_{dt_fim}.csv",
            "text/csv"
        )


# ============================================================
# MODO 3 — POR CENTRO DE RESULTADO
# ============================================================
elif modo == "🏢 Por Centro de Resultado":
    st.subheader("🏢 Ativos por Centro de Resultado")
    st.caption(
        "Selecione um centro de custo e veja todos os ativos alocados a ele. "
        "Linhas com produto identificado aparecem primeiro, ordenadas por mês."
    )

    centros_opts = sorted(
        df_base[df_base["descrcencus"].notna()]["descrcencus"].unique().tolist()
    )

    if not centros_opts:
        st.warning("Nenhum centro de custo encontrado.")
    else:
        centro_esc = st.selectbox(
            "Centro de custo",
            options=centros_opts,
            key="centro_sel"
        )

        df_centro = df_base[df_base["descrcencus"] == centro_esc].copy()

        if df_centro.empty:
            st.info("Sem ativos alocados nesse centro.")
        else:
            # Separa em 2 grupos
            com_produto = df_centro[df_centro["codprod"].notna()].copy()
            sem_produto = df_centro[df_centro["codprod"].isna()].copy()

            # KPIs gerais
            k1, k2, k3, k4 = st.columns(4)
            k1.metric(
                "Valor total alocado",
                f"R$ {df_centro['debito'].sum():,.0f}".replace(",", ".")
            )
            k2.metric(
                "Com produto",
                f"{len(com_produto)} ({100*len(com_produto)/max(len(df_centro),1):.0f}%)"
            )
            k3.metric(
                "Sem produto",
                f"{len(sem_produto)} ({100*len(sem_produto)/max(len(df_centro),1):.0f}%)"
            )
            k4.metric(
                "Notas fiscais",
                df_centro["numnota"].nunique()
            )

            st.divider()

            # Somatório por categoria
            st.markdown("##### 📊 Somatório por categoria")

            resumo_cat = (
                df_centro.groupby("categoria", as_index=False)
                .agg(
                    valor=("debito", "sum"),
                    qtd_itens=("qtdneg", "sum"),
                    produtos=("codprod", "nunique"),
                )
                .sort_values("valor", ascending=False)
            )

            col_g, col_t = st.columns([2, 1])
            with col_g:
                fig = px.pie(
                    resumo_cat,
                    values="valor", names="categoria",
                    title=f"Distribuição de valor — {centro_esc}",
                    hole=0.4
                )
                fig.update_layout(height=380)
                st.plotly_chart(fig, use_container_width=True)
            with col_t:
                st.dataframe(
                    resumo_cat.rename(columns={
                        "categoria": "Categoria",
                        "valor": "Valor R$",
                        "qtd_itens": "Qtd",
                        "produtos": "Produtos",
                    }).style.format({
                        "Valor R$": "R$ {:,.2f}".format,
                        "Qtd": "{:,.0f}".format,
                    }),
                    use_container_width=True,
                    hide_index=True,
                    height=380
                )

            st.divider()

            # Filtros adicionais
            cat_opcoes = ["Todas"] + resumo_cat["categoria"].tolist()
            col_f1, col_f2 = st.columns(2)
            cat_filtro_centro = col_f1.selectbox(
                "Filtrar por categoria",
                cat_opcoes,
                key="cat_centro_filt"
            )
            busca_centro = col_f2.text_input(
                "🔍 Buscar item (produto/fornecedor)",
                placeholder="Filtrar...",
                key="busca_centro"
            )

            # Função auxiliar para aplicar filtros e ordenar por mês
            def aplica_filtros(d):
                if cat_filtro_centro != "Todas":
                    d = d[d["categoria"] == cat_filtro_centro]
                if busca_centro:
                    mask = (
                        d["produto_servico"].fillna("").str.contains(busca_centro, case=False, na=False) |
                        d["codprod"].astype(str).str.contains(busca_centro, na=False) |
                        d["parceiro"].fillna("").str.contains(busca_centro, case=False, na=False)
                    )
                    d = d[mask]
                # Ordena por mês (mais recente primeiro)
                d = d.sort_values("data_efetiva", ascending=False)
                return d

            com_filt = aplica_filtros(com_produto)
            sem_filt = aplica_filtros(sem_produto)

            # ===== SEÇÃO 1: COM PRODUTO IDENTIFICADO =====
            st.markdown("### ✅ Lançamentos COM produto identificado")
            st.caption(
                f"**{len(com_filt)} lançamentos** | "
                f"Total: R$ {com_filt['vlrtot'].fillna(0).sum():,.2f}"
                .replace(",", "X").replace(".", ",").replace("X", ".")
            )

            if com_filt.empty:
                st.info("Sem lançamentos com produto para os filtros atuais.")
            else:
                # Adiciona coluna de mês para visualização
                com_filt_show = com_filt.copy()
                com_filt_show["Mes"] = com_filt_show["data_efetiva"].dt.strftime("%m/%Y")

                detalhe_com = com_filt_show[[
                    "Mes", "data_efetiva", "categoria", "codprod", "produto_servico",
                    "qtdneg", "un", "vlrtot", "numnota", "parceiro", "codemp"
                ]]

                st.dataframe(
                    detalhe_com.rename(columns={
                        "data_efetiva": "Data",
                        "categoria": "Categoria",
                        "codprod": "Cód",
                        "produto_servico": "Produto",
                        "qtdneg": "Qtd",
                        "un": "Un",
                        "vlrtot": "Valor",
                        "numnota": "NF",
                        "parceiro": "Fornecedor",
                        "codemp": "Emp",
                    }).style.format({
                        "Qtd": "{:,.0f}".format,
                        "Valor": "R$ {:,.2f}".format,
                    }),
                    use_container_width=True,
                    hide_index=True,
                    height=400
                )

            st.divider()

            # ===== SEÇÃO 2: SEM PRODUTO (LANÇAMENTOS CONTÁBEIS DIRETOS) =====
            st.markdown("### ⚠️ Lançamentos SEM produto identificado")
            st.caption(
                f"**{len(sem_filt)} lançamentos** | "
                f"Total: R$ {sem_filt['debito'].sum():,.2f}"
                .replace(",", "X").replace(".", ",").replace("X", ".") +
                " | Geralmente transferências de obra, provisões ou ajustes contábeis."
            )

            if sem_filt.empty:
                st.info("Sem lançamentos sem produto para os filtros atuais.")
            else:
                sem_filt_show = sem_filt.copy()
                sem_filt_show["Mes"] = sem_filt_show["data_efetiva"].dt.strftime("%m/%Y")

                # Para os sem produto, mostra histórico contábil em vez de produto
                detalhe_sem = sem_filt_show[[
                    "Mes", "data_efetiva", "categoria", "numdoc",
                    "parceiro_extraido", "debito", "codemp"
                ]]

                st.dataframe(
                    detalhe_sem.rename(columns={
                        "data_efetiva": "Data",
                        "categoria": "Categoria",
                        "numdoc": "Doc",
                        "parceiro_extraido": "Parceiro (histórico)",
                        "debito": "Valor",
                        "codemp": "Emp",
                    }).style.format({
                        "Valor": "R$ {:,.2f}".format,
                    }),
                    use_container_width=True,
                    hide_index=True,
                    height=300
                )

            # Export consolidado
            st.divider()
            todos_filt = pd.concat([com_filt, sem_filt], ignore_index=True)
            csv = todos_filt.to_csv(index=False).encode("utf-8")
            st.download_button(
                f"📥 Exportar centro '{centro_esc}' completo CSV",
                csv,
                f"centro_{centro_esc.replace(' ', '_').replace('/', '_')}.csv",
                "text/csv"
            )
