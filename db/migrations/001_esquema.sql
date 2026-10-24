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

CREATE TABLE localidad (
    cod_postal          VARCHAR(10)     PRIMARY KEY,
    nombre              VARCHAR(80)     NOT NULL,
    provincia           VARCHAR(60)     NOT NULL DEFAULT 'Mendoza',
    encargado_regional  VARCHAR(100)    NOT NULL
);

CREATE TABLE sala_venta (
    id_sala             INTEGER         GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    calle               VARCHAR(100)    NOT NULL,
    numero              INTEGER         NOT NULL CHECK (numero > 0),
    dia_cierre          dia_semana      NOT NULL,
    cod_postal          VARCHAR(10)     NOT NULL
                        REFERENCES localidad (cod_postal)
                        ON DELETE RESTRICT ON UPDATE CASCADE
);

CREATE TABLE empleado (
    cuit                cuit_dom        PRIMARY KEY,
    nombre              VARCHAR(100)    NOT NULL,
    fecha_ingreso       DATE            NOT NULL,
    salario             NUMERIC(12,2)   NOT NULL CHECK (salario > 0),
    id_sala             INTEGER         NOT NULL
                        REFERENCES sala_venta (id_sala)
                        ON DELETE RESTRICT ON UPDATE CASCADE
);

CREATE TABLE finca (
    id_finca            INTEGER         GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    nombre              VARCHAR(80)     NOT NULL UNIQUE,
    superficie_ha       NUMERIC(8,2)    NOT NULL CHECK (superficie_ha > 0),
    departamento        VARCHAR(60)     NOT NULL,
    provincia           VARCHAR(60)     NOT NULL DEFAULT 'Mendoza'
);

CREATE TABLE cepa (
    id_cepa             INTEGER         GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    nombre              VARCHAR(60)     NOT NULL UNIQUE,
    tipo                tipo_cepa       NOT NULL
);

-- Entidad débil: su PK es compuesta por (id_finca, nro_parcela)
CREATE TABLE parcela (
    id_finca            INTEGER         NOT NULL
                        REFERENCES finca (id_finca)
                        ON DELETE CASCADE ON UPDATE CASCADE,
    nro_parcela         SMALLINT        NOT NULL CHECK (nro_parcela > 0),
    superficie_ha       NUMERIC(8,2)    NOT NULL CHECK (superficie_ha > 0),
    anio_plantacion     SMALLINT        NOT NULL CHECK (anio_plantacion BETWEEN 1900 AND 2100),
    id_cepa             INTEGER         NOT NULL
                        REFERENCES cepa (id_cepa)
                        ON DELETE RESTRICT ON UPDATE CASCADE,
    PRIMARY KEY (id_finca, nro_parcela)
);

-- RN-04: una parcela se cosecha como máximo una vez por campaña
CREATE TABLE lote_uva (
    nro_lote            INTEGER         GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    id_finca            INTEGER         NOT NULL,
    nro_parcela         SMALLINT        NOT NULL,
    campania            SMALLINT        NOT NULL CHECK (campania BETWEEN 1990 AND 2100),
    fecha_cosecha       DATE            NOT NULL,
    kilos               NUMERIC(10,2)   NOT NULL CHECK (kilos > 0),
    cuit_bodega         cuit_dom        NOT NULL,
    FOREIGN KEY (id_finca, nro_parcela)
        REFERENCES parcela (id_finca, nro_parcela)
        ON DELETE RESTRICT ON UPDATE CASCADE,
    UNIQUE (id_finca, nro_parcela, campania)
);

CREATE TABLE analisis_calidad (
    id_analisis         INTEGER         GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    nro_lote            INTEGER         NOT NULL
                        REFERENCES lote_uva (nro_lote)
                        ON DELETE CASCADE ON UPDATE CASCADE,
    fecha               DATE            NOT NULL,
    grado_brix          NUMERIC(4,2)    NOT NULL CHECK (grado_brix > 0),
    ph                  NUMERIC(4,2)    NOT NULL CHECK (ph > 0 AND ph <= 14),
    acidez_total        NUMERIC(5,2)    NOT NULL CHECK (acidez_total > 0)
);


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
