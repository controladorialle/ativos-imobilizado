"""Associar baixas contábeis a itens de aquisição específicos.

Cada lançamento a crédito em conta de CUSTO é uma baixa.
O usuário pode vincular essa baixa a uma NF de aquisição anterior,
ou classificar como baixa genérica (transferência, depreciação, etc.).
"""
import streamlit as st
import pandas as pd
from datetime import date
from app import sb

if "user" not in st.session_state:
    st.warning("Faça login primeiro.")
    st.stop()

st.title("🔗 Associar Baixas a Itens Imobilizados")
st.caption(
    "Vincule cada lançamento de baixa contábil ao item específico que foi baixado. "
    "Assim o saldo por produto reflete corretamente o que está ativo."
)

sup = sb()


@st.cache_data(ttl=30)
def carrega_baixas():
    """Pega lançamentos a crédito em contas de CUSTO (baixas)."""
    # Contas de CUSTO
    pc = pd.DataFrame(
        sup.table("plano_contas")
        .select("codctactb,descrcta,categoria_id")
        .eq("tipo", "CUSTO")
        .execute().data
    )
    if pc.empty:
        return pd.DataFrame(), pd.DataFrame()

    codctactbs = pc["codctactb"].tolist()

    # Categorias
    cats = pd.DataFrame(
        sup.table("categorias_contabeis").select("id,nome").execute().data
    )
    cats = cats.rename(columns={"id": "categoria_id", "nome": "categoria"})

    # Lançamentos a crédito (baixas) nessas contas
    baixas_list = []
    for i in range(0, len(codctactbs), 50):
        lote = codctactbs[i:i+50]
        resp = sup.table("lancamentos_contabeis").select(
            "id,numdoc,dtmov,codctactb,codemp,descrcencus,credito,debito,complhist,parceiro_extraido,nota_chave"
        ).in_("codctactb", lote).gt("credito", 0).execute()
        if resp.data:
            baixas_list.append(pd.DataFrame(resp.data))

    if not baixas_list:
        return pd.DataFrame(), cats

    baixas = pd.concat(baixas_list, ignore_index=True)
    baixas = baixas.merge(pc, on="codctactb", how="left")
    baixas = baixas.merge(cats, on="categoria_id", how="left")

    return baixas, cats


@st.cache_data(ttl=30)
def carrega_associadas():
    """Já associadas anteriormente."""
    resp = sup.table("baixas_associadas").select("*").execute()
    return pd.DataFrame(resp.data) if resp.data else pd.DataFrame()


@st.cache_data(ttl=30)
def itens_por_categoria(categoria_id, codemp):
    """Lista itens de aquisição da categoria/empresa para sugestão."""
    if not categoria_id or not codemp:
        return pd.DataFrame()

    # Contas dessa categoria
    pc = pd.DataFrame(
        sup.table("plano_contas")
        .select("codctactb")
        .eq("categoria_id", int(categoria_id))
        .eq("tipo", "CUSTO")
        .execute().data
    )
    if pc.empty:
        return pd.DataFrame()
    codctactbs = pc["codctactb"].tolist()

    # Aquisições nessa categoria
    aquis = []
    for i in range(0, len(codctactbs), 50):
        lote = codctactbs[i:i+50]
        resp = sup.table("lancamentos_contabeis").select(
            "nota_chave"
        ).in_("codctactb", lote).eq("codemp", int(codemp)).gt("debito", 0).execute()
        if resp.data:
            aquis.extend([r["nota_chave"] for r in resp.data if r["nota_chave"]])

    if not aquis:
        return pd.DataFrame()

    chaves_unicas = list(set(aquis))[:200]  # Limita a 200 chaves

    itens = []
    for i in range(0, len(chaves_unicas), 50):
        lote = chaves_unicas[i:i+50]
        resp = sup.table("itens_compra").select(
            "id,numnota,dtentsai,parceiro,produto_servico,codprod,qtdneg,un,vlrtot"
        ).in_("nota_chave", lote).execute()
        if resp.data:
            itens.append(pd.DataFrame(resp.data))

    if not itens:
        return pd.DataFrame()

    return pd.concat(itens, ignore_index=True).sort_values("dtentsai", ascending=False)


# --- Carregar dados ---
with st.spinner("Carregando baixas..."):
    baixas, cats = carrega_baixas()
    associadas = carrega_associadas()

if baixas.empty:
    st.info("Nenhuma baixa registrada ainda no banco.")
    st.stop()

# Marca quais já estão associadas
ids_associados = set(associadas["lanc_baixa_id"].tolist()) if not associadas.empty else set()
baixas["status"] = baixas["id"].apply(
    lambda x: "✅ Associada" if x in ids_associados else "⏳ Pendente"
)

# --- KPIs ---
c1, c2, c3 = st.columns(3)
c1.metric("Total de baixas", len(baixas))
c2.metric("Pendentes", int((baixas["status"] == "⏳ Pendente").sum()))
c3.metric(
    "Valor total das pendentes",
    f"R$ {baixas[baixas['status'] == '⏳ Pendente']['credito'].sum():,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
)

st.divider()

# --- Filtros ---
col1, col2, col3 = st.columns(3)
status_filtro = col1.selectbox("Status", ["Pendentes", "Associadas", "Todas"])
cat_opts = ["Todas"] + sorted(baixas["categoria"].dropna().unique().tolist())
cat_filtro = col2.selectbox("Categoria", cat_opts)
emp_opts = ["Todas"] + sorted(baixas["codemp"].dropna().unique().astype(int).astype(str).tolist())
emp_filtro = col3.selectbox("Empresa", emp_opts)

