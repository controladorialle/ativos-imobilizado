"""Consulta Rápida — busca operacional do dia a dia.

4 modos selecionáveis:
- 🔎 Por Produto: busca por nome/código, quantidade total (com filtro multi de conta contábil/projeto)
- 📅 Por Período: aquisições em um intervalo de datas
- 🏢 Por Centro de Resultado: ativos alocados por centro
- 📒 Por Conta Contábil (Razão): razão analítico de uma conta — débito, crédito, saldo acumulado
"""
import streamlit as st
import pandas as pd
import plotly.express as px
from datetime import date
from app import sb
from utils.auth import requer_perfil

# Bloqueia acesso: admin, editor e leitor podem ver
requer_perfil(["admin", "editor", "leitor"])

st.title("🔍 Consulta Rápida")
st.caption(
    "Consulta operacional dos ativos imobilizados. "
    "Escolha o modo de busca abaixo."
)

sup = sb()

# ============================================================
# CONFIGURAÇÕES
# ============================================================
MIN_CHARS_BUSCA = 3  # mínimo de caracteres para acionar busca por texto
FMT_DATA_BR = "DD/MM/YYYY"  # formato de data brasileiro

# ============================================================
# CARGA DE DADOS (cache de 60s)
# ============================================================

@st.cache_data(ttl=60)
def carrega_base():
    """Cruza lançamentos contábeis de CUSTO (débito) com itens de compra."""
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

    df["dtmov"] = pd.to_datetime(df["dtmov"], errors="coerce")
    df["dtentsai"] = pd.to_datetime(df["dtentsai"], errors="coerce")
    df["data_efetiva"] = df["dtentsai"].fillna(df["dtmov"])
    return df


@st.cache_data(ttl=60)
def lista_contas_com_lancamento():
    """Retorna DataFrame com todas as contas que TÊM lançamento na contabilidade.

    Pega direto de lancamentos_contabeis — não depende de plano_contas estar
    sincronizado. Conta nova classificada pela contabilidade aparece aqui
    automaticamente assim que houver o primeiro lançamento.

    Também identifica contas órfãs (em lancamentos mas não em plano_contas)
    para o usuário pedir classificação à contabilidade.
    """
    # Paginação explícita — Supabase limita a 1000 por padrão
    # e a tabela de lançamentos tem milhares de linhas
    all_rows = []
    page_size = 1000
    offset = 0
    while True:
        resp = (
            sup.table("lancamentos_contabeis")
            .select("codctactb,descrcta")
            .not_.is_("codctactb", "null")
            .range(offset, offset + page_size - 1)
            .execute()
        )
        if not resp.data:
            break
        all_rows.extend(resp.data)
        if len(resp.data) < page_size:
            break
        offset += page_size

    if not all_rows:
        return pd.DataFrame(columns=["codctactb", "descrcta", "no_plano"]), pd.DataFrame()

    df_contas = (
        pd.DataFrame(all_rows)
        .drop_duplicates(subset=["codctactb"])
        .sort_values("descrcta")
        .reset_index(drop=True)
    )

    # Cruza com plano_contas pra identificar órfãs
    plano = sup.table("plano_contas").select("codctactb").execute()
    contas_no_plano = set()
    if plano.data:
        contas_no_plano = {p["codctactb"] for p in plano.data}

    df_contas["no_plano"] = df_contas["codctactb"].isin(contas_no_plano)
    orfas = df_contas[~df_contas["no_plano"]].copy()

    return df_contas, orfas


