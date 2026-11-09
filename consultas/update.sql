-- =============================================================================
-- TPI BASES DE DATOS - UTN FRSR (2026)
-- Proyecto: Bodegas del Atuel
-- Archivo: consultas/update.sql (Etapa 5 - Modificación de Datos)
-- Responsable: Gonzalo (Onza)
-- =============================================================================
-- PAUTAS DE LA CÁTEDRA (Sección 7 - Etapa 5 y Criterios de Aceptación):
--   1. Todas las sentencias de modificación se prueban DENTRO DE UNA TRANSACCIÓN:
--      BEGIN; -> consulta de control previa -> UPDATE -> consulta de control
--      posterior -> ROLLBACK;
--   2. Se documentan las filas afectadas observadas en el dataset histórico.
--   3. Parámetros concretos del dataset indicados con claridad para facilitar
--      su cambio si se requiere.
--   4. Documentación de triggers disparados y constraints involucradas.
-- =============================================================================


-- =============================================================================
-- U1: Recalcular el total de todos los comprobantes aplicando el descuento
--     que corresponde al tipo de cliente.
-- =============================================================================
-- ESTRATEGIA:
--   Por regla RN-08 y RN-06, el descuento del comprobante se calcula a nivel de
--   cada renglón según el descuento vigente del cliente asociado a la cabecera.
--   La actualización se divide en dos fases lógicas dentro de la misma transacción:
--     Paso 1: Sincronizar 'renglon_comprobante.descuento' con el porcentaje de
--             descuento del cliente asociado al comprobante ('cliente.porcentaje_descuento')
--             usando 'fn_descuento_cliente(co.id_cliente)'. Al modificar el renglón,
--             el trigger 'trg_actualizar_totales_comprobante' (RN-08) se dispara
--             automáticamente y recalcula 'subtotal', 'descuento' y 'total' en la cabecera.
--     Paso 2: Sentencia de resguardo sobre 'comprobante' usando una CTE con
--             'fn_total_comprobante(nro)' para garantizar consistencia atómica
--             incluso en comprobantes que no hayan tenido renglones modificados.
-- TRIGGERS DISPARADOS:
--   - 'trg_validar_stock_venta' (BEFORE UPDATE en renglon_comprobante): recalcula NEW.subtotal.
--   - 'trg_actualizar_totales_comprobante' (AFTER UPDATE en renglon_comprobante): actualiza
--     automáticamente subtotal, descuento y total en la cabecera de comprobante.
-- =============================================================================

BEGIN;

-- 1. Control previo: comprobantes con total inconsistente frente a fn_total_comprobante
SELECT COUNT(*) AS comprobantes_inconsistentes_antes
FROM comprobante co
WHERE co.total <> fn_total_comprobante(co.nro_comprobante);

-- 2. Sentencia UPDATE (Paso 1: renglones desalineados con el descuento del cliente)
UPDATE renglon_comprobante rc
SET descuento = c.porcentaje_descuento
FROM comprobante co
JOIN cliente c ON c.id_cliente = co.id_cliente
WHERE co.nro_comprobante = rc.nro_comprobante
  AND rc.descuento IS DISTINCT FROM c.porcentaje_descuento;

-- 3. Sentencia UPDATE (Paso 2: recálculo explícito de cabeceras de comprobante)
WITH totales_calculados AS (
    SELECT
        r.nro_comprobante,
        SUM(r.cantidad * r.precio_unitario)::NUMERIC(14,2) AS subtotal_bruto,
        fn_total_comprobante(r.nro_comprobante) AS total_neto
    FROM renglon_comprobante r
    GROUP BY r.nro_comprobante
)
UPDATE comprobante co
SET subtotal  = tc.subtotal_bruto,
    descuento = tc.subtotal_bruto - tc.total_neto,
    total     = tc.total_neto
FROM totales_calculados tc
WHERE tc.nro_comprobante = co.nro_comprobante
  AND (co.subtotal, co.descuento, co.total) IS DISTINCT FROM
      (tc.subtotal_bruto, tc.subtotal_bruto - tc.total_neto, tc.total_neto);

