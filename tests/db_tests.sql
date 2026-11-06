-- ===================================================================
-- SCRIPT DE AUDITORÍA Y TESTING (QA) - ETAPA 2
-- Proyecto: Bodegas del Atuel
-- Responsable: Juan Manuel
-- ===================================================================

\echo '---------------------------------------------------'
\echo 'INICIANDO BATERÍA DE PRUEBAS QA (Reglas de Negocio)'
\echo '---------------------------------------------------'

-- ---------------------------------------------------------
-- Bloque 1: Seguridad y Roles (007_roles.sql)
-- ---------------------------------------------------------
\echo '>> TEST 1: Permisos de rol_reportes_ro (Debe fallar por permisos)'
BEGIN;
SET ROLE rol_reportes_ro;
INSERT INTO public.vino (nombre, tipo, anada, volumen_ml, precio, graduacion, cuit_bodega) VALUES ('Vino QA', 'tinto', 2026, 750, 1000, 13.5, '30111111118');
RESET ROLE;
ROLLBACK;

-- ---------------------------------------------------------
-- Bloque 2: RN-15 (Restricciones de Dominio y CHECK)
-- ---------------------------------------------------------
\echo '>> TEST 2: Restricciones CHECK de valores positivos (Debe fallar)'
BEGIN;
INSERT INTO public.vino (nombre, tipo, anada, volumen_ml, precio, graduacion, cuit_bodega) VALUES ('Falla Precio', 'blanco', 2026, 750, -500, 12.0, '30111111118');
ROLLBACK;

\echo '>> TEST 3: Restricción CHECK de graduación alcohólica (Debe fallar)'
BEGIN;
INSERT INTO public.vino (nombre, tipo, anada, volumen_ml, precio, graduacion, cuit_bodega) VALUES ('Falla Graduacion', 'tinto', 2026, 750, 2000, 45.0, '30111111118');
ROLLBACK;

-- ---------------------------------------------------------
-- Bloque 3: RN-07 (Incongruencia de Fechas)
-- ---------------------------------------------------------
\echo '>> TEST 4: Fechas incongruentes en permisos (Debe fallar)'
BEGIN;
INSERT INTO public.permiso_exportacion (fecha_emision, fecha_vencimiento) VALUES ('2026-11-10', '2026-11-01');
ROLLBACK;

-- ---------------------------------------------------------
-- Bloque 4: RN-05 (Composición de Cepas)
-- ---------------------------------------------------------
\echo '>> TEST 5: Composición de cepas distinto a 100% (Debe fallar en el COMMIT)'
BEGIN;
ALTER TABLE public.vino DISABLE TRIGGER ALL;
INSERT INTO public.vino (cod_vino, nombre, tipo, anada, volumen_ml, precio, graduacion, cuit_bodega) OVERRIDING SYSTEM VALUE VALUES (9999, 'Vino Cepa', 'tinto', 2026, 750, 1000, 13.5, '30111111118');
ALTER TABLE public.vino ENABLE TRIGGER ALL;

-- Acá está el arreglo: uvas 'tinta' en lugar de 'tinto'
INSERT INTO public.cepa (id_cepa, nombre, tipo) OVERRIDING SYSTEM VALUE VALUES (9998, 'Cepa A', 'tinta'), (9999, 'Cepa B', 'tinta');

INSERT INTO public.composicion_vino (cod_vino, id_cepa, porcentaje) VALUES (9999, 9998, 40.00);
INSERT INTO public.composicion_vino (cod_vino, id_cepa, porcentaje) VALUES (9999, 9999, 40.00);
-- Debería saltar la excepción RN-05 del trigger de Bruno
COMMIT; 

-- ---------------------------------------------------------
-- Bloque 5: RN-10 y RN-11 (Lógica Transaccional)
-- ---------------------------------------------------------
\echo '>> TEST 6: Procesar ingreso inexistente o no terminado (Debe fallar)'
BEGIN;
CALL public.sp_procesar_ingreso(9999);
ROLLBACK;

