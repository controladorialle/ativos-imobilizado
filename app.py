"""
═══════════════════════════════════════════════════════════════════════════════
 SISTEMA CONTÁBIL LLE FERRAGENS — v6.1 (ARQUIVO ÚNICO CONSOLIDADO)
 Controladoria LLE Ferragens LTDA — CNPJ 05.953.543/0001-47
═══════════════════════════════════════════════════════════════════════════════

 Stack: Streamlit Cloud + Supabase (PostgreSQL) + GitHub
 Versão: 6.1 (consolidada, sem conflitos de função)

 COMO USAR ESTE ARQUIVO:
   1) Cole o conteúdo inteiro no app.py do seu repositório GitHub
   2) Faça commit
   3) Aguarde o re-deploy do Streamlit Cloud (~2 min)
   4) Acesse a URL e faça login

 CONFIGURAÇÃO OBRIGATÓRIA — STREAMLIT CLOUD SECRETS:
   Settings → Secrets → cole:
       SUPABASE_URL = "https://SEU-PROJETO.supabase.co"
       SUPABASE_KEY = "eyJhbGciOiJI..."

 ESTRUTURA INTERNA:
   ╔══════════════════════════════════════════════════════════════════════╗
   ║ BLOCO 1 — Imports, configuração, identidade visual, autenticação     ║
   ║ BLOCO 2 — Conexão Supabase + utilitários gerais                      ║
   ║ BLOCO 3 — Parser de Excel + Validação DFC                            ║
   ║ BLOCO 4 — Cálculo de indicadores + Conciliação                       ║
   ║ BLOCO 5 — Telas, dashboards e função main()                          ║
   ╚══════════════════════════════════════════════════════════════════════╝

 DIFERENCIAÇÃO ENTRE EMPRESAS:
   • DRE_Matriz → unidade=Matriz (PISA, ~35% das vendas)
   • DRE_Filial → unidade=Filial (KING, ~65% das vendas)
   • BP_Consol  → unidade=Consol (Balanço já consolidado das 2)
   • DFC_Consol → unidade=Consol (DFC já consolidado das 2)
   • DRE Consolidada = soma em runtime de Matriz + Filial por classificação

 NOMES DE ABA FLEXÍVEIS:
   Aceita: "DRE_Matriz", "dre matriz", "DRE-MATRIZ", "DreMatriz" etc.
   Normalização: lowercase + remove espaços/acentos/underscores/hífens
"""

# ═══════════════════════════════════════════════════════════════════════════════
# BLOCO 1 — IMPORTS, CONFIGURAÇÃO, IDENTIDADE VISUAL, AUTENTICAÇÃO
# ═══════════════════════════════════════════════════════════════════════════════

import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
import plotly.express as px
from plotly.subplots import make_subplots
import hashlib
import unicodedata
import traceback
from datetime import datetime, timedelta
from supabase import create_client, Client
from streamlit_cookies_manager import EncryptedCookieManager
import bcrypt
import secrets as py_secrets


# -----------------------------------------------------------------------------
# CONFIGURAÇÃO DA PÁGINA STREAMLIT
# -----------------------------------------------------------------------------
st.set_page_config(
    page_title="Sistema Contábil LLE",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded"
)


# -----------------------------------------------------------------------------
# IDENTIDADE VISUAL LLE (paleta oficial)
# -----------------------------------------------------------------------------
CORES_LLE = {
    "azul_profundo": "#071639",       # Cabeçalhos, títulos
    "amarelo_logo": "#F8B11E",        # Destaques
    "azul_vibrante": "#003FFE",       # Links
    "verde_institucional": "#0F8C3B", # Indicadores OK
    "azul_corporativo": "#183F78",    # Séries secundárias
    "branco": "#FFFFFF",
    "cinza_claro": "#F2F2F2",         # Linhas alternadas
    "cinza_borda": "#D9D9D9",         # Bordas
    "vermelho": "#C00000",            # Alertas críticos
    "cinza_texto": "#7F7F7F",         # Texto secundário
}

# Layout padrão para todos os gráficos Plotly
PLOTLY_LAYOUT = dict(
    font=dict(family="Montserrat, Calibri, sans-serif", size=12, color=CORES_LLE["azul_profundo"]),
    plot_bgcolor=CORES_LLE["branco"],
    paper_bgcolor=CORES_LLE["branco"],
    xaxis=dict(showgrid=False, linecolor=CORES_LLE["cinza_borda"]),
    yaxis=dict(showgrid=False, linecolor=CORES_LLE["cinza_borda"]),
    colorway=[
        CORES_LLE["azul_profundo"],
        CORES_LLE["amarelo_logo"],
        CORES_LLE["azul_vibrante"],
        CORES_LLE["verde_institucional"],
        CORES_LLE["azul_corporativo"],
        CORES_LLE["cinza_texto"],
    ],
    title_font=dict(size=16, color=CORES_LLE["azul_profundo"], family="Montserrat"),
    hoverlabel=dict(font_family="Montserrat"),
)


# -----------------------------------------------------------------------------
# CSS GLOBAL (customizações da interface Streamlit)
# -----------------------------------------------------------------------------
def aplicar_css_customizado():
    """Aplica identidade visual LLE moderna (header fixo + tabs + cards limpos)."""
    st.markdown(
        f"""
        <style>
            /* ───────────────────────────────────────────────────────── */
            /* TIPOGRAFIA E BASE                                          */
            /* ───────────────────────────────────────────────────────── */
            @import url('https://fonts.googleapis.com/css2?family=Montserrat:wght@400;500;600;700&display=swap');
            
            html, body, [class*="css"], .stApp {{
                font-family: 'Montserrat', 'Calibri', sans-serif !important;
                background-color: #F5F6F8 !important;
            }}
            
            /* Esconde o header padrão do Streamlit */
            header[data-testid="stHeader"] {{
                display: none;
            }}
            
            /* Reduz padding superior */
            .block-container {{
                padding-top: 1rem !important;
                padding-bottom: 2rem !important;
                max-width: 1400px !important;
            }}
            
            /* ───────────────────────────────────────────────────────── */
            /* HEADER FIXO LLE                                            */
            /* ───────────────────────────────────────────────────────── */
            .lle-header {{
                background: linear-gradient(135deg, {CORES_LLE["azul_profundo"]} 0%, {CORES_LLE["azul_corporativo"]} 100%);
                padding: 18px 32px;
                border-radius: 0 0 12px 12px;
                margin-bottom: 24px;
                display: flex;
                align-items: center;
                justify-content: space-between;
                box-shadow: 0 4px 16px rgba(7,22,57,0.15);
            }}
            .lle-header-left {{
                display: flex;
                align-items: center;
                gap: 16px;
            }}
            .lle-logo {{
                background: {CORES_LLE["amarelo_logo"]};
                color: {CORES_LLE["azul_profundo"]};
                width: 48px;
                height: 48px;
                border-radius: 8px;
                display: flex;
                align-items: center;
                justify-content: center;
                font-weight: 800;
                font-size: 16px;
                letter-spacing: -0.5px;
            }}
            .lle-title {{
                color: white;
            }}
            .lle-title h1 {{
                color: white !important;
                margin: 0;
                font-size: 22px;
                font-weight: 700;
                letter-spacing: -0.5px;
            }}
            .lle-title p {{
                color: rgba(255,255,255,0.7);
                margin: 2px 0 0;
                font-size: 12px;
                font-weight: 500;
            }}
            
            /* ───────────────────────────────────────────────────────── */
            /* KPI CARDS (5 cards no topo)                                */
            /* ───────────────────────────────────────────────────────── */
            .kpi-card {{
                background: white;
                border-radius: 12px;
                padding: 16px 18px;
                box-shadow: 0 2px 8px rgba(7,22,57,0.06);
                border: 1px solid #E8EBF0;
                transition: transform 0.15s ease, box-shadow 0.15s ease;
            }}
            .kpi-card:hover {{
                transform: translateY(-2px);
                box-shadow: 0 4px 16px rgba(7,22,57,0.10);
            }}
            .kpi-header {{
                display: flex;
                justify-content: space-between;
                align-items: center;
                margin-bottom: 8px;
            }}
            .kpi-label {{
                font-size: 13px;
                color: #5A6478;
                font-weight: 500;
            }}
            .kpi-icon {{
                color: #C0C7D2;
                font-size: 14px;
            }}
            .kpi-value {{
                font-size: 24px;
                font-weight: 700;
                line-height: 1.1;
                margin-bottom: 6px;
                color: {CORES_LLE["azul_profundo"]};
            }}
            .kpi-value-positive {{ color: {CORES_LLE["verde_institucional"]}; }}
            .kpi-value-negative {{ color: {CORES_LLE["vermelho"]}; }}
            .kpi-value-neutral  {{ color: {CORES_LLE["azul_vibrante"]}; }}
            .kpi-value-warning  {{ color: {CORES_LLE["amarelo_logo"]}; }}
            .kpi-context {{
                font-size: 11px;
                color: #8B95A5;
                font-weight: 400;
            }}
            
            /* ───────────────────────────────────────────────────────── */
            /* CARDS DE CONTEÚDO (DRE, Balanço inferiores)                */
            /* ───────────────────────────────────────────────────────── */
            .content-card {{
                background: white;
                border-radius: 12px;
                padding: 22px 24px;
                box-shadow: 0 2px 8px rgba(7,22,57,0.06);
                border: 1px solid #E8EBF0;
                margin-bottom: 16px;
            }}
            .content-card-title {{
                font-size: 16px;
                font-weight: 600;
                color: {CORES_LLE["azul_profundo"]};
                margin-bottom: 16px;
                padding-bottom: 12px;
                border-bottom: 1px solid #E8EBF0;
                display: flex;
                justify-content: space-between;
                align-items: center;
            }}
            
            /* ───────────────────────────────────────────────────────── */
            /* TABELA EVOLUÇÃO MENSAL                                     */
            /* ───────────────────────────────────────────────────────── */
            .evolucao-table {{
                width: 100%;
                border-collapse: collapse;
                font-size: 13px;
            }}
            .evolucao-table thead th {{
                background: {CORES_LLE["azul_profundo"]};
                color: white;
                padding: 10px 8px;
                text-align: right;
                font-weight: 600;
                font-size: 12px;
                letter-spacing: 0.3px;
            }}
            .evolucao-table thead th:first-child {{
                text-align: left;
                border-radius: 6px 0 0 0;
            }}
            .evolucao-table thead th:last-child {{
                border-radius: 0 6px 0 0;
            }}
            .evolucao-table tbody td {{
                padding: 9px 8px;
                text-align: right;
                border-bottom: 1px solid #F0F2F5;
                font-variant-numeric: tabular-nums;
            }}
            .evolucao-table tbody td:first-child {{
                text-align: left;
                font-weight: 500;
                color: {CORES_LLE["azul_profundo"]};
            }}
            .evolucao-table tbody tr:nth-child(even) {{
                background: #FAFBFC;
            }}
            .evolucao-table tbody td.highlight {{
                color: {CORES_LLE["azul_vibrante"]};
                font-weight: 600;
            }}
            
            /* ───────────────────────────────────────────────────────── */
            /* TABELA DRE SIMPLIFICADA (card inferior)                    */
            /* ───────────────────────────────────────────────────────── */
            .dre-resumo-table {{
                width: 100%;
                border-collapse: collapse;
                font-size: 14px;
            }}
            .dre-resumo-table tr {{
                border-bottom: 1px solid #F0F2F5;
            }}
            .dre-resumo-table td {{
                padding: 11px 8px;
                font-variant-numeric: tabular-nums;
            }}
            .dre-resumo-table td.descricao {{
                color: {CORES_LLE["azul_profundo"]};
                font-weight: 500;
            }}
            .dre-resumo-table td.valor {{
                text-align: right;
                color: {CORES_LLE["azul_profundo"]};
            }}
            .dre-resumo-table tr.destaque-rl td {{
                background: #FAFBFC;
                font-weight: 700;
                border-top: 1px solid #E8EBF0;
                border-bottom: 1px solid #E8EBF0;
            }}
            .dre-resumo-table tr.destaque-final td {{
                background: {CORES_LLE["amarelo_logo"]};
                font-weight: 700;
                color: {CORES_LLE["azul_profundo"]};
                font-size: 15px;
                border-radius: 6px;
            }}
            
            /* ───────────────────────────────────────────────────────── */
            /* BALANÇO (subcabeçalho azul)                                */
            /* ───────────────────────────────────────────────────────── */
            .balanco-bloco {{
                margin-bottom: 16px;
            }}
            .balanco-header {{
                background: {CORES_LLE["azul_profundo"]};
                color: white;
                padding: 8px 14px;
                font-weight: 600;
                font-size: 13px;
                border-radius: 6px 6px 0 0;
                letter-spacing: 0.5px;
            }}
            .balanco-linha {{
                display: flex;
                justify-content: space-between;
                padding: 10px 14px;
                font-size: 14px;
                border-bottom: 1px solid #F0F2F5;
            }}
            .balanco-linha-label {{
                color: {CORES_LLE["azul_profundo"]};
                font-weight: 500;
            }}
            .balanco-linha-valor {{
                font-variant-numeric: tabular-nums;
                color: {CORES_LLE["azul_profundo"]};
            }}
            .balanco-total {{
                background: #FAFBFC;
                font-weight: 700;
                border-top: 2px solid #E8EBF0;
            }}
            
            /* ───────────────────────────────────────────────────────── */
            /* BADGE "Balanço equilibrado"                                */
            /* ───────────────────────────────────────────────────────── */
            .badge-ok {{
                display: inline-flex;
                align-items: center;
                gap: 6px;
                color: {CORES_LLE["verde_institucional"]};
                font-weight: 600;
                font-size: 13px;
                padding: 6px 0;
            }}
            .badge-warn {{
                display: inline-flex;
                align-items: center;
                gap: 6px;
                color: {CORES_LLE["amarelo_logo"]};
                font-weight: 600;
                font-size: 13px;
                padding: 6px 0;
            }}
            
            /* ───────────────────────────────────────────────────────── */
            /* LINK "Detalhar →"                                          */
            /* ───────────────────────────────────────────────────────── */
            .link-detalhar {{
                color: {CORES_LLE["azul_vibrante"]};
                font-size: 13px;
                font-weight: 500;
                text-decoration: none;
            }}
            
            /* ───────────────────────────────────────────────────────── */
            /* TABS HORIZONTAIS (substitui sidebar)                       */
            /* ───────────────────────────────────────────────────────── */
            .stTabs [data-baseweb="tab-list"] {{
                gap: 4px;
                background: {CORES_LLE["azul_profundo"]};
                padding: 0 12px;
                border-radius: 8px;
                margin-bottom: 24px;
            }}
            .stTabs [data-baseweb="tab"] {{
                background: transparent;
                color: rgba(255,255,255,0.7);
                padding: 14px 20px;
                font-weight: 500;
                font-size: 14px;
                border-radius: 0;
                border-bottom: 3px solid transparent;
            }}
            .stTabs [aria-selected="true"] {{
                color: {CORES_LLE["amarelo_logo"]} !important;
                background: transparent !important;
                border-bottom: 3px solid {CORES_LLE["amarelo_logo"]} !important;
            }}
            .stTabs [data-baseweb="tab"]:hover {{
                color: white;
                background: rgba(255,255,255,0.05);
            }}
            
            /* ───────────────────────────────────────────────────────── */
            /* BOTÕES                                                     */
            /* ───────────────────────────────────────────────────────── */
            .stButton > button {{
                background-color: {CORES_LLE["amarelo_logo"]};
                color: {CORES_LLE["azul_profundo"]};
                font-weight: 600;
                border: none;
                border-radius: 8px;
                padding: 8px 16px;
            }}
            .stButton > button:hover {{
                background-color: #E89F0E;
                color: {CORES_LLE["azul_profundo"]};
            }}
            
            /* ───────────────────────────────────────────────────────── */
            /* SELECTBOX no header                                        */
            /* ───────────────────────────────────────────────────────── */
            .header-controls .stSelectbox > div > div {{
                background: white;
                border-radius: 8px;
                border: 1px solid #E8EBF0;
            }}
            
            /* ───────────────────────────────────────────────────────── */
            /* SIDEBAR (mantém pequena para navegação secundária)         */
            /* ───────────────────────────────────────────────────────── */
            [data-testid="stSidebar"] {{
                background: white;
                border-right: 1px solid #E8EBF0;
            }}
            
            /* ───────────────────────────────────────────────────────── */
            /* MÉTRICAS DO STREAMLIT (estilo padronizado)                 */
            /* ───────────────────────────────────────────────────────── */
            [data-testid="stMetricValue"] {{
                color: {CORES_LLE["azul_profundo"]} !important;
                font-weight: 700;
                font-size: 24px;
            }}
            [data-testid="stMetricLabel"] {{
                color: #5A6478 !important;
                font-weight: 500;
                font-size: 13px;
            }}
            [data-testid="stMetricDelta"] {{
                font-size: 12px;
            }}
            
            /* H1/H2 dentro de cards */
            .content-card h1, .content-card h2, .content-card h3 {{
                color: {CORES_LLE["azul_profundo"]};
            }}
            
            /* Esconde footer "Made with Streamlit" */
            footer {{ visibility: hidden; }}
            #MainMenu {{ visibility: hidden; }}
        </style>
        """,
        unsafe_allow_html=True
    )


def render_header(usuario, periodo_atual_label="—", modo_label="Sem ajustes"):
    """Renderiza o header LLE no topo da página."""
    st.markdown(
        f"""
        <div class='lle-header'>
            <div class='lle-header-left'>
                <div class='lle-logo'>LLE</div>
                <div class='lle-title'>
                    <h1>LLE Ferragens</h1>
                    <p>Análise Contábil · Posição 2025 + 2026 · {usuario.get('nome','')}</p>
                </div>
            </div>
            <div style='display: flex; gap: 8px; align-items: center;'>
                <span style='color: rgba(255,255,255,0.6); font-size: 12px;'>Perfil: {usuario.get('perfil','').upper()}</span>
            </div>
        </div>
        """,
        unsafe_allow_html=True
    )


def render_kpi_card(label: str, valor: str, contexto: str = "", cor: str = "neutral", icone: str = "📊"):
    """
    Renderiza um KPI card no estilo da referência.
    
    cor: 'positive', 'negative', 'neutral', 'warning', 'default'
    """
    classe_cor = {
        "positive": "kpi-value-positive",
        "negative": "kpi-value-negative",
        "neutral": "kpi-value-neutral",
        "warning": "kpi-value-warning",
        "default": "",
    }.get(cor, "")
    
    return f"""
        <div class='kpi-card'>
            <div class='kpi-header'>
                <span class='kpi-label'>{label}</span>
                <span class='kpi-icon'>{icone}</span>
            </div>
            <div class='kpi-value {classe_cor}'>{valor}</div>
            <div class='kpi-context'>{contexto}</div>
        </div>
    """


