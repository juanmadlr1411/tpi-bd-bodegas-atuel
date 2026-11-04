-- =============================================================================
-- TPI BASES DE DATOS - UTN FRSR (2026)
-- Proyecto: Bodegas del Atuel
-- Archivo: db/migrations/004_procedimientos.sql (Etapa 2 - H2: Procedimientos)
-- Responsable: Manuel Andrés Perez
-- =============================================================================


BEGIN;

-- =============================================================================
-- 1. PROCEDIMIENTO: sp_procesar_ingreso (Protege RN-10)
-- Propósito: Impacta en el stock del depósito central las botellas de un ingreso
--            que se encuentre en estado 'terminado' y cambia su estado a
--            'procesado' de forma atómica.
-- Parámetros: p_cod_ingreso (INTEGER) -> Código del ingreso a procesar.
-- =============================================================================
CREATE OR REPLACE PROCEDURE sp_procesar_ingreso(p_cod_ingreso INTEGER)
LANGUAGE plpgsql AS $$
DECLARE
    v_estado estado_documento;
    v_cant_renglones INTEGER;
BEGIN
    -- 1. Obtener estado actual y bloquear la cabecera para evitar que otra
    --    sesión concurrente procese el mismo ingreso al mismo tiempo.
    SELECT estado INTO v_estado
    FROM ingreso
    WHERE cod_ingreso = p_cod_ingreso
    FOR UPDATE;

    -- Validar que el ingreso exista
    IF NOT FOUND THEN
        RAISE EXCEPTION 'El ingreso % no existe (RN-10)', p_cod_ingreso
            USING ERRCODE = 'P0001';
    END IF;

    -- 2. Validar regla RN-10: solo un ingreso 'terminado' puede procesarse
    IF v_estado IS DISTINCT FROM 'terminado' THEN
        RAISE EXCEPTION 'El ingreso % se encuentra en estado "%" y solo puede procesarse si está "terminado" (RN-10)',
            p_cod_ingreso, v_estado
            USING ERRCODE = 'P0001';
    END IF;

    -- 3. Validar que el ingreso tenga al menos un renglón cargado
    SELECT COUNT(*) INTO v_cant_renglones
    FROM renglon_ingreso
    WHERE cod_ingreso = p_cod_ingreso;

    IF v_cant_renglones = 0 THEN
        RAISE EXCEPTION 'No se puede procesar el ingreso % porque no tiene renglones cargados (RN-10)',
            p_cod_ingreso
            USING ERRCODE = 'P0001';
    END IF;

    -- 4. Impactar en stock_deposito (UPSERT):
    --    Si el vino aún no tenía fila en stock_deposito, la inserta.
    --    Si ya existía, suma la cantidad ingresada al stock actual.
    INSERT INTO stock_deposito (cod_vino, cantidad)
    SELECT r.cod_vino, r.cantidad
    FROM renglon_ingreso r
    WHERE r.cod_ingreso = p_cod_ingreso
    ORDER BY r.cod_vino
    ON CONFLICT (cod_vino)
    DO UPDATE SET cantidad = stock_deposito.cantidad + EXCLUDED.cantidad;

    -- 5. Cambiar el estado del ingreso a 'procesado' (RN-10)
    UPDATE ingreso
    SET estado = 'procesado'
    WHERE cod_ingreso = p_cod_ingreso;
END;
$$;


-- =============================================================================
-- 2. PROCEDIMIENTO: sp_procesar_transferencia (Protege RN-11)
-- Propósito: Descuenta del depósito central y suma al stock de la sala
--            solicitante los vinos de una transferencia en estado 'terminado',
--            pasándola a 'procesado'. Si falta stock de algún vino (o si el vino
--            ni siquiera tiene fila en stock_deposito), aborta toda la operación.
-- Parámetros: p_nro_transferencia (INTEGER) -> Número de transferencia.
-- =============================================================================
CREATE OR REPLACE PROCEDURE sp_procesar_transferencia(p_nro_transferencia INTEGER)
LANGUAGE plpgsql AS $$
DECLARE
    v_estado estado_documento;
    v_id_sala INTEGER;
    v_cant_renglones INTEGER;
    v_rec RECORD;
    v_stock_actual INTEGER;
BEGIN
    -- 1. Obtener datos de cabecera y bloquear la fila de la transferencia
    SELECT estado, id_sala INTO v_estado, v_id_sala
    FROM transferencia
    WHERE nro_transferencia = p_nro_transferencia
    FOR UPDATE;

    -- Validar que la transferencia exista
    IF NOT FOUND THEN
        RAISE EXCEPTION 'La transferencia % no existe (RN-11)', p_nro_transferencia
            USING ERRCODE = 'P0001';
    END IF;

    -- 2. Validar regla RN-11: solo una transferencia 'terminada' puede procesarse
    IF v_estado IS DISTINCT FROM 'terminado' THEN
        RAISE EXCEPTION 'La transferencia % está en estado "%" y solo puede procesarse si está "terminada" (RN-11)',
            p_nro_transferencia, v_estado
            USING ERRCODE = 'P0001';
    END IF;

    -- 3. Validar que la transferencia tenga al menos un renglón
    SELECT COUNT(*) INTO v_cant_renglones
    FROM renglon_transferencia
    WHERE nro_transferencia = p_nro_transferencia;

    IF v_cant_renglones = 0 THEN
        RAISE EXCEPTION 'La transferencia % no tiene renglones cargados (RN-11)',
            p_nro_transferencia
            USING ERRCODE = 'P0001';
    END IF;

    -- 4. Verificar existencia, bloquear filas en orden de cod_vino (previene deadlocks)
    --    y descontar stock del depósito central.
    --    NOTA DE DISEÑO (Anexo A.6): Se recorre cada renglón verificando que exista
    --    la fila en stock_deposito; si no existe o no alcanza, se lanza excepción
    --    para revertir toda la transacción.
    FOR v_rec IN
        SELECT cod_vino, cantidad
        FROM renglon_transferencia
        WHERE nro_transferencia = p_nro_transferencia
        ORDER BY cod_vino
    LOOP
        -- Bloqueo pesimista sobre la fila del vino en el depósito central
        SELECT cantidad INTO v_stock_actual
        FROM stock_deposito
        WHERE cod_vino = v_rec.cod_vino
        FOR UPDATE;

        -- Si el vino no tiene fila en stock_deposito o la cantidad es menor a la pedida
        IF NOT FOUND OR v_stock_actual < v_rec.cantidad THEN
            RAISE EXCEPTION 'Stock insuficiente en depósito central para el vino %: solicitado %, disponible % (RN-11)',
                v_rec.cod_vino, v_rec.cantidad, COALESCE(v_stock_actual, 0)
                USING ERRCODE = 'P0001';
        END IF;

        -- Descontar del depósito central
        UPDATE stock_deposito
        SET cantidad = cantidad - v_rec.cantidad
        WHERE cod_vino = v_rec.cod_vino;

        -- Sumar al stock de la sala solicitante (crea la fila si no existía)
        INSERT INTO stock_sala (id_sala, cod_vino, cantidad)
        VALUES (v_id_sala, v_rec.cod_vino, v_rec.cantidad)
        ON CONFLICT (id_sala, cod_vino)
        DO UPDATE SET cantidad = stock_sala.cantidad + EXCLUDED.cantidad;
    END LOOP;

    -- 5. Actualizar estado de la transferencia a 'procesado' (RN-11)
    UPDATE transferencia
    SET estado = 'procesado'
    WHERE nro_transferencia = p_nro_transferencia;
END;
$$;

COMMIT;