-- 4. Control posterior: verificar que 0 comprobantes presenten discrepancias
SELECT COUNT(*) AS comprobantes_inconsistentes_despues
FROM comprobante co
WHERE co.total <> fn_total_comprobante(co.nro_comprobante);

-- FILAS AFECTADAS:
--   En el dataset inicial íntegro: 0 renglones desalineados.
--   Si se aplica U6 previamente (suba a 35% a exportadores con >3 permisos):
--   se actualizan 20.160 renglones y el trigger sincroniza sus cabeceras.

ROLLBACK;


-- =============================================================================
-- U2: Aumentar un 20 % el salario de los empleados con más de 5 años de antigüedad.
-- =============================================================================
-- ESTRATEGIA:
--   Se utiliza la función de la cátedra 'fn_antiguedad_anios(fecha_ingreso)' o la
--   condición 'fecha_ingreso < CURRENT_DATE - INTERVAL ''5 years''' para identificar
--   los empleados con más de 5 años trabajados. Se actualiza el salario multiplicando
--   por 1.20 y redondeando a dos decimales con ROUND(..., 2).
-- CONSTRAINTS Y VALIDACIONES:
--   - 'chk_empleado_salario' (salario > 0): se preserva estrictamente positiva.
--   - Tipo de dato: NUMERIC(12,2).
-- =============================================================================

BEGIN;

-- 1. Control previo: listar empleados con más de 5 años de antigüedad y salario actual
SELECT
    cuit,
    nombre,
    fecha_ingreso,
    salario AS salario_anterior,
    fn_antiguedad_anios(fecha_ingreso) AS antiguedad_anios
FROM empleado
WHERE fecha_ingreso < CURRENT_DATE - INTERVAL '5 years'
ORDER BY fecha_ingreso ASC;

-- 2. Sentencia UPDATE
UPDATE empleado
SET salario = ROUND(salario * 1.20, 2)
WHERE fecha_ingreso < CURRENT_DATE - INTERVAL '5 years';

-- 3. Control posterior: verificar incremento del 20% y salario resultante
SELECT
    cuit,
    nombre,
    fecha_ingreso,
    salario AS salario_nuevo,
    fn_antiguedad_anios(fecha_ingreso) AS antiguedad_anios
FROM empleado
WHERE fecha_ingreso < CURRENT_DATE - INTERVAL '5 years'
ORDER BY fecha_ingreso ASC;

-- FILAS AFECTADAS: 3 empleados históricos (confeccionados en 03_complemento_datos_h5.sql).
--   - Ernesto Fuentes (antigüedad 11 años): $1.150.000,00 -> $1.380.000,00
--   - Graciela Ortiz  (antigüedad 8 años):  $1.080.000,00 -> $1.296.000,00
--   - Ramiro Quiroga  (antigüedad 6 años):    $990.000,00 -> $1.188.000,00

ROLLBACK;


-- =============================================================================
-- U3: Incrementar un 13 % el precio de los vinos elaborados por una bodega determinada.
-- =============================================================================
-- PARÁMETRO ELEGIDO DEL DATASET:
--   Bodega: 'Bodega Torres, Perez and Gonzalez' (CUIT: '20635307455').
--   Posee 6 vinos en catálogo. Para cambiar la bodega, modificar el CUIT en el WHERE.
-- ESTRATEGIA:
--   UPDATE directo sobre la tabla 'vino' filtrando por 'cuit_bodega'. Se calcula
--   ROUND(precio * 1.13, 2) para preservar tipo NUMERIC(12,2) y RN-01/RN-15 (precio > 0).
-- TRIGGERS DISPARADOS (Regla RN-13):
--   - 'trg_auditar_cambio_precio' (AFTER UPDATE OF precio ON vino):
--     Registra automáticamente en 'auditoria_precio' el precio anterior,
--     precio nuevo, timestamp actual y el usuario de base de datos ejecutante.
-- =============================================================================

BEGIN;

-- 1. Control previo: precios actuales de los vinos de la bodega y conteo de auditoría
SELECT cod_vino, nombre, anada, volumen_ml, precio AS precio_actual
FROM vino
WHERE cuit_bodega = '20635307455'
ORDER BY cod_vino;

SELECT COUNT(*) AS total_auditorias_previas FROM auditoria_precio;

