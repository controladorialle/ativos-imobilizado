# Sistema de Gestão de Ativos Imobilizados

Sistema online para gestão de ativos imobilizados — aquisições e baixas — com cruzamento automático entre base contábil e base de compras.

## Stack

- **GitHub** — versionamento de código
- **Supabase** — banco de dados (PostgreSQL) + autenticação
- **Streamlit** — interface web (deploy no Streamlit Community Cloud)

## Funcionalidades

- Upload de XLSX **cru** (sem pré-tratamento) — o app faz toda a limpeza
- Diferenciação robusta de NFs duplicadas via hash SHA-256 (NUMNOTA + CGC + data + empresa)
- Extração automática do nome do fornecedor a partir do COMPLHIST contábil
- Matching por similaridade quando o nome não bate exatamente
- Tela de revisão manual para matches aproximados
- Bloqueio de duplicatas em re-importações
- Dashboards de saldo, aquisições e movimentação
- Conciliação contábil x compras
- Análise paralela de depreciação acumulada
- Lançamentos manuais (aquisição/baixa)

## Estrutura

```
.
├── app.py                    # Entry point + login
├── requirements.txt
├── pages/
│   ├── 1_Importar.py
│   ├── 2_Dashboard.py
│   ├── 3_Conciliacao.py
│   ├── 4_Revisao_Manual.py
│   ├── 5_Operacional.py
│   └── 6_Depreciacao.py
├── etl/
│   ├── __init__.py
│   ├── limpeza.py
│   ├── chave.py
│   ├── categorias.py
│   ├── parser_contabil.py
│   ├── parser_compras.py
│   └── duplicatas.py
├── db/
│   ├── 01_schema.sql
│   ├── 02_views.sql
│   ├── 03_rls.sql
│   └── 04_plano_contas.sql
└── .streamlit/
    └── secrets.toml.example
```

## Início rápido

Veja o documento `passo_a_passo_ativos_imobilizados.docx` (fornecido separadamente) para o passo a passo completo.

1. Crie projeto no Supabase
2. Rode os SQLs em `db/` na ordem (01, 02, 03, 04)
3. Crie usuário em Authentication
4. Faça push deste repositório para o GitHub
5. Conecte ao Streamlit Community Cloud
6. Configure `secrets.toml` com URL + anon key do Supabase
7. Deploy

## Configuração local (opcional)

```bash
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate
pip install -r requirements.txt
cp .streamlit/secrets.toml.example .streamlit/secrets.toml
# Edite secrets.toml com suas credenciais
streamlit run app.py
```
