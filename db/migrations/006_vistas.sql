-- =============================================================================
-- TPI BASES DE DATOS - UTN FRSR (2026)
-- Proyecto: Bodegas del Atuel
-- Archivo: db/migrations/006_vistas.sql (Etapa 2 - H2: Vistas y Vista Materializada)
-- Responsable: Gonzalo (Onza)
-- =============================================================================

BEGIN;

-- -----------------------------------------------------------------------------
-- 1. VISTA: vw_stock_total_vino
-- Propósito: Muestra para cada vino del catálogo su stock en el depósito
--            central, la suma de su stock en todas las salas de venta y el
--            stock total consolidado de la empresa.
-- Justificación: Es una vista normal (no materializada) porque el stock cambia
--                constantemente con cada venta, ingreso y transferencia, y
--                también sirve de soporte para la consulta avanzada S9.
--                Usa LEFT JOIN y COALESCE para incluir vinos con stock 0.
-- -----------------------------------------------------------------------------
CREATE OR REPLACE VIEW vw_stock_total_vino AS
SELECT
    v.cod_vino,
    v.nombre AS nombre_vino,
    v.tipo AS tipo_vino,
    v.anada,
    v.volumen_ml,
    v.precio,
    b.razon_social AS bodega_elaboradora,
    COALESCE(sd.cantidad, 0) AS stock_deposito,
    COALESCE(SUM(ss.cantidad), 0)::INTEGER AS stock_salas,
    (COALESCE(sd.cantidad, 0) + COALESCE(SUM(ss.cantidad), 0))::INTEGER AS stock_total
FROM vino v
JOIN bodega b
    ON b.cuit = v.cuit_bodega
LEFT JOIN stock_deposito sd
    ON sd.cod_vino = v.cod_vino
LEFT JOIN stock_sala ss
    ON ss.cod_vino = v.cod_vino
GROUP BY
    v.cod_vino,
    v.nombre,
    v.tipo,
    v.anada,
    v.volumen_ml,
    v.precio,
    b.razon_social,
    sd.cantidad;


-- -----------------------------------------------------------------------------
-- 2. VISTA: vw_documentos_pendientes
-- Propósito: Unifica en un solo listado todos los documentos de movimiento de
--            stock (ingresos al depósito central y transferencias hacia salas)
--            que aún no fueron procesados (estado 'en_confeccion' o 'terminado').
-- Justificación: Es una vista normal porque los operadores necesitan consultar
--                en tiempo real qué documentos están listos para procesar.
--                Usa UNION ALL porque ambos conjuntos son disjuntos por su
--                columna discriminadora tipo_documento, evitando el costo de
--                ordenamiento de UNION.
-- -----------------------------------------------------------------------------
CREATE OR REPLACE VIEW vw_documentos_pendientes AS
SELECT
    'INGRESO'::VARCHAR(15) AS tipo_documento,
    i.cod_ingreso AS nro_documento,
    i.fecha AS fecha_documento,
    i.estado,
     ('Bodega: ' || b.razon_social)::VARCHAR(150) AS origen_o_solicitante,
    COALESCE(SUM(ri.cantidad), 0)::INTEGER AS total_botellas
FROM ingreso i
JOIN bodega b
    ON b.cuit = i.cuit_bodega
LEFT JOIN renglon_ingreso ri
    ON ri.cod_ingreso = i.cod_ingreso
WHERE i.estado <> 'procesado'
GROUP BY
    i.cod_ingreso,
    i.fecha,
    i.estado,
    b.razon_social

UNION ALL

SELECT
    'TRANSFERENCIA'::VARCHAR(15)                AS tipo_documento,
    t.nro_transferencia                         AS nro_documento,
    t.fecha_confeccion                          AS fecha_documento,
    t.estado,
    ('Sala #' || s.id_sala || ' - ' || l.nombre)::VARCHAR(150) AS origen_o_solicitante,
    COALESCE(SUM(rt.cantidad), 0)::INTEGER      AS total_botellas
FROM transferencia t
JOIN sala_venta s
    ON s.id_sala = t.id_sala
JOIN localidad l
    ON l.cod_postal = s.cod_postal
LEFT JOIN renglon_transferencia rt
    ON rt.nro_transferencia = t.nro_transferencia
WHERE t.estado <> 'procesado'
GROUP BY
    t.nro_transferencia,
    t.fecha_confeccion,
    t.estado,
    s.id_sala,
    l.nombre;


-- -----------------------------------------------------------------------------
-- 3. VISTA MATERIALIZADA: mv_ventas_mensuales_sala
-- Propósito: Resume mensualmente por cada sala de venta la cantidad de
--            comprobantes emitidos, el total de botellas vendidas y los
--            importes facturados (subtotal bruto, descuento y total neto).
-- Justificación: Se implementa como MATERIALIZED VIEW porque consolida datos
--                históricos sobre tablas de gran volumen (+150.000 comprobantes
--                y +500.000 renglones), acelerando la carga de reportes.
--                Para actualizarla tras cierres operativos se ejecuta:
--                REFRESH MATERIALIZED VIEW CONCURRENTLY mv_ventas_mensuales_sala;
-- -----------------------------------------------------------------------------
DROP MATERIALIZED VIEW IF EXISTS mv_ventas_mensuales_sala;

CREATE MATERIALIZED VIEW mv_ventas_mensuales_sala AS
SELECT
    s.id_sala,
    l.nombre AS localidad,
    DATE_TRUNC('month', c.fecha)::DATE AS periodo_mes,
    COUNT(DISTINCT c.nro_comprobante)::INTEGER AS cantidad_comprobantes,
    COALESCE(SUM(rc.cantidad), 0)::BIGINT AS botellas_vendidas,
    COALESCE(SUM(rc.subtotal), 0.00)::NUMERIC(14,2) AS monto_neto_facturado
FROM comprobante c
JOIN sala_venta s
    ON s.id_sala = c.id_sala
JOIN localidad l
    ON l.cod_postal = s.cod_postal
JOIN renglon_comprobante rc
    ON rc.nro_comprobante = c.nro_comprobante
GROUP BY
    s.id_sala,
    l.nombre,
    DATE_TRUNC('month', c.fecha)::DATE
WITH DATA;

-- Índice único sobre la vista materializada para permitir REFRESH CONCURRENTLY
CREATE UNIQUE INDEX idx_mv_ventas_mensuales_sala_pk
    ON mv_ventas_mensuales_sala (id_sala, periodo_mes);

COMMIT;