\echo '>> TEST 7: Procesar transferencia inexistente (Debe fallar)'
BEGIN;
CALL public.sp_procesar_transferencia(9999);
ROLLBACK;

-- ---------------------------------------------------------
-- Bloque 6: RN-11 (Inmutabilidad de Documentos)
-- ---------------------------------------------------------
\echo '>> TEST 8: Modificar transferencia procesada (Debe fallar)'
BEGIN;
ALTER TABLE public.transferencia DISABLE TRIGGER ALL;
INSERT INTO public.transferencia (nro_transferencia, id_sala, estado) OVERRIDING SYSTEM VALUE VALUES (9999, 1, 'procesado');
ALTER TABLE public.transferencia ENABLE TRIGGER ALL;
UPDATE public.transferencia SET estado = 'en_confeccion' WHERE nro_transferencia = 9999;
ROLLBACK;

\echo '---------------------------------------------------'
\echo 'BATERÍA DE PRUEBAS FINALIZADA'
\echo '---------------------------------------------------'

-- ---------------------------------------------------------
-- Bloque 7: RN-09 (Stock insuficiente)
-- ---------------------------------------------------------
\echo '>> TEST 9: Venta con stock insuficiente (Debe fallar)'
BEGIN;
-- Intenta vender 50.000 botellas de un vino, forzando el rechazo del trigger
INSERT INTO public.renglon_comprobante (nro_comprobante, cod_vino, cantidad, precio_unitario, descuento, subtotal) 
VALUES (1, 1, 50000, 1000, 0, 50000000);
ROLLBACK;

-- ---------------------------------------------------------
-- Bloque 8: RN-08 y RN-09 (Venta válida, modificación y borrado)
-- ---------------------------------------------------------
\echo '>> TEST 10: Venta válida, modificación de cantidad y borrado (Debe ajustar stock)'
BEGIN;
-- Se asume que el trigger de Br1/Pelu calculará el subtotal y ajustará stock automáticamente.
-- 1. Inserción válida
INSERT INTO public.renglon_comprobante (nro_comprobante, cod_vino, cantidad, precio_unitario, descuento, subtotal) 
VALUES (1, 1, 5, 1000, 0, 5000);
-- 2. Modificación (debe ajustar el stock devolviendo/restando la diferencia)
UPDATE public.renglon_comprobante SET cantidad = 2 WHERE nro_comprobante = 1 AND cod_vino = 1;
-- 3. Borrado (debe reponer el stock a la sala)
DELETE FROM public.renglon_comprobante WHERE nro_comprobante = 1 AND cod_vino = 1;
ROLLBACK;

-- ---------------------------------------------------------
-- Bloque 9: RN-10 y RN-11 (Transiciones inválidas de estado)
-- ---------------------------------------------------------
\echo '>> TEST 11: Transición terminado -> en_confeccion (Debe fallar)'
BEGIN;
ALTER TABLE public.ingreso DISABLE TRIGGER ALL;
INSERT INTO public.ingreso (cod_ingreso, cod_transporte, cuit_bodega, estado) OVERRIDING SYSTEM VALUE VALUES (9998, 1, '30111111118', 'terminado');
ALTER TABLE public.ingreso ENABLE TRIGGER ALL;

UPDATE public.ingreso SET estado = 'en_confeccion' WHERE cod_ingreso = 9998;
ROLLBACK;

\echo '>> TEST 12: Transición en_confeccion -> procesado directa (Debe fallar)'
BEGIN;
ALTER TABLE public.ingreso DISABLE TRIGGER ALL;
INSERT INTO public.ingreso (cod_ingreso, cod_transporte, cuit_bodega, estado) OVERRIDING SYSTEM VALUE VALUES (9997, 1, '30111111118', 'en_confeccion');
ALTER TABLE public.ingreso ENABLE TRIGGER ALL;

