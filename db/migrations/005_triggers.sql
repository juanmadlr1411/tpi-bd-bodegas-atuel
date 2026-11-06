-- =============================================================================
-- TPI BASES DE DATOS - UTN FRSR (2026)
-- Proyecto: Bodegas del Atuel
-- Archivo: db/migrations/005_triggers.sql (Etapa 2 - H2: Business Logic & Triggers)
-- Responsable: Bruno
-- =============================================================================

BEGIN;

-- -----------------------------------------------------------------------------
-- TRIGGER 1: CONSTRAINT TRIGGER DEFERRABLE (RN-05)
-- Regla de Negocio protegida: RN-05 (La composición de cepas de un vino debe sumar 100%)
-- Explicación: Se difiere la validación al final de la transacción (COMMIT) para 
-- permitir insertar/modificar los renglones del corte de cepas de forma secuencial.
-- -----------------------------------------------------------------------------
CREATE OR REPLACE FUNCTION fn_trg_validar_composicion_vino()
RETURNS TRIGGER AS $$
DECLARE
    v_suma NUMERIC(5,2);
    v_cod_vino INT;
BEGIN
    v_cod_vino := COALESCE(NEW.cod_vino, OLD.cod_vino);

    SELECT COALESCE(SUM(porcentaje), 0) INTO v_suma
    FROM composicion_vino
    WHERE cod_vino = v_cod_vino;

    -- Si el vino queda sin componentes (por ejemplo, al eliminarse el vino y
    -- dispararse el ON DELETE CASCADE), no corresponde exigir una suma de 100%.
    IF v_suma = 0 THEN
        IF TG_OP = 'DELETE' THEN
            RETURN OLD;
        END IF;
        RETURN NEW;
    END IF;

    IF v_suma <> 100.00 THEN
        RAISE EXCEPTION 'RN-05 VIOLACIÓN: La suma de porcentajes de cepas para el vino ID % es % %% (debe sumar exactamente 100.00 %%)', 
            v_cod_vino, v_suma;
    END IF;

    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE CONSTRAINT TRIGGER trg_validar_composicion_vino
AFTER INSERT OR UPDATE OR DELETE ON composicion_vino
DEFERRABLE INITIALLY DEFERRED
FOR EACH ROW
EXECUTE FUNCTION fn_trg_validar_composicion_vino();

-- -----------------------------------------------------------------------------
-- TRIGGER 2: BEFORE INSERT OR UPDATE (RN-07)
-- Regla de Negocio protegida: RN-07 (El vencimiento del permiso debe ser posterior a la emisión)
-- Explicación: Intercepta la fila antes de ser escrita para rechazarla en caso de incongruencia de fechas.
-- -----------------------------------------------------------------------------
CREATE OR REPLACE FUNCTION fn_trg_validar_fechas_permiso()
RETURNS TRIGGER AS $$
BEGIN
    IF NEW.fecha_vencimiento <= NEW.fecha_emision THEN
        RAISE EXCEPTION 'RN-07 VIOLACIÓN: La fecha de vencimiento (%) debe ser estrictamente posterior a la fecha de emisión (%)', 
            NEW.fecha_vencimiento, NEW.fecha_emision;
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trg_validar_fechas_permiso
BEFORE INSERT OR UPDATE ON permiso_exportacion
FOR EACH ROW
EXECUTE FUNCTION fn_trg_validar_fechas_permiso();

-- -----------------------------------------------------------------------------
-- TRIGGER 3: AFTER UPDATE OF PRECIO (RN-13)
-- Regla de Negocio protegida: RN-13 (Auditoría automática ante variaciones de precio en vinos)
-- Explicación: Tras modificar el precio de un vino, registra automáticamente en la 
-- tabla auditoria_precio el precio anterior, precio nuevo, fecha/hora y usuario de BD.
-- -----------------------------------------------------------------------------
CREATE OR REPLACE FUNCTION fn_trg_auditar_cambio_precio()
RETURNS TRIGGER AS $$
BEGIN
    IF NEW.precio <> OLD.precio THEN
        INSERT INTO auditoria_precio (cod_vino, precio_anterior, precio_nuevo, fecha_hora, usuario)
        VALUES (OLD.cod_vino, OLD.precio, NEW.precio, CURRENT_TIMESTAMP, CURRENT_USER);
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trg_auditar_cambio_precio
AFTER UPDATE OF precio ON vino
FOR EACH ROW
EXECUTE FUNCTION fn_trg_auditar_cambio_precio();

