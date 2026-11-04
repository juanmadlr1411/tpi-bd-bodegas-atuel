-- =============================================================================
-- TPI BASES DE DATOS - UTN FRSR (2026)
-- Proyecto: Bodegas del Atuel
-- Archivo: db/migrations/005_triggers.sql (Etapa 2 - H2: Business Logic & Triggers)
-- Responsable: Br1 (Integrante 3)
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
-- Explicación: Cada vez que cambia un renglón de comprobante, se recalcula el subtotal,
-- descuento aplicable y total neto en la cabecera correspondiente.
-- -----------------------------------------------------------------------------
CREATE OR REPLACE FUNCTION fn_trg_actualizar_totales_comprobante()
RETURNS TRIGGER AS $$
DECLARE
    v_nro_comprobante INT;
    v_subtotal NUMERIC(14,2);
    v_pct_descuento NUMERIC(5,2);
    v_monto_descuento NUMERIC(14,2);
BEGIN
    v_nro_comprobante := COALESCE(NEW.nro_comprobante, OLD.nro_comprobante);

    SELECT COALESCE(SUM(subtotal), 0) INTO v_subtotal
    FROM renglon_comprobante
    WHERE nro_comprobante = v_nro_comprobante;

    SELECT c.porcentaje_descuento INTO v_pct_descuento
    FROM comprobante comp
    JOIN cliente c ON comp.id_cliente = c.id_cliente
    WHERE comp.nro_comprobante = v_nro_comprobante;

    v_monto_descuento := ROUND(v_subtotal * (COALESCE(v_pct_descuento, 0) / 100.00), 2);

    UPDATE comprobante
    SET subtotal = v_subtotal,
        descuento = v_monto_descuento,
        total = v_subtotal - v_monto_descuento
    WHERE nro_comprobante = v_nro_comprobante;

    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trg_actualizar_totales_comprobante
AFTER INSERT OR UPDATE OR DELETE ON renglon_comprobante
FOR EACH ROW
EXECUTE FUNCTION fn_trg_actualizar_totales_comprobante();

-- -----------------------------------------------------------------------------
-- TRIGGER 6: BEFORE UPDATE OR DELETE (RN-11 / RN-10)
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