# -----------------------------------------------------------------------------
# LISTA PADRÃO DE PERÍODOS (Posição 2025 + 12 meses de 2026)
# -----------------------------------------------------------------------------
PERIODOS_PADRAO = [
    "Posição 2025",
    "jan-26", "fev-26", "mar-26", "abr-26", "mai-26", "jun-26",
    "jul-26", "ago-26", "set-26", "out-26", "nov-26", "dez-26"
]

MESES_NOMES_LONGOS = {
    "janeiro": "jan-26", "fevereiro": "fev-26", "março": "mar-26", "marco": "mar-26",
    "abril": "abr-26", "maio": "mai-26", "junho": "jun-26",
    "julho": "jul-26", "agosto": "ago-26", "setembro": "set-26",
    "outubro": "out-26", "novembro": "nov-26", "dezembro": "dez-26",
}


# -----------------------------------------------------------------------------
# CONEXÃO COM SUPABASE (cliente único, cacheado)
# -----------------------------------------------------------------------------
@st.cache_resource
def get_supabase() -> Client:
    """Retorna o cliente Supabase (criado uma vez e reusado)."""
    try:
        url = st.secrets["SUPABASE_URL"]
        key = st.secrets["SUPABASE_KEY"]
        return create_client(url, key)
    except KeyError as e:
        st.error(
            f"❌ Credencial não encontrada nos Secrets: {e}\n\n"
            "Configure em: share.streamlit.io → seu app → Settings → Secrets"
        )
        st.stop()
    except Exception as e:
        st.error(f"❌ Erro ao conectar com Supabase: {e}")
        st.stop()


# -----------------------------------------------------------------------------
# GERENCIADOR DE COOKIES (autenticação persistente)
# -----------------------------------------------------------------------------
def get_cookie_manager():
    """
    Cria o gerenciador de cookies criptografados para manter o login ativo
    entre refreshes (até 7 dias).
    
    A senha de criptografia vem dos Secrets (chave COOKIE_PASSWORD).
    Se não definida, usa fallback (menos seguro, mas funcional).
    """
    try:
        senha_cookie = st.secrets.get("COOKIE_PASSWORD", "lle_default_cookie_key_2026")
    except Exception:
        senha_cookie = "lle_default_cookie_key_2026"
    
    cookies = EncryptedCookieManager(
        prefix="lle_contabil/",
        password=senha_cookie,
    )
    return cookies


# -----------------------------------------------------------------------------
# UTILITÁRIOS DE SENHA (bcrypt)
# -----------------------------------------------------------------------------
def hash_senha(senha: str) -> str:
    """Gera hash bcrypt seguro de uma senha."""
    return bcrypt.hashpw(senha.encode("utf-8"), bcrypt.gensalt(rounds=12)).decode("utf-8")


def verificar_senha(senha: str, senha_hash: str) -> bool:
    """Verifica se uma senha corresponde ao hash armazenado."""
    if not senha or not senha_hash:
        return False
    try:
        return bcrypt.checkpw(senha.encode("utf-8"), senha_hash.encode("utf-8"))
    except Exception:
        return False


def validar_forca_senha(senha: str) -> tuple:
    """
    Valida a força da senha.
    Returns: (eh_valida: bool, mensagem: str)
    """
    if len(senha) < 6:
        return False, "A senha deve ter no mínimo 6 caracteres."
    if not any(c.isdigit() for c in senha) and not any(not c.isalnum() for c in senha):
        return False, "A senha deve conter pelo menos um número ou caractere especial."
    return True, "OK"


# -----------------------------------------------------------------------------
# AUTENTICAÇÃO — validação de usuário com senha
# -----------------------------------------------------------------------------
def validar_usuario(email: str, senha: str = None):
    """
    Valida o e-mail e (opcionalmente) a senha contra a tabela 'usuarios'.
    
    Args:
        email: e-mail informado no login (em lowercase)
        senha: senha em texto plano (se None, valida só o e-mail — uso interno)
    
    Returns:
        dict com {email, nome, perfil, senha_temporaria} se autorizado e ativo
        None caso contrário
    """
    try:
        supabase = get_supabase()
        resposta = (
            supabase.table("usuarios")
            .select("*")
            .eq("email", email)
            .execute()
        )
        if not resposta.data or len(resposta.data) == 0:
            return None
        
        usuario = resposta.data[0]
        
        # Verifica se está ativo
        if not usuario.get("ativo", True):
            return None
        
        # Se foi passada uma senha, valida
        if senha is not None:
            senha_hash = usuario.get("senha_hash", "")
            if not senha_hash:
                # Usuário sem senha cadastrada — força usar a senha padrão
                return None
            if not verificar_senha(senha, senha_hash):
                return None
            
            # Senha correta: atualiza último login
            try:
                supabase.table("usuarios").update({
                    "ultimo_login": datetime.now().isoformat()
                }).eq("email", email).execute()
            except Exception:
                pass
        
        return {
            "email": usuario["email"],
            "nome": usuario.get("nome", email.split("@")[0]),
            "perfil": usuario.get("perfil", "diretoria"),
            "senha_temporaria": usuario.get("senha_temporaria", False),
        }
    except Exception as e:
        st.error(f"Erro ao validar usuário: {e}")
        return None


def trocar_senha(email: str, senha_atual: str, senha_nova: str) -> tuple:
    """
    Troca a senha de um usuário (requer a senha atual).
    
    Returns: (sucesso: bool, mensagem: str)
    """
    # Valida força da nova senha
    eh_valida, msg = validar_forca_senha(senha_nova)
    if not eh_valida:
        return False, msg
    
    if senha_atual == senha_nova:
        return False, "A nova senha deve ser diferente da senha atual."
    
    # Valida usuário + senha atual
    usuario = validar_usuario(email, senha_atual)
    if not usuario:
        return False, "Senha atual incorreta."
    
    # Atualiza senha
    try:
        supabase = get_supabase()
        novo_hash = hash_senha(senha_nova)
        supabase.table("usuarios").update({
            "senha_hash": novo_hash,
            "senha_temporaria": False,
        }).eq("email", email).execute()
        return True, "Senha alterada com sucesso!"
    except Exception as e:
        return False, f"Erro ao salvar nova senha: {e}"


def resetar_senha_admin(email: str, nova_senha: str, admin_email: str) -> tuple:
    """
    Admin reseta a senha de outro usuário (sem precisar da senha atual).
    A nova senha é marcada como temporária — usuário será forçado a trocar.
    
    Returns: (sucesso: bool, mensagem: str)
    """
    eh_valida, msg = validar_forca_senha(nova_senha)
    if not eh_valida:
        return False, msg
    
    try:
        supabase = get_supabase()
        novo_hash = hash_senha(nova_senha)
        supabase.table("usuarios").update({
            "senha_hash": novo_hash,
            "senha_temporaria": True,
        }).eq("email", email).execute()
        
        # Registra a ação na auditoria
        registrar_ajuste(
            usuario_email=admin_email,
            periodo="-",
            classificacao="ADMIN",
            valor_antigo=0,
            valor_novo=0,
            justificativa=f"Reset de senha do usuário {email}",
        )
        
        return True, f"Senha de {email} resetada. Comunique a senha temporária ao usuário."
    except Exception as e:
        return False, f"Erro: {e}"


# -----------------------------------------------------------------------------
# RECUPERAÇÃO DE SENHA — Pedidos de reset
# -----------------------------------------------------------------------------
def criar_pedido_reset(email: str) -> tuple:
    """
    Usuário solicita reset de senha. Gera código de 6 dígitos.
    
    Returns: (sucesso: bool, codigo_ou_msg: str)
    """
    try:
        supabase = get_supabase()
        
        # Verifica se o e-mail existe e está ativo
        resp = supabase.table("usuarios").select("email,ativo").eq("email", email).execute()
        if not resp.data:
            # Não revelamos se o e-mail existe (segurança)
            return True, "Se o e-mail estiver cadastrado, sua solicitação foi registrada."
        if not resp.data[0].get("ativo", True):
            return True, "Se o e-mail estiver cadastrado, sua solicitação foi registrada."
        
        # Cancela pedidos pendentes anteriores do mesmo e-mail
        supabase.table("pedidos_reset").update({"status": "cancelado"}).eq(
            "email", email
        ).eq("status", "pendente").execute()
        
        # Gera código de 6 dígitos
        codigo = "".join([str(py_secrets.randbelow(10)) for _ in range(6)])
        expira = datetime.now() + timedelta(hours=24)
        
        supabase.table("pedidos_reset").insert({
            "email": email,
            "codigo": codigo,
            "expira_em": expira.isoformat(),
            "status": "pendente",
        }).execute()
        
        return True, codigo
    except Exception as e:
        return False, f"Erro ao criar pedido: {e}"


def listar_pedidos_reset(apenas_pendentes: bool = True) -> list:
    """Lista pedidos de reset (visão do admin)."""
    try:
        supabase = get_supabase()
        query = supabase.table("pedidos_reset").select("*")
        if apenas_pendentes:
            query = query.eq("status", "pendente")
        resp = query.order("solicitado_em", desc=True).execute()
        return resp.data if resp.data else []
    except Exception:
        return []


def aprovar_pedido_reset(pedido_id: int, admin_email: str, nova_senha: str) -> tuple:
    """
    Admin aprova um pedido de reset e define uma nova senha temporária.
    O usuário será notificado fora do app (telefone/whatsapp).
    
    Returns: (sucesso: bool, mensagem: str)
    """
    try:
        supabase = get_supabase()
        
        # Busca o pedido
        resp = supabase.table("pedidos_reset").select("*").eq("id", pedido_id).execute()
        if not resp.data:
            return False, "Pedido não encontrado."
        
        pedido = resp.data[0]
        if pedido["status"] != "pendente":
            return False, f"Pedido já está com status '{pedido['status']}'."
        
        email_usuario = pedido["email"]
        
        # Reseta a senha do usuário
        ok, msg = resetar_senha_admin(email_usuario, nova_senha, admin_email)
        if not ok:
            return False, msg
        
        # Marca pedido como aprovado
        supabase.table("pedidos_reset").update({
            "status": "aprovado",
            "aprovado_por": admin_email,
            "aprovado_em": datetime.now().isoformat(),
        }).eq("id", pedido_id).execute()
        
        return True, f"✅ Senha de {email_usuario} resetada. Comunique a nova senha por canal seguro (WhatsApp/telefone)."
    except Exception as e:
        return False, f"Erro: {e}"


def cancelar_pedido_reset(pedido_id: int) -> bool:
    """Admin cancela um pedido de reset (rejeita)."""
    try:
        supabase = get_supabase()
        supabase.table("pedidos_reset").update({
            "status": "cancelado"
        }).eq("id", pedido_id).execute()
        return True
    except Exception:
        return False

# ═══════════════════════════════════════════════════════════════════════════════
# BLOCO 2 — CARREGAMENTO DE DADOS E UTILITÁRIOS
# ═══════════════════════════════════════════════════════════════════════════════


# -----------------------------------------------------------------------------
# UTILITÁRIOS DE FORMATAÇÃO BR
# -----------------------------------------------------------------------------
def formatar_brl(valor, casas=0):
    """Formata número como moeda brasileira: R$ 1.234,56"""
    try:
        if pd.isna(valor) or valor is None:
            return "R$ -"
        if casas == 0:
            return f"R$ {valor:,.0f}".replace(",", "X").replace(".", ",").replace("X", ".")
        return f"R$ {valor:,.{casas}f}".replace(",", "X").replace(".", ",").replace("X", ".")
    except Exception:
        return "R$ 0"


def formatar_pct(valor, casas=2):
    """Formata número como percentual brasileiro: 12,50%"""
    try:
        if pd.isna(valor) or valor is None:
            return "-"
        return f"{valor:,.{casas}f}%".replace(".", ",")
    except Exception:
        return "0,00%"


def formatar_num(valor, casas=2):
    """Formata número decimal brasileiro: 1,23"""
    try:
        if pd.isna(valor) or valor is None:
            return "-"
        return f"{valor:,.{casas}f}".replace(",", "X").replace(".", ",").replace("X", ".")
    except Exception:
        return "0,00"


# -----------------------------------------------------------------------------
# UTILITÁRIOS DE NORMALIZAÇÃO DE TEXTO
# -----------------------------------------------------------------------------
def normalizar_texto(texto: str) -> str:
    """
    Normaliza texto: lowercase, sem acentos, espaços limpos.
    Útil para comparações flexíveis (nomes de aba, contas DFC).
    """
    if texto is None or pd.isna(texto):
        return ""
    texto = str(texto).strip().lower()
    # Remove acentos
    texto = unicodedata.normalize("NFKD", texto)
    texto = "".join(c for c in texto if not unicodedata.combining(c))
    # Remove espaços extras
    texto = " ".join(texto.split())
    return texto


def normalizar_nome_aba(nome: str) -> str:
    """
    Normaliza nome de aba removendo separadores comuns.
    Ex: 'DRE Matriz', 'dre_matriz', 'DRE-MATRIZ' → 'drematriz'
    """
    n = normalizar_texto(nome)
    for sep in [" ", "_", "-", ".", "/"]:
        n = n.replace(sep, "")
    return n


def calcular_similaridade(s1: str, s2: str) -> float:
    """
    Calcula similaridade entre duas strings (0-100%) usando algoritmo
    de Ratio do difflib (não requer biblioteca externa).
    """
    from difflib import SequenceMatcher
    s1_n = normalizar_texto(s1)
    s2_n = normalizar_texto(s2)
    if not s1_n or not s2_n:
        return 0.0
    return SequenceMatcher(None, s1_n, s2_n).ratio() * 100


# -----------------------------------------------------------------------------
# CARREGAMENTO DE DADOS CONTÁBEIS DO SUPABASE
# -----------------------------------------------------------------------------
@st.cache_data(ttl=300, show_spinner="Carregando dados contábeis...")
def carregar_dados_contabeis():
    """
    Carrega todos os registros da tabela dados_contabeis e devolve
    em formato WIDE (uma coluna por período).
    
    Returns:
        DataFrame com colunas: demonstrativo, unidade, classificacao, descricao,
        Posição 2025, jan-26, fev-26, ..., dez-26
        Ou None se não houver dados.
    """
    try:
        supabase = get_supabase()
        
        # Pagina os resultados (limite padrão do Supabase é 1000)
        todos_registros = []
        pagina = 0
        tamanho_pagina = 1000
        
        while True:
            inicio = pagina * tamanho_pagina
            fim = inicio + tamanho_pagina - 1
            resp = (
                supabase.table("dados_contabeis")
                .select("*")
                .range(inicio, fim)
                .execute()
            )
            if not resp.data:
                break
            todos_registros.extend(resp.data)
            if len(resp.data) < tamanho_pagina:
                break
            pagina += 1
        
        if not todos_registros:
            return None
        
        df_long = pd.DataFrame(todos_registros)
        
        # Padroniza nome do período acumulado
        if "periodo" in df_long.columns:
            df_long["periodo"] = df_long["periodo"].replace({
                "posicao_2025": "Posição 2025",
                "Posicao_2025": "Posição 2025",
            })
        
        # Garante que classificacao seja string
        df_long["classificacao"] = df_long["classificacao"].fillna("").astype(str)
        df_long["descricao"] = df_long["descricao"].fillna("").astype(str)
        
        # Faz o pivot para o formato wide
        if "periodo" in df_long.columns and "valor" in df_long.columns:
            df_wide = df_long.pivot_table(
                index=["demonstrativo", "unidade", "classificacao", "descricao"],
                columns="periodo",
                values="valor",
                aggfunc="sum",
                fill_value=0,
            ).reset_index()
            df_wide.columns.name = None
            
            # Reordena períodos cronologicamente
            colunas_fixas = ["demonstrativo", "unidade", "classificacao", "descricao"]
            colunas_periodo = [p for p in PERIODOS_PADRAO if p in df_wide.columns]
            df_wide = df_wide[colunas_fixas + colunas_periodo]
            return df_wide
        
        return df_long
    
    except Exception as e:
        st.error(f"❌ Erro ao carregar dados: {e}")
        return None


# -----------------------------------------------------------------------------
# PERSISTÊNCIA DE REGISTROS NO SUPABASE
# -----------------------------------------------------------------------------
def salvar_no_supabase(registros: list, usuario_email: str, modo: str = "completo") -> bool:
    """
    Salva uma lista de registros (formato LONG) no Supabase.
    
    Args:
        registros: lista de dicts com {demonstrativo, unidade, classificacao,
                   descricao, conta_reduzida, periodo, valor}
        usuario_email: e-mail do usuário (auditoria)
        modo: 'completo' (apaga tudo do mesmo demonstrativo+unidade antes de inserir)
              'incremental' (faz upsert)
    
    Returns:
        True se sucesso, False se erro
    """
    if not registros:
        st.warning("Nenhum registro para salvar.")
        return False
    
    try:
        supabase = get_supabase()
        
        # Modo completo: apaga combinações (demonstrativo, unidade) que estão no upload
        if modo == "completo":
            combinacoes = set((r["demonstrativo"], r["unidade"]) for r in registros)
            for demo, uni in combinacoes:
                supabase.table("dados_contabeis").delete().eq(
                    "demonstrativo", demo
                ).eq("unidade", uni).execute()
        
        # Adiciona auditoria em cada registro
        for r in registros:
            r["uploaded_by"] = usuario_email
            r["uploaded_at"] = datetime.now().isoformat()
        
        # Insere em lotes de 500
        TAMANHO_LOTE = 500
        total = len(registros)
        progresso = st.progress(0, text="Salvando...")
        
        for i in range(0, total, TAMANHO_LOTE):
            lote = registros[i : i + TAMANHO_LOTE]
            supabase.table("dados_contabeis").insert(lote).execute()
            progresso.progress(min((i + TAMANHO_LOTE) / total, 1.0),
                                text=f"Salvando... {min(i + TAMANHO_LOTE, total)}/{total}")
        
        progresso.empty()
        
        # Limpa o cache para forçar reload
        carregar_dados_contabeis.clear()
        return True
    
    except Exception as e:
        st.error(f"❌ Erro ao salvar: {e}")
        return False


# -----------------------------------------------------------------------------
# GESTÃO DE USUÁRIOS
# -----------------------------------------------------------------------------
def listar_usuarios() -> list:
    """Retorna lista de todos os usuários cadastrados."""
    try:
        supabase = get_supabase()
        resp = supabase.table("usuarios").select("*").execute()
        return resp.data if resp.data else []
    except Exception as e:
        st.error(f"Erro ao listar usuários: {e}")
        return []


