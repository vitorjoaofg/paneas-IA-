-- Popula o campo meta.nomeParteReferencia para processos do TJRJ
UPDATE processos.processos_judiciais
SET dados_completos = jsonb_set(
        dados_completos,
        '{meta}',
        COALESCE(dados_completos->'meta', '{}'::jsonb),
        true
    )
WHERE tribunal = 'TJRJ';

UPDATE processos.processos_judiciais
SET dados_completos = jsonb_set(
        dados_completos,
        '{meta,nomeParteReferencia}',
        to_jsonb('Claro S.A'::text),
        true
    )
WHERE tribunal = 'TJRJ';
