"""Inventário físico anual de imobilizado.

3 abas:
- A) Setup — admin+editor abre ciclo, vê unidades cadastradas
- B) Conferir — contabilidade marca itens em campo (admin+editor)
- C) Resultado — relatório final (todos)
"""
import streamlit as st
import pandas as pd
import plotly.express as px
from datetime import date
from app import sb
from utils.auth import requer_perfil, get_perfil_usuario

# Acesso liberado para todos (cada aba tem proteção interna)
requer_perfil(["admin", "editor", "leitor"])

perfil = get_perfil_usuario()
pode_gerenciar = perfil in ("admin", "editor")

st.title("📋 Inventário Físico de Imobilizado")
st.caption(
    "Controle anual de contagem física dos ativos imobilizados. "
    "Cada unidade cadastrada precisa ser localizada e marcada pela contabilidade."
)

sup = sb()


# ============================================================
# FUNÇÕES DE CARGA
# ============================================================

@st.cache_data(ttl=30)
def carrega_unidades():
    """Carrega todas as unidades cadastradas."""
    resp = sup.table("inventario_unidades").select("*").execute()
    return pd.DataFrame(resp.data) if resp.data else pd.DataFrame()


@st.cache_data(ttl=30)
def carrega_ciclos():
    """Carrega todos os ciclos de inventário."""
    resp = sup.table("inventario_ciclos").select("*").order(
        "ano", desc=True
    ).execute()
    return pd.DataFrame(resp.data) if resp.data else pd.DataFrame()


@st.cache_data(ttl=30)
def conta_marcacoes_por_ciclo():
    """Conta marcações por ciclo (pra mostrar progresso)."""
    resp = sup.table("inventario_marcacoes").select(
        "ciclo_id, status"
    ).execute()
    if not resp.data:
        return pd.DataFrame()
    df = pd.DataFrame(resp.data)
    return df.groupby(["ciclo_id", "status"]).size().reset_index(name="qtd")


# ============================================================
# ABAS
# ============================================================

tab_setup, tab_conferir, tab_resultado = st.tabs([
    "⚙️ Setup",
    "✅ Conferir",
    "📊 Resultado",
])


# ============================================================
# ABA A — SETUP (admin + editor)
# ============================================================

