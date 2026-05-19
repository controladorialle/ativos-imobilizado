"""Diagnóstico de Secrets e conexão Supabase."""
import streamlit as st

st.set_page_config(page_title="Diagnóstico", layout="wide")
st.title("🔧 Diagnóstico de configuração")

st.header("1. Os Secrets estão chegando?")

try:
    url = st.secrets["supabase"]["url"]
    anon = st.secrets["supabase"]["anon_key"]
    service = st.secrets["supabase"]["service_key"]
    st.success("✅ Os 3 secrets foram lidos com sucesso")

    st.write("**URL configurada:**")
    st.code(url)

    st.write(f"**anon_key tem {len(anon)} caracteres**")
    st.write(f"**Começa com:** `{anon[:20]}...`")
    st.write(f"**Termina com:** `...{anon[-10:]}`")
    st.write(f"**Tem quebra de linha?** {'⚠️ SIM (problema!)' if chr(10) in anon else '✅ NÃO'}")
    st.write(f"**Tem espaço no começo/fim?** {'⚠️ SIM (problema!)' if anon != anon.strip() else '✅ NÃO'}")

    st.write(f"**service_key tem {len(service)} caracteres**")
    st.write(f"**Começa com:** `{service[:20]}...`")
    st.write(f"**Termina com:** `...{service[-10:]}`")
    st.write(f"**Tem quebra de linha?** {'⚠️ SIM (problema!)' if chr(10) in service else '✅ NÃO'}")
    st.write(f"**Tem espaço no começo/fim?** {'⚠️ SIM (problema!)' if service != service.strip() else '✅ NÃO'}")

except Exception as e:
    st.error(f"❌ Erro ao ler secrets: {e}")
    st.stop()

st.header("2. A biblioteca supabase consegue conectar?")
try:
    from supabase import create_client
    cli = create_client(url, anon)
    st.success("✅ Cliente Supabase criado")
except Exception as e:
    st.error(f"❌ Erro ao criar cliente: {e}")
    st.stop()

st.header("3. Consegue consultar uma tabela?")
try:
    resp = cli.table("empresas").select("*").execute()
    st.success(f"✅ Consulta funcionou! Retornou {len(resp.data)} linha(s)")
    st.write("Dados:")
    st.json(resp.data)
except Exception as e:
    st.error(f"❌ Erro na consulta: {e}")
    st.write("**Detalhe completo do erro:**")
    st.code(str(e))

st.header("4. Consegue testar login?")
with st.form("teste"):
    email = st.text_input("E-mail", value="controladoria@grupolle.com.br")
    senha = st.text_input("Senha", type="password")
    ok = st.form_submit_button("Testar login")

if ok:
    try:
        resp = cli.auth.sign_in_with_password({"email": email, "password": senha})
        st.success(f"✅ Login OK! Usuário: {resp.user.email}")
    except Exception as e:
        st.error(f"❌ Falha: {e}")
        st.code(str(e))