-- -----------------------------------------------------------------------------
-- TRIGGER 4: BEFORE INSERT OR UPDATE (RN-06)
-- Regla de Negocio protegida: RN-06 (Descuentos según tipo de cliente: Socio 10%, Distribuidor 20%, Exportador 30%)
-- Explicación: Asigna automáticamente el porcentaje de descuento correspondiente al cliente según su tipo.
-- -----------------------------------------------------------------------------
CREATE OR REPLACE FUNCTION fn_trg_asignar_descuento_cliente()
RETURNS TRIGGER AS $$
BEGIN
    CASE NEW.tipo_cliente
        WHEN 'socio' THEN 
            NEW.porcentaje_descuento := 10.00;
        WHEN 'distribuidor' THEN 
            NEW.porcentaje_descuento := 20.00;
        WHEN 'exportador' THEN 
            NEW.porcentaje_descuento := 30.00;
    END CASE;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trg_asignar_descuento_cliente
BEFORE INSERT OR UPDATE OF tipo_cliente ON cliente
FOR EACH ROW
EXECUTE FUNCTION fn_trg_asignar_descuento_cliente();

-- -----------------------------------------------------------------------------
-- TRIGGER 5: AFTER INSERT OR UPDATE OR DELETE (RN-08)
-- Regla de Negocio protegida: RN-08 (Cálculo y preservación automática de montos en comprobantes)
-- Explicación: Cada vez que cambia un renglón de comprobante, se recalcula el
-- subtotal bruto, el descuento total y el total neto en la cabecera correspondiente.
-- Si un renglón se mueve de comprobante, se recalculan ambas cabeceras.
-- -----------------------------------------------------------------------------
CREATE OR REPLACE FUNCTION fn_trg_actualizar_totales_comprobante()
RETURNS TRIGGER AS $$
DECLARE
    v_nros   INT[];
    v_nro    INT;
    v_bruto  NUMERIC(14,2);
    v_neto   NUMERIC(14,2);
BEGIN
    IF TG_OP = 'DELETE' THEN
        v_nros := ARRAY[OLD.nro_comprobante];
    ELSIF TG_OP = 'UPDATE'
          AND OLD.nro_comprobante IS DISTINCT FROM NEW.nro_comprobante THEN
        v_nros := ARRAY[OLD.nro_comprobante, NEW.nro_comprobante];
    ELSE
        v_nros := ARRAY[NEW.nro_comprobante];
    END IF;

    FOREACH v_nro IN ARRAY v_nros LOOP
        SELECT COALESCE(SUM(cantidad * precio_unitario), 0)
          INTO v_bruto
          FROM renglon_comprobante
         WHERE nro_comprobante = v_nro;

        v_neto := COALESCE(fn_total_comprobante(v_nro), 0.00);

        UPDATE comprobante
           SET subtotal  = v_bruto,
               descuento = v_bruto - v_neto,
               total     = v_neto
         WHERE nro_comprobante = v_nro;
    END LOOP;

    RETURN NULL;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trg_actualizar_totales_comprobante
AFTER INSERT OR UPDATE OR DELETE ON renglon_comprobante
FOR EACH ROW
EXECUTE FUNCTION fn_trg_actualizar_totales_comprobante();

-- -----------------------------------------------------------------------------
-- TRIGGER 6: BEFORE INSERT OR UPDATE (RN-09)
-- Regla de Negocio protegida: RN-09 (No vender más botellas de las disponibles en la sala)
-- Explicación: Calcula el subtotal neto del renglón y valida/bloquea el stock de la
-- sala antes de registrar la venta, serializando operaciones concurrentes.
-- -----------------------------------------------------------------------------
CREATE OR REPLACE FUNCTION fn_trg_validar_stock_venta()
RETURNS TRIGGER AS $$
DECLARE
    v_sala_nueva INTEGER;
    v_sala_vieja INTEGER;
    v_requerido  INTEGER;
    v_disponible INTEGER;
