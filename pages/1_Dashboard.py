"""Dashboard principal — saldo, aquisições e movimentação por categoria e centro de custo."""
import streamlit as st
import pandas as pd
import plotly.express as px
from app import sb

if "user" not in st.session_state:
    st.warning("Faça login primeiro.")
    st.stop()

st.title("📊 Dashboard")

sup = sb()


@st.cache_data(ttl=60)
def carrega_saldo():
    return pd.DataFrame(sup.table("vw_saldo_categoria").select("*").execute().data)


@st.cache_data(ttl=60)
def carrega_movimentacao():
    return pd.DataFrame(sup.table("vw_movimentacao_mensal").select("*").execute().data)


saldo = carrega_saldo()
mov = carrega_movimentacao()

if saldo.empty:
    st.info("Sem dados ainda. Vá em **Importar** para carregar as bases.")
    st.stop()

# ---------- Filtros ----------
st.sidebar.header("Filtros")

empresas = sorted(saldo["empresa"].unique())
empresa = st.sidebar.multiselect("Empresa", empresas, default=empresas)

cats = sorted(saldo["categoria"].unique())
categoria = st.sidebar.multiselect("Categoria", cats, default=cats)

centros = sorted(saldo["descrcencus"].dropna().unique())
centro = st.sidebar.multiselect(
    "Centro de custo",
    centros,
    default=centros,
    help="Centros de custo extraídos da base contábil (colunas M e N)"
)

tipos = st.sidebar.multiselect(
    "Tipo de movimentação", ["AQUISICAO", "BAIXA"],
    default=["AQUISICAO", "BAIXA"]
)

if not mov.empty:
    meses = sorted(mov["mes"].unique())
    mes_ini, mes_fim = st.sidebar.select_slider(
        "Período (mês)",
        options=meses,
        value=(meses[0], meses[-1])
    )
else:
    mes_ini = mes_fim = None

# Aplica filtros
saldo_f = saldo[
    saldo["empresa"].isin(empresa) &
    saldo["categoria"].isin(categoria) &
    saldo["descrcencus"].isin(centro)
]

if not mov.empty:
    mov_f = mov[
        mov["categoria"].isin(categoria) &
        mov["movimentacao"].isin(tipos) &
        mov["descrcencus"].isin(centro)
    ]
    if mes_ini and mes_fim:
        mov_f = mov_f[(mov_f["mes"] >= mes_ini) & (mov_f["mes"] <= mes_fim)]
else:
    mov_f = pd.DataFrame()

# ---------- KPIs ----------
k1, k2, k3, k4 = st.columns(4)
k1.metric(
    "Aquisições",
    f"R$ {saldo_f['total_aquisicoes'].sum():,.0f}".replace(",", ".")
)
k2.metric(
    "Baixas",
    f"R$ {saldo_f['total_baixas'].sum():,.0f}".replace(",", ".")
)
k3.metric(
    "Saldo",
    f"R$ {saldo_f['saldo'].sum():,.0f}".replace(",", ".")
)
k4.metric("Lançamentos de aquisição", int(saldo_f['qtd_aquisicoes'].sum()))

# ---------- Abas ----------
t1, t2, t3, t4 = st.tabs([
    "Saldo por categoria",
    "Por centro de custo",
    "Aquisições",
    "Movimentação no tempo"
])

with t1:
    if not saldo_f.empty:
        agg = (saldo_f.groupby(["categoria", "empresa"], as_index=False)
               [["total_aquisicoes", "total_baixas", "saldo",
                 "qtd_aquisicoes", "qtd_baixas"]]
               .sum())
        fig = px.bar(
            agg.sort_values("saldo", ascending=True),
            x="saldo", y="categoria",
            color="empresa", orientation="h",
            title="Saldo por categoria (R$)",
            labels={"saldo": "Saldo (R$)", "categoria": "Categoria"}
        )
        fig.update_layout(height=500)
        st.plotly_chart(fig, use_container_width=True)
        st.subheader("Detalhamento")
        st.dataframe(
            agg.style.format({
                "total_aquisicoes": "R$ {:,.2f}".format,
                "total_baixas": "R$ {:,.2f}".format,
                "saldo": "R$ {:,.2f}".format
            }),
            use_container_width=True
        )

with t2:
    if not saldo_f.empty:
        resumo_centro = (saldo_f.groupby("descrcencus", as_index=False)
                         [["total_aquisicoes", "total_baixas", "saldo"]]
                         .sum().sort_values("saldo", ascending=False))
        fig = px.bar(
            resumo_centro.head(20),
            x="saldo", y="descrcencus", orientation="h",
            title="Top 20 centros de custo por saldo",
            labels={"saldo": "Saldo (R$)", "descrcencus": "Centro de custo"}
        )
        fig.update_layout(height=550)
        st.plotly_chart(fig, use_container_width=True)

        st.subheader("Cruzamento Centro de custo × Categoria")
        pivot = saldo_f.pivot_table(
            index="descrcencus", columns="categoria",
            values="saldo", aggfunc="sum", fill_value=0
        )
        st.dataframe(
            pivot.style.format("R$ {:,.2f}".format),
            use_container_width=True
        )

with t3:
    if not saldo_f.empty:
        agg2 = (saldo_f.groupby(["categoria", "empresa"], as_index=False)
                ["total_aquisicoes"].sum())
        col1, col2 = st.columns(2)
        with col1:
            fig = px.pie(
                agg2, values="total_aquisicoes", names="categoria",
                title="Distribuição de aquisições por categoria"
            )
            st.plotly_chart(fig, use_container_width=True)
        with col2:
            fig = px.bar(
                agg2.sort_values("total_aquisicoes", ascending=False),
                x="categoria", y="total_aquisicoes", color="empresa",
                title="Aquisições por categoria",
                labels={"total_aquisicoes": "Aquisições (R$)"}
            )
            fig.update_layout(xaxis_tickangle=-45)
            st.plotly_chart(fig, use_container_width=True)

with t4:
    if not mov_f.empty:
        agg = mov_f.groupby(["mes", "movimentacao"], as_index=False)["total"].sum()
        fig = px.bar(
            agg, x="mes", y="total", color="movimentacao",
            barmode="group",
            title="Aquisições x Baixas por mês",
            labels={"mes": "Mês", "total": "Valor (R$)"}
        )
        st.plotly_chart(fig, use_container_width=True)

        st.subheader("Acumulado por mês e categoria")
        pivot = mov_f.pivot_table(
            index="mes", columns=["categoria", "movimentacao"],
            values="total", aggfunc="sum", fill_value=0
        )
        st.dataframe(pivot, use_container_width=True)
    else:
        st.info("Sem dados de movimentação no período selecionado.")
