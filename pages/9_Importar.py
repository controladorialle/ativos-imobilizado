"""Página de importação — upload de XLSX cru com detecção de duplicatas."""
import streamlit as st
import pandas as pd
import uuid
from app import sb
from etl.parser_contabil import parse as parse_cont
from etl.parser_compras import parse as parse_comp
from utils.auth import requer_perfil

# Bloqueia acesso: só ADMIN pode importar
requer_perfil(["admin"])

st.title("📥 Importar bases (XLSX cru)")
st.caption("Suba os arquivos exatamente como saem do ERP — o sistema cuida do resto.")

tab_p, tab_c = st.tabs(["1️⃣ Base de Compras", "2️⃣ Base Contábil"])

# ===== ABA 1 — COMPRAS =====
# Importa PRIMEIRO porque alimenta o dicionário de parceiros (CGC + nome)
with tab_p:
    st.markdown(
        "**Importe a base de compras primeiro.** Ela alimenta o dicionário "
        "de parceiros usado depois pelo cruzamento da base contábil."
    )

    arq = st.file_uploader("Arquivo XLSX", type=["xlsx"], key="up_p")
    if arq:
        try:
            df, inv = parse_comp(arq)
        except ValueError as e:
            st.error(str(e))
            st.stop()

        st.success(
            f"{len(df)} linhas válidas | {len(inv)} descartadas "
            "(faltam dados essenciais)"
        )

        c1, c2, c3 = st.columns(3)
        c1.metric("Notas únicas (chave)", df["nota_chave"].nunique())
        c2.metric("Itens de imobilizado", int(df["is_imobilizado"].sum()))
        c3.metric(
            "Valor total",
            f"R$ {df['VLRTOT'].sum():,.0f}".replace(",", ".")
        )

        st.subheader("Preview (20 primeiras linhas)")
        st.dataframe(df.head(20), use_container_width=True)

        if st.button("📤 Gravar no banco", type="primary", key="grava_p"):
            sup = sb()
            imp_id = str(uuid.uuid4())

            # Carrega chaves naturais já existentes para detectar duplicatas
            with st.spinner("Verificando duplicatas..."):
                ja = sup.table("itens_compra").select(
                    "codemp,numnota,cgc_cpf,dtentsai,codprod,vlrtot"
                ).execute().data

                existentes = set()
                for r in ja:
                    existentes.add((
                        r.get("codemp"),
                        r.get("numnota"),
                        r.get("cgc_cpf") or "",
                        str(r.get("dtentsai")) if r.get("dtentsai") else "",
                        r.get("codprod") or 0,
                        float(r.get("vlrtot") or 0)
                    ))

            def chave_nat(row):
                return (
                    row["CODEMP"],
                    row["NUMNOTA"],
                    row["CGC_CPF"] or "",
                    row["DTENTSAI"].isoformat() if row["DTENTSAI"] else "",
                    row["CODPROD"] or 0,
                    float(row["VLRTOT"] or 0)
                )

            dup_mask = df.apply(lambda r: chave_nat(r) in existentes, axis=1)
            df_novas = df[~dup_mask].copy()
            df_dup = df[dup_mask]

            st.info(
                f"🟢 Novas: {len(df_novas)} | "
                f"🟡 Duplicatas bloqueadas: {len(df_dup)}"
            )

            if not df_dup.empty:
                with st.expander("Ver duplicatas bloqueadas"):
                    st.dataframe(
                        df_dup[[
                            "NUMNOTA", "PARCEIRO", "DTENTSAI",
                            "PRODUTO_SERVICO", "VLRTOT"
                        ]],
                        use_container_width=True
                    )

            # Upsert no dicionário de parceiros
            parc = (df_novas[["CODPARC", "PARCEIRO", "CGC_CPF"]]
                    .dropna(subset=["CODPARC", "PARCEIRO"])
                    .drop_duplicates(subset=["CODPARC"]))

            with st.spinner(f"Atualizando dicionário de parceiros ({len(parc)})..."):
                for _, r in parc.iterrows():
                    try:
                        sup.table("parceiros").upsert({
                            "codparc": int(r["CODPARC"]),
                            "nome": r["PARCEIRO"],
                            "cgc_cpf": r["CGC_CPF"]
                        }).execute()
                    except Exception:
                        pass

            # Prepara registros para inserção
            registros = []
            for _, r in df_novas.iterrows():
                registros.append({
                    "importacao_id": imp_id,
                    "nota_chave": r["nota_chave"],
                    "codemp": int(r["CODEMP"]) if pd.notna(r["CODEMP"]) else None,
                    "numnota": int(r["NUMNOTA"]) if pd.notna(r["NUMNOTA"]) else None,
                    "nunota": int(r["NUNOTA"]) if pd.notna(r["NUNOTA"]) else None,
                    "codparc": int(r["CODPARC"]) if pd.notna(r["CODPARC"]) else None,
                    "parceiro": r["PARCEIRO"],
                    "cgc_cpf": r["CGC_CPF"],
                    "dtentsai": r["DTENTSAI"].isoformat() if r["DTENTSAI"] else None,
                    "dtmov": r["DTMOV"].isoformat() if r["DTMOV"] else None,
                    "codtipoper": int(r["CODTIPOPER"]) if pd.notna(r["CODTIPOPER"]) else None,
                    "descroper": r["DESCROPER"],
                    "codprod": int(r["CODPROD"]) if pd.notna(r["CODPROD"]) else None,
                    "produto_servico": r["PRODUTO_SERVICO"],
                    "qtdneg": float(r["QTDNEG"] or 0),
                    "un": r["UN"],
                    "vlrtot": float(r["VLRTOT"] or 0),
                    "seguimento": r["SEGUIMENTO"],
                    "confirmada": bool(r["CONFIRMADA"]),
                    "is_imobilizado": bool(r["is_imobilizado"]),
                })

            # Cria header da importação
            sup.table("importacoes").insert({
                "id": imp_id,
                "tipo": "COMPRAS",
                "nome_arquivo": arq.name,
                "linhas_lidas": int(len(df)),
                "linhas_gravadas": int(len(df_novas)),
                "linhas_bloqueadas": int(len(df_dup)),
                "valor_total": float(df_novas["VLRTOT"].sum()),
                "usuario_email": st.session_state["user"]
            }).execute()

            # Insere itens em lotes
            progresso = st.progress(0.0, "Gravando...")
            BATCH = 300
            total = len(registros)
            for i in range(0, total, BATCH):
                lote = registros[i:i + BATCH]
                try:
                    sup.table("itens_compra").insert(lote).execute()
                except Exception as e:
                    st.warning(f"Falha em lote {i}-{i+BATCH}: {e}")
                progresso.progress(min((i + BATCH) / max(total, 1), 1.0), "Gravando...")

            st.success(f"✅ Concluído. {len(df_novas)} linhas gravadas.")

