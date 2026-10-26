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

CREATE TABLE bodega (
    cuit                cuit_dom        PRIMARY KEY,
    razon_social        VARCHAR(100)    NOT NULL UNIQUE,
    domicilio           VARCHAR(150)    NOT NULL
);

-- Vínculo referencial entre LOTE_UVA y BODEGA (Sección 3) - RN-14
ALTER TABLE lote_uva
    ADD CONSTRAINT fk_lote_uva_bodega
    FOREIGN KEY (cuit_bodega)
    REFERENCES bodega (cuit)
    ON DELETE RESTRICT ON UPDATE CASCADE;

-- RN-01: El precio de un vino es único y siempre mayor que cero.
-- RN-14: No se puede borrar una bodega con vinos asociados (ON DELETE RESTRICT).
CREATE TABLE vino (
    cod_vino            INTEGER         GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    nombre              VARCHAR(80)     NOT NULL,
    tipo                tipo_vino       NOT NULL,
    anada               SMALLINT        NOT NULL CHECK (anada BETWEEN 1990 AND 2100),
    volumen_ml          INTEGER         NOT NULL CHECK (volumen_ml IN (187, 375, 750, 1500, 3000)),
    graduacion          NUMERIC(4,2)    NOT NULL CHECK (graduacion BETWEEN 5 AND 20),
    precio              NUMERIC(12,2)   NOT NULL CHECK (precio > 0),
    cuit_bodega         cuit_dom        NOT NULL
                        REFERENCES bodega (cuit)
                        ON DELETE RESTRICT ON UPDATE CASCADE,
    UNIQUE (nombre, anada, volumen_ml)
);

-- Relación N:M entre VINO y CEPA con atributo propio (porcentaje)
CREATE TABLE composicion_vino (
    cod_vino            INTEGER         NOT NULL
                        REFERENCES vino (cod_vino)
                        ON DELETE CASCADE ON UPDATE CASCADE,
    id_cepa             INTEGER         NOT NULL
                        REFERENCES cepa (id_cepa)
                        ON DELETE RESTRICT ON UPDATE CASCADE,
    porcentaje          NUMERIC(5,2)    NOT NULL CHECK (porcentaje > 0 AND porcentaje <= 100),
    PRIMARY KEY (cod_vino, id_cepa)
);

CREATE TABLE maridaje (
    id_maridaje             INTEGER     GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    nombre                  VARCHAR(80) NOT NULL UNIQUE,
    temperatura_servicio    SMALLINT    NOT NULL CHECK (temperatura_servicio BETWEEN 0 AND 30)
);

-- Relación N:M entre VINO y MARIDAJE
CREATE TABLE vino_maridaje (
    cod_vino            INTEGER         NOT NULL
                        REFERENCES vino (cod_vino)
                        ON DELETE CASCADE ON UPDATE CASCADE,
    id_maridaje         INTEGER         NOT NULL
                        REFERENCES maridaje (id_maridaje)
                        ON DELETE RESTRICT ON UPDATE CASCADE,
    PRIMARY KEY (cod_vino, id_maridaje)
);

-- Jerarquía ERE: Supertipo CLIENTE
-- RN-06: El descuento inicial depende del tipo de cliente, pero se protege el rango (0 a 100)
CREATE TABLE cliente (
    id_cliente              INTEGER             GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    nombre_razon_social     VARCHAR(120)        NOT NULL,
    tipo_documento          VARCHAR(10)         NOT NULL,
    nro_documento           VARCHAR(20)         NOT NULL,
    direccion               VARCHAR(150)        NOT NULL,
    cod_postal              VARCHAR(10)         NOT NULL
                            REFERENCES localidad (cod_postal)
                            ON DELETE RESTRICT ON UPDATE CASCADE,
    fecha_alta              DATE                NOT NULL DEFAULT CURRENT_DATE,
    tipo_cliente            tipo_cliente_enum   NOT NULL,
    porcentaje_descuento    NUMERIC(5,2)        NOT NULL CHECK (porcentaje_descuento BETWEEN 0 AND 100),
    UNIQUE (tipo_documento, nro_documento)
);

