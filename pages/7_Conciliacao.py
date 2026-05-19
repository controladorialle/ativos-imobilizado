"""Conciliação contábil x compras."""
import streamlit as st
import pandas as pd
from app import sb

if "user" not in st.session_state:
    st.warning("Faça login primeiro.")
    st.stop()

st.title("🔍 Conciliação contábil x compras")
st.caption(
    "Cruzamento pelo hash da NF (NUMNOTA + CGC + data + empresa). "
    "Notas que aparecem só em uma base ou com diferença de valor são listadas."
)

sup = sb()


@st.cache_data(ttl=60)
def carrega():
    return pd.DataFrame(sup.table("vw_conciliacao").select("*").execute().data)


df = carrega()

if df.empty:
    st.info("Sem dados ainda. Importe as bases primeiro.")
    st.stop()

# Filtros
status = st.selectbox(
    "Filtrar por status",
    ["TODOS", "SO_EM_CONTABIL", "SO_EM_COMPRAS", "DIVERGENCIA_VALOR", "OK"]
)

if status != "TODOS":
    df_view = df[df["status"] == status]
else:
    df_view = df

# Métricas
c1, c2, c3, c4 = st.columns(4)
c1.metric("Total", len(df))
c2.metric("Só em contábil", int((df["status"] == "SO_EM_CONTABIL").sum()))
c3.metric("Só em compras", int((df["status"] == "SO_EM_COMPRAS").sum()))
c4.metric("Divergência de valor", int((df["status"] == "DIVERGENCIA_VALOR").sum()))

ok_pct = (df["status"] == "OK").sum() / len(df) * 100 if len(df) else 0
st.progress(ok_pct / 100, f"{ok_pct:.1f}% das notas com status OK")

# Tabela
st.dataframe(df_view, use_container_width=True)

# Export
st.download_button(
    "📥 Exportar CSV",
    df_view.to_csv(index=False).encode("utf-8"),
    "conciliacao.csv",
    "text/csv"
)