BEGIN
    NEW.subtotal := ROUND(
        NEW.cantidad * NEW.precio_unitario * (1 - NEW.descuento / 100.0), 2
    );

    SELECT id_sala INTO v_sala_nueva
      FROM comprobante
     WHERE nro_comprobante = NEW.nro_comprobante;

    IF TG_OP = 'INSERT' THEN
        v_requerido := NEW.cantidad;
    ELSIF NEW.cod_vino <> OLD.cod_vino THEN
        v_requerido := NEW.cantidad;
    ELSE
        SELECT id_sala INTO v_sala_vieja
          FROM comprobante
         WHERE nro_comprobante = OLD.nro_comprobante;

        IF v_sala_nueva IS DISTINCT FROM v_sala_vieja THEN
            v_requerido := NEW.cantidad;
        ELSE
            v_requerido := NEW.cantidad - OLD.cantidad;
        END IF;
    END IF;

    IF v_requerido > 0 THEN
        -- Bloqueo pesimista: serializa ventas concurrentes del mismo vino/sala
        PERFORM 1
           FROM stock_sala
          WHERE id_sala = v_sala_nueva AND cod_vino = NEW.cod_vino
          FOR UPDATE;

        v_disponible := fn_stock_sala(v_sala_nueva, NEW.cod_vino);

        IF v_disponible < v_requerido THEN
            RAISE EXCEPTION 'Stock insuficiente del vino % en la sala %: disponible %, requerido % (RN-09)',
                NEW.cod_vino, v_sala_nueva, v_disponible, v_requerido
                USING ERRCODE = 'P0001';
        END IF;
    END IF;

    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trg_validar_stock_venta
BEFORE INSERT OR UPDATE ON renglon_comprobante
FOR EACH ROW
EXECUTE FUNCTION fn_trg_validar_stock_venta();

-- -----------------------------------------------------------------------------
-- TRIGGER 7: AFTER INSERT OR UPDATE OR DELETE (RN-09)
-- Regla de Negocio protegida: RN-09 (Actualización automática del stock de la sala)
-- Explicación: Descuenta o repone las botellas vendidas tras confirmarse el renglón.
-- -----------------------------------------------------------------------------
CREATE OR REPLACE FUNCTION fn_trg_actualizar_stock_venta()
RETURNS TRIGGER AS $$
DECLARE
    v_sala_nueva INTEGER;
    v_sala_vieja INTEGER;
BEGIN
    IF TG_OP <> 'DELETE' THEN
        SELECT id_sala INTO v_sala_nueva
          FROM comprobante
         WHERE nro_comprobante = NEW.nro_comprobante;
    END IF;

    IF TG_OP = 'INSERT' THEN
        UPDATE stock_sala
           SET cantidad = cantidad - NEW.cantidad
         WHERE id_sala = v_sala_nueva AND cod_vino = NEW.cod_vino;

    ELSIF TG_OP = 'UPDATE' THEN
        SELECT id_sala INTO v_sala_vieja
          FROM comprobante
         WHERE nro_comprobante = OLD.nro_comprobante;

        IF NEW.nro_comprobante = OLD.nro_comprobante
           AND NEW.cod_vino = OLD.cod_vino
           AND v_sala_nueva = v_sala_vieja THEN
            UPDATE stock_sala
               SET cantidad = cantidad - (NEW.cantidad - OLD.cantidad)
             WHERE id_sala = v_sala_nueva AND cod_vino = NEW.cod_vino;
        ELSE
            UPDATE stock_sala
               SET cantidad = cantidad + OLD.cantidad
             WHERE id_sala = v_sala_vieja AND cod_vino = OLD.cod_vino;

            UPDATE stock_sala
               SET cantidad = cantidad - NEW.cantidad
             WHERE id_sala = v_sala_nueva AND cod_vino = NEW.cod_vino;
        END IF;

    ELSE
        SELECT id_sala INTO v_sala_vieja
          FROM comprobante
         WHERE nro_comprobante = OLD.nro_comprobante;

        -- Si la cabecera ya no existe es un borrado en cascada (purga histórica):
        -- se decide no reponer stock.
        IF FOUND THEN
            UPDATE stock_sala
               SET cantidad = cantidad + OLD.cantidad
             WHERE id_sala = v_sala_vieja AND cod_vino = OLD.cod_vino;
        END IF;
    END IF;

    RETURN NULL;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trg_actualizar_stock_venta