def cadastrar_usuario(email: str, nome: str, perfil: str) -> bool:
    """Cadastra novo usuário na tabela 'usuarios'."""
    try:
        supabase = get_supabase()
        supabase.table("usuarios").insert({
            "email": email.lower().strip(),
            "nome": nome.strip(),
            "perfil": perfil,
            "ativo": True,
        }).execute()
        return True
    except Exception as e:
        st.error(f"Erro ao cadastrar usuário: {e}")
        return False


def desativar_usuario(email: str) -> bool:
    """Marca um usuário como inativo (preserva histórico)."""
    try:
        supabase = get_supabase()
        supabase.table("usuarios").update({"ativo": False}).eq("email", email).execute()
        return True
    except Exception as e:
        st.error(f"Erro ao desativar usuário: {e}")
        return False


# -----------------------------------------------------------------------------
# MAPEAMENTO DFC
# -----------------------------------------------------------------------------
def carregar_mapeamento_dfc() -> dict:
    """Carrega mapeamento DFC aprovado. Retorna dict {codigo_hash: registro}."""
    try:
        supabase = get_supabase()
        resp = supabase.table("dfc_contas_mapeamento").select("*").execute()
        if resp.data:
            return {item["codigo_gerado"]: item for item in resp.data}
        return {}
    except Exception:
        return {}


def salvar_mapeamento_dfc(contas: list, usuario_email: str) -> bool:
    """Salva o mapeamento DFC aprovado no Supabase."""
    try:
        supabase = get_supabase()
        for conta in contas:
            registro = {
                "codigo_gerado": conta["codigo"],
                "descricao_original": conta["descricao"],
                "descricao_normalizada": normalizar_texto(conta["descricao"]),
                "classificacao_inferida": conta.get("classificacao", ""),
                "tipo_hierarquia": conta.get("tipo_hierarquia", "analitica"),
                "aprovado": True,
                "aprovado_por": usuario_email,
                "aprovado_em": datetime.now().isoformat(),
            }
            supabase.table("dfc_contas_mapeamento").upsert(
                registro, on_conflict="codigo_gerado"
            ).execute()
        return True
    except Exception as e:
        st.error(f"Erro ao salvar mapeamento DFC: {e}")
        return False


# -----------------------------------------------------------------------------
# AJUSTES MANUAIS (trilha de auditoria)
# -----------------------------------------------------------------------------
def registrar_ajuste(usuario_email: str, periodo: str, classificacao: str,
                      valor_antigo: float, valor_novo: float, justificativa: str) -> bool:
    """Grava um ajuste manual na tabela 'ajustes' (auditoria)."""
    try:
        supabase = get_supabase()
        supabase.table("ajustes").insert({
            "usuario_email": usuario_email,
            "periodo": periodo,
            "classificacao": classificacao,
            "valor_antigo": float(valor_antigo),
            "valor_novo": float(valor_novo),
            "justificativa": justificativa,
            "data": datetime.now().isoformat(),
        }).execute()
        return True
    except Exception as e:
        st.error(f"Erro ao registrar ajuste: {e}")
        return False


# -----------------------------------------------------------------------------
# CONSOLIDAÇÃO DRE (Matriz + Filial)
# -----------------------------------------------------------------------------
def consolidar_dre(df: pd.DataFrame) -> pd.DataFrame:
    """
    Gera linhas consolidadas de DRE somando Matriz + Filial por classificação.
    Adiciona ao DataFrame original linhas com unidade='Consolidado'.
    
    Pré-requisito: plano de contas idêntico entre Matriz e Filial.
    """
    dre = df[df["demonstrativo"] == "DRE"].copy()
    if len(dre) == 0:
        return df
    
    # Filtra Matriz e Filial
    matriz_filial = dre[dre["unidade"].isin(["Matriz", "Filial"])].copy()
    if len(matriz_filial) == 0:
        return df
    
    # Identifica colunas de período
    colunas_periodo = [c for c in df.columns if c in PERIODOS_PADRAO]
    
    # Soma por classificação + descrição
    consol = (
        matriz_filial.groupby(["classificacao", "descricao"], as_index=False)[colunas_periodo]
        .sum()
    )
    consol["demonstrativo"] = "DRE"
    consol["unidade"] = "Consolidado"
    
    # Garante ordem de colunas idêntica ao original
    colunas_fixas = ["demonstrativo", "unidade", "classificacao", "descricao"]
    colunas_finais = colunas_fixas + colunas_periodo
    consol = consol[colunas_finais]
    
    # Concatena
    df_resultado = pd.concat([df, consol], ignore_index=True)
    return df_resultado


# -----------------------------------------------------------------------------
# CONVERSÃO BP: variações → saldos acumulados
# -----------------------------------------------------------------------------
def periodos_disponiveis(df: pd.DataFrame, demonstrativo: str = None) -> list:
    """
    Lista os períodos que tem DADOS REAIS para um determinado demonstrativo.
    
    Diferente da lista PERIODOS_PADRAO (que é fixa), aqui filtramos só
    períodos que tem ao menos um valor não-zero para o demonstrativo.
    
    Útil porque a DRE NÃO tem "Posição 2025" (é fluxo, só meses do ano).
    """
    colunas_periodo = [c for c in PERIODOS_PADRAO if c in df.columns]
    
    if demonstrativo is None:
        return colunas_periodo
    
    df_demo = df[df["demonstrativo"] == demonstrativo]
    if len(df_demo) == 0:
        return []
    
    # Mantém só períodos com pelo menos uma linha não-zerada
    periodos_com_dados = []
    for periodo in colunas_periodo:
        if periodo in df_demo.columns:
            if df_demo[periodo].abs().sum() > 0:
                periodos_com_dados.append(periodo)
    
    return periodos_com_dados


def calcular_saldos_acumulados_bp(df: pd.DataFrame) -> pd.DataFrame:
    """
    Converte VARIAÇÕES mensais do BP em SALDOS ACUMULADOS.
    
    Como o BP do Excel da LLE traz variações mensais (jan-26 = mudança em janeiro),
    precisamos somar acumulado: Posição 2025 + jan-26 = saldo em jan-26.
    
    Adiciona colunas '<periodo>_saldo' ao DataFrame.
    """
    df = df.copy()
    bp_mask = df["demonstrativo"] == "BP"
    
    # Ordem cronológica dos meses
    meses_2026 = [m for m in PERIODOS_PADRAO if m != "Posição 2025" and m in df.columns]
    
    # Saldo de Posição 2025 é o ponto de partida (já é saldo absoluto)
    if "Posição 2025" in df.columns:
        df.loc[bp_mask, "Posição 2025_saldo"] = df.loc[bp_mask, "Posição 2025"]
    
    # Vai acumulando mês a mês
    saldo_anterior = df.loc[bp_mask, "Posição 2025"].copy() if "Posição 2025" in df.columns else 0
    
    for mes in meses_2026:
        df.loc[bp_mask, f"{mes}_saldo"] = saldo_anterior + df.loc[bp_mask, mes]
        saldo_anterior = df.loc[bp_mask, f"{mes}_saldo"].copy()
    
    return df

# ═══════════════════════════════════════════════════════════════════════════════
# BLOCO 3 — PARSER DE EXCEL + VALIDAÇÃO DFC
# ═══════════════════════════════════════════════════════════════════════════════


# -----------------------------------------------------------------------------
# MAPA DE NOMES DE ABA (normalizado → tipo/unidade)
# Aceita variações: 'DRE_Matriz', 'dre matriz', 'DRE-MATRIZ', 'DreMatriz', etc.
# -----------------------------------------------------------------------------
SHEET_MAP_NORMALIZADO = {
    "drematriz": ("DRE", "Matriz"),
    "drefilial": ("DRE", "Filial"),
    "bpconsol": ("BP", "Consol"),
    "bpconsolidado": ("BP", "Consol"),
    "dfcconsol": ("DFC", "Consol"),
    "dfcconsolidado": ("DFC", "Consol"),
}


def identificar_aba(nome_aba: str):
    """
    Identifica o tipo e unidade de uma aba pelo nome (flexível).
    
    Returns:
        Tupla (demonstrativo, unidade) ou (None, None) se não reconhecida.
    """
    nome_normalizado = normalizar_nome_aba(nome_aba)
    return SHEET_MAP_NORMALIZADO.get(nome_normalizado, (None, None))


# -----------------------------------------------------------------------------
# GERAÇÃO DE CÓDIGO DFC (hash MD5 estável)
# -----------------------------------------------------------------------------
def gerar_codigo_dfc(descricao: str) -> str:
    """
    Gera código único para conta DFC baseado em hash MD5 da descrição
    normalizada. Mesma descrição = mesmo código, sempre.
    
    Returns:
        String tipo 'DFC_a1b2c3d4' (8 caracteres do hash)
    """
    desc_normalizada = normalizar_texto(descricao)
    hash_md5 = hashlib.md5(desc_normalizada.encode("utf-8")).hexdigest()
    return f"DFC_{hash_md5[:8]}"


# -----------------------------------------------------------------------------
# INFERÊNCIA DE HIERARQUIA DFC
# -----------------------------------------------------------------------------
def inferir_hierarquia_dfc(descricao: str):
    """
    Infere o tipo hierárquico de uma linha do DFC pela descrição.
    
    Returns:
        Tupla (tipo_hierarquia, classificacao_inferida)
        tipo_hierarquia: 'cabecalho', 'subtotal', 'total', 'analitica', 'saldo'
        classificacao_inferida: código tipo '5.1', '5.2', '5.3' (operacional, invest, financ)
    """
    desc_upper = descricao.upper().strip()
    
    # Cabeçalhos de seção
    if any(p in desc_upper for p in [
        "FLUXO DE CAIXA DAS ATIVIDADES OPERACIONAIS",
        "ATIVIDADES OPERACIONAIS",
    ]):
        return "cabecalho", "5.1"
    if "ATIVIDADES DE INVESTIMENTO" in desc_upper:
        return "cabecalho", "5.2"
    if "ATIVIDADES DE FINANCIAMENTO" in desc_upper:
        return "cabecalho", "5.3"
    
    # Totais/Subtotais
    if any(p in desc_upper for p in [
        "CAIXA LÍQUIDO GERADO", "CAIXA LIQUIDO GERADO",
        "CAIXA LÍQUIDO APLICADO", "CAIXA LIQUIDO APLICADO",
        "(=)", "TOTAL "
    ]):
        if "OPERACI" in desc_upper:
            return "subtotal", "5.1.99"
        elif "INVESTI" in desc_upper:
            return "subtotal", "5.2.99"
        elif "FINANCI" in desc_upper:
            return "subtotal", "5.3.99"
        else:
            return "subtotal", "5.99"
    
    # Saldos de caixa
    if "SALDO" in desc_upper and "CAIXA" in desc_upper:
        if "INICIAL" in desc_upper:
            return "saldo", "5.0.01"
        elif "FINAL" in desc_upper:
            return "saldo", "5.0.02"
        return "saldo", "5.0"
    
    # Variação de caixa
    if "VARIAÇÃO" in desc_upper or "VARIACAO" in desc_upper:
        return "total", "5.0.99"
    
    # Padrão: linha analítica, infere seção pelo contexto da descrição
    if any(p in desc_upper for p in ["RECEBIMENTO", "PAGAMENTO", "FORNECEDOR", "CLIENTE",
                                       "IMPOSTO", "SALARIO", "SALÁRIO", "TRIBUTO"]):
        return "analitica", "5.1.01"
    if any(p in desc_upper for p in ["IMOBILIZADO", "INVESTIMENTO", "AQUISIÇÃO", "AQUISICAO",
                                       "VENDA DE ATIVO"]):
        return "analitica", "5.2.01"
    if any(p in desc_upper for p in ["EMPRÉSTIMO", "EMPRESTIMO", "FINANCIAMENTO",
                                       "DIVIDENDO", "CAPITAL"]):
        return "analitica", "5.3.01"
    
    return "analitica", "5.99.99"


# -----------------------------------------------------------------------------
# PARSER PRINCIPAL DO EXCEL
# -----------------------------------------------------------------------------
def parse_excel_lle(arquivo):
    """
    Parser principal do Excel da LLE Ferragens.
    
    Funcionalidades:
        - Detecta as 4 abas (com nomes flexíveis)
        - Inverte sinais quando detecta convenção contábil
        - Ignora colunas extras (Total, Posição 2026)
        - Gera códigos DFC via hash MD5
        - Identifica linhas especiais (subtotais, totais)
    
    Returns:
        dict com:
            'sucesso': bool
            'registros': lista de dicts no formato LONG
            'abas_encontradas': lista de nomes de aba processadas
            'abas_ignoradas': lista de nomes de aba ignoradas
            'avisos': lista de mensagens informativas
            'contas_dfc_novas': lista de contas DFC detectadas
            'erro': str (se sucesso=False)
    """
    resultado = {
        "sucesso": False,
        "registros": [],
        "abas_encontradas": [],
        "abas_ignoradas": [],
        "avisos": [],
        "contas_dfc_novas": [],
        "erro": None,
    }
    
    try:
        xls = pd.ExcelFile(arquivo)
        
        for nome_aba in xls.sheet_names:
            demo, unidade = identificar_aba(nome_aba)
            
            if not demo:
                resultado["abas_ignoradas"].append(nome_aba)
                continue
            
            resultado["abas_encontradas"].append(f"{nome_aba} → {demo}/{unidade}")
            
            # === PROCESSAMENTO ESPECÍFICO POR TIPO ===
            if demo == "DFC":
                registros_dfc, contas_novas = _processar_dfc(
                    arquivo, nome_aba, resultado["avisos"]
                )
                resultado["registros"].extend(registros_dfc)
                resultado["contas_dfc_novas"].extend(contas_novas)
            else:
                # DRE ou BP
                registros = _processar_dre_bp(
                    arquivo, nome_aba, demo, unidade, resultado["avisos"]
                )
                resultado["registros"].extend(registros)
        
        if not resultado["registros"]:
            resultado["erro"] = (
                "Nenhum registro extraído. Verifique se as abas estão com nomes "
                "reconhecíveis: DRE_Matriz, DRE_Filial, BP_Consol, DFC_Consol."
            )
            return resultado
        
        resultado["sucesso"] = True
        return resultado
    
    except Exception as e:
        tb = traceback.format_exc()
        resultado["erro"] = f"{type(e).__name__}: {e}\n\n{tb}"
        return resultado


# -----------------------------------------------------------------------------
# PROCESSAMENTO DE DRE E BP
# -----------------------------------------------------------------------------
def _processar_dre_bp(arquivo, nome_aba: str, demo: str, unidade: str, avisos: list) -> list:
    """
    Processa uma aba de DRE ou BP.
    
    Returns:
        Lista de registros no formato LONG.
    """
    df = pd.read_excel(arquivo, sheet_name=nome_aba)
    cols = df.columns.tolist()
    registros = []
    
    if not cols:
        avisos.append(f"⚠️ Aba '{nome_aba}' está vazia.")
        return []
    
    # Detecta colunas (flexível)
    col_reduzida = next(
        (c for c in cols if "reduzida" in str(c).lower()
         or str(c).strip().lower() == "conta"),
        cols[0]
    )
    col_classif = next(
        (c for c in cols if "classif" in str(c).lower()),
        cols[1] if len(cols) > 1 else None
    )
    col_desc = next(
        (c for c in cols if "descri" in str(c).lower()),
        cols[2] if len(cols) > 2 else None
    )
    
    # === MAPEIA COLUNAS DE PERÍODO ===
    col_periodo_map = {}
    for col in cols:
        col_str = str(col).lower().strip()
        # Posição 2025
        if "posi" in col_str and "25" in col_str:
            col_periodo_map[col] = "Posição 2025"
            continue
        # Posição 2026 → IGNORAR (BP traz, mas calculamos do zero)
        if "posi" in col_str and "26" in col_str:
            continue
        # Colunas "Total" → IGNORAR
        if col_str == "total":
            continue
        # Meses de 2026
        for mes_long, mes_short in MESES_NOMES_LONGOS.items():
            if mes_long in col_str:
                col_periodo_map[col] = mes_short
                break
        else:
            # Tenta abreviações tipo "jan", "fev"
            for mes_padrao in PERIODOS_PADRAO[1:]:  # jan-26 ... dez-26
                mes_abrev = mes_padrao.split("-")[0]
                if mes_abrev in col_str and ("26" in col_str or "2026" in col_str):
                    col_periodo_map[col] = mes_padrao
                    break
    
    if not col_periodo_map:
        avisos.append(f"⚠️ Aba '{nome_aba}': nenhuma coluna de período identificada.")
        return []
    
    # === DETECTA CONVENÇÃO DE SINAIS ===
    inverter_dre = False
    inverter_bp = False
    
    if demo == "DRE" and col_desc:
        primeiro_periodo = list(col_periodo_map.keys())[0]
        mask_rb = df[col_desc].astype(str).str.contains(
            "RECEITA BRUTA", case=False, na=False, regex=False
        )
        if mask_rb.any():
            valor_rb = df.loc[mask_rb, primeiro_periodo].iloc[0]
            if pd.notna(valor_rb) and float(valor_rb) < 0:
                inverter_dre = True
                avisos.append(
                    f"🔄 {nome_aba}: convenção contábil detectada → sinais invertidos para gerencial"
                )
    
    if demo == "BP" and col_desc:
        primeiro_periodo = list(col_periodo_map.keys())[0]
        mask_pass = df[col_desc].astype(str).str.contains(
            "PASSIVO", case=False, na=False, regex=False
        )
        if mask_pass.any():
            valor_pass = df.loc[mask_pass, primeiro_periodo].iloc[0]
            if pd.notna(valor_pass) and float(valor_pass) < 0:
                inverter_bp = True
                avisos.append(
                    f"🔄 BP: Passivo negativo detectado → sinais invertidos no Passivo+PL"
                )
    
    # === PROCESSA LINHAS ===
    for _, row in df.iterrows():
        reduzida_raw = row[col_reduzida] if pd.notna(row[col_reduzida]) else None
        if reduzida_raw is None:
            continue
        
        # Normaliza reduzida
        try:
            reduzida_str = str(reduzida_raw).strip()
            if reduzida_str.replace(".", "").replace("-", "").isdigit():
                reduzida_str = str(int(float(reduzida_str)))
        except Exception:
            reduzida_str = str(reduzida_raw).strip()
        
        if not reduzida_str or reduzida_str.lower() == "nan":
            continue
        
        # Normaliza classificação
        classif_raw = row[col_classif] if col_classif and pd.notna(row[col_classif]) else ""
        classif = str(classif_raw).strip().replace(",", ".")
        if classif and "." in classif:
            partes = [p.lstrip("0") or "0" for p in classif.split(".")]
            if all(p.isdigit() for p in partes):
                classif = ".".join(partes)
        
        # Descrição
        desc = str(row[col_desc]).strip() if col_desc and pd.notna(row[col_desc]) else ""
        if not desc or desc.lower() == "nan":
            continue
        
        # Cria um registro por período
        for col_excel, periodo_padrao in col_periodo_map.items():
            valor = row[col_excel]
            if pd.isna(valor):
                valor = 0
            try:
                valor = float(valor)
            except Exception:
                valor = 0
            
            # APLICA INVERSÃO DE SINAIS
            if inverter_dre and demo == "DRE":
                valor = -valor
            elif inverter_bp and demo == "BP":
                if classif.startswith("2"):  # Passivo + PL
                    valor = -valor
            
            registros.append({
                "demonstrativo": demo,
                "unidade": unidade,
                "conta_reduzida": reduzida_str,
                "classificacao": classif,
                "descricao": desc,
                "periodo": periodo_padrao,
                "valor": valor,
            })
    
    return registros


