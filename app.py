"""Sistema de Gestão de Ativos Imobilizados - chaves embutidas (emergência)."""
import streamlit as st
from supabase import create_client

# ============================================================
# CHAVES DO SUPABASE — SUBSTITUA AS 3 LINHAS ABAIXO
# ============================================================
SUPABASE_URL = "https://vyxcttiiemzaxqjxtspc.supabase.co"
SUPABASE_ANON_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6InZ5eGN0dGlpZW16YXhxanh0c3BjIiwicm9sZSI6ImFub24iLCJpYXQiOjE3NzkxMjA3MjUsImV4cCI6MjA5NDY5NjcyNX0.kzwqS7gZSv8xVuuAW2eH4YLw2JF9ECIxK0X0hH5JL9g"
SUPABASE_SERVICE_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6InZ5eGN0dGlpZW16YXhxanh0c3BjIiwicm9sZSI6InNlcnZpY2Vfcm9sZSIsImlhdCI6MTc3OTEyMDcyNSwiZXhwIjoyMDk0Njk2NzI1fQ.ccCE5X00sqW5AFu3hRX5vZhKMIPBf0Px-cEOeC0oFtw"
# ============================================================

st.set_page_config(
    page_title="Ativos Imobilizados",
    page_icon="🏢",
    layout="wide",
)


@st.cache_resource
def sb():
    return create_client(SUPABASE_URL, SUPABASE_ANON_KEY)


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
            with st.expander("Diagnóstico"):
                st.write(f"URL: `{SUPABASE_URL}`")
                st.write(f"Chave (primeiros 20): `{SUPABASE_ANON_KEY[:20]}`")
                st.write(f"Tamanho: {len(SUPABASE_ANON_KEY)}")
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

    # TESTE TEMPORARIO



    # DIAGNOSTICO TEMPORARIO
    from utils.auth import _get_supabase
    email_logado = st.session_state.get("user")
    st.sidebar.info(f"Email logado: {repr(email_logado)}")
    st.sidebar.info(f"Tamanho: {len(email_logado) if email_logado else 0}")
    try:
        resp = _get_supabase().table("usuarios_app").select("email, perfil, ativo").execute()
        st.sidebar.info(f"Linhas na tabela: {len(resp.data)}")
        for linha in resp.data:
            st.sidebar.write(linha)
    except Exception as e:
        st.sidebar.error(f"Erro consultando: {e}")


    

    st.title("🏢 Gestão de Ativos Imobilizados")
    st.markdown(
        """
        Use o menu lateral para navegar:
        - **Importar** — carregue as bases XLSX
        - **Dashboard** — saldo, aquisições e movimentação
        - **Conciliação** — divergências contábil x compras
        - **Revisão Manual** — NFs com match aproximado
        - **Operacional** — lançamentos manuais
        - **Depreciação** — análise de depreciação
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
                    f"{imp['linhas_gravadas']} linhas — "
                    f"{imp['criado_em'][:16]}"
                )
        else:
            st.info("Nenhuma importação ainda. Vá em **Importar**.")
    except Exception as e:
        st.warning(f"Erro ao carregar histórico: {e}")
if __name__ == "__main__":
    main()