df = baixas.copy()
if status_filtro == "Pendentes":
    df = df[df["status"] == "⏳ Pendente"]
elif status_filtro == "Associadas":
    df = df[df["status"] == "✅ Associada"]
if cat_filtro != "Todas":
    df = df[df["categoria"] == cat_filtro]
if emp_filtro != "Todas":
    df = df[df["codemp"].astype(int).astype(str) == emp_filtro]

df = df.sort_values("dtmov", ascending=False)

st.write(f"**{len(df)} baixas** para revisar (mostrando até 30):")

# --- Lista de baixas ---
for _, row in df.head(30).iterrows():
    titulo = (
        f"{row['status']} | "
        f"{row['dtmov']} | "
        f"{row['categoria']} | "
        f"R$ {float(row['credito']):,.2f} | "
        f"Doc {row['numdoc']}"
    )

    with st.expander(titulo):
        col_a, col_b = st.columns([2, 1])
        with col_a:
            st.write(f"**Histórico:** {row.get('complhist', '')}")
            st.write(f"**Centro de custo:** {row.get('descrcencus', '?')}")
            st.write(f"**Parceiro extraído:** {row.get('parceiro_extraido', '(não detectado)')}")
            st.write(f"**Empresa:** {row.get('codemp')}")
        with col_b:
            st.metric("Valor da baixa", f"R$ {float(row['credito']):,.2f}")

        if row["status"] == "✅ Associada":
            # Mostra detalhes da associação existente
            assoc = associadas[associadas["lanc_baixa_id"] == row["id"]].iloc[0]
            st.success(f"**Já associada como:** {assoc['tipo_baixa']}")
            if assoc.get("descricao"):
                st.write(f"**Descrição:** {assoc['descricao']}")

            if st.button("🗑️ Remover associação", key=f"del_{row['id']}"):
                sup.table("baixas_associadas").delete().eq("id", int(assoc["id"])).execute()
                st.cache_data.clear()
                st.rerun()
            continue

        # --- Formulário de associação ---
        st.write("**Classifique esta baixa:**")
        tipo = st.radio(
            "Tipo",
            options=[
                "ITEM",
                "TRANSFERENCIA",
                "DEPRECIACAO",
                "VENDA",
                "SUCATEAMENTO",
                "OUTRO"
            ],
            format_func=lambda x: {
                "ITEM": "🎯 Item específico (associar a uma NF de aquisição)",
                "TRANSFERENCIA": "🏗️ Transferência de obra → ativo final",
                "DEPRECIACAO": "📉 Depreciação integral",
                "VENDA": "💰 Venda sem rastreio de item",
                "SUCATEAMENTO": "♻️ Sucateamento/descarte",
                "OUTRO": "❓ Outro",
            }[x],
            key=f"tipo_{row['id']}",
            horizontal=False,
        )

        item_id_escolhido = None
        if tipo == "ITEM":
            st.write("**Selecione o item:**")
            itens_cat = itens_por_categoria(row["categoria_id"], row["codemp"])
            if itens_cat.empty:
                st.warning("Sem itens de aquisição encontrados para essa categoria/empresa.")
            else:
                # Busca por nome
                busca = st.text_input(
                    "Filtrar itens",
                    placeholder="Digite parte do nome ou número da NF",
                    key=f"busca_{row['id']}"
                )
                if busca:
                    mask = (
                        itens_cat["produto_servico"].str.contains(busca, case=False, na=False) |
                        itens_cat["numnota"].astype(str).str.contains(busca, na=False) |
                        itens_cat["parceiro"].str.contains(busca, case=False, na=False)
                    )
                    itens_cat = itens_cat[mask]

                if itens_cat.empty:
                    st.info("Sem itens correspondentes.")
                else:
                    opcoes = {
                        f"NF {r['numnota']} | {r['dtentsai']} | {r['parceiro'][:30] if r['parceiro'] else '?'} | "
                        f"{r['produto_servico'][:40] if r['produto_servico'] else '?'} | "
                        f"Qtd {r['qtdneg']} {r['un'] or ''} | R$ {float(r['vlrtot'] or 0):,.2f}": int(r["id"])
                        for _, r in itens_cat.head(50).iterrows()
                    }
                    label_escolhida = st.selectbox(
                        "Item",
                        options=list(opcoes.keys()),
                        key=f"item_{row['id']}"
                    )
                    item_id_escolhido = opcoes[label_escolhida]

        descricao = st.text_area(
            "Observação (opcional)",
            placeholder="Ex: veículo vendido para terceiro, sucateado por defeito, etc.",
            key=f"desc_{row['id']}"
        )

        if st.button("✅ Salvar associação", key=f"save_{row['id']}", type="primary"):
            try:
                sup.table("baixas_associadas").insert({
                    "lanc_baixa_id": int(row["id"]),
                    "item_origem_id": item_id_escolhido,
                    "tipo_baixa": tipo,
                    "descricao": descricao or None,
                    "valor_baixado": float(row["credito"]),
                    "data_baixa": row["dtmov"],
                    "usuario_email": st.session_state["user"],
                }).execute()
                st.success("Associação salva!")
                st.cache_data.clear()
                st.rerun()
            except Exception as e:
                st.error(f"Erro ao salvar: {e}")
