-- =============================================================================
-- TPI BASES DE DATOS - UTN FRSR (2026)
-- Proyecto: Bodegas del Atuel
-- Archivo: db/seed/03_complemento_datos_h5.sql (Etapa 5 - Preparación de datos)
-- Responsable: Gonzalo
-- =============================================================================
-- PROPÓSITO
--   El volcado histórico compartido (58 meses) llegó con cuatro tablas vacías:
--   permiso_exportacion, lote_uva, analisis_calidad y auditoria_precio. Esto
--   incumple el mínimo de H3 («todas las tablas deben tener al menos una fila»)
--   y deja sin datos a consignas de H5 (U6, S10). Además, ningún empleado supera
--   los 5 años de antigüedad, por lo que U2 no afectaría filas.
--
--   Este script completa esos huecos de forma:
--     * DETERMINÍSTICA: no usa random(); todos los valores salen de aritmética
--       sobre las claves, así que dos ejecuciones producen los mismos datos.
--     * IDEMPOTENTE: ON CONFLICT DO NOTHING / NOT EXISTS. Correrlo dos veces no
--       duplica filas.
--     * CON LAS REGLAS ACTIVAS: no se deshabilita ningún trigger. RN-07 (fechas
--       de permisos) y los CHECK de RN-15 validan cada fila insertada.
--     * SIN FECHAS RELATIVAS: se usan fechas fijas (tope 2026-10-31, fin del
--       historial) para que el resultado no dependa del día en que se ejecuta.
--
--   auditoria_precio NO se completa a mano: la llena el trigger RN-13 cuando se
--   ejecutan U3/U5 (y por diseño no debe cargarse manualmente).
--
-- USO (desde la raíz del repo, con el contenedor levantado):
--   docker exec -i bodegas_atuel_db psql -U admin_atuel -d bodegas_atuel \
--       -v ON_ERROR_STOP=1 < db/seed/03_complemento_datos_h5.sql
-- =============================================================================

BEGIN;

-- -----------------------------------------------------------------------------
-- 1. PERMISOS DE EXPORTACIÓN (RN-07) — habilita U6
--    Cantidad de permisos por exportador (determinística por id_cliente):
--      id % 20 = 0  -> 5 permisos
--      id % 20 = 10 -> 4 permisos
--      resto        -> 1 a 3 permisos (1 + id % 3)
--    Emisión: fecha_alta del cliente + 45 días por cada permiso adicional.
--    Vencimiento: emisión + 730 días (siempre posterior -> cumple RN-07).
--    Solo se generan permisos emitidos hasta 2026-10-31 (fin del historial).
-- -----------------------------------------------------------------------------
INSERT INTO permiso_exportacion (cod_permiso, id_cliente, fecha_emision, fecha_vencimiento)
SELECT
    format('PERM-EXP-%s-%s', lpad(ce.id_cliente::TEXT, 5, '0'), lpad(k::TEXT, 2, '0')),
    ce.id_cliente,
    c.fecha_alta + (k - 1) * 45,
    c.fecha_alta + (k - 1) * 45 + 730
FROM cliente_exportador ce
JOIN cliente c
    ON c.id_cliente = ce.id_cliente
CROSS JOIN LATERAL generate_series(
    1,
    CASE
        WHEN ce.id_cliente % 20 = 0  THEN 5
        WHEN ce.id_cliente % 20 = 10 THEN 4
        ELSE 1 + ce.id_cliente % 3
    END
) AS k
WHERE c.fecha_alta + (k - 1) * 45 <= DATE '2026-10-31'
ON CONFLICT (cod_permiso) DO NOTHING;


-- -----------------------------------------------------------------------------
-- 2. LOTES DE UVA (RN-04) — habilita S10
--    Una cosecha por parcela y campaña (2022 a 2026), respetando el
--    UNIQUE (id_finca, nro_parcela, campania). Cosecha entre febrero y abril.
--    Kilos entre 4.500 y 22.499 para que el rendimiento kg/ha varíe entre
--    parcelas de una misma finca. La bodega destino rota sobre las existentes.
-- -----------------------------------------------------------------------------
INSERT INTO lote_uva (id_finca, nro_parcela, campania, fecha_cosecha, kilos, cuit_bodega)
SELECT
    p.id_finca,
    p.nro_parcela,
    camp,
    make_date(camp,
              2 + (p.id_finca + p.nro_parcela + camp) % 3,
              1 + (p.id_finca * 7 + p.nro_parcela * 3 + camp) % 28),
    4500 + ((p.id_finca * 37 + p.nro_parcela * 101 + camp * 13) % 18000),
    b.cuits[1 + (p.id_finca + p.nro_parcela + camp) % array_length(b.cuits, 1)]