# -----------------------------------------------------------------------------
# PROCESSAMENTO DA DFC
# -----------------------------------------------------------------------------
def _processar_dfc(arquivo, nome_aba: str, avisos: list):
    """
    Processa a aba DFC (sem código nem classificação no Excel original).
    
    Returns:
        Tupla (registros, contas_novas)
    """
    df_raw = pd.read_excel(arquivo, sheet_name=nome_aba, header=None)
    registros = []
    contas_novas = []
    
    # Procura a linha que tem os nomes dos meses (header)
    linha_header = None
    for idx in range(min(15, len(df_raw))):
        linha_textos = df_raw.iloc[idx].astype(str).str.upper().tolist()
        linha_concat = " ".join(linha_textos)
        if any(mes in linha_concat for mes in ["JANEIRO", "FEVEREIRO", "JAN", "FEV"]):
            linha_header = idx
            break
    
    if linha_header is None:
        # Tenta usar a primeira linha como header padrão
        avisos.append(f"⚠️ DFC '{nome_aba}': linha de cabeçalho não detectada, tentando header=0")
        df_dfc = pd.read_excel(arquivo, sheet_name=nome_aba)
        return _processar_dfc_fallback(df_dfc, avisos)
    
    # Mapeia colunas pela linha de header detectada
    headers = df_raw.iloc[linha_header].astype(str).str.strip().tolist()
    
    col_descricao_idx = None
    col_meses = {}
    col_ytd_idx = None
    
    for idx, h in enumerate(headers):
        h_upper = str(h).upper().strip()
        # Tenta identificar o mês
        for mes_long, mes_short in MESES_NOMES_LONGOS.items():
            if mes_long.upper() in h_upper:
                col_meses[mes_short] = idx
                break
        else:
            # Tenta abreviações
            for mes_padrao in PERIODOS_PADRAO[1:]:
                mes_abrev = mes_padrao.split("-")[0].upper()
                if mes_abrev == h_upper or h_upper.startswith(mes_abrev):
                    col_meses[mes_padrao] = idx
                    break
            else:
                if "YTD" in h_upper or "ACUMULADO" in h_upper or ("POSI" in h_upper and "25" in h_upper):
                    col_ytd_idx = idx
                elif col_descricao_idx is None and idx <= 2 and h_upper not in ["NAN", ""]:
                    col_descricao_idx = idx
    
    # Fallback para descrição
    if col_descricao_idx is None:
        col_descricao_idx = 0
    
    if col_ytd_idx is not None:
        col_meses["Posição 2025"] = col_ytd_idx
    
    # Processa linhas após o header
    for idx in range(linha_header + 1, len(df_raw)):
        row = df_raw.iloc[idx]
        
        desc_raw = row.iloc[col_descricao_idx]
        if pd.isna(desc_raw):
            continue
        descricao = str(desc_raw).strip()
        if not descricao or descricao.lower() == "nan":
            continue
        
        codigo_dfc = gerar_codigo_dfc(descricao)
        tipo_hier, classif_inferida = inferir_hierarquia_dfc(descricao)
        
        contas_novas.append({
            "codigo": codigo_dfc,
            "descricao": descricao,
            "tipo_hierarquia": tipo_hier,
            "classificacao": classif_inferida,
        })
        
        for periodo_padrao, col_idx in col_meses.items():
            if col_idx >= len(row):
                continue
            valor = row.iloc[col_idx]
            if pd.isna(valor):
                valor = 0
            try:
                valor = float(valor)
            except Exception:
                valor = 0
            
            registros.append({
                "demonstrativo": "DFC",
                "unidade": "Consol",
                "conta_reduzida": codigo_dfc,
                "classificacao": classif_inferida,
                "descricao": descricao,
                "periodo": periodo_padrao,
                "valor": valor,
            })
    
    return registros, contas_novas


def _processar_dfc_fallback(df, avisos):
    """Fallback de processamento DFC quando header não é detectado."""
    registros = []
    contas_novas = []
    
    cols = df.columns.tolist()
    col_desc = cols[0] if cols else None
    
    col_meses = {}
    for col in cols:
        col_str = str(col).lower().strip()
        for mes_long, mes_short in MESES_NOMES_LONGOS.items():
            if mes_long in col_str:
                col_meses[mes_short] = col
                break
    
    if not col_meses or not col_desc:
        avisos.append("⚠️ DFC fallback: estrutura não reconhecida.")
        return [], []
    
    for _, row in df.iterrows():
        desc = row[col_desc]
        if pd.isna(desc):
            continue
        descricao = str(desc).strip()
        if not descricao or descricao.lower() == "nan":
            continue
        
        codigo_dfc = gerar_codigo_dfc(descricao)
        tipo_hier, classif_inferida = inferir_hierarquia_dfc(descricao)
        
        contas_novas.append({
            "codigo": codigo_dfc,
            "descricao": descricao,
            "tipo_hierarquia": tipo_hier,
            "classificacao": classif_inferida,
        })
        
        for periodo_padrao, col_excel in col_meses.items():
            valor = row[col_excel]
            if pd.isna(valor):
                valor = 0
            try:
                valor = float(valor)
            except Exception:
                valor = 0
            
            registros.append({
                "demonstrativo": "DFC",
                "unidade": "Consol",
                "conta_reduzida": codigo_dfc,
                "classificacao": classif_inferida,
                "descricao": descricao,
                "periodo": periodo_padrao,
                "valor": valor,
            })
    
    return registros, contas_novas


# -----------------------------------------------------------------------------
# VALIDAÇÃO DE CONTAS DFC (compara com banco)
# -----------------------------------------------------------------------------
def validar_contas_dfc(contas_novas: list) -> dict:
    """
    Compara contas DFC do upload com mapeamento já cadastrado.
    
    Returns:
        dict com chaves:
            'novas': contas totalmente novas
            'existentes': contas já cadastradas (reutilizar)
            'similares': contas parecidas (revisar manualmente)
    """
    mapeamento = carregar_mapeamento_dfc()
    contas_existentes_list = list(mapeamento.values())
    
    resultado = {"novas": [], "existentes": [], "similares": []}
    
    for nova in contas_novas:
        codigo = nova["codigo"]
        descricao = nova["descricao"]
        
        # Já existe pelo hash?
        if codigo in mapeamento:
            resultado["existentes"].append({**nova, "existing": mapeamento[codigo]})
            continue
        
        # Procura por similaridade
        mais_similar = None
        maior_score = 0
        for existente in contas_existentes_list:
            score = calcular_similaridade(descricao, existente.get("descricao_original", ""))
            if score > maior_score and score >= 70:
                maior_score = score
                mais_similar = existente
        
        if mais_similar:
            resultado["similares"].append({
                **nova,
                "similaridade": maior_score,
                "similar_existente": mais_similar,
            })
        else:
            resultado["novas"].append(nova)
    
    return resultado

# ═══════════════════════════════════════════════════════════════════════════════
# BLOCO 4 — CÁLCULO DE INDICADORES + CONCILIAÇÃO
# ═══════════════════════════════════════════════════════════════════════════════


# -----------------------------------------------------------------------------
# UTILITÁRIOS DE BUSCA DE VALORES
# -----------------------------------------------------------------------------
def buscar_valor(df, classificacao: str, periodo: str,
                  demonstrativo: str = None, unidade: str = None,
                  usar_saldo_acumulado: bool = False) -> float:
    """
    Busca valor por classificação contábil.
    
    Se usar_saldo_acumulado=True e o demonstrativo for BP, busca na
    coluna f"{periodo}_saldo" (saldos acumulados).
    """
    try:
        filtro = df["classificacao"] == classificacao
        if demonstrativo:
            filtro &= df["demonstrativo"] == demonstrativo
        if unidade:
            filtro &= df["unidade"] == unidade
        
        coluna = periodo
        if usar_saldo_acumulado and demonstrativo == "BP":
            coluna_saldo = f"{periodo}_saldo"
            if coluna_saldo in df.columns:
                coluna = coluna_saldo
        
        if coluna not in df.columns:
            return 0.0
        
        resultado = df.loc[filtro, coluna]
        if len(resultado) == 0:
            return 0.0
        return float(resultado.sum())
    except Exception:
        return 0.0


def buscar_valor_descricao(df, descricao_parcial: str, periodo: str,
                            demonstrativo: str = None, unidade: str = None) -> float:
    """Busca valor por descrição parcial (case-insensitive)."""
    try:
        filtro = df["descricao"].str.contains(descricao_parcial, case=False, na=False)
        if demonstrativo:
            filtro &= df["demonstrativo"] == demonstrativo
        if unidade:
            filtro &= df["unidade"] == unidade
        
        if periodo not in df.columns:
            return 0.0
        resultado = df.loc[filtro, periodo]
        if len(resultado) == 0:
            return 0.0
        return float(resultado.sum())
    except Exception:
        return 0.0


# -----------------------------------------------------------------------------
# CÁLCULO PRINCIPAL: 30+ INDICADORES
# -----------------------------------------------------------------------------
def calcular_indicadores_completos(df, periodo: str,
                                     unidade_dre: str = "Consolidado",
                                     usar_saldo_bp: bool = True) -> dict:
    """
    Calcula todos os indicadores financeiros para um período.
    
    Args:
        df: DataFrame com dados contábeis
        periodo: período de referência
        unidade_dre: 'Consolidado', 'Matriz' ou 'Filial'
        usar_saldo_bp: True para usar saldos acumulados do BP
    
    Returns:
        dict com 30+ indicadores
    """
    ind = {}
    
    # === VALORES BASE DRE ===
    receita_bruta = buscar_valor(df, "3.1", periodo, "DRE", unidade_dre)
    receita_liquida = buscar_valor(df, "3.3", periodo, "DRE", unidade_dre)
    if receita_liquida == 0:
        receita_liquida = buscar_valor_descricao(df, "RECEITA LÍQUIDA", periodo, "DRE", unidade_dre)
    if receita_liquida == 0:
        receita_liquida = buscar_valor_descricao(df, "RECEITA LIQUIDA", periodo, "DRE", unidade_dre)
    
    cmv = abs(buscar_valor(df, "4.1", periodo, "DRE", unidade_dre))
    if cmv == 0:
        cmv = abs(buscar_valor_descricao(df, "CMV", periodo, "DRE", unidade_dre))
    
    lucro_bruto = receita_liquida - cmv
    
    despesas_operacionais = abs(buscar_valor(df, "4.2", periodo, "DRE", unidade_dre))
    despesas_financeiras = abs(buscar_valor(df, "4.3", periodo, "DRE", unidade_dre))
    receitas_financeiras = buscar_valor(df, "3.4", periodo, "DRE", unidade_dre)
    
    ebitda = buscar_valor_descricao(df, "EBITDA", periodo, "DRE", unidade_dre)
    if ebitda == 0:
        depreciacao = abs(buscar_valor_descricao(df, "deprecia", periodo, "DRE", unidade_dre))
        ebitda = lucro_bruto - despesas_operacionais + depreciacao
    
    ebit = lucro_bruto - despesas_operacionais
    
    lucro_liquido = buscar_valor(df, "3.99", periodo, "DRE", unidade_dre)
    if lucro_liquido == 0:
        lucro_liquido = buscar_valor_descricao(df, "LUCRO LÍQUIDO", periodo, "DRE", unidade_dre)
    if lucro_liquido == 0:
        lucro_liquido = buscar_valor_descricao(df, "RESULTADO LÍQUIDO", periodo, "DRE", unidade_dre)
    
    subvencao = buscar_valor_descricao(df, "subvenç", periodo, "DRE", unidade_dre)
    if subvencao == 0:
        subvencao = buscar_valor_descricao(df, "riolog", periodo, "DRE", unidade_dre)
    
    # === VALORES BASE BP (saldos acumulados) ===
    ativo_total = buscar_valor(df, "1", periodo, "BP", "Consol", usar_saldo_bp)
    ativo_circulante = buscar_valor(df, "1.1", periodo, "BP", "Consol", usar_saldo_bp)
    ativo_nao_circulante = buscar_valor(df, "1.2", periodo, "BP", "Consol", usar_saldo_bp)
    
    caixa = buscar_valor(df, "1.1.01", periodo, "BP", "Consol", usar_saldo_bp)
    contas_receber = buscar_valor(df, "1.1.02", periodo, "BP", "Consol", usar_saldo_bp)
    estoques = buscar_valor(df, "1.1.03", periodo, "BP", "Consol", usar_saldo_bp)
    imobilizado = buscar_valor(df, "1.2.03", periodo, "BP", "Consol", usar_saldo_bp)
    
    passivo_total = buscar_valor(df, "2", periodo, "BP", "Consol", usar_saldo_bp)
    passivo_circulante = buscar_valor(df, "2.1", periodo, "BP", "Consol", usar_saldo_bp)
    passivo_nao_circulante = buscar_valor(df, "2.2", periodo, "BP", "Consol", usar_saldo_bp)
    patrimonio_liquido = buscar_valor(df, "2.3", periodo, "BP", "Consol", usar_saldo_bp)
    fornecedores = buscar_valor(df, "2.1.01", periodo, "BP", "Consol", usar_saldo_bp)
    
    # === VALORES BASE DFC ===
    fco = buscar_valor_descricao(df, "operacion", periodo, "DFC", "Consol")
    fci = buscar_valor_descricao(df, "investiment", periodo, "DFC", "Consol")
    fcf = buscar_valor_descricao(df, "financiament", periodo, "DFC", "Consol")
    
    # ─────────────────────────────────────────────────────────────────────────
    # 1) RENTABILIDADE
    # ─────────────────────────────────────────────────────────────────────────
    ind["margem_bruta"] = (lucro_bruto / receita_liquida * 100) if receita_liquida else 0
    ind["margem_operacional"] = (ebit / receita_liquida * 100) if receita_liquida else 0
    ind["margem_ebitda"] = (ebitda / receita_liquida * 100) if receita_liquida else 0
    ind["margem_liquida"] = (lucro_liquido / receita_liquida * 100) if receita_liquida else 0
    ind["roe"] = (lucro_liquido / patrimonio_liquido * 100) if patrimonio_liquido else 0
    ind["roa"] = (lucro_liquido / ativo_total * 100) if ativo_total else 0
    ind["roi"] = (ebit / ativo_total * 100) if ativo_total else 0
    
    # ─────────────────────────────────────────────────────────────────────────
    # 2) LIQUIDEZ
    # ─────────────────────────────────────────────────────────────────────────
    ind["liquidez_corrente"] = (ativo_circulante / passivo_circulante) if passivo_circulante else 0
    ind["liquidez_seca"] = ((ativo_circulante - estoques) / passivo_circulante) if passivo_circulante else 0
    ind["liquidez_imediata"] = (caixa / passivo_circulante) if passivo_circulante else 0
    cap_terceiros = passivo_circulante + passivo_nao_circulante
    ind["liquidez_geral"] = (
        (ativo_circulante + ativo_nao_circulante - imobilizado) / cap_terceiros
    ) if cap_terceiros else 0
    ind["capital_giro"] = ativo_circulante - passivo_circulante
    
    # ─────────────────────────────────────────────────────────────────────────
    # 3) ENDIVIDAMENTO
    # ─────────────────────────────────────────────────────────────────────────
    ind["endividamento_geral"] = (cap_terceiros / ativo_total * 100) if ativo_total else 0
    ind["endividamento_pl"] = (cap_terceiros / patrimonio_liquido * 100) if patrimonio_liquido else 0
    ind["composicao_endividamento"] = (passivo_circulante / cap_terceiros * 100) if cap_terceiros else 0
    ind["imobilizacao_pl"] = (imobilizado / patrimonio_liquido * 100) if patrimonio_liquido else 0
    ind["imobilizacao_recursos_perm"] = (
        imobilizado / (patrimonio_liquido + passivo_nao_circulante) * 100
    ) if (patrimonio_liquido + passivo_nao_circulante) else 0
    
    # ─────────────────────────────────────────────────────────────────────────
    # 4) COBERTURA
    # ─────────────────────────────────────────────────────────────────────────
    ind["cobertura_juros"] = (ebit / despesas_financeiras) if despesas_financeiras else 0
    ind["cobertura_divida_ebitda"] = (ebitda / cap_terceiros) if cap_terceiros else 0
    ind["divida_liquida_ebitda"] = ((cap_terceiros - caixa) / ebitda) if ebitda else 0
    
    # ─────────────────────────────────────────────────────────────────────────
    # 5) ATIVIDADE
    # ─────────────────────────────────────────────────────────────────────────
    ind["giro_ativo"] = (receita_liquida / ativo_total) if ativo_total else 0
    ind["giro_estoque"] = (cmv / estoques) if estoques else 0
    ind["pme"] = (estoques / cmv * 360) if cmv else 0
    ind["pmr"] = (contas_receber / receita_bruta * 360) if receita_bruta else 0
    ind["pmp"] = (fornecedores / cmv * 360) if cmv else 0
    ind["ciclo_operacional"] = ind["pme"] + ind["pmr"]
    ind["ciclo_financeiro"] = ind["ciclo_operacional"] - ind["pmp"]
    
    # ─────────────────────────────────────────────────────────────────────────
    # 6) KPIs LLE
    # ─────────────────────────────────────────────────────────────────────────
    ind["lucro_sem_subvencao"] = lucro_liquido - subvencao
    ind["peso_subvencao_receita"] = (subvencao / receita_liquida * 100) if receita_liquida else 0
    ind["peso_subvencao_pl"] = (subvencao / patrimonio_liquido * 100) if patrimonio_liquido else 0
    ind["peso_subvencao_lucro"] = (subvencao / lucro_liquido * 100) if lucro_liquido else 0
    ind["qualidade_lucro"] = (fco / lucro_liquido * 100) if lucro_liquido else 0
    
    # Runway de caixa
    despesa_mensal = (despesas_operacionais + cmv) / 12 if (despesas_operacionais + cmv) else 1
    ind["runway_meses"] = (caixa / despesa_mensal) if despesa_mensal else 0
    
    # Cobertura CD King
    cmv_king_estimado = cmv * 0.65
    ind["cobertura_cd_king"] = (
        estoques * 0.65 / (cmv_king_estimado / 12)
    ) if cmv_king_estimado else 0
    
    # ─────────────────────────────────────────────────────────────────────────
    # 7) FLUXOS DE CAIXA
    # ─────────────────────────────────────────────────────────────────────────
    ind["fco"] = fco
    ind["fci"] = fci
    ind["fcf"] = fcf
    ind["fluxo_total"] = fco + fci + fcf
    ind["fco_sobre_receita"] = (fco / receita_liquida * 100) if receita_liquida else 0
    
    # ─────────────────────────────────────────────────────────────────────────
    # 8) VALORES BASE (para uso em dashboards)
    # ─────────────────────────────────────────────────────────────────────────
    ind["_base_receita_bruta"] = receita_bruta
    ind["_base_receita_liquida"] = receita_liquida
    ind["_base_cmv"] = cmv
    ind["_base_lucro_bruto"] = lucro_bruto
    ind["_base_ebitda"] = ebitda
    ind["_base_ebit"] = ebit
    ind["_base_lucro_liquido"] = lucro_liquido
    ind["_base_subvencao"] = subvencao
    ind["_base_ativo_total"] = ativo_total
    ind["_base_passivo_total"] = passivo_total
    ind["_base_patrimonio_liquido"] = patrimonio_liquido
    ind["_base_caixa"] = caixa
    ind["_base_estoques"] = estoques
    ind["_base_despesas_operacionais"] = despesas_operacionais
    ind["_base_despesas_financeiras"] = despesas_financeiras
    
    return ind


