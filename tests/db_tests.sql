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
-- Debería saltar la excepción RN-05 del trigger de Br1
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
