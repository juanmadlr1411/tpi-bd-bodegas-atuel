-- =============================================================================
-- TPI BODEGAS DEL ATUEL | ETAPA 5 - DELETE (D1 a D6)
-- Responsable: Santiago | Datos / QA | PostgreSQL 16, SQL nativo
-- =============================================================================
-- EJECUCION: usar psql -X -v ON_ERROR_STOP=1 -f consultas/delete.sql
-- SEGURIDAD: cada ejercicio usa su propia transaccion y termina en ROLLBACK.
-- DOCUMENTACION DE FILAS: psql muestra DELETE N; anotar el N medido en cada
-- ejercicio despues de la prueba, sin inventar cantidades dependientes de la fecha.
-- El dataset de 58 meses (2022-01 a 2026-10) puede dar DELETE 0 en D1 y D4.
-- =============================================================================

-- -----------------------------------------------------------------------------
-- D1. Borrar comprobantes de socios de mas de 5 anios.
-- FK: renglon_comprobante.nro_comprobante -> comprobante.nro_comprobante
--     ON DELETE CASCADE. Los renglones asociados se borran automaticamente.
--     comprobante.id_cliente -> cliente.id_cliente ON DELETE RESTRICT protege
--     la eliminacion del cliente mientras conserve comprobantes, no este DELETE.
-- Filas afectadas: completar tras ejecutar (salida 'DELETE N').
-- -----------------------------------------------------------------------------
BEGIN;

-- Control previo: cabeceras y renglones que serian afectados.
SELECT COUNT(*) AS d1_comprobantes_previos
FROM comprobante co
WHERE co.id_cliente IN (SELECT cs.id_cliente FROM cliente_socio cs)
  AND co.fecha < CURRENT_DATE - INTERVAL '5 years';

SELECT COUNT(*) AS d1_renglones_previos
FROM renglon_comprobante rc
JOIN comprobante co ON co.nro_comprobante = rc.nro_comprobante
WHERE co.id_cliente IN (SELECT cs.id_cliente FROM cliente_socio cs)
  AND co.fecha < CURRENT_DATE - INTERVAL '5 years';

DELETE FROM comprobante co
WHERE co.id_cliente IN (SELECT cs.id_cliente FROM cliente_socio cs)
  AND co.fecha < CURRENT_DATE - INTERVAL '5 years';

-- Control posterior: condicion agotada; no quedan detalles sin cabecera.
SELECT COUNT(*) AS d1_comprobantes_restantes
FROM comprobante co
WHERE co.id_cliente IN (SELECT cs.id_cliente FROM cliente_socio cs)
  AND co.fecha < CURRENT_DATE - INTERVAL '5 years';

SELECT COUNT(*) AS d1_renglones_huerfanos
FROM renglon_comprobante rc
LEFT JOIN comprobante co ON co.nro_comprobante = rc.nro_comprobante
WHERE co.nro_comprobante IS NULL;

ROLLBACK;

-- -----------------------------------------------------------------------------
-- D2. Eliminar cepas sin vino compuesto ni parcela plantada.
-- FK: composicion_vino.id_cepa -> cepa.id_cepa ON DELETE RESTRICT.
-- FK: parcela.id_cepa -> cepa.id_cepa ON DELETE RESTRICT.
-- Ambas relaciones protegen las cepas en uso; solo se borra una cepa sin referencias.
-- Fixture 'Cepa Test H5 QA D2' se crea y se borra dentro de la misma transaccion.
-- Usa id negativo OVERRIDING SYSTEM VALUE para no avanzar la secuencia IDENTITY:
-- ROLLBACK revierte las filas, pero no revierte avances de secuencias.
-- Filas afectadas esperadas en el catalogo original: 1 (fixture); validar 'DELETE N'.
-- -----------------------------------------------------------------------------
BEGIN;

INSERT INTO cepa (id_cepa, nombre, tipo) OVERRIDING SYSTEM VALUE
VALUES (-20261109, 'Cepa Test H5 QA D2', 'tinta');

-- Control previo: la cepa de prueba existe y no tiene referencias.
SELECT c.id_cepa, c.nombre, c.tipo,
       (SELECT COUNT(*) FROM composicion_vino cv WHERE cv.id_cepa = c.id_cepa) AS vinos,
       (SELECT COUNT(*) FROM parcela p WHERE p.id_cepa = c.id_cepa) AS parcelas
FROM cepa c
WHERE c.nombre = 'Cepa Test H5 QA D2';

