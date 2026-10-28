-- =============================================================================
-- TPI BASES DE DATOS - UTN FRSR (2026)
-- Proyecto: Bodegas del Atuel
-- Archivo: db/migrations/003_funciones.sql (Etapa 2 - H2: Funciones)
-- Responsable: Gonzalo (Onza)
-- =============================================================================

BEGIN;

-- -----------------------------------------------------------------------------
-- 1. FUNCIÓN: fn_stock_sala
-- Propósito: Devuelve la cantidad de botellas disponibles de un vino en una
--            sala de venta determinada. Si no existe registro en stock_sala,
--            retorna 0. Utilizada para validar RN-09 antes de cada venta.
-- Parámetros:
--   - p_sala (INTEGER): Identificador de la sala de venta (id_sala).
--   - p_vino (INTEGER): Código del vino a consultar (cod_vino).
-- Volatilidad: STABLE, porque no modifica datos pero lee la tabla stock_sala,
--              cuyos valores pueden variar entre distintas transacciones.
-- -----------------------------------------------------------------------------
CREATE OR REPLACE FUNCTION fn_stock_sala(p_sala INTEGER, p_vino INTEGER)
RETURNS INTEGER
LANGUAGE sql STABLE AS $$
    SELECT COALESCE(
        (SELECT cantidad
         FROM stock_sala
         WHERE id_sala = p_sala AND cod_vino = p_vino),
        0
    );
$$;


-- -----------------------------------------------------------------------------
-- 2. FUNCIÓN: fn_descuento_por_tipo
-- Propósito: Retorna el porcentaje de descuento normativo que corresponde a
--            cada categoría de cliente según la regla RN-06:
--            socio = 10%, distribuidor = 20%, exportador = 30%.
-- Parámetros:
--   - p_tipo (tipo_cliente_enum): Categoría del cliente ('socio',
--                                 'distribuidor', 'exportador').
-- Volatilidad: IMMUTABLE, porque el resultado depende exclusivamente del valor
--              del parámetro recibido, sin consultar tablas ni el reloj.
-- -----------------------------------------------------------------------------
CREATE OR REPLACE FUNCTION fn_descuento_por_tipo(p_tipo tipo_cliente_enum)
RETURNS NUMERIC(5,2)
LANGUAGE sql IMMUTABLE AS $$
    SELECT CASE p_tipo
        WHEN 'socio'        THEN 10.00
        WHEN 'distribuidor' THEN 20.00
        WHEN 'exportador'   THEN 30.00
    END;
$$;


-- -----------------------------------------------------------------------------
-- 3. FUNCIÓN: fn_descuento_cliente
-- Propósito: Obtiene el porcentaje de descuento vigente para un cliente
--            específico a partir de su ID (RN-06). Si el cliente no existe,
--            retorna 0.00.
-- Parámetros:
--   - p_id_cliente (INTEGER): Identificador único del cliente (id_cliente).
-- Volatilidad: STABLE, porque realiza una lectura sobre la tabla cliente.
-- -----------------------------------------------------------------------------
CREATE OR REPLACE FUNCTION fn_descuento_cliente(p_id_cliente INTEGER)
RETURNS NUMERIC(5,2)
LANGUAGE sql STABLE AS $$
    SELECT COALESCE(
        (SELECT porcentaje_descuento
         FROM cliente
         WHERE id_cliente = p_id_cliente),
        0.00
    );
$$;


-- -----------------------------------------------------------------------------
-- 4. FUNCIÓN: fn_total_comprobante
-- Propósito: Calcula el importe total neto de un comprobante sumando el
--            importe de todos sus renglones con su respectivo porcentaje de
--            descuento aplicado (RN-08). Si no tiene renglones, retorna 0.00.
-- Parámetros:
--   - p_nro_comprobante (INTEGER): Número de comprobante (nro_comprobante).
-- Volatilidad: STABLE, porque consulta las filas de renglon_comprobante.
-- -----------------------------------------------------------------------------
CREATE OR REPLACE FUNCTION fn_total_comprobante(p_nro_comprobante INTEGER)
RETURNS NUMERIC(14,2)
LANGUAGE sql STABLE AS $$
    SELECT COALESCE(
        ROUND(SUM(cantidad * precio_unitario * (1 - (descuento / 100.0))), 2),
        0.00
    )
    FROM renglon_comprobante
    WHERE nro_comprobante = p_nro_comprobante;
$$;


-- -----------------------------------------------------------------------------
-- 5. FUNCIÓN: fn_antiguedad_anios
-- Propósito: Calcula los años completos de antigüedad desde una fecha de
--            ingreso laboral hasta la fecha actual (CURRENT_DATE).
-- Parámetros:
--   - p_fecha_ingreso (DATE): Fecha de alta laboral del empleado.
-- Volatilidad: STABLE, porque depende de CURRENT_DATE (su valor es constante
--              dentro de una misma consulta, pero cambia día a día).
-- -----------------------------------------------------------------------------
CREATE OR REPLACE FUNCTION fn_antiguedad_anios(p_fecha_ingreso DATE)
RETURNS INTEGER
LANGUAGE sql STABLE AS $$
    SELECT EXTRACT(YEAR FROM AGE(CURRENT_DATE, p_fecha_ingreso))::INTEGER;
$$;

COMMIT;