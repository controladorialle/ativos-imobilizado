"""Lançamentos manuais — aquisição ou baixa avulsa."""
import streamlit as st
import pandas as pd
from datetime import date
from app import sb
from utils.auth import requer_perfil

# Bloqueia acesso: admin e editor podem entrar (leitor não)
requer_perfil(["admin", "editor"])

st.title("📝 Lançamento manual")
st.caption("Registre uma aquisição ou baixa sem precisar fazer upload de arquivo.")

sup = sb()


@st.cache_data(ttl=60)
def carrega_contas():
    data = sup.table("plano_contas").select("codctactb,descrcta,tipo").execute().data
    return pd.DataFrame(data)


contas = carrega_contas()

tab1, tab2 = st.tabs(["Novo lançamento", "Histórico"])

with tab1:
    with st.form("mov"):
        tipo = st.selectbox("Tipo de movimentação", ["AQUISICAO", "BAIXA"])
        codemp = st.selectbox("Empresa", [1, 2])
        if not contas.empty:
            contas_custo = contas[contas["tipo"] == "CUSTO"].sort_values("descrcta")
            opcoes_conta = {
                f"{r['codctactb']} — {r['descrcta']}": r["codctactb"]
                for _, r in contas_custo.iterrows()
            }
            label = st.selectbox("Conta contábil", list(opcoes_conta.keys()))
            codctactb = opcoes_conta[label]
        else:
            codctactb = st.number_input("Código da conta (CODCTACTB)", step=1, format="%d")
        numdoc = st.text_input("Nº documento (opcional)")
        parceiro = st.text_input("Fornecedor / contraparte")
        valor = st.number_input("Valor (R$)", min_value=0.0, format="%.2f")
        data_mov = st.date_input("Data", value=date.today())
        desc = st.text_area("Descrição")
        ok = st.form_submit_button("Registrar", type="primary")
    if ok:
        if valor <= 0:
            st.error("Valor precisa ser maior que zero.")
        else:
            try:
                sup.table("movimentacoes_manuais").insert({
                    "tipo": tipo,
                    "codemp": int(codemp),
                    "codctactb": int(codctactb),
                    "numdoc": int(numdoc) if numdoc.strip().isdigit() else None,
                    "parceiro": parceiro or None,
                    "valor": float(valor),
                    "data": data_mov.isoformat(),
                    "descricao": desc or None,
                    "usuario_email": st.session_state["user"],
                }).execute()
                st.success("✅ Lançamento registrado.")
            except Exception as e:
                st.error(f"Falha ao gravar: {e}")

with tab2:
    historico = pd.DataFrame(
        sup.table("movimentacoes_manuais")
        .select("*")
        .order("criado_em", desc=True)
        .limit(100)
        .execute()
        .data
    )
    if historico.empty:
        st.info("Nenhum lançamento manual ainda.")
    else:
        st.dataframe(historico, use_container_width=True)
        st.download_button(
            "📥 Exportar CSV",
            historico.to_csv(index=False).encode("utf-8"),
            "movimentacoes_manuais.csv",
            "text/csv"
        )