-- 2. Sentencia UPDATE (+13% sobre vinos de la bodega seleccionada)
UPDATE vino
SET precio = ROUND(precio * 1.13, 2)
WHERE cuit_bodega = '20635307455';

-- 3. Control posterior: precios actualizados y verificación del trigger de auditoría (RN-13)
SELECT cod_vino, nombre, anada, volumen_ml, precio AS precio_nuevo
FROM vino
WHERE cuit_bodega = '20635307455'
ORDER BY cod_vino;

SELECT
    id_auditoria,
    cod_vino,
    precio_anterior,
    precio_nuevo,
    fecha_hora,
    usuario
FROM auditoria_precio
WHERE cod_vino IN (SELECT cod_vino FROM vino WHERE cuit_bodega = '20635307455')
ORDER BY id_auditoria DESC;

-- FILAS AFECTADAS: 6 vinos modificados; 6 filas insertadas automáticamente por el trigger RN-13.

ROLLBACK;


-- =============================================================================
-- U4: En las salas cuyo día de cierre es lunes cambiarlo a miércoles y viceversa,
--     en una sola sentencia.
-- =============================================================================
-- ESTRATEGIA:
--   Uso de expresión condicional CASE dentro de una única sentencia UPDATE.
--   Como la columna 'dia_cierre' es de tipo ENUM 'dia_semana', se realiza el
--   cast explícito '::dia_semana' para garantizar seguridad de tipos y evitar
--   estados intermedios inconsistentes.
-- =============================================================================

BEGIN;

-- 1. Control previo: salas que cierran lunes o miércoles
SELECT id_sala, calle, numero, dia_cierre, cod_postal
FROM sala_venta
WHERE dia_cierre IN ('lunes', 'miercoles')
ORDER BY id_sala;

-- 2. Sentencia UPDATE en una sola instrucción
UPDATE sala_venta
SET dia_cierre = CASE dia_cierre
    WHEN 'lunes'::dia_semana     THEN 'miercoles'::dia_semana
    WHEN 'miercoles'::dia_semana THEN 'lunes'::dia_semana
END
WHERE dia_cierre IN ('lunes', 'miercoles');

-- 3. Control posterior: verificar el intercambio simétrico de días de cierre
SELECT id_sala, calle, numero, dia_cierre, cod_postal
FROM sala_venta
WHERE dia_cierre IN ('lunes', 'miercoles')
ORDER BY id_sala;

-- FILAS AFECTADAS: 2 salas (sala 3 y sala 4, que cerraban los lunes, pasan a miércoles).

ROLLBACK;


-- =============================================================================
-- U5: Aplicar un 15 % de descuento de precio a los 10 vinos menos vendidos de toda la red.
-- =============================================================================
-- ESTRATEGIA:
--   1. Se utiliza una CTE ('WITH menos_vendidos AS (...)') que agrupa los renglones
--      de comprobante de toda la red sumando la cantidad total vendida por vino.
--      Se utiliza 'LEFT JOIN' sobre 'vino' con 'COALESCE(SUM(rc.cantidad), 0)' para
--      incluir vinos sin ventas, y se desempata por 'cod_vino ASC' con 'LIMIT 10'.
--   2. Se une la CTE en el UPDATE ('UPDATE vino v SET precio = ROUND(v.precio * 0.85, 2) FROM menos_vendidos mv WHERE v.cod_vino = mv.cod_vino').
-- TRIGGERS DISPARADOS:
--   - 'trg_auditar_cambio_precio' (RN-13): audita automáticamente la baja del 15%
--     en 'auditoria_precio' para los 10 vinos identificados.
-- =============================================================================

BEGIN;

-- 1. Control previo: listar los 10 vinos menos vendidos con su precio actual y botellas vendidas
WITH menos_vendidos AS (
    SELECT
        v.cod_vino,
        v.nombre,
        v.precio,
        COALESCE(SUM(rc.cantidad), 0) AS botellas_vendidas
    FROM vino v
    LEFT JOIN renglon_comprobante rc ON rc.cod_vino = v.cod_vino
    GROUP BY v.cod_vino, v.nombre, v.precio
    ORDER BY botellas_vendidas ASC, v.cod_vino ASC
    LIMIT 10
)
SELECT * FROM menos_vendidos;