SELECT COUNT(*) AS d2_cepas_sin_uso_antes
FROM cepa c
WHERE NOT EXISTS (SELECT 1 FROM composicion_vino cv WHERE cv.id_cepa = c.id_cepa)
  AND NOT EXISTS (SELECT 1 FROM parcela p WHERE p.id_cepa = c.id_cepa);

DELETE FROM cepa c
WHERE NOT EXISTS (SELECT 1 FROM composicion_vino cv WHERE cv.id_cepa = c.id_cepa)
  AND NOT EXISTS (SELECT 1 FROM parcela p WHERE p.id_cepa = c.id_cepa);

-- Control posterior: fixture eliminado y ninguna referencia huerfana.
SELECT COUNT(*) AS d2_fixture_restante
FROM cepa WHERE nombre = 'Cepa Test H5 QA D2';

SELECT COUNT(*) AS d2_cepas_sin_uso_despues
FROM cepa c
WHERE NOT EXISTS (SELECT 1 FROM composicion_vino cv WHERE cv.id_cepa = c.id_cepa)
  AND NOT EXISTS (SELECT 1 FROM parcela p WHERE p.id_cepa = c.id_cepa);

SELECT COUNT(*) AS d2_referencias_huerfanas
FROM (
    SELECT cv.id_cepa FROM composicion_vino cv LEFT JOIN cepa c ON c.id_cepa = cv.id_cepa WHERE c.id_cepa IS NULL
    UNION ALL
    SELECT p.id_cepa FROM parcela p LEFT JOIN cepa c ON c.id_cepa = p.id_cepa WHERE c.id_cepa IS NULL
) AS referencias;

ROLLBACK;

-- -----------------------------------------------------------------------------
-- D3. Eliminar empleados con menos de 2 anios de antiguedad de una sala.
-- Parametro verificable: id_sala = 5. Se muestra su localidad antes de borrar.
-- FK: empleado.id_sala -> sala_venta.id_sala ON DELETE RESTRICT; protege la sala
-- frente a su eliminacion, pero no bloquea la baja de sus empleados.
-- Filas afectadas: completar tras ejecutar (salida 'DELETE N').
-- -----------------------------------------------------------------------------
BEGIN;

-- Control previo: localidad de la sala y empleados que cumplen el filtro.
SELECT s.id_sala, l.cod_postal, l.nombre AS localidad
FROM sala_venta s
JOIN localidad l ON l.cod_postal = s.cod_postal
WHERE s.id_sala = 5;

SELECT e.cuit, e.nombre, e.fecha_ingreso,
       fn_antiguedad_anios(e.fecha_ingreso) AS antiguedad_anios
FROM empleado e
WHERE e.id_sala = 5
  AND fn_antiguedad_anios(e.fecha_ingreso) < 2
ORDER BY e.cuit;

DELETE FROM empleado e
WHERE e.id_sala = 5
  AND fn_antiguedad_anios(e.fecha_ingreso) < 2;

-- Control posterior: no quedan empleados del grupo seleccionado.
SELECT COUNT(*) AS d3_empleados_restantes
FROM empleado e
WHERE e.id_sala = 5
  AND fn_antiguedad_anios(e.fecha_ingreso) < 2;

ROLLBACK;

-- -----------------------------------------------------------------------------
-- D4. Eliminar socios antiguos sin compras.
-- FK: cliente_socio.id_cliente -> cliente.id_cliente ON DELETE CASCADE.
-- FK: comprobante.id_cliente -> cliente.id_cliente ON DELETE RESTRICT.
-- La condicion NOT EXISTS evita borrar clientes con comprobantes.
-- Filas afectadas: completar tras ejecutar (salida 'DELETE N').
-- -----------------------------------------------------------------------------
BEGIN;

-- Control previo.
SELECT c.id_cliente, c.nombre_razon_social, c.fecha_alta
FROM cliente c
WHERE c.tipo_cliente = 'socio'
  AND c.fecha_alta < CURRENT_DATE - INTERVAL '5 years'
  AND NOT EXISTS (SELECT 1 FROM comprobante co WHERE co.id_cliente = c.id_cliente)
ORDER BY c.id_cliente;

DELETE FROM cliente c
WHERE c.tipo_cliente = 'socio'
  AND c.fecha_alta < CURRENT_DATE - INTERVAL '5 years'
  AND NOT EXISTS (SELECT 1 FROM comprobante co WHERE co.id_cliente = c.id_cliente);

