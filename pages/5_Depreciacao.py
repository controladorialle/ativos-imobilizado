"""Análise paralela de depreciação acumulada."""
import streamlit as st
import pandas as pd
import plotly.express as px
from app import sb
from utils.auth import requer_perfil

# Bloqueia acesso: admin, editor e leitor podem ver
requer_perfil(["admin", "editor", "leitor"])

st.title("📉 Análise de Depreciação Acumulada")
st.caption(
    "Visão paralela — não impacta o saldo principal de aquisições no Dashboard."
)

sup = sb()


@st.cache_data(ttl=60)
def carrega():
    return pd.DataFrame(sup.table("vw_depreciacao").select("*").execute().data)


df = carrega()
if df.empty:
    st.info("Sem dados ainda. Importe as bases primeiro.")
    st.stop()

# Taxa implícita (depreciação acumulada / custo líquido)
df["taxa_implicita_pct"] = (
    df["deprec_acumulada"] / df["custo_liquido"].replace(0, pd.NA) * 100
).round(1)

c1, c2, c3 = st.columns(3)
c1.metric(
    "Custo líquido total",
    f"R$ {df['custo_liquido'].sum():,.0f}".replace(",", ".")
)
c2.metric(
    "Depreciação acumulada",
    f"R$ {df['deprec_acumulada'].sum():,.0f}".replace(",", ".")
)
taxa_media = (
    df["deprec_acumulada"].sum() / df["custo_liquido"].sum() * 100
    if df["custo_liquido"].sum() > 0 else 0
)
c3.metric("Taxa média implícita", f"{taxa_media:.1f}%")

# Gráficos
fig = px.bar(
    df, x="categoria", y=["custo_liquido", "deprec_acumulada"],
    barmode="group",
    title="Custo vs Depreciação por categoria",
    labels={"value": "Valor (R$)", "variable": "Tipo"}
)
fig.update_layout(xaxis_tickangle=-30)
st.plotly_chart(fig, use_container_width=True)

# Tabela
st.subheader("Detalhamento")
st.dataframe(
    df.style.format({
        "custo_liquido": "R$ {:,.2f}".format,
        "deprec_acumulada": "R$ {:,.2f}".format,
        "taxa_implicita_pct": "{:.1f}%".format
    }),
    use_container_width=True
)
