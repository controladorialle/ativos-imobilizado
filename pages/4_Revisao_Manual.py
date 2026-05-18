"""Revisão manual de matches aproximados de NF."""
import streamlit as st
import pandas as pd
from app import sb

if "user" not in st.session_state:
    st.warning("Faça login primeiro.")
    st.stop()

st.title("🛠️ Revisão manual de matches")
st.caption(
    "Lançamentos contábeis cuja identificação do parceiro foi aproximada (score 0.60–0.84). "
    "Selecione o parceiro correto para que a chave de cruzamento seja recalculada."
)

sup = sb()


@st.cache_data(ttl=10)
def carrega_pendentes():
    return pd.DataFrame(
        sup.table("revisao_pendente")
        .select("*, lanc:lancamentos_contabeis(numdoc,complhist,debito,credito,dtmov,codemp)")
        .eq("status", "PENDENTE")
        .order("criado_em")
        .limit(200)
        .execute()
        .data
    )


pend = carrega_pendentes()

if pend.empty:
    st.success("✅ Sem pendências de revisão.")
    st.stop()

st.info(f"{len(pend)} lançamentos aguardando revisão (mostrando até 200)")

for _, row in pend.iterrows():
    l = row["lanc"]
    if not l:
        continue

    valor = l.get("debito") or l.get("credito") or 0
    titulo = (
        f"NF {l.get('numdoc', '?')} | {l.get('dtmov', '?')} | "
        f"R$ {float(valor):,.2f}"
    )

    with st.expander(titulo):
        st.write(f"**Empresa:** {l.get('codemp')}")
        st.write(f"**Histórico contábil:** {l.get('complhist', '')}")
        st.write(f"**Parceiro extraído do histórico:** `{row['parceiro_extraido']}`")

        candidatos = row["candidatos_json"] or []
        if not candidatos:
            st.warning("Sem candidatos sugeridos.")
            continue

        st.write("**Candidatos sugeridos (ordenados por similaridade):**")

        opcoes = {}
        for c in candidatos:
            label = f"{c['nome']} (codparc {c['codparc']}, score {c['score']})"
            opcoes[label] = c["codparc"]
        opcoes["⛔ Nenhum — deixar sem match"] = None

        escolha = st.radio(
            "Selecione o parceiro correto:",
            list(opcoes.keys()),
            key=f"r_{row['id']}"
        )

        c1, c2 = st.columns(2)
        if c1.button("✅ Confirmar", key=f"ok_{row['id']}", type="primary"):
            codparc = opcoes[escolha]
            try:
                sup.table("revisao_pendente").update({
                    "status": "RESOLVIDO",
                    "resolvido_para": codparc,
                    "usuario_email": st.session_state["user"],
                    "resolvido_em": "now()"
                }).eq("id", row["id"]).execute()

                if codparc:
                    parc = sup.table("parceiros").select("cgc_cpf").eq(
                        "codparc", codparc
                    ).execute().data
                    if parc:
                        sup.table("lancamentos_contabeis").update({
                            "codparc_resolvido": codparc,
                            "cgc_cpf_resolvido": parc[0]["cgc_cpf"],
                            "match_status": "OK"
                        }).eq("id", row["lanc_id"]).execute()

                st.success("Atualizado.")
                st.cache_data.clear()
                st.rerun()
            except Exception as e:
                st.error(f"Falha: {e}")

        if c2.button("🚫 Ignorar", key=f"ig_{row['id']}"):
            try:
                sup.table("revisao_pendente").update({
                    "status": "IGNORADO",
                    "usuario_email": st.session_state["user"],
                    "resolvido_em": "now()"
                }).eq("id", row["id"]).execute()
                st.cache_data.clear()
                st.rerun()
            except Exception as e:
                st.error(f"Falha: {e}")