-- Control posterior: condicion agotada y subtipo sin huerfanos.
SELECT COUNT(*) AS d4_socios_antiguos_sin_compras_restantes
FROM cliente c
WHERE c.tipo_cliente = 'socio'
  AND c.fecha_alta < CURRENT_DATE - INTERVAL '5 years'
  AND NOT EXISTS (SELECT 1 FROM comprobante co WHERE co.id_cliente = c.id_cliente);

SELECT COUNT(*) AS d4_clientes_socio_huerfanos
FROM cliente_socio cs
LEFT JOIN cliente c ON c.id_cliente = cs.id_cliente
WHERE c.id_cliente IS NULL;

ROLLBACK;

-- -----------------------------------------------------------------------------
-- D5. Eliminar ingresos procesados de mas de 365 dias.
-- FK: renglon_ingreso.cod_ingreso -> ingreso.cod_ingreso ON DELETE CASCADE.
-- RN-12: fn_trg_bloquear_renglon permite DELETE del detalle durante la cascada
-- cuando ya no encuentra la cabecera; no permite editar un renglon de un
-- documento procesado mientras este siga existiendo.
-- RN-14: los FK RESTRICT en ingreso impiden borrar transportistas/bodegas con
-- ingresos asociados; no impiden eliminar el propio ingreso.
-- Filas afectadas: completar tras ejecutar (salida 'DELETE N').
-- -----------------------------------------------------------------------------
BEGIN;

-- Control previo: ingresos y renglones afectados.
SELECT COUNT(*) AS d5_ingresos_previos
FROM ingreso i
WHERE i.estado = 'procesado'
  AND i.fecha < CURRENT_DATE - INTERVAL '365 days';

SELECT COUNT(*) AS d5_renglones_previos
FROM renglon_ingreso ri
JOIN ingreso i ON i.cod_ingreso = ri.cod_ingreso
WHERE i.estado = 'procesado'
  AND i.fecha < CURRENT_DATE - INTERVAL '365 days';

DELETE FROM ingreso i
WHERE i.estado = 'procesado'
  AND i.fecha < CURRENT_DATE - INTERVAL '365 days';

-- Control posterior: no quedan ingresos candidatos ni renglones huerfanos.
SELECT COUNT(*) AS d5_ingresos_restantes
FROM ingreso i
WHERE i.estado = 'procesado'
  AND i.fecha < CURRENT_DATE - INTERVAL '365 days';

SELECT COUNT(*) AS d5_renglones_huerfanos
FROM renglon_ingreso ri
LEFT JOIN ingreso i ON i.cod_ingreso = ri.cod_ingreso
WHERE i.cod_ingreso IS NULL;

ROLLBACK;

-- -----------------------------------------------------------------------------
-- D6. Eliminar socios sin compras de una localidad especifica.
-- Parametro: cod_postal = '5501'. Comprobar primero su nombre real en localidad.
-- FK: cliente_socio.id_cliente -> cliente.id_cliente ON DELETE CASCADE.
-- FK: comprobante.id_cliente -> cliente.id_cliente ON DELETE RESTRICT.
-- La condicion NOT EXISTS excluye los clientes con ventas.
-- Filas afectadas: completar tras ejecutar (salida 'DELETE N').
-- -----------------------------------------------------------------------------
BEGIN;

-- Control previo: identificar localidad y contar candidatos.
SELECT cod_postal, nombre, provincia FROM localidad WHERE cod_postal = '5501';

SELECT COUNT(*) AS d6_socios_previos
FROM cliente c
WHERE c.tipo_cliente = 'socio'
  AND c.cod_postal = '5501'
  AND NOT EXISTS (SELECT 1 FROM comprobante co WHERE co.id_cliente = c.id_cliente);

DELETE FROM cliente c
WHERE c.tipo_cliente = 'socio'
  AND c.cod_postal = '5501'
  AND NOT EXISTS (SELECT 1 FROM comprobante co WHERE co.id_cliente = c.id_cliente);

-- Control posterior: condicion agotada y sin registros huerfanos de subtipo.
SELECT COUNT(*) AS d6_socios_restantes
FROM cliente c
WHERE c.tipo_cliente = 'socio'
  AND c.cod_postal = '5501'
  AND NOT EXISTS (SELECT 1 FROM comprobante co WHERE co.id_cliente = c.id_cliente);

SELECT COUNT(*) AS d6_clientes_socio_huerfanos
FROM cliente_socio cs
LEFT JOIN cliente c ON c.id_cliente = cs.id_cliente
WHERE c.id_cliente IS NULL;

ROLLBACK;
