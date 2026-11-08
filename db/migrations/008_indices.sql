-- ==============================================================================
-- BLOQUE 1: ÍNDICES SOBRE CLAVES FORÁNEAS (Responsable: Manuel)
-- ==============================================================================

-- Optimiza joins con cliente sobre 150.000 comprobantes (consultas S3, S12, D1, D4)
-- y acelera las verificaciones de integridad referencial (ON DELETE RESTRICT).
CREATE INDEX IF NOT EXISTS idx_fk_comprobante_cliente ON comprobante (id_cliente);

-- Optimiza filtros y joins por vino sobre los 15.004 renglones de transferencia (consulta S4).
CREATE INDEX IF NOT EXISTS idx_fk_renglon_transf_vino ON renglon_transferencia (cod_vino);

-- Optimiza joins y agrupaciones por empresa transportista (consultas I1 y S7).
-- Nota: No se incluye índice sobre renglon_comprobante(cod_vino) para delegarlo al índice INCLUDE.
CREATE INDEX IF NOT EXISTS idx_fk_ingreso_transporte ON ingreso (cod_transporte);