"""Helper de autenticacao e controle de perfil."""
import streamlit as st
from supabase import create_client


SUPABASE_URL = "https://vyxcttiiemzaxqjxtspc.supabase.co"
SUPABASE_ANON_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6InZ5eGN0dGlpZW16YXhxanh0c3BjIiwicm9sZSI6ImFub24iLCJpYXQiOjE3NzkxMjA3MjUsImV4cCI6MjA5NDY5NjcyNX0.kzwqS7gZSv8xVuuAW2eH4YLw2JF9ECIxK0X0hH5JL9g"


@st.cache_resource
def _get_supabase():
    return create_client(SUPABASE_URL, SUPABASE_ANON_KEY)


def get_email_usuario():
    return st.session_state.get("user")


def get_perfil_usuario():
    if "perfil_cache" in st.session_state:
        return st.session_state["perfil_cache"]

    email = get_email_usuario()
    if not email:
        return None

    try:
        resp = (
            _get_supabase()
            .table("usuarios_app")
            .select("perfil, ativo")
            .eq("email", email)
            .eq("ativo", True)
            .limit(1)
            .execute()
        )
    except Exception as e:
        st.error(f"Erro ao consultar perfil: {e}")
        return None

    if not resp.data:
        st.session_state["perfil_cache"] = None
        return None

    perfil = resp.data[0]["perfil"]
    st.session_state["perfil_cache"] = perfil
    return perfil


def requer_login():
    email = get_email_usuario()
    if not email:
        st.error("Voce precisa estar logado")
        st.stop()
    return email


def requer_perfil(perfis_permitidos):
    requer_login()
    perfil = get_perfil_usuario()

    if perfil is None:
        st.error("Acesso negado")
        st.warning(
            "Seu e-mail nao esta cadastrado no sistema ou esta inativo. "
            "Solicite acesso ao administrador "
            "(matheus.lima@grupolle.com.br)."
        )
        st.stop()

    if perfil not in perfis_permitidos:
        st.error("Voce nao tem permissao para acessar esta pagina")
        st.info(
            f"Seu perfil: {perfil}  \n"
            f"Perfis permitidos: {', '.join(perfis_permitidos)}"
        )
        st.stop()

    return perfil


def pode_editar():
    return get_perfil_usuario() in ("admin", "editor")


def eh_admin():
    return get_perfil_usuario() == "admin"


def limpar_cache_perfil():
    st.session_state.pop("perfil_cache", None)
