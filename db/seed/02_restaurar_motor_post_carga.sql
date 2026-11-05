-- =============================================================================
-- TPI BASES DE DATOS - UTN FRSR (2026)
-- Proyecto: Bodegas del Atuel
-- Archivo: db/seed/02_restaurar_motor_post_carga.sql (Etapa 3 - H3: Post-Carga)
-- Responsable: Gonzalo
-- Propósito: Rehabilitar todos los triggers de negocio una vez finalizada la
--            carga masiva, refrescar la vista materializada de reportes y
--            actualizar las estadísticas del planificador con ANALYZE.
-- =============================================================================

BEGIN;

-- 1. Rehabilitar triggers de usuario en todas las tablas operativas
ALTER TABLE vino                  ENABLE TRIGGER USER;
ALTER TABLE composicion_vino      ENABLE TRIGGER USER;
ALTER TABLE auditoria_precio      ENABLE TRIGGER USER;

ALTER TABLE cliente               ENABLE TRIGGER USER;
ALTER TABLE comprobante           ENABLE TRIGGER USER;
ALTER TABLE renglon_comprobante   ENABLE TRIGGER USER;

ALTER TABLE ingreso               ENABLE TRIGGER USER;
ALTER TABLE renglon_ingreso       ENABLE TRIGGER USER;
ALTER TABLE transferencia         ENABLE TRIGGER USER;
ALTER TABLE renglon_transferencia ENABLE TRIGGER USER;

ALTER TABLE stock_deposito        ENABLE TRIGGER USER;
ALTER TABLE stock_sala            ENABLE TRIGGER USER;

-- 2. Poblar/actualizar la vista materializada con los +150.000 comprobantes cargados
REFRESH MATERIALIZED VIEW mv_ventas_mensuales_sala;

COMMIT;

-- 3. Actualizar estadísticas del catálogo para que PostgreSQL conozca el nuevo volumen
ANALYZE;