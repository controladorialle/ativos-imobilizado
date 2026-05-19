"""Diagnóstico profundo — mostra exatamente o que o app está vendo."""
import streamlit as st
import requests

st.set_page_config(page_title="Diagnóstico Profundo", layout="wide")
st.title("🔬 Diagnóstico profundo")

# 1. Mostrar URL e início+fim das chaves
st.header("1. O que o Streamlit está lendo dos Secrets")

try:
    url = st.secrets["supabase"]["url"]
    anon = st.secrets["supabase"]["anon_key"]
    service = st.secrets["supabase"]["service_key"]
except Exception as e:
    st.error(f"Erro lendo secrets: {e}")
    st.stop()

st.write("**URL:**")
st.code(url)

st.write("**anon_key:**")
st.write(f"- Total: {len(anon)} caracteres")
st.write(f"- Primeiros 30: `{anon[:30]}`")
st.write(f"- Últimos 20: `{anon[-20:]}`")
st.write(f"- Tem `\\n`? {chr(10) in anon}")
st.write(f"- Tem espaço? {' ' in anon}")

st.write("**service_key:**")
st.write(f"- Total: {len(service)} caracteres")
st.write(f"- Primeiros 30: `{service[:30]}`")
st.write(f"- Últimos 20: `{service[-20:]}`")

# 2. Chamar a API REST do Supabase diretamente (sem biblioteca)
st.header("2. Teste direto da API (sem biblioteca supabase)")

url_clean = url.strip().rstrip("/")
if not url_clean.startswith("https://"):
    url_clean = "https://" + url_clean
if url_clean.startswith("https://https://"):
    url_clean = url_clean.replace("https://https://", "https://")

st.write(f"**URL limpa:** `{url_clean}`")

test_endpoint = f"{url_clean}/rest/v1/empresas?select=*"
headers = {
    "apikey": anon.strip(),
    "Authorization": f"Bearer {anon.strip()}",
}

st.write(f"**Endpoint:** `{test_endpoint}`")

try:
    r = requests.get(test_endpoint, headers=headers, timeout=10)
    st.write(f"**Status HTTP:** {r.status_code}")
    st.write(f"**Resposta:**")
    st.code(r.text[:500])
except Exception as e:
    st.error(f"Erro de rede: {e}")

# 3. Teste com biblioteca supabase
st.header("3. Teste com biblioteca supabase")
try:
    from supabase import create_client
    cli = create_client(url_clean, anon.strip())
    st.success("✅ Cliente criado")
    try:
        resp = cli.table("empresas").select("*").execute()
        st.success(f"✅ Consulta OK: {len(resp.data)} linhas")
        st.json(resp.data)
    except Exception as e2:
        st.error(f"❌ Erro na consulta: {e2}")
        st.code(str(e2))
except Exception as e:
    st.error(f"❌ Erro ao criar cliente: {e}")
    st.code(str(e))