-- 2. Sentencia UPDATE
WITH menos_vendidos AS (
    SELECT v.cod_vino
    FROM vino v
    LEFT JOIN renglon_comprobante rc ON rc.cod_vino = v.cod_vino
    GROUP BY v.cod_vino
    ORDER BY COALESCE(SUM(rc.cantidad), 0) ASC, v.cod_vino ASC
    LIMIT 10
)
UPDATE vino v
SET precio = ROUND(v.precio * 0.85, 2)
FROM menos_vendidos mv
WHERE v.cod_vino = mv.cod_vino;

-- 3. Control posterior: verificar precios reducidos y auditoría automática (RN-13)
SELECT
    a.id_auditoria,
    a.cod_vino,
    v.nombre,
    a.precio_anterior,
    a.precio_nuevo,
    ROUND((1 - a.precio_nuevo / a.precio_anterior) * 100, 2) AS pct_descuento_realizado,
    a.fecha_hora,
    a.usuario
FROM auditoria_precio a
JOIN vino v ON v.cod_vino = a.cod_vino
ORDER BY a.id_auditoria DESC
LIMIT 10;

-- FILAS AFECTADAS: 10 vinos actualizados; 10 registros automáticos en auditoria_precio.

ROLLBACK;


-- =============================================================================
-- U6: A los exportadores con más de 3 permisos de exportación, subirles el descuento al 35 %.
-- =============================================================================
-- ESTRATEGIA:
--   Se actualiza la tabla 'cliente' para aquellos clientes que cumplen:
--     1) 'tipo_cliente = ''exportador'''
--     2) Poseen más de 3 permisos en 'permiso_exportacion'
--   Se utiliza una subconsulta con 'GROUP BY id_cliente HAVING COUNT(*) > 3'
--   sobre 'permiso_exportacion'.
-- CONSTRAINTS Y TRIGGERS:
--   - 'chk_cliente_descuento': 35% está dentro del rango permitido (0 a 100).
--   - El trigger 'trg_asignar_descuento_cliente' solo actúa BEFORE INSERT o
--     UPDATE OF tipo_cliente, por lo que no interfiere al actualizar directamente
--     la columna 'porcentaje_descuento'.
-- =============================================================================

BEGIN;

-- 1. Control previo: listar exportadores con más de 3 permisos y su descuento actual
SELECT
    c.id_cliente,
    c.nombre_razon_social,
    c.tipo_cliente,
    c.porcentaje_descuento AS descuento_actual,
    COUNT(pe.cod_permiso) AS cant_permisos
FROM cliente c
JOIN cliente_exportador ce ON ce.id_cliente = c.id_cliente
JOIN permiso_exportacion pe ON pe.id_cliente = ce.id_cliente
GROUP BY c.id_cliente, c.nombre_razon_social, c.tipo_cliente, c.porcentaje_descuento
HAVING COUNT(pe.cod_permiso) > 3
ORDER BY c.id_cliente;

-- 2. Sentencia UPDATE
UPDATE cliente c
SET porcentaje_descuento = 35.00
WHERE c.tipo_cliente = 'exportador'
  AND c.id_cliente IN (
      SELECT pe.id_cliente
      FROM permiso_exportacion pe
      GROUP BY pe.id_cliente
      HAVING COUNT(pe.cod_permiso) > 3
  );

-- 3. Control posterior: verificar actualización al 35.00 %
SELECT
    c.id_cliente,
    c.nombre_razon_social,
    c.tipo_cliente,
    c.porcentaje_descuento AS nuevo_descuento,
    COUNT(pe.cod_permiso) AS cant_permisos
FROM cliente c
JOIN cliente_exportador ce ON ce.id_cliente = c.id_cliente
JOIN permiso_exportacion pe ON pe.id_cliente = ce.id_cliente
GROUP BY c.id_cliente, c.nombre_razon_social, c.tipo_cliente, c.porcentaje_descuento
HAVING COUNT(pe.cod_permiso) > 3
ORDER BY c.id_cliente;

-- FILAS AFECTADAS: 29 clientes exportadores con >3 permisos actualizados al 35.00 %.

ROLLBACK;
