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


-- ==============================================================================
-- BLOQUE 2: ÍNDICE COMPUESTO E ÍNDICE PARCIAL (Responsable: Gonzalo)
-- ==============================================================================

-- Índice Compuesto B-Tree sobre comprobante (id_sala, fecha).
-- Primero condición de igualdad (id_sala) y luego condición de rango (fecha)
-- para optimizar consultas acotadas por sala y ventana temporal (ej. S3 y S8).
CREATE INDEX IF NOT EXISTS idx_comprobante_sala_fecha
    ON comprobante (id_sala, fecha);

-- Índice Parcial B-Tree sobre transferencia para documentos no procesados.
-- Indexa únicamente la fracción activa ('en_confeccion' y 'terminado'),
-- optimizando la vista vw_documentos_pendientes y la consulta S5.
CREATE INDEX IF NOT EXISTS idx_transferencia_pendientes
    ON transferencia (id_sala, fecha_confeccion)
    WHERE estado <> 'procesado';

-- ==============================================================================
-- BLOQUE 3: ÍNDICES ESPECIALES INCLUDE Y BRIN (Responsable: Santiago)
-- ==============================================================================

-- Índice covering para consultas de ventas agrupadas por vino.
-- INCLUDE permite consultar cantidad y subtotal desde el índice.
CREATE INDEX IF NOT EXISTS idx_rc_vino_include_cant
    ON renglon_comprobante (cod_vino)
    INCLUDE (cantidad, subtotal);

-- Índice BRIN para consultas por rangos de fechas históricas.
-- Aprovecha la correlación entre las fechas y el orden físico de inserción.
CREATE INDEX IF NOT EXISTS idx_comprobante_fecha_brin
    ON comprobante USING brin (fecha);
