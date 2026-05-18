-- =========================================================
-- Views de análise — Sistema de Ativos Imobilizados
-- Rodar depois do 01_schema.sql
-- =========================================================

-- Saldo por categoria + centro de custo (aquisição - baixa) em contas de CUSTO
create or replace view vw_saldo_categoria as
select
  c.id                                                     as categoria_id,
  c.nome                                                   as categoria,
  l.codemp,
  e.nome                                                   as empresa,
  coalesce(l.codcencus, 0)                                 as codcencus,
  coalesce(l.descrcencus, '(sem centro)')                  as descrcencus,
  count(*) filter (where l.movimentacao = 'AQUISICAO')     as qtd_aquisicoes,
  count(*) filter (where l.movimentacao = 'BAIXA')         as qtd_baixas,
  coalesce(sum(l.debito), 0)                               as total_aquisicoes,
  coalesce(sum(l.credito), 0)                              as total_baixas,
  coalesce(sum(l.debito), 0) - coalesce(sum(l.credito), 0) as saldo
from lancamentos_contabeis l
join plano_contas pc on pc.codctactb = l.codctactb
join categorias_contabeis c on c.id = pc.categoria_id
join empresas e on e.codemp = l.codemp
where pc.tipo = 'CUSTO'
group by c.id, c.nome, l.codemp, e.nome, l.codcencus, l.descrcencus;

-- Movimentação mensal por categoria + centro de custo
create or replace view vw_movimentacao_mensal as
select
  date_trunc('month', l.dtmov)::date     as mes,
  c.nome                                 as categoria,
  l.codemp,
  coalesce(l.codcencus, 0)               as codcencus,
  coalesce(l.descrcencus, '(sem centro)') as descrcencus,
  l.movimentacao,
  count(*)                               as qtd,
  sum(l.valor)                           as total
from lancamentos_contabeis l
join plano_contas pc on pc.codctactb = l.codctactb
join categorias_contabeis c on c.id = pc.categoria_id
where pc.tipo = 'CUSTO'
group by 1, 2, 3, 4, 5, 6;

-- Conciliação por nota_chave (chave hash NUMNOTA+CGC+data+empresa)
create or replace view vw_conciliacao as
with cont as (
  select
    nota_chave, codemp,
    min(numdoc)    as numnota,
    min(complhist) as exemplo_hist,
    sum(case when debito > 0 then debito else -credito end) as valor_contabil
  from lancamentos_contabeis
  where tem_nf = true and nota_chave is not null
  group by nota_chave, codemp
),
comp as (
  select
    nota_chave, codemp,
    min(numnota)  as numnota,
    min(parceiro) as parceiro,
    sum(case when is_imobilizado then vlrtot else 0 end) as valor_imob_compras,
    sum(vlrtot)                                          as valor_total_compras
  from itens_compra
  group by nota_chave, codemp
)
select
  coalesce(cont.nota_chave, comp.nota_chave) as nota_chave,
  coalesce(cont.codemp, comp.codemp)         as codemp,
  coalesce(cont.numnota, comp.numnota)       as numnota,
  comp.parceiro,
  cont.exemplo_hist,
  cont.valor_contabil,
  comp.valor_imob_compras,
  comp.valor_total_compras,
  case
    when cont.nota_chave is null then 'SO_EM_COMPRAS'
    when comp.nota_chave is null then 'SO_EM_CONTABIL'
    when abs(coalesce(cont.valor_contabil, 0) - coalesce(comp.valor_imob_compras, 0)) > 1
         then 'DIVERGENCIA_VALOR'
    else 'OK'
  end as status
from cont
full outer join comp using (nota_chave, codemp);

-- Análise de depreciação acumulada (visão paralela)
create or replace view vw_depreciacao as
select
  c.nome      as categoria,
  l.codemp,
  sum(case when pc.tipo = 'CUSTO' then l.valor *
           (case when l.movimentacao = 'AQUISICAO' then 1 else -1 end)
           else 0 end) as custo_liquido,
  sum(case when pc.tipo = 'DEPRECIACAO' then l.credito - l.debito
           else 0 end) as deprec_acumulada
from lancamentos_contabeis l
join plano_contas pc on pc.codctactb = l.codctactb
join categorias_contabeis c on c.id = pc.categoria_id
where pc.tipo in ('CUSTO', 'DEPRECIACAO')
group by c.nome, l.codemp;