AFTER INSERT OR UPDATE OR DELETE ON renglon_comprobante
FOR EACH ROW
EXECUTE FUNCTION fn_trg_actualizar_stock_venta();

-- -----------------------------------------------------------------------------
-- TRIGGER 8: BEFORE INSERT OR UPDATE (RN-10 / RN-11)
-- Reglas de Negocio protegidas: RN-10 (Ingresos) y RN-11 (Transferencias)
-- Explicación: Fuerza el estado inicial 'en_confeccion' y solo permite las
-- transiciones en_confeccion -> terminado -> procesado.
-- -----------------------------------------------------------------------------
CREATE OR REPLACE FUNCTION fn_trg_validar_transicion_estado()
RETURNS TRIGGER AS $$
BEGIN
    IF TG_OP = 'INSERT' THEN
        IF NEW.estado <> 'en_confeccion' THEN
            RAISE EXCEPTION 'El documento debe crearse en estado en_confeccion (RN-10/RN-11)'
                USING ERRCODE = 'P0001';
        END IF;
        RETURN NEW;
    END IF;

    IF NEW.estado = OLD.estado THEN
        RETURN NEW;
    END IF;

    IF NOT (
        (OLD.estado = 'en_confeccion' AND NEW.estado = 'terminado') OR
        (OLD.estado = 'terminado'     AND NEW.estado = 'procesado')
    ) THEN
        RAISE EXCEPTION 'Transición de estado inválida: % -> % (RN-10/RN-11)',
            OLD.estado, NEW.estado
            USING ERRCODE = 'P0001';
    END IF;

    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trg_validar_estado_ingreso
BEFORE INSERT OR UPDATE ON ingreso
FOR EACH ROW
EXECUTE FUNCTION fn_trg_validar_transicion_estado();

CREATE TRIGGER trg_validar_estado_transferencia
BEFORE INSERT OR UPDATE ON transferencia
FOR EACH ROW
EXECUTE FUNCTION fn_trg_validar_transicion_estado();

-- -----------------------------------------------------------------------------
-- TRIGGER 9: BEFORE INSERT OR UPDATE OR DELETE (RN-12)
-- Regla de Negocio protegida: RN-12 (Los renglones solo se modifican mientras el
-- documento está en confección)
-- Explicación: Valida la cabecera destino/actual y, si un renglón se mueve de
-- documento, también valida la cabecera de origen.
-- -----------------------------------------------------------------------------
CREATE OR REPLACE FUNCTION fn_trg_bloquear_renglon()
RETURNS TRIGGER AS $$
DECLARE
    v_estado   estado_documento;
    v_id       INTEGER;
    v_id_viejo INTEGER;