@st.cache_data(ttl=60)
def carrega_razao(codctactb: int, empresas: tuple):
    """Carrega TODOS os lançamentos (débito e crédito) de uma conta específica.

    Diferente de carrega_base, esta função:
    - Não filtra por tipo='CUSTO' em plano_contas
    - Não filtra debito > 0 (traz crédito também)
    - Aceita filtro de empresas
    """
    query = sup.table("lancamentos_contabeis").select(
        "id,dtmov,numdoc,complhist,codcencus,descrcencus,"
        "parceiro_extraido,debito,credito,codemp"
    ).eq("codctactb", codctactb)

    if empresas:
        query = query.in_("codemp", list(empresas))

    resp = query.execute()
    if not resp.data:
        return pd.DataFrame()

    df = pd.DataFrame(resp.data)
    df["dtmov"] = pd.to_datetime(df["dtmov"], errors="coerce")
    df["debito"] = pd.to_numeric(df["debito"], errors="coerce").fillna(0)
    df["credito"] = pd.to_numeric(df["credito"], errors="coerce").fillna(0)
    df = df.sort_values(["dtmov", "id"]).reset_index(drop=True)
    df["saldo_acumulado"] = (df["debito"] - df["credito"]).cumsum()
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
    options=[
        "🔎 Por Produto",
        "📅 Por Período",
        "🏢 Por Centro de Resultado",
        "📒 Por Conta Contábil (Razão)",
    ],
    horizontal=True,
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
    st.caption("Busque um produto pelo nome ou código. Veja a quantidade total adquirida.")

    # ----- Filtro de conta contábil/projeto (multi) -----
    contas_disponiveis = (
        df_base[["codctactb", "descrcta"]]
        .dropna()
        .drop_duplicates()
        .sort_values("descrcta")
    )
    contas_labels = {
        f"{int(r['codctactb'])} — {r['descrcta']}": int(r['codctactb'])
        for _, r in contas_disponiveis.iterrows()
    }

    contas_escolhidas_labels = st.multiselect(
        "🏷️ Filtrar por conta contábil / projeto",
        options=list(contas_labels.keys()),
        default=[],
        placeholder="Todas as contas (sem filtro)",
        help=(
            "Selecione uma ou mais contas para restringir a busca. "
            "Útil para isolar produtos de um projeto específico "
            "(ex: 'Projeto Novo CDK-Maquinas e Equipamentos')."
        )
    )

    if contas_escolhidas_labels:
        codcts_filtro = [contas_labels[lbl] for lbl in contas_escolhidas_labels]
        df_base_prod = df_base[df_base["codctactb"].isin(codcts_filtro)].copy()
        st.caption(
            f"📌 Filtrando por {len(codcts_filtro)} conta(s) — "
            f"{len(df_base_prod)} lançamentos no escopo."
        )
    else:
        df_base_prod = df_base.copy()

    # ----- Busca de texto -----
    col_b, col_c = st.columns([3, 1])
    busca = col_b.text_input(
        f"Buscar produto (nome ou código) — mínimo {MIN_CHARS_BUSCA} caracteres",
        placeholder="Ex: computador (acha 'microcomputador'), monitor, 28031...",
        key="busca_prod",
        help=(
            f"Pressione Enter após digitar. A busca casa em qualquer posição do nome "
            f"(ex: 'computador' encontra 'microcomputador'). Mínimo {MIN_CHARS_BUSCA} caracteres."
        )
    )
    ordenar_por = col_c.selectbox(
        "Ordenar por",
        ["Quantidade ↓", "Valor ↓", "Nome A→Z"],
        key="ord_prod"
    )

    if not busca:
        st.info(f"👆 Digite pelo menos {MIN_CHARS_BUSCA} caracteres e pressione Enter.")
    elif len(busca.strip()) < MIN_CHARS_BUSCA:
        st.warning(
            f"⚠️ Digite pelo menos {MIN_CHARS_BUSCA} caracteres "
            f"(você digitou {len(busca.strip())})."
        )
    else:
        mask = (
            df_base_prod["produto_servico"].fillna("").str.contains(busca, case=False, na=False) |
            df_base_prod["codprod"].astype(str).str.contains(busca, na=False)
        )
        df_busca = df_base_prod[mask & df_base_prod["codprod"].notna()].copy()

        if df_busca.empty:
            st.warning(f"Nenhum produto encontrado para '{busca}'.")
        else:
            resumo = (
                df_busca.groupby(["codprod", "produto_servico", "un"], as_index=False)
                .agg(
                    qtd_total=("qtdneg", "sum"),
                    valor_total=("vlrtot", "sum"),
                    qtd_notas=("numnota", "nunique"),
                )
            )

            if ordenar_por == "Quantidade ↓":
                resumo = resumo.sort_values("qtd_total", ascending=False)
            elif ordenar_por == "Valor ↓":
                resumo = resumo.sort_values("valor_total", ascending=False)
            else:
                resumo = resumo.sort_values("produto_servico")

            k1, k2, k3 = st.columns(3)
            k1.metric("Produtos encontrados", f"{len(resumo):,}".replace(",", "."))
            k2.metric(
                "Quantidade total",
                f"{int(resumo['qtd_total'].sum()):,}".replace(",", ".")
            )
            k3.metric(
                "Valor total",
                f"R$ {resumo['valor_total'].sum():,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
            )

            st.divider()

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

            st.divider()
            st.markdown("##### 🧾 Ver notas fiscais de um produto")

            opcoes = {
                f"{r['codprod']} — {r['produto_servico'][:60]}": r['codprod']
                for _, r in resumo.iterrows()
            }
            label_esc = st.selectbox("Produto", options=list(opcoes.keys()), key="prod_detalhe")
            codprod_esc = opcoes[label_esc]

            df_prod = df_busca[df_busca["codprod"] == codprod_esc].copy()
            detalhe = df_prod[[
                "numnota", "data_efetiva", "parceiro", "qtdneg", "un",
                "vlrtot", "descrcencus", "categoria", "descrcta", "codemp"
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
                    "descrcta": "Conta Contábil",
                    "codemp": "Empresa",
                }).style.format({
                    "Qtd": "{:,.0f}".format,
                    "Valor": "R$ {:,.2f}".format,
                }),
                use_container_width=True,
                hide_index=True,
                height=350,
                column_config={
                    "Data": st.column_config.DateColumn(format=FMT_DATA_BR),
                }
            )

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
    st.caption("Veja tudo que foi adquirido em um intervalo de datas específico.")

    data_min = df_base["data_efetiva"].min().date() if pd.notna(df_base["data_efetiva"].min()) else date.today()
    data_max = df_base["data_efetiva"].max().date() if pd.notna(df_base["data_efetiva"].max()) else date.today()

    cp1, cp2, cp3 = st.columns([2, 2, 2])
    dt_ini = cp1.date_input(
        "De", value=data_min, min_value=data_min, max_value=data_max,
        key="dt_ini_p", format=FMT_DATA_BR
    )
    dt_fim = cp2.date_input(
        "Até", value=data_max, min_value=data_min, max_value=data_max,
        key="dt_fim_p", format=FMT_DATA_BR
    )
    cats_opts = sorted(df_base["categoria"].dropna().unique().tolist())
    cat_filtro = cp3.multiselect("Categoria(s)", cats_opts, default=cats_opts, key="cat_filt_p")

    df_per = df_base[
        (df_base["data_efetiva"].dt.date >= dt_ini) &
        (df_base["data_efetiva"].dt.date <= dt_fim) &
        (df_base["categoria"].isin(cat_filtro))
    ].copy()

    if df_per.empty:
        st.warning("Sem aquisições no período/filtros selecionados.")
    else:
        k1, k2, k3, k4 = st.columns(4)
        k1.metric("Valor total", f"R$ {df_per['debito'].sum():,.0f}".replace(",", "."))
        k2.metric(
            "Quantidade itens",
            f"{int(df_per['qtdneg'].fillna(0).sum()):,}".replace(",", ".")
        )
        k3.metric("Notas fiscais", f"{df_per['numnota'].nunique():,}".replace(",", "."))
        k4.metric("Produtos distintos", f"{df_per['codprod'].nunique():,}".replace(",", "."))

        st.divider()

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
            height=400,
            column_config={
                "Data": st.column_config.DateColumn(format=FMT_DATA_BR),
            }
        )

        csv = detalhe.to_csv(index=False).encode("utf-8")
        st.download_button(
            "📥 Exportar período CSV",
            csv,
            f"aquisicoes_{dt_ini}_a_{dt_fim}.csv",
            "text/csv"
        )