-- Subtipo 1: SOCIO
CREATE TABLE cliente_socio (
    id_cliente          INTEGER         PRIMARY KEY
                        REFERENCES cliente (id_cliente)
                        ON DELETE CASCADE ON UPDATE CASCADE
);

-- Subtipo 2: DISTRIBUIDOR
CREATE TABLE cliente_distribuidor (
    id_cliente          INTEGER         PRIMARY KEY
                        REFERENCES cliente (id_cliente)
                        ON DELETE CASCADE ON UPDATE CASCADE,
    zona_cobertura      VARCHAR(100)    NOT NULL,
    nro_habilitacion    VARCHAR(40)     NOT NULL UNIQUE
);

-- Subtipo 3: EXPORTADOR
CREATE TABLE cliente_exportador (
    id_cliente          INTEGER         PRIMARY KEY
                        REFERENCES cliente (id_cliente)
                        ON DELETE CASCADE ON UPDATE CASCADE,
    pais_destino        VARCHAR(80)     NOT NULL
);

-- RN-07: Un exportador puede tener varios permisos; el vencimiento es posterior a la emisión.
CREATE TABLE permiso_exportacion (
    cod_permiso         VARCHAR(40)     PRIMARY KEY,
    id_cliente          INTEGER         NOT NULL
                        REFERENCES cliente_exportador (id_cliente)
                        ON DELETE CASCADE ON UPDATE CASCADE,
    fecha_emision       DATE            NOT NULL,
    fecha_vencimiento   DATE            NOT NULL,
    CHECK (fecha_vencimiento > fecha_emision)
);


-- =============================================================================
-- 4. SUBDOMINIO VENTAS, LOGÍSTICA, STOCK Y AUDITORÍA (Responsable: Br1)
-- Tablas: comprobante, renglon_comprobante, transportista,
--         transportista_localidad, ingreso, renglon_ingreso, transferencia,
--         renglon_transferencia, stock_sala, stock_deposito, auditoria_precio
-- =============================================================================

CREATE TABLE comprobante (
    nro_comprobante     INTEGER         GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    fecha               DATE            NOT NULL DEFAULT CURRENT_DATE,
    id_cliente          INTEGER         NOT NULL
                        REFERENCES cliente (id_cliente)
                        ON DELETE RESTRICT ON UPDATE CASCADE,
    id_sala             INTEGER         NOT NULL
                        REFERENCES sala_venta (id_sala)
                        ON DELETE RESTRICT ON UPDATE CASCADE,
    subtotal            NUMERIC(14,2)   NOT NULL DEFAULT 0 CHECK (subtotal >= 0),
    descuento           NUMERIC(14,2)   NOT NULL DEFAULT 0 CHECK (descuento >= 0),
    total               NUMERIC(14,2)   NOT NULL DEFAULT 0 CHECK (total >= 0)
);

CREATE TABLE renglon_comprobante (
    nro_comprobante     INTEGER         NOT NULL
                        REFERENCES comprobante (nro_comprobante)
                        ON DELETE CASCADE ON UPDATE CASCADE,
    cod_vino            INTEGER         NOT NULL
                        REFERENCES vino (cod_vino)
                        ON DELETE RESTRICT ON UPDATE CASCADE,
    cantidad            INTEGER         NOT NULL CHECK (cantidad > 0),
    precio_unitario     NUMERIC(12,2)   NOT NULL CHECK (precio_unitario > 0),
    descuento           NUMERIC(5,2)    NOT NULL CHECK (descuento BETWEEN 0 AND 100),
    subtotal            NUMERIC(14,2)   NOT NULL CHECK (subtotal > 0),
    PRIMARY KEY (nro_comprobante, cod_vino)
);

-- -----------------------------------------------------------------------------
-- 6. SUBDOMINIO: TRANSPORTE, STOCK, INGRESOS Y TRANSFERENCIAS (Sección 3.5)
-- -----------------------------------------------------------------------------

CREATE TABLE transportista (
    cod_transporte      INTEGER         GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    razon_social        VARCHAR(100)    NOT NULL UNIQUE,
    cuit                cuit_dom        NOT NULL UNIQUE,
    email               VARCHAR(100)    NOT NULL,
    telefono            VARCHAR(30)     NOT NULL,
    domicilio           VARCHAR(150)    NOT NULL
);