BEGIN
    IF TG_TABLE_NAME = 'renglon_ingreso' THEN
        v_id := CASE WHEN TG_OP = 'DELETE' THEN OLD.cod_ingreso ELSE NEW.cod_ingreso END;
        IF TG_OP = 'UPDATE' THEN
            v_id_viejo := OLD.cod_ingreso;
        END IF;

        SELECT estado INTO v_estado FROM ingreso WHERE cod_ingreso = v_id;
    ELSE
        v_id := CASE WHEN TG_OP = 'DELETE' THEN OLD.nro_transferencia ELSE NEW.nro_transferencia END;
        IF TG_OP = 'UPDATE' THEN
            v_id_viejo := OLD.nro_transferencia;
        END IF;

        SELECT estado INTO v_estado FROM transferencia WHERE nro_transferencia = v_id;
    END IF;

    -- Borrado en cascada de la cabecera: no bloquear (necesario para D5)
    IF NOT FOUND THEN
        IF TG_OP = 'DELETE' THEN
            RETURN OLD;
        END IF;
        RAISE EXCEPTION 'El documento % no existe (RN-12)', v_id
            USING ERRCODE = 'P0001';
    END IF;

    IF v_estado IS DISTINCT FROM 'en_confeccion' THEN
        RAISE EXCEPTION 'No se puede modificar el renglón: el documento % está en estado % (RN-12)',
            v_id, v_estado
            USING ERRCODE = 'P0001';
    END IF;

    -- Si en un UPDATE el renglón cambia de documento, el documento de origen
    -- también debe estar en confección.
    IF TG_OP = 'UPDATE' AND v_id_viejo IS DISTINCT FROM v_id THEN
        IF TG_TABLE_NAME = 'renglon_ingreso' THEN
            SELECT estado INTO v_estado
              FROM ingreso
             WHERE cod_ingreso = v_id_viejo;
        ELSE
            SELECT estado INTO v_estado
              FROM transferencia
             WHERE nro_transferencia = v_id_viejo;
        END IF;

        IF NOT FOUND THEN
            RAISE EXCEPTION 'El documento de origen % no existe (RN-12)', v_id_viejo
                USING ERRCODE = 'P0001';
        END IF;

        IF v_estado IS DISTINCT FROM 'en_confeccion' THEN
            RAISE EXCEPTION 'No se puede mover el renglón: el documento de origen % está en estado % (RN-12)',
                v_id_viejo, v_estado
                USING ERRCODE = 'P0001';
        END IF;
    END IF;

    IF TG_OP = 'DELETE' THEN
        RETURN OLD;
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trg_bloquear_renglon_ingreso
BEFORE INSERT OR UPDATE OR DELETE ON renglon_ingreso
FOR EACH ROW
EXECUTE FUNCTION fn_trg_bloquear_renglon();

CREATE TRIGGER trg_bloquear_renglon_transferencia
BEFORE INSERT OR UPDATE OR DELETE ON renglon_transferencia
FOR EACH ROW
EXECUTE FUNCTION fn_trg_bloquear_renglon();

-- -----------------------------------------------------------------------------
-- TRIGGER 10: BEFORE INSERT OR UPDATE (RN-11)
-- Regla de Negocio protegida: RN-11 (Fecha de confección actual e inmodificable)
-- Explicación: Fuerza la fecha actual al crear la transferencia y bloquea
-- cualquier intento posterior de modificarla.
-- -----------------------------------------------------------------------------
CREATE OR REPLACE FUNCTION fn_trg_fecha_confeccion_transferencia()
RETURNS TRIGGER AS $$
BEGIN
    IF TG_OP = 'INSERT' THEN
        NEW.fecha_confeccion := CURRENT_DATE;
    ELSIF NEW.fecha_confeccion IS DISTINCT FROM OLD.fecha_confeccion THEN
        RAISE EXCEPTION 'La fecha de confección de una transferencia no se puede modificar (RN-11)'
            USING ERRCODE = 'P0001';
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trg_fecha_confeccion_transferencia
BEFORE INSERT OR UPDATE ON transferencia
FOR EACH ROW
EXECUTE FUNCTION fn_trg_fecha_confeccion_transferencia();

-- -----------------------------------------------------------------------------
-- TRIGGER 11: BEFORE UPDATE OR DELETE (RN-11 / RN-10)
-- Regla de Negocio protegida: RN-11 (Inmutabilidad de transferencias finalizadas/procesadas)
-- Explicación: Impide la modificación o eliminación de transferencias cuyo estado ya sea 'procesado'.
-- -----------------------------------------------------------------------------
CREATE OR REPLACE FUNCTION fn_trg_bloquear_transferencia_procesada()
RETURNS TRIGGER AS $$
BEGIN
    IF TG_OP = 'DELETE' AND OLD.estado = 'procesado' THEN
        RAISE EXCEPTION 'RN-11 VIOLACIÓN: No se puede eliminar una transferencia que ya fue procesada';
    END IF;

    IF TG_OP = 'UPDATE' AND OLD.estado = 'procesado' THEN
        RAISE EXCEPTION 'RN-11 VIOLACIÓN: No se puede modificar una transferencia que ya fue procesada';
    END IF;

    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trg_bloquear_transferencia_procesada
BEFORE UPDATE OR DELETE ON transferencia
FOR EACH ROW
EXECUTE FUNCTION fn_trg_bloquear_transferencia_procesada();

COMMIT;