# ============================================================
# MODO 3 — POR CENTRO DE RESULTADO (com produto primeiro)
# ============================================================
elif modo == "🏢 Por Centro de Resultado":
    st.subheader("🏢 Ativos por Centro de Resultado")
    st.caption(
        "Selecione um centro de custo e veja todos os ativos alocados a ele. "
        "Linhas com produto identificado aparecem primeiro, ordenadas por mês (mais recente)."
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
            com_produto = df_centro[df_centro["codprod"].notna()].copy()
            sem_produto = df_centro[df_centro["codprod"].isna()].copy()

            # KPIs
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
            k4.metric("Notas fiscais", df_centro["numnota"].nunique())

            st.divider()

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

            # Filtros
            cat_opcoes = ["Todas"] + resumo_cat["categoria"].tolist()
            col_f1, col_f2 = st.columns(2)
            cat_filtro_centro = col_f1.selectbox(
                "Filtrar por categoria",
                cat_opcoes,
                key="cat_centro_filt"
            )
            busca_centro = col_f2.text_input(
                "🔍 Buscar item (produto/fornecedor)",
                placeholder=f"Filtrar (mín. {MIN_CHARS_BUSCA} chars)...",
                key="busca_centro",
                help=(
                    f"Busca por substring (ex: 'computador' encontra 'microcomputador'). "
                    f"Mínimo {MIN_CHARS_BUSCA} caracteres."
                )
            )

            # Valida mínimo de caracteres na busca
            busca_centro_efetiva = (
                busca_centro if busca_centro and len(busca_centro.strip()) >= MIN_CHARS_BUSCA
                else ""
            )
            if busca_centro and len(busca_centro.strip()) < MIN_CHARS_BUSCA:
                st.caption(
                    f"⚠️ Busca ignorada — digite pelo menos {MIN_CHARS_BUSCA} caracteres."
                )

            def aplica_filtros(d):
                if cat_filtro_centro != "Todas":
                    d = d[d["categoria"] == cat_filtro_centro]
                if busca_centro_efetiva:
                    mask = (
                        d["produto_servico"].fillna("").str.contains(busca_centro_efetiva, case=False, na=False) |
                        d["codprod"].astype(str).str.contains(busca_centro_efetiva, na=False) |
                        d["parceiro"].fillna("").str.contains(busca_centro_efetiva, case=False, na=False)
                    )
                    d = d[mask]
                d = d.sort_values("data_efetiva", ascending=False)
                return d

            com_filt = aplica_filtros(com_produto)
            sem_filt = aplica_filtros(sem_produto)

            # SEÇÃO 1
            st.markdown("### ✅ Lançamentos COM produto identificado")
            total_com = com_filt['vlrtot'].fillna(0).sum() if not com_filt.empty else 0
            st.caption(
                f"**{len(com_filt)} lançamentos** | "
                f"Total: R$ {total_com:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
            )

            if com_filt.empty:
                st.info("Sem lançamentos com produto para os filtros atuais.")
            else:
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
                    height=400,
                    column_config={
                        "Data": st.column_config.DateColumn(format=FMT_DATA_BR),
                    }
                )

            st.divider()

            # SEÇÃO 2
            st.markdown("### ⚠️ Lançamentos SEM produto identificado")
            total_sem = sem_filt['debito'].sum() if not sem_filt.empty else 0
            st.caption(
                f"**{len(sem_filt)} lançamentos** | "
                f"Total: R$ {total_sem:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".") +
                " | Geralmente transferências de obra, provisões ou ajustes contábeis."
            )

            if sem_filt.empty:
                st.info("Sem lançamentos sem produto para os filtros atuais.")
            else:
                sem_filt_show = sem_filt.copy()
                sem_filt_show["Mes"] = sem_filt_show["data_efetiva"].dt.strftime("%m/%Y")

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
                    height=300,
                    column_config={
                        "Data": st.column_config.DateColumn(format=FMT_DATA_BR),
                    }
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


