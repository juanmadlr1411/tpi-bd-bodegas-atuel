-- =============================================================================
-- TPI BASES DE DATOS - UTN FRSR (2026)
-- Proyecto: Bodegas del Atuel
-- Archivo: db/seed/01_preparar_motor_pre_carga.sql (Etapa 3 - H3: Pre-Carga)
-- Responsable: Gonzalo
-- Propósito: Deshabilitar temporalmente los triggers de usuario antes de la
--            inyección masiva de datos históricos para evitar colisiones con
--            reglas de tiempo real (RN-08, RN-09, RN-10, RN-11, RN-12, RN-13)
--            y sobrecarga fila por fila, manteniendo activas las FOREIGN KEY.
-- =============================================================================

BEGIN;

-- 1. Subdominio Vinos y Composición (RN-05: suma 100%, RN-13: auditoría precio)
ALTER TABLE vino                  DISABLE TRIGGER USER;
ALTER TABLE composicion_vino      DISABLE TRIGGER USER;
ALTER TABLE auditoria_precio      DISABLE TRIGGER USER;

-- 2. Subdominio Clientes y Ventas (RN-06: descuento, RN-07: permisos, RN-08: totales, RN-09: stock)
ALTER TABLE cliente               DISABLE TRIGGER USER;
ALTER TABLE permiso_exportacion   DISABLE TRIGGER USER;
ALTER TABLE comprobante           DISABLE TRIGGER USER;
ALTER TABLE renglon_comprobante   DISABLE TRIGGER USER;

-- 3. Subdominio Logística y Movimientos (RN-10, RN-11: estados/fecha, RN-12: bloqueo)
ALTER TABLE ingreso               DISABLE TRIGGER USER;
ALTER TABLE renglon_ingreso       DISABLE TRIGGER USER;
ALTER TABLE transferencia         DISABLE TRIGGER USER;
ALTER TABLE renglon_transferencia DISABLE TRIGGER USER;

-- 4. Subdominio Existencias de Stock
ALTER TABLE stock_deposito        DISABLE TRIGGER USER;
ALTER TABLE stock_sala            DISABLE TRIGGER USER;

COMMIT;