# -----------------------------------------------------------------------------
# ANÁLISE VERTICAL
# -----------------------------------------------------------------------------
def analise_vertical(df, periodo: str, demonstrativo: str = "DRE",
                      unidade: str = "Consolidado", usar_saldo_bp: bool = True) -> pd.DataFrame:
    """
    Análise Vertical: cada conta como % de uma base.
    - DRE: base = Receita Líquida
    - BP:  base = Ativo Total
    """
    filtro = df["demonstrativo"] == demonstrativo
    if demonstrativo == "DRE":
        filtro &= df["unidade"] == unidade
    else:
        filtro &= df["unidade"] == "Consol"
    
    df_filt = df[filtro].copy()
    
    coluna_valor = periodo
    if usar_saldo_bp and demonstrativo == "BP":
        coluna_saldo = f"{periodo}_saldo"
        if coluna_saldo in df.columns:
            coluna_valor = coluna_saldo
    
    if coluna_valor not in df_filt.columns:
        df_filt["AV"] = 0.0
        return df_filt[["classificacao", "descricao", "AV"]].head(0)
    
    if demonstrativo == "DRE":
        base = buscar_valor(df, "3.3", periodo, "DRE", unidade)
        if base == 0:
            base = buscar_valor_descricao(df, "RECEITA LÍQUIDA", periodo, "DRE", unidade)
        if base == 0:
            base = buscar_valor(df, "3.1", periodo, "DRE", unidade)
    else:
        base = buscar_valor(df, "1", periodo, "BP", "Consol", usar_saldo_bp)
    
    if base == 0:
        df_filt["AV"] = 0.0
    else:
        df_filt["AV"] = (df_filt[coluna_valor] / base * 100).round(2)
    
    df_filt["valor_periodo"] = df_filt[coluna_valor]
    return df_filt[["classificacao", "descricao", "valor_periodo", "AV"]]


# -----------------------------------------------------------------------------
# ANÁLISE HORIZONTAL
# -----------------------------------------------------------------------------
def analise_horizontal(df, periodo_base: str, periodo_comp: str,
                        demonstrativo: str = "DRE",
                        unidade: str = "Consolidado",
                        usar_saldo_bp: bool = True) -> pd.DataFrame:
    """Análise Horizontal: variação % entre dois períodos."""
    filtro = df["demonstrativo"] == demonstrativo
    if demonstrativo == "DRE":
        filtro &= df["unidade"] == unidade
    else:
        filtro &= df["unidade"] == "Consol"
    
    df_filt = df[filtro].copy()
    
    col_base = periodo_base
    col_comp = periodo_comp
    if usar_saldo_bp and demonstrativo == "BP":
        if f"{periodo_base}_saldo" in df.columns:
            col_base = f"{periodo_base}_saldo"
        if f"{periodo_comp}_saldo" in df.columns:
            col_comp = f"{periodo_comp}_saldo"
    
    if col_base not in df_filt.columns or col_comp not in df_filt.columns:
        return pd.DataFrame()
    
    df_filt["Variacao_Absoluta"] = df_filt[col_comp] - df_filt[col_base]
    df_filt["AH"] = df_filt.apply(
        lambda r: ((r[col_comp] / r[col_base]) - 1) * 100 if r[col_base] != 0 else 0,
        axis=1
    ).round(2)
    
    df_filt["valor_base"] = df_filt[col_base]
    df_filt["valor_comp"] = df_filt[col_comp]
    return df_filt[["classificacao", "descricao", "valor_base", "valor_comp",
                     "Variacao_Absoluta", "AH"]]


# -----------------------------------------------------------------------------
# RUNWAY DE CAIXA
# -----------------------------------------------------------------------------
def calcular_runway_caixa(df, periodo_atual: str, meses_historico: int = 6) -> dict:
    """Calcula runway = caixa atual / burn rate médio histórico."""
    caixa = buscar_valor(df, "1.1.01", periodo_atual, "BP", "Consol", True)
    
    # Identifica meses anteriores
    todas_colunas = [c for c in df.columns if c in PERIODOS_PADRAO]
    if periodo_atual in todas_colunas:
        idx = todas_colunas.index(periodo_atual)
        meses_anteriores = todas_colunas[max(0, idx - meses_historico):idx]
    else:
        meses_anteriores = todas_colunas[-meses_historico:]
    
    if not meses_anteriores:
        burn = 1
    else:
        despesas = []
        for mes in meses_anteriores:
            cmv = abs(buscar_valor(df, "4.1", mes, "DRE", "Consolidado"))
            desp = abs(buscar_valor(df, "4.2", mes, "DRE", "Consolidado"))
            despesas.append(cmv + desp)
        burn = sum(despesas) / len(despesas) if despesas else 1
    
    runway = (caixa / burn) if burn else 0
    
    if runway >= 12:
        cenario, cor = "CONFORTÁVEL", CORES_LLE["verde_institucional"]
    elif runway >= 6:
        cenario, cor = "ATENÇÃO", CORES_LLE["amarelo_logo"]
    else:
        cenario, cor = "CRÍTICO", CORES_LLE["vermelho"]
    
    return {
        "caixa_atual": caixa,
        "burn_rate_mensal": burn,
        "runway_meses": round(runway, 1),
        "cenario": cenario,
        "cor": cor,
    }


# -----------------------------------------------------------------------------
# DEPENDÊNCIA DE SUBVENÇÃO
# -----------------------------------------------------------------------------
def calcular_dependencia_subvencao(df, periodo: str) -> dict:
    """Avalia dependência da LLE em relação às subvenções Riolog."""
    subvencao = buscar_valor_descricao(df, "subvenç", periodo, "DRE", "Consolidado")
    if subvencao == 0:
        subvencao = buscar_valor_descricao(df, "riolog", periodo, "DRE", "Consolidado")
    
    lucro = buscar_valor(df, "3.99", periodo, "DRE", "Consolidado")
    if lucro == 0:
        lucro = buscar_valor_descricao(df, "LUCRO LÍQUIDO", periodo, "DRE", "Consolidado")
    
    receita = buscar_valor(df, "3.3", periodo, "DRE", "Consolidado")
    if receita == 0:
        receita = buscar_valor_descricao(df, "RECEITA LÍQUIDA", periodo, "DRE", "Consolidado")
    
    pl = buscar_valor(df, "2.3", periodo, "BP", "Consol", True)
    
    lucro_sem = lucro - subvencao
    peso_lucro = (subvencao / lucro * 100) if lucro else 0
    peso_receita = (subvencao / receita * 100) if receita else 0
    peso_pl = (subvencao / pl * 100) if pl else 0
    
    if abs(peso_lucro) > 80:
        nivel, cor = "CRÍTICA", CORES_LLE["vermelho"]
        alerta = "🔴 Dependência crítica. Risco se Riolog encerrar."
    elif abs(peso_lucro) > 50:
        nivel, cor = "ALTA", CORES_LLE["amarelo_logo"]
        alerta = "🟡 Dependência elevada. Diversificar é prioridade."
    elif abs(peso_lucro) > 20:
        nivel, cor = "MODERADA", CORES_LLE["azul_vibrante"]
        alerta = "🔵 Dependência moderada. Monitorar."
    else:
        nivel, cor = "BAIXA", CORES_LLE["verde_institucional"]
        alerta = "🟢 Operação saudável e independente."
    
    return {
        "subvencao_total": subvencao,
        "lucro_com_subvencao": lucro,
        "lucro_sem_subvencao": lucro_sem,
        "peso_no_lucro": round(peso_lucro, 2),
        "peso_na_receita": round(peso_receita, 2),
        "peso_no_pl": round(peso_pl, 2),
        "nivel": nivel,
        "cor": cor,
        "alerta": alerta,
    }


# -----------------------------------------------------------------------------
# CONCILIAÇÃO DRE × BP × DFC
# -----------------------------------------------------------------------------
def conciliar_demonstrativos(df, periodo_atual: str, periodo_anterior: str,
                              tolerancia: float = 1.0) -> dict:
    """Valida a integridade dos 3 demonstrativos."""
    resultado = {
        "periodo_atual": periodo_atual,
        "periodo_anterior": periodo_anterior,
        "validacoes": [],
        "status_geral": "OK",
    }
    
    # 1) BP fecha?
    ativo = buscar_valor(df, "1", periodo_atual, "BP", "Consol", True)
    pl = buscar_valor(df, "2.3", periodo_atual, "BP", "Consol", True)
    pc = buscar_valor(df, "2.1", periodo_atual, "BP", "Consol", True)
    pnc = buscar_valor(df, "2.2", periodo_atual, "BP", "Consol", True)
    total_passivo_pl = pc + pnc + pl
    
    diff_bp = abs(ativo - total_passivo_pl)
    bp_ok = diff_bp <= tolerancia
    resultado["validacoes"].append({
        "nome": "BP Fecha (Ativo = Passivo + PL)",
        "esperado": ativo,
        "realizado": total_passivo_pl,
        "diferenca": diff_bp,
        "passou": bp_ok,
        "status": "✅ OK" if bp_ok else "❌ DIVERGÊNCIA",
    })
    
    # 2) Lucro DRE × Variação PL
    lucro = buscar_valor(df, "3.99", periodo_atual, "DRE", "Consolidado")
    if lucro == 0:
        lucro = buscar_valor_descricao(df, "LUCRO LÍQUIDO", periodo_atual, "DRE", "Consolidado")
    
    pl_atual = buscar_valor(df, "2.3", periodo_atual, "BP", "Consol", True)
    pl_anterior = buscar_valor(df, "2.3", periodo_anterior, "BP", "Consol", True)
    var_pl = pl_atual - pl_anterior
    diff_pl = abs(lucro - var_pl)
    pl_ok = diff_pl <= max(tolerancia, abs(lucro) * 0.05)
    
    resultado["validacoes"].append({
        "nome": "Lucro DRE × Variação PL",
        "esperado": lucro,
        "realizado": var_pl,
        "diferenca": diff_pl,
        "passou": pl_ok,
        "status": "✅ OK" if pl_ok else "⚠️ ATENÇÃO (verificar dividendos/aporte)",
    })
    
    # 3) Variação Caixa BP × Soma DFC
    caixa_atual = buscar_valor(df, "1.1.01", periodo_atual, "BP", "Consol", True)
    caixa_anterior = buscar_valor(df, "1.1.01", periodo_anterior, "BP", "Consol", True)
    var_caixa = caixa_atual - caixa_anterior
    
    fco = buscar_valor_descricao(df, "operacion", periodo_atual, "DFC", "Consol")
    fci = buscar_valor_descricao(df, "investiment", periodo_atual, "DFC", "Consol")
    fcf = buscar_valor_descricao(df, "financiament", periodo_atual, "DFC", "Consol")
    total_dfc = fco + fci + fcf
    
    diff_caixa = abs(var_caixa - total_dfc)
    caixa_ok = diff_caixa <= tolerancia
    
    resultado["validacoes"].append({
        "nome": "Variação Caixa BP × Soma DFC",
        "esperado": var_caixa,
        "realizado": total_dfc,
        "diferenca": diff_caixa,
        "passou": caixa_ok,
        "status": "✅ OK" if caixa_ok else "❌ DIVERGÊNCIA",
    })
    
    # 4) Composição DFC
    resultado["validacoes"].append({
        "nome": "Composição DFC",
        "esperado": total_dfc,
        "realizado": total_dfc,
        "diferenca": 0,
        "passou": True,
        "status": f"FCO: {formatar_brl(fco)} | FCI: {formatar_brl(fci)} | FCF: {formatar_brl(fcf)}",
    })
    
    if not all(v["passou"] for v in resultado["validacoes"]):
        resultado["status_geral"] = "DIVERGÊNCIAS"
    
    return resultado


# -----------------------------------------------------------------------------
# MARGEM POR UNIDADE (PISA × KING)
# -----------------------------------------------------------------------------
def calcular_margem_unidade(df, periodo: str) -> dict:
    """Compara performance de PISA (Matriz) × KING (Filial)."""
    unidades = {}
    
    for nome_apresentado, codigo in [("PISA (Matriz)", "Matriz"), ("KING (Filial)", "Filial")]:
        receita_bruta = buscar_valor(df, "3.1", periodo, "DRE", codigo)
        receita_liquida = buscar_valor(df, "3.3", periodo, "DRE", codigo)
        if receita_liquida == 0:
            receita_liquida = buscar_valor_descricao(df, "RECEITA LÍQUIDA", periodo, "DRE", codigo)
        
        cmv = abs(buscar_valor(df, "4.1", periodo, "DRE", codigo))
        lucro_bruto = receita_liquida - cmv
        desp_op = abs(buscar_valor(df, "4.2", periodo, "DRE", codigo))
        ebit = lucro_bruto - desp_op
        
        lucro = buscar_valor(df, "3.99", periodo, "DRE", codigo)
        if lucro == 0:
            lucro = buscar_valor_descricao(df, "LUCRO LÍQUIDO", periodo, "DRE", codigo)
        
        unidades[nome_apresentado] = {
            "receita_bruta": receita_bruta,
            "receita_liquida": receita_liquida,
            "cmv": cmv,
            "lucro_bruto": lucro_bruto,
            "despesas_operacionais": desp_op,
            "ebit": ebit,
            "lucro_liquido": lucro,
            "margem_bruta": (lucro_bruto / receita_liquida * 100) if receita_liquida else 0,
            "margem_operacional": (ebit / receita_liquida * 100) if receita_liquida else 0,
            "margem_liquida": (lucro / receita_liquida * 100) if receita_liquida else 0,
        }
    
    total_rec = sum(u["receita_liquida"] for u in unidades.values())
    total_luc = sum(u["lucro_liquido"] for u in unidades.values())
    for nome in unidades:
        unidades[nome]["part_receita"] = (
            unidades[nome]["receita_liquida"] / total_rec * 100
        ) if total_rec else 0
        unidades[nome]["part_lucro"] = (
            unidades[nome]["lucro_liquido"] / total_luc * 100
        ) if total_luc else 0
    
    return unidades


# -----------------------------------------------------------------------------
# COMPARATIVO DE PERÍODOS
# -----------------------------------------------------------------------------
def comparativo_periodos(df, lista_periodos: list,
                          indicadores: list = None) -> pd.DataFrame:
    """Evolução de indicadores ao longo dos períodos."""
    if indicadores is None:
        indicadores = ["margem_bruta", "margem_liquida", "roe", "liquidez_corrente"]
    
    resultado = []
    for periodo in lista_periodos:
        ind = calcular_indicadores_completos(df, periodo)
        linha = {"Periodo": periodo}
        for kpi in indicadores:
            linha[kpi] = ind.get(kpi, 0)
        resultado.append(linha)
    
    return pd.DataFrame(resultado)


# -----------------------------------------------------------------------------
# DETECÇÃO DE ANOMALIAS
# -----------------------------------------------------------------------------
def detectar_anomalias(df, periodo_atual: str, periodo_anterior: str,
                        limite_pct: float = 50) -> pd.DataFrame:
    """Detecta contas com variação acima do limite."""
    if periodo_atual not in df.columns or periodo_anterior not in df.columns:
        return pd.DataFrame()
    
    df_copy = df.copy()
    df_copy["variacao_abs"] = df_copy[periodo_atual] - df_copy[periodo_anterior]
    df_copy["variacao_pct"] = df_copy.apply(
        lambda r: abs((r[periodo_atual] / r[periodo_anterior] - 1) * 100)
        if r[periodo_anterior] != 0 else 0,
        axis=1
    )
    
    anomalias = df_copy[
        (df_copy["variacao_pct"] > limite_pct) &
        (df_copy["variacao_abs"].abs() > 1000)
    ].copy()
    anomalias = anomalias.sort_values("variacao_pct", ascending=False)
    
    return anomalias[["demonstrativo", "unidade", "classificacao", "descricao",
                       periodo_anterior, periodo_atual, "variacao_abs", "variacao_pct"]]

# ═══════════════════════════════════════════════════════════════════════════════
# BLOCO 5 — TELAS, DASHBOARDS E MAIN
# ═══════════════════════════════════════════════════════════════════════════════


