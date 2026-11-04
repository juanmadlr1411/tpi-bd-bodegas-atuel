-- =======================================================================================
-- HITO 2: SCRIPT DE PRUEBAS UNITARIAS (QA)
-- Autor: Juan Manuel (Infraestructura y QA)
-- Objetivo: Validar Reglas de Negocio (RN) mediante casos de éxito y falla esperada.
-- =======================================================================================

-- ---------------------------------------------------------------------------------------
-- TEST 1: RN-09 (Validación de stock en venta) - FALLA ESPERADA
-- Disparador: Trigger BEFORE INSERT en renglon_comprobante (Manuel/Bruno)
-- Error esperado: Rechazo por stock insuficiente en la sala.
-- ---------------------------------------------------------------------------------------
BEGIN;
    -- Intentamos vender 5000 botellas de un vino que sabemos que no tiene ese stock
    INSERT INTO renglon_comprobante (id_comprobante, id_vino, cantidad, precio_unitario)
    VALUES (1, 1, 5000, 15000);
ROLLBACK;


-- ---------------------------------------------------------------------------------------
-- TEST 2: RN-05 (Suma de porcentajes de corte) - ÉXITO ESPERADO
-- Disparador: CONSTRAINT TRIGGER DEFERRABLE (Manuel)
-- Comportamiento esperado: La transacción hace COMMIT exitosamente porque suma 100%.
-- ---------------------------------------------------------------------------------------
BEGIN;
    INSERT INTO composicion_vino (id_vino, id_cepa, porcentaje) VALUES (2, 1, 60.00);
    INSERT INTO composicion_vino (id_vino, id_cepa, porcentaje) VALUES (2, 2, 40.00);
COMMIT;


-- ---------------------------------------------------------------------------------------
-- TEST 3: RN-12 (Bloqueo de renglones) - FALLA ESPERADA
-- Disparador: Trigger BEFORE UPDATE en renglon_ingreso (Bruno)
-- Error esperado: No admite cambios si el documento ya no está 'en_confeccion'.
-- ---------------------------------------------------------------------------------------
BEGIN;
    -- Intentamos modificar la cantidad de un renglón que pertenece a un ingreso 'procesado'
    UPDATE renglon_ingreso 
    SET cantidad = 150 
    WHERE id_ingreso = 2; -- Asumiendo que el ingreso 2 está procesado
ROLLBACK;


-- ---------------------------------------------------------------------------------------
-- TEST 4: CHECK Básico (Precio > 0) - FALLA ESPERADA
-- Disparador: Restricción CHECK en tabla vino (Punto 1 de la rúbrica)
-- Error esperado: Violación del constraint CHECK (precio_sugerido > 0).
-- ---------------------------------------------------------------------------------------
BEGIN;
    UPDATE vino SET precio_sugerido = -500 WHERE id_vino = 1;
ROLLBACK;