UPDATE public.ingreso SET estado = 'procesado' WHERE cod_ingreso = 9997;
ROLLBACK;

-- ---------------------------------------------------------
-- Bloque 10: RN-12 (Bloqueo de renglones en documento cerrado)
-- ---------------------------------------------------------
\echo '>> TEST 13: Insertar renglón en documento terminado/procesado (Debe fallar)'
BEGIN;
-- Usa el ingreso 9998 creado temporalmente arriba (estado 'terminado')
INSERT INTO public.renglon_ingreso (cod_ingreso, cod_vino, cantidad) VALUES (9998, 1, 100);
ROLLBACK;

-- ---------------------------------------------------------
-- Bloque 11: RN-11 (Inmutabilidad de fecha de confección)
-- ---------------------------------------------------------
\echo '>> TEST 14: Modificar fecha_confeccion de transferencia (Debe fallar)'
BEGIN;
ALTER TABLE public.transferencia DISABLE TRIGGER ALL;
INSERT INTO public.transferencia (nro_transferencia, id_sala, fecha_confeccion) OVERRIDING SYSTEM VALUE VALUES (9998, 1, CURRENT_DATE);
ALTER TABLE public.transferencia ENABLE TRIGGER ALL;

UPDATE public.transferencia SET fecha_confeccion = '2020-01-01' WHERE nro_transferencia = 9998;
ROLLBACK;

-- ---------------------------------------------------------
-- Bloque 12: RN-13 (Auditoría de Precio)
-- ---------------------------------------------------------
\echo '>> TEST 15: Cambio de precio de un vino genera auditoría (Debe funcionar)'
BEGIN;
ALTER TABLE public.vino DISABLE TRIGGER ALL;
INSERT INTO public.vino (cod_vino, nombre, tipo, anada, volumen_ml, precio, graduacion, cuit_bodega) OVERRIDING SYSTEM VALUE VALUES (9998, 'Vino Audit', 'tinto', 2026, 750, 1000, 13.5, '30111111118');
ALTER TABLE public.vino ENABLE TRIGGER ALL;

-- Se actualiza el precio para disparar el trigger AFTER UPDATE
UPDATE public.vino SET precio = 1500 WHERE cod_vino = 9998;
-- Validamos que se haya insertado en auditoria_precio
SELECT cod_vino, precio_anterior, precio_nuevo FROM public.auditoria_precio WHERE cod_vino = 9998;
ROLLBACK;

-- ---------------------------------------------------------
-- Bloque 13: RN-08 (Cálculo de totales del comprobante)
-- ---------------------------------------------------------
\echo '>> TEST 16: Comparar comprobante.total con fn_total_comprobante() (Deben coincidir)'
BEGIN;
-- Inyectamos un comprobante temporal
ALTER TABLE public.comprobante DISABLE TRIGGER ALL;
INSERT INTO public.comprobante (nro_comprobante, id_cliente, id_sala, subtotal, descuento, total) OVERRIDING SYSTEM VALUE VALUES (9999, 1, 1, 0, 0, 0);
ALTER TABLE public.comprobante ENABLE TRIGGER ALL;

-- Insertamos un renglón para que el trigger AFTER INSERT calcule el total en la tabla
INSERT INTO public.renglon_comprobante (nro_comprobante, cod_vino, cantidad, precio_unitario, descuento, subtotal) 
VALUES (9999, 1, 5, 1000, 10, 4500);

-- Comparamos el valor almacenado por el trigger contra la función de cálculo
SELECT 
    total AS "Total en Tabla", 
    public.fn_total_comprobante(9999) AS "Total por Función",
    CASE 
        WHEN total = public.fn_total_comprobante(9999) THEN 'ÉXITO: COINCIDEN' 
        ELSE 'ERROR: DIFIEREN' 
    END AS "Resultado_Auditoria"
FROM public.comprobante 
WHERE nro_comprobante = 9999;
ROLLBACK;