with tab_setup:
    if not pode_gerenciar:
        st.warning(
            "🚫 Apenas administradores e editores podem acessar o Setup. "
            "Use a aba **Resultado** pra consultar o inventário."
        )
    else:
        # ---- SEÇÃO 1: Resumo de unidades ----
        st.subheader("📦 Unidades cadastradas")

        unidades = carrega_unidades()

        if unidades.empty:
            st.error(
                "Nenhuma unidade cadastrada. Rode o SQL de 'explosão' "
                "no Supabase pra gerar as unidades a partir dos dados existentes."
            )
        else:
            ativas = unidades[unidades["ativo"] == True]
            baixadas = unidades[unidades["ativo"] == False]

            c1, c2, c3, c4 = st.columns(4)
            c1.metric("Total", len(unidades))
            c2.metric("Ativas", len(ativas))
            c3.metric("Baixadas", len(baixadas))
            c4.metric(
                "Valor total ativo",
                f"R$ {ativas['valor_unitario'].sum():,.0f}".replace(",", ".")
            )

            st.divider()

            # Distribuição por categoria
            col_cat, col_loc = st.columns(2)

            with col_cat:
                st.markdown("**Por categoria**")
                resumo_cat = (
                    ativas.groupby("categoria", as_index=False)
                    .agg(
                        unidades=("id", "count"),
                        valor=("valor_unitario", "sum")
                    )
                    .sort_values("unidades", ascending=False)
                )
                fig = px.bar(
                    resumo_cat,
                    x="unidades", y="categoria",
                    orientation="h",
                    title=None,
                    labels={"unidades": "Unidades", "categoria": ""}
                )
                fig.update_layout(height=350, showlegend=False)
                st.plotly_chart(fig, use_container_width=True)

            with col_loc:
                st.markdown("**Top 10 localidades**")
                resumo_loc = (
                    ativas.groupby(["codemp", "descrcencus"], as_index=False)
                    .agg(unidades=("id", "count"))
                    .sort_values("unidades", ascending=False)
                    .head(10)
                )
                resumo_loc["label"] = (
                    "Emp " + resumo_loc["codemp"].astype(str) +
                    " — " + resumo_loc["descrcencus"].fillna("(sem centro)")
                )
                fig = px.bar(
                    resumo_loc.sort_values("unidades"),
                    x="unidades", y="label",
                    orientation="h",
                    title=None,
                    labels={"unidades": "Unidades", "label": ""}
                )
                fig.update_layout(height=350, showlegend=False)
                st.plotly_chart(fig, use_container_width=True)

            with st.expander("Ver lista completa de unidades"):
                st.dataframe(
                    ativas[[
                        "plaqueta", "categoria", "produto_servico",
                        "codemp", "descrcencus", "data_aquisicao",
                        "valor_unitario", "parceiro"
                    ]].rename(columns={
                        "plaqueta": "Plaqueta",
                        "categoria": "Categoria",
                        "produto_servico": "Produto",
                        "codemp": "Emp",
                        "descrcencus": "Centro",
                        "data_aquisicao": "Aquisição",
                        "valor_unitario": "Valor R$",
                        "parceiro": "Fornecedor",
                    }).style.format({
                        "Valor R$": "R$ {:,.2f}".format,
                    }),
                    use_container_width=True,
                    hide_index=True,
                    height=400
                )

        st.divider()

        # ---- SEÇÃO 2: Ciclos de inventário ----
        st.subheader("🔄 Ciclos de inventário")

        ciclos = carrega_ciclos()
        marc_count = conta_marcacoes_por_ciclo()

        if not ciclos.empty:
            for _, ciclo in ciclos.iterrows():
                titulo = f"{ciclo['nome']} — Status: {ciclo['status']}"
                with st.expander(titulo, expanded=(ciclo["status"] == "ABERTO")):
                    c1, c2, c3 = st.columns(3)
                    c1.write(f"**Ano:** {ciclo['ano']}")
                    c2.write(f"**Abertura:** {ciclo['data_abertura']}")
                    c3.write(
                        f"**Fechamento:** {ciclo['data_fechamento'] or '(em aberto)'}"
                    )

                    if ciclo.get("observacao"):
                        st.write(f"**Observação:** {ciclo['observacao']}")
                    st.write(f"**Criado por:** {ciclo.get('criado_por', '?')}")

                    # Mostra progresso
                    if not marc_count.empty:
                        prog = marc_count[marc_count["ciclo_id"] == ciclo["id"]]
                        if not prog.empty:
                            total_marc = prog["qtd"].sum()
                            pendentes = int(
                                prog[prog["status"] == "PENDENTE"]["qtd"].sum()
                            )
                            verificadas = total_marc - pendentes
                            pct = (verificadas / total_marc * 100) if total_marc else 0
                            st.progress(
                                pct / 100,
                                f"{verificadas} de {total_marc} verificadas ({pct:.1f}%)"
                            )
                            st.dataframe(
                                prog.rename(columns={
                                    "status": "Status",
                                    "qtd": "Qtd",
                                }).drop(columns=["ciclo_id"]),
                                use_container_width=True,
                                hide_index=True,
                            )

                    # Botão de fechar ciclo (só se aberto)
                    if ciclo["status"] == "ABERTO":
                        if st.button(
                            "🔒 Fechar este ciclo",
                            key=f"fechar_{ciclo['id']}",
                            help="Marca o ciclo como FECHADO. Não impede edição posterior."
                        ):
                            try:
                                sup.table("inventario_ciclos").update({
                                    "status": "FECHADO",
                                    "data_fechamento": date.today().isoformat(),
                                }).eq("id", int(ciclo["id"])).execute()
                                st.success("Ciclo fechado.")
                                st.cache_data.clear()
                                st.rerun()
                            except Exception as e:
                                st.error(f"Falha: {e}")
        else:
            st.info("Nenhum ciclo cadastrado ainda. Crie o primeiro abaixo.")

        st.divider()

        # ---- SEÇÃO 3: Abrir novo ciclo ----
        st.subheader("➕ Abrir novo ciclo")

        # Bloqueia se já houver ciclo aberto no ano
        ciclo_aberto = ciclos[ciclos["status"] == "ABERTO"] if not ciclos.empty else pd.DataFrame()

        if not ciclo_aberto.empty:
            st.warning(
                f"⚠️ Já existe um ciclo aberto: **{ciclo_aberto.iloc[0]['nome']}**. "
                "Feche-o antes de abrir outro."
            )
        elif unidades.empty:
            st.warning("Cadastre unidades antes de abrir um ciclo.")
        else:
            with st.form("novo_ciclo"):
                ano_default = date.today().year
                ano = st.number_input(
                    "Ano do ciclo",
                    min_value=2020,
                    max_value=2050,
                    value=ano_default,
                    step=1,
                )
                nome = st.text_input(
                    "Nome do ciclo",
                    value=f"Inventário Anual {ano_default}",
                )
                observacao = st.text_area(
                    "Observação (opcional)",
                    placeholder="Ex: Inventário com participação da empresa X de auditoria..."
                )

                ativas_count = int((unidades["ativo"] == True).sum())
                st.info(
                    f"Ao abrir o ciclo, **{ativas_count} marcações** serão criadas "
                    "(uma por unidade ativa), todas em status PENDENTE."
                )

                submit = st.form_submit_button(
                    "🟢 Abrir ciclo", type="primary"
                )

            if submit:
                # Cria ciclo
                try:
                    resp = sup.table("inventario_ciclos").insert({
                        "nome": nome,
                        "ano": int(ano),
                        "data_abertura": date.today().isoformat(),
                        "status": "ABERTO",
                        "observacao": observacao or None,
                        "criado_por": st.session_state["user"],
                    }).execute()
                    ciclo_id = resp.data[0]["id"]
                except Exception as e:
                    st.error(f"Falha ao criar ciclo: {e}")
                    st.stop()

                # Cria marcações em lote pra cada unidade ativa
                ativas = unidades[unidades["ativo"] == True]
                marcacoes_payload = [
                    {
                        "ciclo_id": ciclo_id,
                        "unidade_id": int(u["id"]),
                        "status": "PENDENTE",
                    }
                    for _, u in ativas.iterrows()
                ]

                progresso = st.progress(0.0, "Criando marcações...")
                BATCH = 200
                total = len(marcacoes_payload)
                erros = 0
                for i in range(0, total, BATCH):
                    lote = marcacoes_payload[i:i+BATCH]
                    try:
                        sup.table("inventario_marcacoes").insert(lote).execute()
                    except Exception as e:
                        erros += 1
                        st.warning(f"Falha em lote {i}: {e}")
                    progresso.progress(
                        min((i + BATCH) / max(total, 1), 1.0),
                        f"Criadas {min(i+BATCH, total)} de {total}..."
                    )

                if erros == 0:
                    st.success(f"✅ Ciclo aberto com {total} marcações PENDENTES.")
                else:
                    st.warning(
                        f"Ciclo aberto, mas houve {erros} lote(s) com falha. "
                        "Verifique no banco."
                    )
                st.cache_data.clear()
                st.rerun()


# ============================================================
# ABA B — CONFERIR (placeholder)
# ============================================================

with tab_conferir:
    st.info(
        "🚧 **Em construção.**  \n"
        "Esta aba vai permitir à contabilidade marcar cada unidade como "
        "Encontrada, Não Encontrada, em Manutenção, etc., com filtros por "
        "localidade e categoria.  \n\n"
        "Por enquanto, abra um ciclo na aba **Setup** e aguarde a próxima versão."
    )


# ============================================================
# ABA C — RESULTADO (placeholder)
# ============================================================

with tab_resultado:
    st.info(
        "🚧 **Em construção.**  \n"
        "Esta aba vai mostrar o relatório final do inventário: divergências, "
        "valor financeiro do faltante, exportação Excel pra auditoria."
    )