# =============================================================================
# TELA: LOGIN
# =============================================================================
def tela_login(cookies=None):
    """Tela de login com senha + opções de recuperação."""
    
    # Inicializa estados auxiliares
    if "modo_login" not in st.session_state:
        st.session_state["modo_login"] = "login"  # 'login', 'esqueci', 'codigo_enviado'
    
    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        st.markdown(
            f"""
            <div style='text-align: center; padding: 30px 0;'>
                <h1 style='color: {CORES_LLE["azul_profundo"]}; margin: 0;'>
                    Sistema Contábil LLE
                </h1>
                <p style='color: {CORES_LLE["azul_corporativo"]}; font-size: 14px; margin-top: 8px;'>
                    Controladoria — Grupo LLE Ferragens
                </p>
            </div>
            """,
            unsafe_allow_html=True
        )
        
        # ─────────────────────────────────────────────────────────────────
        # MODO LOGIN PADRÃO
        # ─────────────────────────────────────────────────────────────────
        if st.session_state["modo_login"] == "login":
            with st.container(border=True):
                st.markdown("### 🔐 Acesso ao Sistema")
                
                email = st.text_input(
                    "E-mail corporativo:",
                    placeholder="seu.email@grupolle.com.br",
                    key="login_email"
                )
                senha = st.text_input(
                    "Senha:",
                    type="password",
                    placeholder="Digite sua senha",
                    key="login_senha"
                )
                manter_logado = st.checkbox(
                    "🔄 Manter conectado por 7 dias",
                    value=True,
                    help="Marque para não precisar logar de novo ao atualizar a página."
                )
                
                col_btn1, col_btn2 = st.columns([2, 1])
                with col_btn1:
                    entrar = st.button("Entrar", type="primary", use_container_width=True)
                with col_btn2:
                    esqueci = st.button("Esqueci a senha", use_container_width=True)
                
                if esqueci:
                    st.session_state["modo_login"] = "esqueci"
                    st.rerun()
                
                if entrar:
                    if not email or not senha:
                        st.error("Por favor, informe e-mail e senha.")
                    else:
                        usuario = validar_usuario(email.strip().lower(), senha)
                        if usuario:
                            st.session_state["autenticado"] = True
                            st.session_state["usuario"] = usuario
                            
                            # Grava cookie (se opção marcada)
                            if manter_logado and cookies is not None:
                                try:
                                    cookies["usuario_email"] = usuario["email"]
                                    cookies["usuario_nome"] = usuario["nome"]
                                    cookies["usuario_perfil"] = usuario["perfil"]
                                    cookies["login_timestamp"] = str(int(datetime.now().timestamp()))
                                    cookies.save()
                                except Exception as e:
                                    st.warning(f"Login OK, mas cookie falhou: {e}")
                            
                            if usuario.get("senha_temporaria"):
                                st.warning("⚠️ Você está usando uma senha temporária. Por favor, troque agora.")
                            
                            st.success(f"Bem-vindo(a), {usuario['nome']}!")
                            st.rerun()
                        else:
                            st.error("❌ E-mail ou senha incorretos.")
            
            # Info sobre primeira senha
            with st.expander("ℹ️ Primeiro acesso?"):
                st.markdown("""
                Se este é seu primeiro acesso ou você foi cadastrado recentemente:
                - Sua senha inicial padrão é: **`lle@2026`**
                - Ao entrar, o sistema solicitará que você troque para uma senha pessoal.
                
                **Esqueceu a senha?** Clique no botão "Esqueci a senha" e siga as instruções.
                """)
        
        # ─────────────────────────────────────────────────────────────────
        # MODO ESQUECI MINHA SENHA
        # ─────────────────────────────────────────────────────────────────
        elif st.session_state["modo_login"] == "esqueci":
            with st.container(border=True):
                st.markdown("### 🔓 Recuperação de Senha")
                st.info(
                    "Informe seu e-mail. Será gerado um pedido de reset que o "
                    "administrador deverá aprovar. Você receberá a nova senha "
                    "por um canal seguro (WhatsApp/telefone)."
                )
                
                email_reset = st.text_input(
                    "Seu e-mail cadastrado:",
                    placeholder="seu.email@grupolle.com.br",
                    key="reset_email"
                )
                
                col_btn1, col_btn2 = st.columns(2)
                with col_btn1:
                    solicitar = st.button(
                        "Solicitar reset",
                        type="primary",
                        use_container_width=True
                    )
                with col_btn2:
                    voltar = st.button("Voltar ao login", use_container_width=True)
                
                if voltar:
                    st.session_state["modo_login"] = "login"
                    st.rerun()
                
                if solicitar:
                    if not email_reset:
                        st.error("Por favor, informe seu e-mail.")
                    else:
                        ok, resultado = criar_pedido_reset(email_reset.strip().lower())
                        if ok:
                            st.session_state["modo_login"] = "codigo_enviado"
                            st.session_state["codigo_solicitado"] = resultado
                            st.session_state["email_reset"] = email_reset.strip().lower()
                            st.rerun()
                        else:
                            st.error(resultado)
        
        # ─────────────────────────────────────────────────────────────────
        # MODO CÓDIGO ENVIADO (confirmação)
        # ─────────────────────────────────────────────────────────────────
        elif st.session_state["modo_login"] == "codigo_enviado":
            with st.container(border=True):
                st.markdown("### ✅ Pedido Registrado")
                st.success(
                    f"Pedido de reset criado para **{st.session_state.get('email_reset', '')}**."
                )
                st.info(
                    "**Próximos passos:**\n\n"
                    "1. Entre em contato com o administrador da Controladoria\n"
                    "2. Informe seu pedido pelo WhatsApp ou telefone\n"
                    "3. O admin irá gerar e enviar sua nova senha temporária\n"
                    "4. No próximo login, use a nova senha (será solicitada troca imediata)\n\n"
                    "📞 **Admin:** Controladoria LLE — controladoria@grupolle.com.br"
                )
                
                if st.button("← Voltar ao login", type="primary", use_container_width=True):
                    st.session_state["modo_login"] = "login"
                    st.session_state.pop("codigo_solicitado", None)
                    st.session_state.pop("email_reset", None)
                    st.rerun()
        
        st.markdown(
            f"<p style='text-align: center; color: {CORES_LLE['cinza_texto']}; "
            "font-size: 11px; margin-top: 20px;'>"
            "LLE Ferragens LTDA — CNPJ 05.953.543/0001-47"
            "</p>",
            unsafe_allow_html=True
        )


# =============================================================================
# TELA: TROCAR MINHA SENHA (todos os perfis)
# =============================================================================
def tela_trocar_senha():
    """Tela onde o usuário troca sua própria senha."""
    st.markdown("## 🔐 Trocar Minha Senha")
    
    usuario = st.session_state.get("usuario", {})
    email = usuario.get("email", "")
    
    if usuario.get("senha_temporaria"):
        st.warning(
            "⚠️ Você está usando uma **senha temporária**. "
            "Por segurança, defina uma nova senha agora."
        )
    
    with st.form("form_trocar_senha"):
        st.markdown(f"**Usuário:** {email}")
        
        senha_atual = st.text_input("Senha atual:", type="password")
        senha_nova = st.text_input(
            "Nova senha:",
            type="password",
            help="Mínimo 6 caracteres, com ao menos um número ou caractere especial."
        )
        senha_nova_conf = st.text_input("Confirme a nova senha:", type="password")
        
        submitted = st.form_submit_button("💾 Salvar nova senha", type="primary")
        
        if submitted:
            if not senha_atual or not senha_nova or not senha_nova_conf:
                st.error("Preencha todos os campos.")
            elif senha_nova != senha_nova_conf:
                st.error("A nova senha e a confirmação não conferem.")
            else:
                ok, msg = trocar_senha(email, senha_atual, senha_nova)
                if ok:
                    st.success(f"✅ {msg}")
                    # Atualiza o flag de senha temporária na sessão
                    st.session_state["usuario"]["senha_temporaria"] = False
                    st.balloons()
                else:
                    st.error(f"❌ {msg}")


# =============================================================================
# TELA: GERENCIAR PEDIDOS DE RESET (apenas admin)
# =============================================================================
def tela_pedidos_reset():
    """Admin vê pedidos pendentes e aprova com nova senha."""
    st.markdown("## 🔑 Pedidos de Reset de Senha")
    
    if st.session_state.get("usuario", {}).get("perfil") != "admin":
        st.error("⛔ Apenas administradores podem acessar esta tela.")
        return
    
    pedidos = listar_pedidos_reset(apenas_pendentes=True)
    
    if not pedidos:
        st.info("📭 Nenhum pedido de reset pendente.")
    else:
        st.warning(f"⚠️ {len(pedidos)} pedido(s) aguardando aprovação.")
        
        for pedido in pedidos:
            with st.container(border=True):
                col_a, col_b = st.columns([2, 1])
                
                with col_a:
                    st.markdown(f"**📧 E-mail:** {pedido['email']}")
                    st.caption(f"Solicitado em: {pedido['solicitado_em'][:19].replace('T', ' ')}")
                    st.caption(f"Expira em: {pedido['expira_em'][:19].replace('T', ' ')}")
                
                with col_b:
                    with st.form(f"form_aprovar_{pedido['id']}"):
                        nova_senha = st.text_input(
                            "Nova senha temporária:",
                            value="lle@2026",
                            key=f"senha_{pedido['id']}",
                            help="O usuário será forçado a trocar no primeiro login."
                        )
                        col_btn1, col_btn2 = st.columns(2)
                        with col_btn1:
                            aprovar = st.form_submit_button("✅ Aprovar", type="primary")
                        with col_btn2:
                            cancelar = st.form_submit_button("❌ Cancelar")
                        
                        if aprovar:
                            admin_email = st.session_state["usuario"]["email"]
                            ok, msg = aprovar_pedido_reset(pedido["id"], admin_email, nova_senha)
                            if ok:
                                st.success(msg)
                                st.rerun()
                            else:
                                st.error(msg)
                        
                        if cancelar:
                            if cancelar_pedido_reset(pedido["id"]):
                                st.info(f"Pedido de {pedido['email']} cancelado.")
                                st.rerun()
    
    # Histórico
    st.divider()
    with st.expander("📜 Histórico de Pedidos (últimos 20)"):
        try:
            supabase = get_supabase()
            resp = supabase.table("pedidos_reset").select("*").order(
                "solicitado_em", desc=True
            ).limit(20).execute()
            if resp.data:
                df_hist = pd.DataFrame(resp.data)
                colunas_show = [c for c in ["email", "status", "solicitado_em",
                                              "aprovado_por", "aprovado_em"]
                                 if c in df_hist.columns]
                st.dataframe(df_hist[colunas_show], use_container_width=True, hide_index=True)
        except Exception:
            st.info("Sem histórico.")


# =============================================================================
# TELA: UPLOAD DE EXCEL
# =============================================================================
def tela_upload():
    """Tela para upload do Excel com os 4 demonstrativos."""
    
    st.markdown("## 📤 Upload de Demonstrativos Contábeis")
    st.markdown(
        "Envie o arquivo Excel com **4 abas**: DRE_Matriz, DRE_Filial, "
        "BP_Consol e DFC_Consol. Os nomes são **case-insensitive**."
    )
    
    arquivo = st.file_uploader(
        "Selecione o arquivo Excel:",
        type=["xlsx", "xlsm"],
        help="Aceita nomes flexíveis: 'DRE Matriz', 'dre_matriz', 'DRE-MATRIZ' etc."
    )
    
    if arquivo is None:
        # Mostra exemplo do formato esperado
        with st.expander("ℹ️ Ver formato esperado do Excel"):
            st.markdown("""
            **4 abas obrigatórias** (nomes flexíveis):
            
            | Aba | Tratamento | Conteúdo |
            |---|---|---|
            | `DRE_Matriz` | unidade=Matriz | DRE da unidade PISA |
            | `DRE_Filial` | unidade=Filial | DRE da unidade KING |
            | `BP_Consol` | unidade=Consol | Balanço já consolidado |
            | `DFC_Consol` | unidade=Consol | DFC já consolidado |
            
            **Colunas esperadas em DRE e BP:**
            - Conta Reduzida | Classificação | Descrição | Posição 2025 | jan-26 | fev-26 | ... | dez-26
            
            **Tratamentos automáticos:**
            - ✅ Inversão de sinais (contábil → gerencial) se Receita Bruta vier negativa
            - ✅ Cálculo de saldos acumulados do BP (variações → saldos)
            - ✅ Geração de códigos DFC via hash MD5
            - ✅ Ignora colunas extras ('Total', 'Posição 2026')
            """)
        return
    
    with st.spinner("📊 Processando arquivo..."):
        resultado = parse_excel_lle(arquivo)
    
    if not resultado["sucesso"]:
        st.error(f"❌ {resultado['erro']}")
        return
    
    # Mostra avisos do parser
    for aviso in resultado["avisos"]:
        st.info(aviso)
    
    if resultado["abas_ignoradas"]:
        st.warning(
            f"⚠️ Abas ignoradas (nomes não reconhecidos): "
            f"{', '.join(resultado['abas_ignoradas'])}"
        )
    
    st.success(
        f"✅ {len(resultado['abas_encontradas'])} abas processadas: "
        f"{', '.join(resultado['abas_encontradas'])}"
    )
    
    # Contagem por demonstrativo
    contagens = {}
    descricoes_unicas = set()
    for r in resultado["registros"]:
        chave = (r["demonstrativo"], r["unidade"])
        desc_key = (r["demonstrativo"], r["unidade"], r["descricao"])
        if desc_key not in descricoes_unicas:
            descricoes_unicas.add(desc_key)
            contagens[chave] = contagens.get(chave, 0) + 1
    
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("DRE Matriz", contagens.get(("DRE", "Matriz"), 0))
    col2.metric("DRE Filial", contagens.get(("DRE", "Filial"), 0))
    col3.metric("BP Consol", contagens.get(("BP", "Consol"), 0))
    col4.metric("DFC Consol", contagens.get(("DFC", "Consol"), 0))
    
    st.info(f"📊 Total de {len(resultado['registros'])} registros mensais a salvar.")
    
    # Guarda na sessão
    st.session_state["registros_pendentes"] = resultado["registros"]
    st.session_state["contas_dfc_pendentes"] = resultado["contas_dfc_novas"]
    
    # Valida DFC contra o banco
    contas_para_aprovar = []
    if resultado["contas_dfc_novas"]:
        try:
            validacao = validar_contas_dfc(resultado["contas_dfc_novas"])
            contas_para_aprovar = validacao["novas"] + validacao["similares"]
            
            if validacao["existentes"]:
                st.info(
                    f"♻️ {len(validacao['existentes'])} contas DFC já cadastradas "
                    "(serão reutilizadas)."
                )
            if contas_para_aprovar:
                st.warning(
                    f"⚠️ {len(contas_para_aprovar)} contas DFC precisam validação manual."
                )
        except Exception as e:
            st.warning(f"⚠️ Validação DFC pulada: {e}")
    
    st.divider()
    
    # Se houver contas para validar, abre a tela
    if contas_para_aprovar:
        tela_validacao_dfc(contas_para_aprovar)
        return
    
    # Senão, botão direto de salvar
    if st.button("💾 Salvar no Banco de Dados", type="primary", use_container_width=True):
        usuario_email = st.session_state["usuario"]["email"]
        
        # Salva mapeamento DFC primeiro (das contas novas detectadas)
        if resultado["contas_dfc_novas"]:
            salvar_mapeamento_dfc(resultado["contas_dfc_novas"], usuario_email)
        
        # Salva os dados contábeis
        ok = salvar_no_supabase(resultado["registros"], usuario_email, modo="completo")
        if ok:
            st.success("✅ Dados salvos com sucesso!")
            st.balloons()
            # Limpa estado
            st.session_state.pop("registros_pendentes", None)
            st.session_state.pop("contas_dfc_pendentes", None)


# =============================================================================
# TELA: VALIDAÇÃO DE CONTAS DFC NOVAS
# =============================================================================
def tela_validacao_dfc(contas_para_aprovar: list):
    """Tela para validação manual de novas contas DFC."""
    st.markdown("### 🔍 Validação de Contas DFC")
    st.info(
        "O DFC não traz códigos contábeis no Excel original. O sistema gera códigos "
        "via hash MD5 da descrição. Revise as contas abaixo e confirme."
    )
    
    contas_aprovadas = []
    
    with st.form("form_validacao_dfc"):
        for idx, conta in enumerate(contas_para_aprovar):
            with st.container(border=True):
                col_a, col_b = st.columns([3, 2])
                
                with col_a:
                    st.markdown(f"**Descrição:** {conta['descricao']}")
                    st.caption(f"Código gerado: `{conta['codigo']}`")
                    
                    if "similar_existente" in conta:
                        sim = conta["similar_existente"]
                        st.markdown(
                            f"💡 **Similar a:** {sim.get('descricao_original', '?')} "
                            f"({conta.get('similaridade', 0):.0f}% de similaridade)"
                        )
                
                with col_b:
                    classif = st.text_input(
                        "Classificação:",
                        value=conta.get("classificacao", ""),
                        key=f"classif_{idx}"
                    )
                    tipo = st.selectbox(
                        "Tipo de Fluxo:",
                        ["Operacional", "Investimento", "Financiamento"],
                        index=["Operacional", "Investimento", "Financiamento"].index(
                            conta.get("classificacao", "5.1.01")[2:3] == "1" and "Operacional"
                            or (conta.get("classificacao", "5.1.01")[2:3] == "2" and "Investimento")
                            or "Financiamento"
                        ) if conta.get("classificacao", "")[:3] in ["5.1", "5.2", "5.3"] else 0,
                        key=f"tipo_{idx}"
                    )
                
                contas_aprovadas.append({
                    "codigo": conta["codigo"],
                    "descricao": conta["descricao"],
                    "classificacao": classif,
                    "tipo_hierarquia": conta.get("tipo_hierarquia", "analitica"),
                })
        
        submitted = st.form_submit_button(
            "✅ Aprovar Todas e Salvar Dados",
            type="primary",
            use_container_width=True
        )
    
    if submitted:
        usuario_email = st.session_state["usuario"]["email"]
        
        # Salva mapeamento DFC
        with st.spinner("Salvando mapeamento DFC..."):
            salvar_mapeamento_dfc(contas_aprovadas, usuario_email)
        
        # Salva dados contábeis
        registros = st.session_state.get("registros_pendentes", [])
        if registros:
            with st.spinner("Salvando dados contábeis..."):
                ok = salvar_no_supabase(registros, usuario_email, modo="completo")
            if ok:
                st.success("✅ Tudo salvo com sucesso!")
                st.balloons()
                st.session_state.pop("registros_pendentes", None)
                st.session_state.pop("contas_dfc_pendentes", None)