FROM parcela p
CROSS JOIN generate_series(2022, 2026) AS camp
CROSS JOIN (SELECT array_agg(cuit ORDER BY cuit) AS cuits FROM bodega) AS b
WHERE p.anio_plantacion <= camp
ON CONFLICT (id_finca, nro_parcela, campania) DO NOTHING;


-- -----------------------------------------------------------------------------
-- 3. ANÁLISIS DE CALIDAD — dos análisis por lote (día de cosecha y +2 días)
--    Brix 21,0–26,4 · pH 3,20–3,85 · acidez 4,50–7,49 g/L (rangos enológicos).
--    Solo se insertan para lotes que todavía no tienen análisis (idempotente).
-- -----------------------------------------------------------------------------
INSERT INTO analisis_calidad (nro_lote, fecha, grado_brix, ph, acidez_total)
SELECT
    l.nro_lote,
    l.fecha_cosecha + d,
    21.00 + ((l.nro_lote * 7 + d) % 55) / 10.0,
    3.20 + ((l.nro_lote * 3 + d) % 66) / 100.0,
    4.50 + ((l.nro_lote * 11 + d) % 300) / 100.0
FROM lote_uva l
CROSS JOIN (VALUES (0), (2)) AS dias(d)
WHERE NOT EXISTS (
    SELECT 1 FROM analisis_calidad a WHERE a.nro_lote = l.nro_lote
);


-- -----------------------------------------------------------------------------
-- 4. EMPLEADOS CON MÁS DE 5 AÑOS DE ANTIGÜEDAD — habilita U2
--    El historial de empleados empieza en 2021-12, por lo que nadie supera los
--    5 años. Se agregan tres empleados históricos con CUIT ficticio válido para
--    el dominio cuit_dom (11 dígitos).
-- -----------------------------------------------------------------------------
INSERT INTO empleado (cuit, nombre, fecha_ingreso, salario, id_sala)
SELECT v.cuit, v.nombre, v.fecha_ingreso, v.salario, v.id_sala
FROM (VALUES
    ('20150302011', 'Ernesto Fuentes (histórico)', DATE '2015-03-02', 1150000.00, 1),
    ('27180801022', 'Graciela Ortiz (histórico)',  DATE '2018-08-01', 1080000.00, 3),
    ('23200615033', 'Ramiro Quiroga (histórico)',  DATE '2020-06-15',  990000.00, 6)
) AS v(cuit, nombre, fecha_ingreso, salario, id_sala)
WHERE EXISTS (SELECT 1 FROM sala_venta s WHERE s.id_sala = v.id_sala)
ON CONFLICT (cuit) DO NOTHING;


-- -----------------------------------------------------------------------------
-- 5. CONTROL POSTERIOR (debe mostrar filas > 0 en las cuatro tablas)
-- -----------------------------------------------------------------------------
SELECT 'permiso_exportacion' AS tabla, COUNT(*) AS filas FROM permiso_exportacion
UNION ALL
SELECT 'exportadores con > 3 permisos', COUNT(*)
FROM (SELECT id_cliente FROM permiso_exportacion
      GROUP BY id_cliente HAVING COUNT(*) > 3) x
UNION ALL
SELECT 'lote_uva', COUNT(*) FROM lote_uva
UNION ALL
SELECT 'analisis_calidad', COUNT(*) FROM analisis_calidad
UNION ALL
SELECT 'empleados con > 5 años', COUNT(*)
FROM empleado WHERE fecha_ingreso < CURRENT_DATE - INTERVAL '5 years';

COMMIT;

ANALYZE permiso_exportacion;
ANALYZE lote_uva;
ANALYZE analisis_calidad;
ANALYZE empleado;