CREATE TABLE transportista_localidad (
    cod_transporte      INTEGER         NOT NULL
                        REFERENCES transportista (cod_transporte)
                        ON DELETE RESTRICT ON UPDATE CASCADE,
    cod_postal          VARCHAR(10)     NOT NULL
                        REFERENCES localidad (cod_postal)
                        ON DELETE RESTRICT ON UPDATE CASCADE,
    PRIMARY KEY (cod_transporte, cod_postal)
);

CREATE TABLE ingreso (
    cod_ingreso         INTEGER             GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    fecha               DATE                NOT NULL DEFAULT CURRENT_DATE,
    estado              estado_documento    NOT NULL DEFAULT 'en_confeccion',
    cod_transporte      INTEGER             NOT NULL
                        REFERENCES transportista (cod_transporte)
                        ON DELETE RESTRICT ON UPDATE CASCADE,
    cuit_bodega         cuit_dom            NOT NULL
                        REFERENCES bodega (cuit)
                        ON DELETE RESTRICT ON UPDATE CASCADE
);

CREATE TABLE renglon_ingreso (
    cod_ingreso         INTEGER         NOT NULL
                        REFERENCES ingreso (cod_ingreso)
                        ON DELETE CASCADE ON UPDATE CASCADE,
    cod_vino            INTEGER         NOT NULL
                        REFERENCES vino (cod_vino)
                        ON DELETE RESTRICT ON UPDATE CASCADE,
    cantidad            INTEGER         NOT NULL CHECK (cantidad > 0),
    PRIMARY KEY (cod_ingreso, cod_vino)
);

CREATE TABLE transferencia (
    nro_transferencia   INTEGER             GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    id_sala             INTEGER             NOT NULL
                        REFERENCES sala_venta (id_sala)
                        ON DELETE RESTRICT ON UPDATE CASCADE,
    fecha_confeccion    DATE                NOT NULL DEFAULT CURRENT_DATE,
    estado              estado_documento    NOT NULL DEFAULT 'en_confeccion'
);

CREATE TABLE renglon_transferencia (
    nro_transferencia   INTEGER         NOT NULL
                        REFERENCES transferencia (nro_transferencia)
                        ON DELETE CASCADE ON UPDATE CASCADE,
    cod_vino            INTEGER         NOT NULL
                        REFERENCES vino (cod_vino)
                        ON DELETE RESTRICT ON UPDATE CASCADE,
    cantidad            INTEGER         NOT NULL CHECK (cantidad > 0),
    PRIMARY KEY (nro_transferencia, cod_vino)
);

CREATE TABLE stock_sala (
    id_sala             INTEGER         NOT NULL
                        REFERENCES sala_venta (id_sala)
                        ON DELETE RESTRICT ON UPDATE CASCADE,
    cod_vino            INTEGER         NOT NULL
                        REFERENCES vino (cod_vino)
                        ON DELETE RESTRICT ON UPDATE CASCADE,
    cantidad            INTEGER         NOT NULL DEFAULT 0 CHECK (cantidad >= 0),
    PRIMARY KEY (id_sala, cod_vino)
);

CREATE TABLE stock_deposito (
    cod_vino            INTEGER         PRIMARY KEY
                        REFERENCES vino (cod_vino)
                        ON DELETE RESTRICT ON UPDATE CASCADE,
    cantidad            INTEGER         NOT NULL DEFAULT 0 CHECK (cantidad >= 0)
);

-- -----------------------------------------------------------------------------
-- 7. AUDITORÍA (RN-13)
-- -----------------------------------------------------------------------------

CREATE TABLE auditoria_precio (
    id_auditoria        INTEGER         GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    cod_vino            INTEGER         NOT NULL
                        REFERENCES vino (cod_vino)
                        ON DELETE RESTRICT ON UPDATE CASCADE,
    precio_anterior     NUMERIC(12,2)   NOT NULL CHECK (precio_anterior > 0),
    precio_nuevo        NUMERIC(12,2)   NOT NULL CHECK (precio_nuevo > 0),
    fecha_hora          TIMESTAMP       NOT NULL DEFAULT CURRENT_TIMESTAMP,
    usuario             VARCHAR(80)     NOT NULL DEFAULT CURRENT_USER
);

COMMIT;
