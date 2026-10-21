-- =============================================================================
-- TPI BASES DE DATOS - UTN FRSR (2026)
-- Proyecto: Bodegas del Atuel
-- Archivo: db/migrations/001_esquema.sql (Etapa 1 - H1: Modelado Físico Base)
-- =============================================================================

BEGIN;

-- =============================================================================
-- 1. DOMINIOS Y TIPOS ENUMERADOS (Responsable: Delgado)
-- =============================================================================

-- Dominio para validar que todo CUIT tenga exactamente 11 dígitos numéricos
CREATE DOMAIN cuit_dom AS CHAR(11)
    CHECK (VALUE ~ '^[0-9]{11}$');

-- Estado de documentos de stock (ingresos y transferencias) - RN-10 y RN-11
CREATE TYPE estado_documento AS ENUM ('en_confeccion', 'terminado', 'procesado');

-- Tipos de vino permitidos en el catálogo
CREATE TYPE tipo_vino AS ENUM ('tinto', 'blanco', 'rosado', 'espumante');

-- Tipos de cepa permitidos
CREATE TYPE tipo_cepa AS ENUM ('tinta', 'blanca');

-- Tipos de cliente de la jerarquía ERE
CREATE TYPE tipo_cliente_enum AS ENUM ('socio', 'distribuidor', 'exportador');

-- Días de la semana para el cierre semanal de las salas de venta
CREATE TYPE dia_semana AS ENUM (
    'lunes', 'martes', 'miercoles', 'jueves', 'viernes', 'sabado', 'domingo'
);


-- =============================================================================
-- 2. SUBDOMINIO GEOGRAFÍA, SALAS Y PRODUCCIÓN DE UVA (Responsable: Onza)
-- Tablas: localidad, sala_venta, empleado, finca, cepa, parcela,
--         lote_uva, analisis_calidad
-- =============================================================================

-- [GONZALO: Insertar aquí los CREATE TABLE de tus 8 tablas]


-- =============================================================================
-- 3. SUBDOMINIO BODEGAS, VINOS Y CLIENTES (Responsable: Pelu)
-- Tablas: bodega, vino, composicion_vino, maridaje, vino_maridaje,
--         cliente, cliente_socio, cliente_distribuidor, cliente_exportador,
--         permiso_exportacion
-- =============================================================================

-- [MANUEL: Insertar aquí los CREATE TABLE de tus 10 tablas]


-- =============================================================================
-- 4. SUBDOMINIO VENTAS, LOGÍSTICA, STOCK Y AUDITORÍA (Responsable: Br1)
-- Tablas: comprobante, renglon_comprobante, transportista,
--         transportista_localidad, ingreso, renglon_ingreso, transferencia,
--         renglon_transferencia, stock_sala, stock_deposito, auditoria_precio
-- =============================================================================

-- [BRUNO: Insertar aquí los CREATE TABLE de tus 11 tablas]

COMMIT;