# ===== ABA 2 — CONTÁBIL =====
with tab_c:
    st.markdown(
        "**Pré-requisito:** a base de compras já deve ter sido importada "
        "para que o dicionário de parceiros esteja populado."
    )

    arq = st.file_uploader("Arquivo XLSX", type=["xlsx"], key="up_c")
    if arq:
        sup = sb()
        parc = pd.DataFrame(
            sup.table("parceiros").select("*").execute().data
        )

        if parc.empty:
            st.warning(
                "Tabela de parceiros vazia. Importe a base de compras primeiro."
            )
            st.stop()

        try:
            df = parse_cont(arq, parc)
        except ValueError as e:
            st.error(str(e))
            st.stop()

        st.success(f"{len(df)} linhas lidas")

        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Total", len(df))
        c2.metric("Match OK", int((df["match_status"] == "OK").sum()))
        c3.metric("Aproximado", int((df["match_status"] == "APROXIMADO").sum()))
        c4.metric(
            "Sem match / Sem NF",
            int(df["match_status"].isin(["SEM_MATCH", "SEM_NF"]).sum())
        )

        st.subheader("Preview (30 primeiras linhas)")
        st.dataframe(
            df[[
                "DTMOV", "NUMDOC", "DESCRCTA", "parceiro_extraido",
                "match_status", "match_score", "DEBITO", "CREDITO"
            ]].head(30),
            use_container_width=True
        )

        if st.button("📤 Gravar no banco", type="primary", key="grava_c"):
            imp_id = str(uuid.uuid4())

            # Verifica duplicatas pela chave natural
            with st.spinner("Verificando duplicatas..."):
                ja = sup.table("lancamentos_contabeis").select(
                    "codemp,dtmov,codctactb,numdoc,numlote,numlanc,complhist"
                ).execute().data

                existentes = set()
                for r in ja:
                    existentes.add((
                        r.get("codemp"),
                        str(r.get("dtmov")) if r.get("dtmov") else "",
                        r.get("codctactb"),
                        r.get("numdoc") or 0,
                        r.get("numlote") or 0,
                        r.get("numlanc") or 0,
                        r.get("complhist") or ""
                    ))

            def chave_nat(row):
                return (
                    row["CODEMP"],
                    row["DTMOV"].isoformat() if row["DTMOV"] else "",
                    row["CODCTACTB"],
                    row["NUMDOC"] or 0,
                    row["NUMLOTE"] or 0,
                    row["NUMLANC"] or 0,
                    row["COMPLHIST"] or ""
                )

            dup_mask = df.apply(lambda r: chave_nat(r) in existentes, axis=1)
            df_novas = df[~dup_mask].copy()
            df_dup = df[dup_mask]

            st.info(
                f"🟢 Novas: {len(df_novas)} | "
                f"🟡 Duplicatas bloqueadas: {len(df_dup)}"
            )

            if not df_dup.empty:
                with st.expander("Ver duplicatas bloqueadas"):
                    st.dataframe(
                        df_dup[[
                            "DTMOV", "NUMDOC", "DESCRCTA", "DEBITO", "CREDITO"
                        ]].head(50),
                        use_container_width=True
                    )

            # Cria header da importação
            sup.table("importacoes").insert({
                "id": imp_id,
                "tipo": "CONTABIL",
                "nome_arquivo": arq.name,
                "linhas_lidas": int(len(df)),
                "linhas_gravadas": int(len(df_novas)),
                "linhas_bloqueadas": int(len(df_dup)),
                "valor_total": float((df_novas["DEBITO"] - df_novas["CREDITO"]).sum()),
                "usuario_email": st.session_state["user"]
            }).execute()

            # Prepara registros, separando os que precisam de revisão
            registros = []
            for _, r in df_novas.iterrows():
                rec = {
                    "importacao_id": imp_id,
                    "nota_chave": r["nota_chave"],
                    "match_status": r["match_status"],
                    "match_score": float(r["match_score"]) if pd.notna(r["match_score"]) else None,
                    "codemp": int(r["CODEMP"]) if pd.notna(r["CODEMP"]) else None,
                    "referencia": r["REFERENCIA"].isoformat() if r["REFERENCIA"] else None,
                    "dtmov": r["DTMOV"].isoformat() if r["DTMOV"] else None,
                    "codctactb": int(r["CODCTACTB"]) if pd.notna(r["CODCTACTB"]) else None,
                    "descrcta": r["DESCRCTA"],
                    "numdoc": int(r["NUMDOC"]) if pd.notna(r["NUMDOC"]) else None,
                    "numlote": int(r["NUMLOTE"]) if pd.notna(r["NUMLOTE"]) else None,
                    "numlanc": int(r["NUMLANC"]) if pd.notna(r["NUMLANC"]) else None,
                    "codcencus": int(r["CODCENCUS"]) if pd.notna(r["CODCENCUS"]) else None,
                    "descrcencus": r["DESCRCENCUS"],
                    "complhist": r["COMPLHIST"],
                    "parceiro_extraido": r["parceiro_extraido"],
                    "codparc_resolvido": int(r["codparc_resolvido"]) if pd.notna(r["codparc_resolvido"]) else None,
                    "cgc_cpf_resolvido": r["cgc_cpf_resolvido"],
                    "debito": float(r["DEBITO"] or 0),
                    "credito": float(r["CREDITO"] or 0),
                    "usado": r["USADO"],
                    "tipolancamento": r["TIPOLANCAMENTO"],
                    "tem_nf": bool(r["tem_nf"]),
                }
                registros.append((rec, r.get("candidatos")))

            progresso = st.progress(0.0, "Gravando...")
            BATCH = 300
            total = len(registros)
            for i in range(0, total, BATCH):
                lote_full = registros[i:i + BATCH]
                lote = [x[0] for x in lote_full]
                try:
                    resp = sup.table("lancamentos_contabeis").insert(lote).execute()
                    # Cria revisões pendentes para os APROXIMADOS com candidatos
                    for inserido, (_, cand) in zip(resp.data, lote_full):
                        if cand:
                            try:
                                sup.table("revisao_pendente").insert({
                                    "lanc_id": inserido["id"],
                                    "parceiro_extraido": inserido.get("parceiro_extraido"),
                                    "candidatos_json": cand,
                                    "status": "PENDENTE"
                                }).execute()
                            except Exception:
                                pass
                except Exception as e:
                    st.warning(f"Falha em lote {i}-{i+BATCH}: {e}")
                progresso.progress(min((i + BATCH) / max(total, 1), 1.0), "Gravando...")

            st.success(f"✅ Concluído. {len(df_novas)} linhas gravadas.")
