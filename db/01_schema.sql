-- =========================================================
-- Sistema de Gestão de Ativos Imobilizados — Schema v2
-- Rodar uma única vez no SQL Editor do Supabase
-- =========================================================

create extension if not exists "uuid-ossp";

-- 1) Empresas
create table if not exists empresas (
  codemp        smallint primary key,
  nome          text not null,
  criado_em     timestamptz default now()
);

insert into empresas (codemp, nome) values
  (1, 'Empresa 1'),
  (2, 'Empresa 2')
on conflict (codemp) do nothing;

-- 2) Categorias contábeis (agrupamento amigável)
create table if not exists categorias_contabeis (
  id            serial primary key,
  prefixo       text not null unique,
  nome          text not null,
  ordem         smallint default 0
);

insert into categorias_contabeis (prefixo, nome, ordem) values
  ('1.2.03.01', 'Terrenos', 1),
  ('1.2.03.02', 'Edificações', 2),
  ('1.2.03.03', 'Móveis e Utensílios', 3),
  ('1.2.03.04', 'Máquinas e Equipamentos', 4),
  ('1.2.03.05', 'Equipamentos de Informática', 5),
  ('1.2.03.06', 'Equipamentos de Comunicação', 6),
  ('1.2.03.07', 'Instalações', 7),
  ('1.2.03.08', 'Veículos e Caminhões', 8),
  ('1.2.03.09', 'Softwares', 9),
  ('1.2.03.15', 'Benfeitorias', 10),
  ('1.2.03.16', 'Imobilizado em Andamento', 11)
on conflict (prefixo) do nothing;

-- 3) Plano de contas
create table if not exists plano_contas (
  codctactb     bigint primary key,
  ctactb        text not null,
  descrcta      text not null,
  categoria_id  int references categorias_contabeis(id),
  tipo          text not null check (tipo in ('CUSTO','DEPRECIACAO','AMORTIZACAO','CIAP'))
);

-- 4) Parceiros (dicionário) — alimentado pela base de compras
create table if not exists parceiros (
  codparc       int primary key,
  nome          text not null,
  cgc_cpf       text,
  nome_norm     text generated always as (lower(trim(nome))) stored
);
create index if not exists idx_parc_cgc on parceiros(cgc_cpf);
create index if not exists idx_parc_nome_norm on parceiros(nome_norm);

-- 5) Importações (cabeçalho)
create table if not exists importacoes (
  id                 uuid primary key default uuid_generate_v4(),
  tipo               text check (tipo in ('CONTABIL','COMPRAS')),
  nome_arquivo       text,
  linhas_lidas       int,
  linhas_gravadas    int,
  linhas_bloqueadas  int,
  valor_total        numeric(18,2),
  usuario_email      text,
  criado_em          timestamptz default now()
);

-- 6) Lançamentos contábeis — cada linha da base1
create table if not exists lancamentos_contabeis (
  id                  bigserial primary key,
  importacao_id       uuid references importacoes(id),
  nota_chave          char(16),
  match_status        text check (match_status in ('OK','APROXIMADO','SEM_MATCH','SEM_NF')),
  match_score         numeric(4,3),
  codemp              smallint references empresas(codemp),
  referencia          date,
  dtmov               date not null,
  codctactb           bigint references plano_contas(codctactb),
  descrcta            text,
  numdoc              bigint,
  numlote             int,
  numlanc             int,
  codcencus           int,
  descrcencus         text,
  complhist           text,
  parceiro_extraido   text,
  codparc_resolvido   int references parceiros(codparc),
  cgc_cpf_resolvido   text,
  debito              numeric(18,2) default 0,
  credito             numeric(18,2) default 0,
  usado               text,
  tipolancamento      text,
  tem_nf              boolean default true,
  movimentacao        text generated always as (
    case when debito > 0 then 'AQUISICAO' else 'BAIXA' end
  ) stored,
  valor               numeric(18,2) generated always as (
    case when debito > 0 then debito else credito end
  ) stored,
  criado_em           timestamptz default now()
);

-- Chave natural para impedir duplicatas reais
create unique index if not exists uq_lanc_natural on lancamentos_contabeis
  (codemp, dtmov, codctactb, coalesce(numdoc, 0),
   coalesce(numlote, 0), coalesce(numlanc, 0), coalesce(complhist, ''));

create index if not exists idx_lanc_chave on lancamentos_contabeis(nota_chave);
create index if not exists idx_lanc_numdoc on lancamentos_contabeis(numdoc);
create index if not exists idx_lanc_codctactb on lancamentos_contabeis(codctactb);
create index if not exists idx_lanc_dtmov on lancamentos_contabeis(dtmov);

-- 7) Itens de compra — cada linha da base2
create table if not exists itens_compra (
  id              bigserial primary key,
  importacao_id   uuid references importacoes(id),
  nota_chave      char(16) not null,
  codemp          smallint references empresas(codemp),
  numnota         bigint not null,
  nunota          bigint,
  codparc         int,
  parceiro        text,
  cgc_cpf         text,
  dtentsai        date,
  dtmov           date,
  codtipoper      int,
  descroper       text,
  codprod         int,
  produto_servico text,
  qtdneg          numeric(18,3),
  un              text,
  vlrtot          numeric(18,2),
  seguimento      text,
  confirmada      boolean,
  is_imobilizado  boolean default false,
  criado_em       timestamptz default now()
);

create unique index if not exists uq_item_natural on itens_compra
  (codemp, numnota, coalesce(cgc_cpf, ''), coalesce(dtentsai, '1900-01-01'::date),
   coalesce(codprod, 0), coalesce(vlrtot, 0));

create index if not exists idx_itens_chave on itens_compra(nota_chave);
create index if not exists idx_itens_numnota on itens_compra(numnota);
create index if not exists idx_itens_imob on itens_compra(is_imobilizado);

-- 8) Transferências de obra (rastreio obra -> ativo final)
create table if not exists transferencias_obra (
  id                  bigserial primary key,
  data_transferencia  date,
  origem_lanc_id      bigint references lancamentos_contabeis(id),
  destino_lanc_id     bigint references lancamentos_contabeis(id),
  valor               numeric(18,2),
  descricao           text,
  criado_em           timestamptz default now()
);

-- 9) Log de duplicatas bloqueadas
create table if not exists importacoes_log (
  id              bigserial primary key,
  importacao_id   uuid references importacoes(id),
  motivo          text,
  payload_json    jsonb,
  criado_em       timestamptz default now()
);

-- 10) Fila de revisão manual de matches
create table if not exists revisao_pendente (
  id                  bigserial primary key,
  lanc_id             bigint references lancamentos_contabeis(id) on delete cascade,
  parceiro_extraido   text,
  candidatos_json     jsonb,
  status              text default 'PENDENTE' check (status in ('PENDENTE','RESOLVIDO','IGNORADO')),
  resolvido_para      int references parceiros(codparc),
  usuario_email       text,
  criado_em           timestamptz default now(),
  resolvido_em        timestamptz
);

-- 11) Movimentações manuais (registradas pela tela operacional)
create table if not exists movimentacoes_manuais (
  id              bigserial primary key,
  tipo            text check (tipo in ('AQUISICAO','BAIXA')),
  codemp          smallint references empresas(codemp),
  codctactb       bigint references plano_contas(codctactb),
  numdoc          bigint,
  parceiro        text,
  valor           numeric(18,2) not null,
  data            date not null,
  descricao       text,
  usuario_email   text,
  criado_em       timestamptz default now()
);