# =============================================================================
# DASHBOARD: VISÃO GERAL
# =============================================================================
def dashboard_visao_geral(df, periodo, unidade_dre="Consolidado", usar_saldo_bp=True):
    """Dashboard principal no estilo da referência."""
    ind = calcular_indicadores_completos(df, periodo, unidade_dre, usar_saldo_bp)
    
    # ─────────────────────────────────────────────────────────────────────
    # LINHA 1 — 5 KPI CARDS PRINCIPAIS
    # ─────────────────────────────────────────────────────────────────────
    lucro_liq = ind["_base_lucro_liquido"]
    margem_liq = ind["margem_liquida"]
    liq_corrente = ind["liquidez_corrente"]
    roe = ind["roe"]
    endiv = ind["endividamento_geral"]
    
    # Contexto: "Mês · Unidade"
    contexto_geral = f"{periodo} · {unidade_dre}"
    
    cards_html = "<div style='display: grid; grid-template-columns: repeat(5, 1fr); gap: 14px; margin-bottom: 24px;'>"
    cards_html += render_kpi_card(
        label="Lucro Líquido",
        valor=formatar_brl(lucro_liq),
        contexto=contexto_geral,
        cor="positive" if lucro_liq >= 0 else "negative",
        icone="📈" if lucro_liq >= 0 else "📉",
    )
    cards_html += render_kpi_card(
        label="Margem Líquida",
        valor=formatar_pct(margem_liq, 1),
        contexto=contexto_geral,
        cor="default",
        icone="📊",
    )
    cards_html += render_kpi_card(
        label="Liquidez Corrente",
        valor=formatar_num(liq_corrente, 2),
        contexto=contexto_geral,
        cor="neutral",
        icone="〰️",
    )
    cards_html += render_kpi_card(
        label="ROE",
        valor=formatar_pct(roe, 1),
        contexto=contexto_geral,
        cor="positive" if roe >= 0 else "negative",
        icone="↗",
    )
    cards_html += render_kpi_card(
        label="Endividamento",
        valor=formatar_pct(endiv, 1),
        contexto=contexto_geral,
        cor="warning" if endiv > 60 else "default",
        icone="↘",
    )
    cards_html += "</div>"
    st.markdown(cards_html, unsafe_allow_html=True)
    
    # ─────────────────────────────────────────────────────────────────────
    # LINHA 2 — EVOLUÇÃO MENSAL (tabela com 4 indicadores × 12 meses)
    # ─────────────────────────────────────────────────────────────────────
    meses_disponiveis = [p for p in PERIODOS_PADRAO if p != "Posição 2025" and p in df.columns]
    
    if meses_disponiveis:
        # Coleta dados de cada mês
        evolucao = {
            "Receita Líquida": [],
            "Lucro Líquido": [],
            "Ativo Total": [],
            "Patrimônio Líquido": [],
        }
        
        for mes in meses_disponiveis:
            rl = buscar_valor(df, "3.3", mes, "DRE", unidade_dre)
            if rl == 0:
                rl = buscar_valor_descricao(df, "RECEITA LÍQUIDA", mes, "DRE", unidade_dre)
            ll = buscar_valor(df, "3.99", mes, "DRE", unidade_dre)
            if ll == 0:
                ll = buscar_valor_descricao(df, "LUCRO LÍQUIDO", mes, "DRE", unidade_dre)
            at = buscar_valor(df, "1", mes, "BP", "Consol", usar_saldo_bp)
            pl = buscar_valor(df, "2.3", mes, "BP", "Consol", usar_saldo_bp)
            
            evolucao["Receita Líquida"].append(rl)
            evolucao["Lucro Líquido"].append(ll)
            evolucao["Ativo Total"].append(at)
            evolucao["Patrimônio Líquido"].append(pl)
        
        # Header da tabela
        meses_curtos = [m.split("-")[0].capitalize() for m in meses_disponiveis]
        
        html_evol = "<div class='content-card'>"
        html_evol += "<div class='content-card-title'>📊 Evolução Mensal · Indicadores Principais</div>"
        html_evol += "<table class='evolucao-table'><thead><tr>"
        html_evol += "<th>Indicador</th>"
        for mes_curto in meses_curtos:
            html_evol += f"<th>{mes_curto}</th>"
        html_evol += "</tr></thead><tbody>"
        
        for nome_kpi, valores in evolucao.items():
            html_evol += f"<tr><td>{nome_kpi}</td>"
            for idx_v, v in enumerate(valores):
                classe = "highlight" if meses_disponiveis[idx_v] == periodo else ""
                html_evol += f"<td class='{classe}'>{formatar_brl(v).replace('R$ ', '')}</td>"
            html_evol += "</tr>"
        
        html_evol += "</tbody></table></div>"
        st.markdown(html_evol, unsafe_allow_html=True)
    
    # ─────────────────────────────────────────────────────────────────────
    # LINHA 3 — DRE simplificada + Balanço resumo (lado a lado)
    # ─────────────────────────────────────────────────────────────────────
    col_dre, col_bp = st.columns(2)
    
    with col_dre:
        # DRE Resumida
        rl = ind["_base_receita_liquida"]
        cmv = ind["_base_cmv"]
        # Tenta pegar despesas comerciais e admin separadas
        desp_com = buscar_valor(df, "4.2.02", periodo, "DRE", unidade_dre)
        desp_adm = buscar_valor(df, "4.2.01", periodo, "DRE", unidade_dre)
        rec_fin = buscar_valor(df, "3.4", periodo, "DRE", unidade_dre)
        desp_fin = ind["_base_despesas_financeiras"]
        irpj = abs(buscar_valor(df, "4.4", periodo, "DRE", unidade_dre))
        if irpj == 0:
            irpj = abs(buscar_valor_descricao(df, "IRPJ", periodo, "DRE", unidade_dre))
        if irpj == 0:
            irpj = abs(buscar_valor_descricao(df, "CSLL", periodo, "DRE", unidade_dre))
        ll = ind["_base_lucro_liquido"]
        
        html_dre = f"""
        <div class='content-card'>
            <div class='content-card-title'>
                <span>📑 DRE · {unidade_dre} · {periodo}</span>
                <span class='link-detalhar'>Detalhar →</span>
            </div>
            <table class='dre-resumo-table'>
                <tr class='destaque-rl'>
                    <td class='descricao'>Receita Líquida</td>
                    <td class='valor'>{formatar_brl(rl)}</td>
                </tr>
                <tr>
                    <td class='descricao'>CPV</td>
                    <td class='valor'>({formatar_brl(abs(cmv)).replace('R$ ','')})</td>
                </tr>
                <tr>
                    <td class='descricao'>Despesas Comerciais</td>
                    <td class='valor'>({formatar_brl(abs(desp_com)).replace('R$ ','')})</td>
                </tr>
                <tr>
                    <td class='descricao'>Despesas Administrativas</td>
                    <td class='valor'>({formatar_brl(abs(desp_adm)).replace('R$ ','')})</td>
                </tr>
                <tr>
                    <td class='descricao'>Receitas Financeiras</td>
                    <td class='valor'>{formatar_brl(rec_fin)}</td>
                </tr>
                <tr>
                    <td class='descricao'>Despesas Financeiras</td>
                    <td class='valor'>({formatar_brl(abs(desp_fin)).replace('R$ ','')})</td>
                </tr>
                <tr>
                    <td class='descricao'>IRPJ/CSLL</td>
                    <td class='valor'>({formatar_brl(irpj).replace('R$ ','')})</td>
                </tr>
                <tr class='destaque-final'>
                    <td class='descricao'>LUCRO LÍQUIDO</td>
                    <td class='valor'>{formatar_brl(ll)}</td>
                </tr>
            </table>
        </div>
        """
        st.markdown(html_dre, unsafe_allow_html=True)
    
    with col_bp:
        # Balanço resumido
        ac = buscar_valor(df, "1.1", periodo, "BP", "Consol", usar_saldo_bp)
        anc = buscar_valor(df, "1.2", periodo, "BP", "Consol", usar_saldo_bp)
        at = ac + anc
        pc = buscar_valor(df, "2.1", periodo, "BP", "Consol", usar_saldo_bp)
        pnc = buscar_valor(df, "2.2", periodo, "BP", "Consol", usar_saldo_bp)
        pl = buscar_valor(df, "2.3", periodo, "BP", "Consol", usar_saldo_bp)
        tot_pas = pc + pnc + pl
        
        diff = abs(at - tot_pas)
        bp_ok = diff < max(1.0, at * 0.001)  # 0.1% de tolerância
        
        badge = (
            "<div class='badge-ok'>✅ Balanço equilibrado</div>"
            if bp_ok else
            f"<div class='badge-warn'>⚠️ Diferença: {formatar_brl(diff)}</div>"
        )
        
        html_bp = f"""
        <div class='content-card'>
            <div class='content-card-title'>
                <span>💼 Balanço · Consolidado · {periodo}</span>
                <span class='link-detalhar'>Detalhar →</span>
            </div>
            <div style='display: grid; grid-template-columns: 1fr 1fr; gap: 14px;'>
                <div class='balanco-bloco'>
                    <div class='balanco-header'>ATIVO</div>
                    <div class='balanco-linha'>
                        <span class='balanco-linha-label'>Circulante</span>
                        <span class='balanco-linha-valor'>{formatar_brl(ac).replace('R$ ','')}</span>
                    </div>
                    <div class='balanco-linha'>
                        <span class='balanco-linha-label'>Não Circulante</span>
                        <span class='balanco-linha-valor'>{formatar_brl(anc).replace('R$ ','')}</span>
                    </div>
                    <div class='balanco-linha balanco-total'>
                        <span class='balanco-linha-label'>Total</span>
                        <span class='balanco-linha-valor'>{formatar_brl(at).replace('R$ ','')}</span>
                    </div>
                </div>
                <div class='balanco-bloco'>
                    <div class='balanco-header'>PASSIVO + PL</div>
                    <div class='balanco-linha'>
                        <span class='balanco-linha-label'>Passivo Circ.</span>
                        <span class='balanco-linha-valor'>{formatar_brl(pc).replace('R$ ','')}</span>
                    </div>
                    <div class='balanco-linha'>
                        <span class='balanco-linha-label'>Passivo NC</span>
                        <span class='balanco-linha-valor'>{formatar_brl(pnc).replace('R$ ','')}</span>
                    </div>
                    <div class='balanco-linha'>
                        <span class='balanco-linha-label'>Patrim. Líquido</span>
                        <span class='balanco-linha-valor'>{formatar_brl(pl).replace('R$ ','')}</span>
                    </div>
                    <div class='balanco-linha balanco-total'>
                        <span class='balanco-linha-label'>Total</span>
                        <span class='balanco-linha-valor'>{formatar_brl(tot_pas).replace('R$ ','')}</span>
                    </div>
                </div>
            </div>
            <div style='margin-top: 14px;'>{badge}</div>
        </div>
        """
        st.markdown(html_bp, unsafe_allow_html=True)
    
    # ─────────────────────────────────────────────────────────────────────
    # LINHA 4 — KPIs LLE estratégicos (em formato compacto)
    # ─────────────────────────────────────────────────────────────────────
    st.markdown("<br>", unsafe_allow_html=True)
    runway = calcular_runway_caixa(df, periodo)
    
    kpis_lle = "<div style='display: grid; grid-template-columns: repeat(4, 1fr); gap: 14px;'>"
    kpis_lle += render_kpi_card(
        label="Lucro sem Subvenção",
        valor=formatar_brl(ind["lucro_sem_subvencao"]),
        contexto=f"Peso da subvenção: {ind['peso_subvencao_lucro']:.1f}%",
        cor="positive" if ind["lucro_sem_subvencao"] >= 0 else "negative",
        icone="🎁",
    )
    kpis_lle += render_kpi_card(
        label="Runway de Caixa",
        valor=f"{runway['runway_meses']:.1f} meses",
        contexto=runway["cenario"],
        cor="positive" if runway["runway_meses"] >= 12 else ("warning" if runway["runway_meses"] >= 6 else "negative"),
        icone="⏱",
    )
    kpis_lle += render_kpi_card(
        label="Cobertura CD King",
        valor=f"{ind['cobertura_cd_king']:.1f} meses",
        contexto="Estoque KING / CMV mensal",
        cor="default",
        icone="📦",
    )
    kpis_lle += render_kpi_card(
        label="EBITDA",
        valor=formatar_brl(ind["_base_ebitda"]),
        contexto=f"Margem: {ind['margem_ebitda']:.1f}%",
        cor="positive" if ind["_base_ebitda"] >= 0 else "negative",
        icone="💰",
    )
    kpis_lle += "</div>"
    st.markdown(kpis_lle, unsafe_allow_html=True)


# =============================================================================
# DASHBOARD: DRE
# =============================================================================
def dashboard_dre(df, periodo, usar_saldo_bp=True):
    """DRE detalhada com drill-down e AV."""
    st.markdown(f"## 📑 Demonstração de Resultado — {periodo}")
    
    col_f1, col_f2 = st.columns(2)
    with col_f1:
        unidade_filtro = st.selectbox(
            "Unidade:",
            ["Consolidado", "Matriz", "Filial"],
            format_func=lambda x: {
                "Consolidado": "Consolidado (PISA + KING)",
                "Matriz": "PISA (Matriz)",
                "Filial": "KING (Filial)"
            }[x]
        )
    with col_f2:
        nivel_max = st.slider("Nível hierárquico:", 1, 5, 3)
    
    # Filtra DRE
    df_dre = df[(df["demonstrativo"] == "DRE") & (df["unidade"] == unidade_filtro)].copy()
    if len(df_dre) == 0:
        st.warning("Sem dados para essa unidade.")
        return
    
    df_dre["nivel"] = df_dre["classificacao"].fillna("").str.count(r"\.") + 1
    df_dre = df_dre[df_dre["nivel"] <= nivel_max]
    
    # AV
    av = analise_vertical(df, periodo, "DRE", unidade_filtro)
    df_dre = df_dre.merge(av[["classificacao", "AV"]], on="classificacao", how="left")
    
    if periodo not in df_dre.columns:
        st.error(f"Período '{periodo}' não disponível.")
        return
    
    df_show = df_dre[["classificacao", "descricao", periodo, "AV"]].copy()
    df_show.columns = ["Classificação", "Descrição", "Valor (R$)", "AV (%)"]
    
    st.dataframe(
        df_show.style.format({
            "Valor (R$)": lambda x: formatar_brl(x),
            "AV (%)": lambda x: formatar_pct(x),
        }),
        use_container_width=True,
        height=600,
        hide_index=True,
    )
    
    st.divider()
    st.markdown("### Margens")
    ind = calcular_indicadores_completos(df, periodo, unidade_filtro, usar_saldo_bp)
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Margem Bruta", formatar_pct(ind["margem_bruta"]))
    c2.metric("Margem EBITDA", formatar_pct(ind["margem_ebitda"]))
    c3.metric("Margem Operacional", formatar_pct(ind["margem_operacional"]))
    c4.metric("Margem Líquida", formatar_pct(ind["margem_liquida"]))


# =============================================================================
# DASHBOARD: BALANÇO PATRIMONIAL
# =============================================================================
def dashboard_bp(df, periodo, usar_saldo_bp=True):
    """BP com liquidez, endividamento e drill-down."""
    st.markdown(f"## 💼 Balanço Patrimonial — {periodo}")
    st.caption(f"Visualização: **{'Saldos Acumulados' if usar_saldo_bp else 'Variações do mês'}**")
    
    ind = calcular_indicadores_completos(df, periodo, "Consolidado", usar_saldo_bp)
    
    # Liquidez
    st.markdown("### 💧 Liquidez")
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Liquidez Corrente", formatar_num(ind["liquidez_corrente"]))
    c2.metric("Liquidez Seca", formatar_num(ind["liquidez_seca"]))
    c3.metric("Liquidez Imediata", formatar_num(ind["liquidez_imediata"]))
    c4.metric("Liquidez Geral", formatar_num(ind["liquidez_geral"]))
    
    st.divider()
    
    # Endividamento
    st.markdown("### 📊 Endividamento")
    c5, c6, c7, c8 = st.columns(4)
    c5.metric("Endiv. Geral", formatar_pct(ind["endividamento_geral"]))
    c6.metric("Endiv. / PL", formatar_pct(ind["endividamento_pl"]))
    c7.metric("Composição CP", formatar_pct(ind["composicao_endividamento"]))
    c8.metric("Imobilização PL", formatar_pct(ind["imobilizacao_pl"]))
    
    st.divider()
    
    # BP detalhado
    nivel_max = st.slider("Nível hierárquico:", 1, 5, 2, key="bp_nivel")
    df_bp = df[df["demonstrativo"] == "BP"].copy()
    df_bp["nivel"] = df_bp["classificacao"].fillna("").str.count(r"\.") + 1
    df_bp = df_bp[df_bp["nivel"] <= nivel_max]
    
    av_bp = analise_vertical(df, periodo, "BP", "Consol", usar_saldo_bp)
    df_bp = df_bp.merge(av_bp[["classificacao", "AV"]], on="classificacao", how="left")
    
    coluna_valor = f"{periodo}_saldo" if usar_saldo_bp and f"{periodo}_saldo" in df_bp.columns else periodo
    
    df_show = df_bp[["classificacao", "descricao", coluna_valor, "AV"]].copy()
    df_show.columns = ["Classificação", "Descrição", "Saldo (R$)", "AV (%)"]
    
    st.dataframe(
        df_show.style.format({
            "Saldo (R$)": lambda x: formatar_brl(x),
            "AV (%)": lambda x: formatar_pct(x),
        }),
        use_container_width=True,
        height=500,
        hide_index=True,
    )


# =============================================================================
# DASHBOARD: DFC
# =============================================================================
def dashboard_dfc(df, periodo):
    """DFC com fluxos e composição."""
    st.markdown(f"## 💸 Demonstração do Fluxo de Caixa — {periodo}")
    
    ind = calcular_indicadores_completos(df, periodo)
    
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("FCO (Operacional)", formatar_brl(ind["fco"]))
    c2.metric("FCI (Investimento)", formatar_brl(ind["fci"]))
    c3.metric("FCF (Financiamento)", formatar_brl(ind["fcf"]))
    c4.metric("Fluxo Total", formatar_brl(ind["fluxo_total"]))
    
    st.divider()
    
    st.markdown("### Composição do Fluxo")
    caixa_inicial = ind["_base_caixa"] - ind["fluxo_total"]
    fig = go.Figure(go.Waterfall(
        x=["Caixa Inicial", "FCO", "FCI", "FCF", "Caixa Final"],
        measure=["absolute", "relative", "relative", "relative", "total"],
        y=[caixa_inicial, ind["fco"], ind["fci"], ind["fcf"], 0],
        increasing=dict(marker=dict(color=CORES_LLE["verde_institucional"])),
        decreasing=dict(marker=dict(color=CORES_LLE["vermelho"])),
        totals=dict(marker=dict(color=CORES_LLE["azul_profundo"])),
    ))
    fig.update_layout(**PLOTLY_LAYOUT, height=400)
    st.plotly_chart(fig, use_container_width=True)
    
    # Detalhe
    df_dfc = df[df["demonstrativo"] == "DFC"].copy()
    st.markdown("### Detalhamento")
    if periodo in df_dfc.columns:
        df_show = df_dfc[["descricao", periodo]].rename(
            columns={"descricao": "Descrição", periodo: "Valor (R$)"}
        )
        st.dataframe(
            df_show.style.format({"Valor (R$)": lambda x: formatar_brl(x)}),
            use_container_width=True,
            height=400,
            hide_index=True,
        )


