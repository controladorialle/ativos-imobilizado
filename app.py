"""Sistema de Gestão de Ativos Imobilizados - entry point."""
import streamlit as st
from supabase import create_client, ClientOptions

st.set_page_config(
    page_title="Ativos Imobilizados",
    page_icon="🏢",
    layout="wide",
)


@st.cache_resource
def sb():
    """Cliente Supabase reutilizável.

    Limpa URL e chave para evitar problemas de espaços/duplicação.
    Funciona com chaves Legacy (eyJ...) e novas (sb_publishable_...).
    """
    url = st.secrets["supabase"]["url"].strip()
    # Remove https:// duplicado se houver
    while url.startswith("https://https://"):
        url = url.replace("https://https://", "https://", 1)
    if not url.startswith("https://"):
        url = "https://" + url
    url = url.rstrip("/")

    key = st.secrets["supabase"]["anon_key"].strip().replace("\n", "").replace("\r", "")

    return create_client(url, key)


def login_form():
    st.title("🏢 Gestão de Ativos Imobilizados")
    st.markdown("Faça login para continuar")
    with st.form("login"):
        email = st.text_input("E-mail")
        senha = st.text_input("Senha", type="password")
        ok = st.form_submit_button("Entrar", type="primary")
    if ok:
        try:
            sess = sb().auth.sign_in_with_password(
                {"email": email, "password": senha}
            )
            st.session_state["user"] = sess.user.email
            st.rerun()
        except Exception as e:
            st.error(f"Falha no login: {e}")
            with st.expander("Diagnóstico (clique para ver detalhes)"):
                url_dbg = st.secrets["supabase"]["url"]
                key_dbg = st.secrets["supabase"]["anon_key"]
                st.write(f"URL lida: `{url_dbg}`")
                st.write(f"Chave (primeiros 20): `{key_dbg[:20]}`")
                st.write(f"Tamanho da chave: {len(key_dbg)}")
                st.code(str(e))


def main():
    if "user" not in st.session_state:
        login_form()
        return

    st.sidebar.success(f"Logado: {st.session_state['user']}")
    if st.sidebar.button("Sair"):
        try:
            sb().auth.sign_out()
        except Exception:
            pass
        del st.session_state["user"]
        st.rerun()

    st.title("🏢 Gestão de Ativos Imobilizados")
    st.markdown(
        """
        Use o menu lateral para navegar:

        - **Importar** — carregue as bases XLSX cruas (contábil e compras)
        - **Dashboard** — saldo, aquisições e movimentação por categoria
        - **Conciliação** — divergências entre contábil e compras
        - **Revisão Manual** — NFs com match aproximado para o usuário resolver
        - **Operacional** — lançamentos manuais (aquisição/baixa)
        - **Depreciação** — análise paralela de depreciação acumulada
        """
    )

    try:
        sup = sb()
        importacoes = sup.table("importacoes").select("*").order(
            "criado_em", desc=True
        ).limit(5).execute().data
        if importacoes:
            st.subheader("Últimas importações")
            for imp in importacoes:
                st.write(
                    f"📥 **{imp['tipo']}** — {imp['nome_arquivo']} — "
                    f"{imp['linhas_gravadas']} linhas gravadas — "
                    f"{imp['linhas_bloqueadas']} duplicatas bloqueadas — "
                    f"{imp['criado_em'][:16]}"
                )
        else:
            st.info("Nenhuma importação registrada. Comece pela página **Importar**.")
    except Exception as e:
        st.warning(f"Não foi possível carregar o histórico: {e}")


if __name__ == "__main__":
    main()