# ============================================================
# MODO 4 — POR CONTA CONTÁBIL (RAZÃO)
# ============================================================
elif modo == "📒 Por Conta Contábil (Razão)":
    st.subheader("📒 Razão da Conta Contábil")
    st.caption(
        "Selecione uma conta contábil para ver o razão analítico: "
        "todos os lançamentos a débito e crédito com saldo acumulado."
    )

    df_contas, contas_orfas = lista_contas_com_lancamento()

    if df_contas.empty:
        st.warning("Nenhuma conta com lançamento encontrada.")
        st.stop()

    # Alerta de contas órfãs (em lançamentos mas não no plano_contas)
    if not contas_orfas.empty:
        with st.expander(
            f"⚠️ {len(contas_orfas)} conta(s) com lançamento ainda não classificada(s) no plano_contas",
            expanded=False
        ):
            st.caption(
                "Essas contas vieram da contabilidade mas ainda não foram cadastradas em "
                "`plano_contas` com tipo/categoria. Você pode consultá-las normalmente no "
                "razão, mas elas não aparecem nos outros modos da Consulta Rápida (que "
                "filtram por contas de CUSTO). Peça à contabilidade para classificá-las."
            )
            st.dataframe(
                contas_orfas[["codctactb", "descrcta"]].rename(columns={
                    "codctactb": "Código",
                    "descrcta": "Descrição",
                }),
                use_container_width=True,
                hide_index=True,
            )

    # Dropdown de conta
    contas_labels = {
        f"{int(r['codctactb'])} — {r['descrcta']}"
        + ("" if r["no_plano"] else " ⚠️ não classificada"): int(r['codctactb'])
        for _, r in df_contas.iterrows()
    }

    conta_label = st.selectbox(
        "Conta contábil / projeto",
        options=list(contas_labels.keys()),
        key="razao_conta"
    )
    codctactb_esc = contas_labels[conta_label]

    # Carrega razão respeitando filtro global de empresa
    with st.spinner("Carregando razão da conta..."):
        df_razao = carrega_razao(codctactb_esc, tuple(empresa_sel))

    if df_razao.empty:
        st.info("Sem lançamentos nessa conta para as empresas selecionadas.")
    else:
        # ----- Filtro de período opcional -----
        data_min_r = df_razao["dtmov"].min().date() if pd.notna(df_razao["dtmov"].min()) else date.today()
        data_max_r = df_razao["dtmov"].max().date() if pd.notna(df_razao["dtmov"].max()) else date.today()

        cr1, cr2 = st.columns(2)
        dt_ini_r = cr1.date_input(
            "De", value=data_min_r,
            min_value=data_min_r, max_value=data_max_r,
            key="dt_ini_razao", format=FMT_DATA_BR
        )
        dt_fim_r = cr2.date_input(
            "Até", value=data_max_r,
            min_value=data_min_r, max_value=data_max_r,
            key="dt_fim_razao", format=FMT_DATA_BR
        )

        df_razao_per = df_razao[
            (df_razao["dtmov"].dt.date >= dt_ini_r) &
            (df_razao["dtmov"].dt.date <= dt_fim_r)
        ].copy()

        # Recalcula saldo acumulado dentro do período filtrado
        # (mantém o saldo histórico até a data inicial como saldo de abertura)
        saldo_abertura = (
            df_razao[df_razao["dtmov"].dt.date < dt_ini_r]
            .assign(mov=lambda d: d["debito"] - d["credito"])["mov"].sum()
        )
        df_razao_per = df_razao_per.sort_values(["dtmov", "id"]).reset_index(drop=True)
        df_razao_per["saldo_acumulado"] = (
            saldo_abertura + (df_razao_per["debito"] - df_razao_per["credito"]).cumsum()
        )

        if df_razao_per.empty:
            st.warning("Sem lançamentos nesse período.")
        else:
            # ----- KPIs -----
            total_debito = df_razao_per["debito"].sum()
            total_credito = df_razao_per["credito"].sum()
            saldo_final = saldo_abertura + (total_debito - total_credito)

            def fmt_brl(v):
                return f"R$ {v:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")

            k1, k2, k3, k4 = st.columns(4)
            k1.metric("Saldo abertura", fmt_brl(saldo_abertura))
            k2.metric("Total débito", fmt_brl(total_debito))
            k3.metric("Total crédito", fmt_brl(total_credito))
            k4.metric("Saldo final", fmt_brl(saldo_final))

            st.divider()

            # ----- Tabela do razão -----
            st.markdown(f"##### Lançamentos da conta `{codctactb_esc}` — {df_contas[df_contas['codctactb']==codctactb_esc]['descrcta'].iloc[0]}")
            st.caption(
                f"{len(df_razao_per)} lançamentos | "
                f"Período: {dt_ini_r.strftime('%d/%m/%Y')} a {dt_fim_r.strftime('%d/%m/%Y')}"
            )

            df_show = df_razao_per[[
                "dtmov", "numdoc", "complhist", "parceiro_extraido",
                "descrcencus", "debito", "credito", "saldo_acumulado", "codemp"
            ]].copy()

            st.dataframe(
                df_show.rename(columns={
                    "dtmov": "Data",
                    "numdoc": "Doc",
                    "complhist": "Histórico",
                    "parceiro_extraido": "Parceiro",
                    "descrcencus": "Centro de Custo",
                    "debito": "Débito",
                    "credito": "Crédito",
                    "saldo_acumulado": "Saldo Acumulado",
                    "codemp": "Emp",
                }).style.format({
                    "Débito": lambda v: fmt_brl(v) if v else "",
                    "Crédito": lambda v: fmt_brl(v) if v else "",
                    "Saldo Acumulado": fmt_brl,
                }),
                use_container_width=True,
                hide_index=True,
                height=500,
                column_config={
                    "Data": st.column_config.DateColumn(format=FMT_DATA_BR),
                }
            )

            # ----- Export CSV -----
            csv = df_show.to_csv(index=False).encode("utf-8")
            descr_safe = (
                df_contas[df_contas['codctactb']==codctactb_esc]['descrcta'].iloc[0]
                .replace(' ', '_').replace('/', '_').replace('(', '').replace(')', '')
            )
            st.download_button(
                f"📥 Exportar razão CSV",
                csv,
                f"razao_{codctactb_esc}_{descr_safe}_{dt_ini_r}_a_{dt_fim_r}.csv",
                "text/csv"
            )