# =============================================================================
# DASHBOARD: PISA × KING
# =============================================================================
def dashboard_unidades(df, periodo):
    """Comparativo entre as duas unidades."""
    st.markdown(f"## 🏢 Comparativo PISA × KING — {periodo}")
    
    unidades = calcular_margem_unidade(df, periodo)
    
    c1, c2 = st.columns(2)
    for col, (nome, dados) in zip([c1, c2], unidades.items()):
        with col:
            st.markdown(f"### {nome}")
            st.metric("Receita Líquida", formatar_brl(dados["receita_liquida"]),
                      delta=f"Part: {dados['part_receita']:.1f}%")
            st.metric("Lucro Líquido", formatar_brl(dados["lucro_liquido"]),
                      delta=f"Part: {dados['part_lucro']:.1f}%")
            st.metric("Margem Bruta", formatar_pct(dados["margem_bruta"]))
            st.metric("Margem Líquida", formatar_pct(dados["margem_liquida"]))
    
    st.divider()
    
    # Gráfico comparativo
    st.markdown("### Comparativo de Margens")
    df_comp = pd.DataFrame([
        {"Unidade": nome, "Margem Bruta": d["margem_bruta"],
         "Margem Operacional": d["margem_operacional"],
         "Margem Líquida": d["margem_liquida"]}
        for nome, d in unidades.items()
    ])
    
    fig = go.Figure()
    for kpi, cor in zip(
        ["Margem Bruta", "Margem Operacional", "Margem Líquida"],
        [CORES_LLE["azul_profundo"], CORES_LLE["amarelo_logo"], CORES_LLE["verde_institucional"]]
    ):
        fig.add_trace(go.Bar(name=kpi, x=df_comp["Unidade"], y=df_comp[kpi],
                              marker_color=cor))
    fig.update_layout(**PLOTLY_LAYOUT, barmode="group", height=400)
    st.plotly_chart(fig, use_container_width=True)


# =============================================================================
# DASHBOARD: SUBVENÇÃO
# =============================================================================
def dashboard_subvencao(df, periodo):
    """Análise da dependência de subvenções Riolog."""
    st.markdown(f"## 🎁 Análise de Subvenção Riolog — {periodo}")
    
    dados = calcular_dependencia_subvencao(df, periodo)
    
    st.markdown(
        f"""
        <div style='background-color: {dados["cor"]}20;
                    border-left: 4px solid {dados["cor"]};
                    padding: 16px; border-radius: 4px; margin: 16px 0;'>
            <h4 style='color: {dados["cor"]}; margin: 0;'>
                Nível de Dependência: {dados["nivel"]}
            </h4>
            <p style='margin: 8px 0 0; color: {CORES_LLE["azul_profundo"]};'>
                {dados["alerta"]}
            </p>
        </div>
        """,
        unsafe_allow_html=True
    )
    
    c1, c2, c3 = st.columns(3)
    c1.metric("Subvenção no Período", formatar_brl(dados["subvencao_total"]))
    c2.metric("Lucro com Subvenção", formatar_brl(dados["lucro_com_subvencao"]))
    c3.metric("Lucro sem Subvenção", formatar_brl(dados["lucro_sem_subvencao"]))
    
    c4, c5, c6 = st.columns(3)
    c4.metric("Peso no Lucro", formatar_pct(dados["peso_no_lucro"]))
    c5.metric("Peso na Receita", formatar_pct(dados["peso_na_receita"]))
    c6.metric("Peso no PL", formatar_pct(dados["peso_no_pl"]))


# =============================================================================
# DASHBOARD: CONCILIAÇÃO
# =============================================================================
def dashboard_conciliacao(df, periodo_atual, periodo_anterior):
    """Conciliação DRE × BP × DFC."""
    st.markdown(f"## ✅ Conciliação — {periodo_atual} vs {periodo_anterior}")
    
    resultado = conciliar_demonstrativos(df, periodo_atual, periodo_anterior)
    
    if resultado["status_geral"] == "OK":
        st.success("✅ Todas as validações passaram. Demonstrativos conciliados.")
    else:
        st.warning(f"⚠️ {resultado['status_geral']} — revise abaixo.")
    
    for v in resultado["validacoes"]:
        with st.container(border=True):
            ca, cb, cc = st.columns([2, 1, 1])
            with ca:
                st.markdown(f"**{v['nome']}**")
                st.caption(v["status"])
            with cb:
                st.metric("Esperado", formatar_brl(v["esperado"]))
            with cc:
                st.metric("Realizado", formatar_brl(v["realizado"]),
                          delta=f"Diff: {formatar_brl(v['diferenca'])}")


# =============================================================================
# DASHBOARD: ANOMALIAS
# =============================================================================
def tela_anomalias(df, periodo_atual, periodo_anterior):
    """Detecção de variações fora da curva."""
    st.markdown(f"## 🚨 Anomalias — {periodo_atual} vs {periodo_anterior}")
    
    limite = st.slider("Limite de variação % considerada anômala:", 20, 200, 50)
    anomalias = detectar_anomalias(df, periodo_atual, periodo_anterior, limite)
    
    if len(anomalias) == 0:
        st.success(f"✅ Nenhuma anomalia acima de {limite}%.")
    else:
        st.warning(f"⚠️ {len(anomalias)} anomalias detectadas.")
        st.dataframe(
            anomalias.style.format({
                periodo_anterior: lambda x: formatar_brl(x),
                periodo_atual: lambda x: formatar_brl(x),
                "variacao_abs": lambda x: formatar_brl(x),
                "variacao_pct": lambda x: formatar_pct(x),
            }),
            use_container_width=True,
            height=500,
            hide_index=True,
        )


# =============================================================================
# TELA: USUÁRIOS (admin)
# =============================================================================
def tela_usuarios():
    """Gestão de usuários (cadastro + reset de senha)."""
    st.markdown("## 👥 Gestão de Usuários")
    
    if st.session_state.get("usuario", {}).get("perfil") != "admin":
        st.error("⛔ Apenas administradores podem acessar esta tela.")
        return
    
    # Listagem
    usuarios = listar_usuarios()
    if usuarios:
        df_u = pd.DataFrame(usuarios)
        colunas_show = []
        for c in ["email", "nome", "perfil", "ativo", "senha_temporaria", "ultimo_login"]:
            if c in df_u.columns:
                colunas_show.append(c)
        st.dataframe(df_u[colunas_show], use_container_width=True, hide_index=True)
    
    st.divider()
    
    # Cadastro
    st.markdown("### ➕ Cadastrar Novo Usuário")
    with st.form("form_novo_usuario"):
        c1, c2 = st.columns(2)
        with c1:
            novo_email = st.text_input("E-mail:")
            novo_nome = st.text_input("Nome:")
        with c2:
            novo_perfil = st.selectbox("Perfil:", ["diretoria", "controller", "admin"])
            senha_inicial = st.text_input(
                "Senha inicial:",
                value="lle@2026",
                help="O usuário será forçado a trocar no primeiro login."
            )
        
        if st.form_submit_button("Cadastrar", type="primary"):
            if not novo_email or not novo_nome:
                st.error("Preencha e-mail e nome.")
            else:
                eh_valida, msg = validar_forca_senha(senha_inicial)
                if not eh_valida:
                    st.error(f"Senha inválida: {msg}")
                else:
                    try:
                        supabase = get_supabase()
                        supabase.table("usuarios").insert({
                            "email": novo_email.lower().strip(),
                            "nome": novo_nome.strip(),
                            "perfil": novo_perfil,
                            "ativo": True,
                            "senha_hash": hash_senha(senha_inicial),
                            "senha_temporaria": True,
                        }).execute()
                        st.success(
                            f"✅ Usuário **{novo_email}** cadastrado com perfil **{novo_perfil}**!\n\n"
                            f"📞 Comunique a senha inicial **`{senha_inicial}`** ao usuário por canal seguro."
                        )
                        st.rerun()
                    except Exception as e:
                        st.error(f"Erro ao cadastrar: {e}")
    
    st.divider()
    
    # Reset de senha (admin força reset de outro usuário)
    st.markdown("### 🔑 Resetar Senha de um Usuário")
    with st.form("form_reset_senha_admin"):
        emails_lista = [u["email"] for u in usuarios] if usuarios else []
        if not emails_lista:
            st.info("Nenhum usuário cadastrado.")
        else:
            c1, c2 = st.columns(2)
            with c1:
                email_alvo = st.selectbox("Usuário:", emails_lista)
            with c2:
                nova_senha_reset = st.text_input(
                    "Nova senha temporária:",
                    value="lle@2026"
                )
            
            if st.form_submit_button("🔄 Resetar Senha", type="primary"):
                admin_email = st.session_state["usuario"]["email"]
                ok, msg = resetar_senha_admin(email_alvo, nova_senha_reset, admin_email)
                if ok:
                    st.success(msg)
                else:
                    st.error(msg)


# =============================================================================
# FUNÇÃO MAIN
# =============================================================================
def main():
    """Ponto de entrada da aplicação — layout com header LLE + tabs horizontais."""
    aplicar_css_customizado()
    
    # Inicializa gerenciador de cookies
    cookies = get_cookie_manager()
    if not cookies.ready():
        st.stop()
    
    # Inicializa estado de sessão
    if "autenticado" not in st.session_state:
        st.session_state["autenticado"] = False
    
    # AUTO-LOGIN via cookie
    if not st.session_state["autenticado"]:
        email_cookie = cookies.get("usuario_email")
        timestamp_cookie = cookies.get("login_timestamp")
        
        if email_cookie and timestamp_cookie:
            try:
                ts = int(timestamp_cookie)
                agora = int(datetime.now().timestamp())
                if (agora - ts) < (7 * 24 * 60 * 60):
                    usuario = validar_usuario(email_cookie)
                    if usuario:
                        st.session_state["autenticado"] = True
                        st.session_state["usuario"] = usuario
                    else:
                        cookies["usuario_email"] = ""
                        cookies["login_timestamp"] = ""
                        cookies.save()
                else:
                    cookies["usuario_email"] = ""
                    cookies["login_timestamp"] = ""
                    cookies.save()
            except Exception:
                pass
    
    if not st.session_state["autenticado"]:
        tela_login(cookies)
        return
    
    usuario = st.session_state["usuario"]
    
    # Força troca de senha temporária
    if usuario.get("senha_temporaria"):
        render_header(usuario)
        st.warning(
            "⚠️ **Você está usando uma senha temporária.** "
            "Por segurança, é necessário definir uma nova senha agora."
        )
        tela_trocar_senha()
        return
    
    # ─────────────────────────────────────────────────────────────────────
    # HEADER LLE (topo fixo)
    # ─────────────────────────────────────────────────────────────────────
    render_header(usuario)
    
    # ─────────────────────────────────────────────────────────────────────
    # CARREGAMENTO DE DADOS
    # ─────────────────────────────────────────────────────────────────────
    df_base = carregar_dados_contabeis()
    df = None
    if df_base is not None and len(df_base) > 0:
        df = consolidar_dre(df_base)
        df = calcular_saldos_acumulados_bp(df)
    
    # ─────────────────────────────────────────────────────────────────────
    # BARRA DE CONTROLES (período + unidade + opções)
    # ─────────────────────────────────────────────────────────────────────
    if df is not None and len(df) > 0:
        periodos_dre = periodos_disponiveis(df, "DRE")
        periodos_bp = periodos_disponiveis(df, "BP")
        periodos_dfc = periodos_disponiveis(df, "DFC")
        
        todos_periodos = []
        for p in PERIODOS_PADRAO:
            if p in periodos_dre or p in periodos_bp or p in periodos_dfc:
                todos_periodos.append(p)
        
        periodos_mensais = [p for p in todos_periodos if p != "Posição 2025"]
        if not periodos_mensais:
            periodos_mensais = todos_periodos
        
        col_p1, col_p2, col_p3, col_p4 = st.columns([2, 2, 2, 1])
        
        with col_p1:
            periodo_atual = st.selectbox(
                "📅 Período",
                periodos_mensais,
                index=len(periodos_mensais) - 1 if periodos_mensais else 0,
                key="periodo_atual_main",
            )
        with col_p2:
            unidade_dre = st.selectbox(
                "🏢 Unidade DRE",
                ["Consolidado", "Matriz", "Filial"],
                format_func=lambda x: {
                    "Consolidado": "Consolidado",
                    "Matriz": "PISA (Matriz)",
                    "Filial": "KING (Filial)"
                }[x],
                key="unidade_main",
            )
        with col_p3:
            modo_bp = st.selectbox(
                "💼 BP",
                ["Saldos Acumulados", "Variações do mês"],
                key="modo_bp_main",
            )
            usar_saldo_bp = (modo_bp == "Saldos Acumulados")
        with col_p4:
            st.markdown("<div style='padding-top: 28px;'>", unsafe_allow_html=True)
            if st.button("🚪 Sair", use_container_width=True, key="logout_btn"):
                try:
                    cookies["usuario_email"] = ""
                    cookies["usuario_nome"] = ""
                    cookies["usuario_perfil"] = ""
                    cookies["login_timestamp"] = ""
                    cookies.save()
                except Exception:
                    pass
                st.session_state["autenticado"] = False
                st.session_state.pop("usuario", None)
                st.rerun()
            st.markdown("</div>", unsafe_allow_html=True)
        
        # Período de comparação (default: primeiro disponível)
        periodo_anterior = todos_periodos[0] if todos_periodos else periodo_atual
    else:
        periodo_atual = None
        periodo_anterior = None
        usar_saldo_bp = True
        unidade_dre = "Consolidado"
        
        # Mesmo sem dados, mostra botão de logout
        col_logout = st.columns([6, 1])
        with col_logout[1]:
            if st.button("🚪 Sair", use_container_width=True, key="logout_btn_no_data"):
                try:
                    cookies["usuario_email"] = ""
                    cookies["login_timestamp"] = ""
                    cookies.save()
                except Exception:
                    pass
                st.session_state["autenticado"] = False
                st.session_state.pop("usuario", None)
                st.rerun()
    
    # ─────────────────────────────────────────────────────────────────────
    # TABS HORIZONTAIS (navegação principal)
    # ─────────────────────────────────────────────────────────────────────
    perfil = usuario["perfil"]
    
    # Define tabs por perfil
    if perfil == "admin":
        tabs_labels = ["📊 Dashboard", "📑 DRE", "💼 Balanço", "💸 DFC",
                       "🏢 PISA × KING", "🎁 Subvenção", "✅ Conciliação",
                       "🚨 Anomalias", "📤 Upload", "👥 Usuários",
                       "🔑 Resets", "🔐 Senha"]
    elif perfil == "controller":
        tabs_labels = ["📊 Dashboard", "📑 DRE", "💼 Balanço", "💸 DFC",
                       "🏢 PISA × KING", "🎁 Subvenção", "✅ Conciliação",
                       "🚨 Anomalias", "📤 Upload", "🔐 Senha"]
    else:
        tabs_labels = ["📊 Dashboard", "📑 DRE", "💼 Balanço", "💸 DFC",
                       "🏢 PISA × KING", "🎁 Subvenção", "🔐 Senha"]
    
    tabs = st.tabs(tabs_labels)
    
    # ─────────────────────────────────────────────────────────────────────
    # CONTEÚDO DE CADA TAB
    # ─────────────────────────────────────────────────────────────────────
    sem_dados_msg = "📤 Por favor, faça upload do Excel para visualizar os dashboards."
    
    # Dashboard
    with tabs[0]:
        if df is None or len(df) == 0:
            st.info(sem_dados_msg)
        else:
            dashboard_visao_geral(df, periodo_atual, unidade_dre, usar_saldo_bp)
    
    # DRE
    with tabs[1]:
        if df is None or len(df) == 0:
            st.info(sem_dados_msg)
        else:
            dashboard_dre(df, periodo_atual, usar_saldo_bp)
    
    # Balanço
    with tabs[2]:
        if df is None or len(df) == 0:
            st.info(sem_dados_msg)
        else:
            dashboard_bp(df, periodo_atual, usar_saldo_bp)
    
    # DFC
    with tabs[3]:
        if df is None or len(df) == 0:
            st.info(sem_dados_msg)
        else:
            dashboard_dfc(df, periodo_atual)
    
    # PISA × KING
    with tabs[4]:
        if df is None or len(df) == 0:
            st.info(sem_dados_msg)
        else:
            dashboard_unidades(df, periodo_atual)
    
    # Subvenção
    with tabs[5]:
        if df is None or len(df) == 0:
            st.info(sem_dados_msg)
        else:
            dashboard_subvencao(df, periodo_atual)
    
    # Conciliação / Anomalias / Upload / Usuários / Resets / Senha
    indice = 6
    if perfil in ["admin", "controller"]:
        with tabs[indice]:  # Conciliação
            if df is None or len(df) == 0:
                st.info(sem_dados_msg)
            else:
                dashboard_conciliacao(df, periodo_atual, periodo_anterior)
        indice += 1
        with tabs[indice]:  # Anomalias
            if df is None or len(df) == 0:
                st.info(sem_dados_msg)
            else:
                tela_anomalias(df, periodo_atual, periodo_anterior)
        indice += 1
        with tabs[indice]:  # Upload
            tela_upload()
        indice += 1
    
    if perfil == "admin":
        with tabs[indice]:  # Usuários
            tela_usuarios()
        indice += 1
        with tabs[indice]:  # Pedidos de Reset
            tela_pedidos_reset()
        indice += 1
    
    # Trocar senha (sempre o último tab)
    with tabs[indice]:
        tela_trocar_senha()


# ═══════════════════════════════════════════════════════════════════════════════
# PONTO DE ENTRADA
# ═══════════════════════════════════════════════════════════════════════════════
if __name__ == "__main__":
    main()

# ═══════════════════════════════════════════════════════════════════════════════
# FIM DO ARQUIVO — Sistema Contábil LLE v6.1
# ═══════════════════════════════════════════════════════════════════════════════
