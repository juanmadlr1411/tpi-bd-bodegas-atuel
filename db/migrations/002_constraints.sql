-- =============================================================================
-- TPI BASES DE DATOS - UTN FRSR (2026)
-- Proyecto: Bodegas del Atuel
-- Archivo: db/migrations/002_constraints.sql (Etapa 2 - H2: Integrity Constraints)
-- Responsable: Bruno
-- =============================================================================

BEGIN;

-- -----------------------------------------------------------------------------
-- 1. VALORES DEFAULT (3 requeridos)
-- -----------------------------------------------------------------------------
-- Garantiza que si no se indica provincia en localidad se asigne 'Mendoza'
ALTER TABLE localidad 
    ALTER COLUMN provincia SET DEFAULT 'Mendoza';

-- Garantiza que la fecha de emisión del comprobante sea la fecha actual
ALTER TABLE comprobante 
    ALTER COLUMN fecha SET DEFAULT CURRENT_DATE;

-- Estado inicial por defecto para nuevos ingresos al depósito
ALTER TABLE ingreso 
    ALTER COLUMN estado SET DEFAULT 'en_confeccion';

-- -----------------------------------------------------------------------------
-- 2. RESTRICCIONES UNIQUE ADICIONALES (4 requeridas)
-- -----------------------------------------------------------------------------
-- Evita nombres repetidos de cepas en el catálogo
ALTER TABLE cepa 
    ADD CONSTRAINT uq_cepa_nombre UNIQUE (nombre);

-- Evita razones sociales duplicadas en bodegas elaboradoras
ALTER TABLE bodega 
    ADD CONSTRAINT uq_bodega_razon_social UNIQUE (razon_social);

-- Evita nombres repetidos de platos o acompañamientos en maridajes
ALTER TABLE maridaje 
    ADD CONSTRAINT uq_maridaje_nombre UNIQUE (nombre);

-- Garantiza unicidad del CUIT en la tabla de transportistas
ALTER TABLE transportista 
    ADD CONSTRAINT uq_transportista_cuit UNIQUE (cuit);

-- -----------------------------------------------------------------------------
-- 3. RESTRICCIONES CHECK (8 requeridas)
-- -----------------------------------------------------------------------------
-- RN-07: Validar que la fecha de vencimiento sea estrictamente mayor a la fecha de emisión
ALTER TABLE permiso_exportacion 
    ADD CONSTRAINT chk_permiso_fechas CHECK (fecha_vencimiento > fecha_emision);

-- RN-15: El salario del empleado debe ser estrictamente positivo
ALTER TABLE empleado 
    ADD CONSTRAINT chk_empleado_salario CHECK (salario > 0);

-- RN-15: La superficie de la finca en hectáreas debe ser positiva
ALTER TABLE finca 
    ADD CONSTRAINT chk_finca_superficie CHECK (superficie_ha > 0);

-- RN-15: El precio del vino debe ser mayor a cero
ALTER TABLE vino 
    ADD CONSTRAINT chk_vino_precio CHECK (precio > 0);

-- RN-15: Graduación alcohólica dentro de los parámetros enológicos (5% a 20%)
ALTER TABLE vino 
    ADD CONSTRAINT chk_vino_graduacion CHECK (graduacion BETWEEN 5.00 AND 20.00);

-- RN-15: La cantidad de botellas vendidas en un renglón debe ser mayor a cero
ALTER TABLE renglon_comprobante 
    ADD CONSTRAINT chk_renglon_cantidad CHECK (cantidad > 0);

-- RN-06: Porcentaje de descuento de cliente entre 0 y 100
ALTER TABLE cliente 
    ADD CONSTRAINT chk_cliente_descuento CHECK (porcentaje_descuento BETWEEN 0.00 AND 100.00);

-- Validación de rango enológico para el pH en análisis de calidad (0 a 14)
ALTER TABLE analisis_calidad 
    ADD CONSTRAINT chk_analisis_ph CHECK (ph BETWEEN 0.00 AND 14.00);

COMMIT;