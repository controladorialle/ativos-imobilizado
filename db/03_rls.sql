-- =========================================================
-- Row Level Security (RLS) — Sistema de Ativos Imobilizados
-- Rodar depois do 02_views.sql
-- Política: qualquer usuário AUTENTICADO tem acesso total.
-- =========================================================

alter table empresas              enable row level security;
alter table categorias_contabeis  enable row level security;
alter table plano_contas          enable row level security;
alter table parceiros             enable row level security;
alter table lancamentos_contabeis enable row level security;
alter table itens_compra          enable row level security;
alter table transferencias_obra   enable row level security;
alter table importacoes           enable row level security;
alter table importacoes_log       enable row level security;
alter table revisao_pendente      enable row level security;
alter table movimentacoes_manuais enable row level security;

-- Aplica policies de read/write para 'authenticated' em todas as tabelas
do $$
declare t text;
begin
  for t in
    select tablename from pg_tables where schemaname = 'public'
  loop
    -- Remove se já existirem (idempotente)
    execute format('drop policy if exists "auth_read_%s" on %I;', t, t);
    execute format('drop policy if exists "auth_write_%s" on %I;', t, t);

    execute format(
      'create policy "auth_read_%s" on %I '
      'for select to authenticated using (true);',
      t, t
    );
    execute format(
      'create policy "auth_write_%s" on %I '
      'for all to authenticated using (true) with check (true);',
      t, t
    );
  end loop;
end $$;
