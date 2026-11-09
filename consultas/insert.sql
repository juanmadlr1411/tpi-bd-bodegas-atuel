-- ==============================================================================
-- TPI BODEGAS DEL ATUEL - ETAPA 5: CONSULTAS SQL (INSERT)
-- RESPONSABLE: Manuel (Datos)
-- ==============================================================================

-- ------------------------------------------------------------------------------
-- Insertar nueva cobertura en transportista_localidad para Gral. Alvear ('5501') 
-- con el transportista que menos ingresos trasladó en el último trimestre.
-- ------------------------------------------------------------------------------
BEGIN;
DO $$ 
DECLARE 
    v_transporte INT;
BEGIN
    -- Estrategia: Buscar el transportista con menos viajes cruzando con ingresos recientes
    SELECT t.cod_transporte INTO v_transporte
    FROM transportista t
    LEFT JOIN ingreso i ON t.cod_transporte = i.cod_transporte 
                        AND i.fecha >= (CURRENT_DATE - INTERVAL '3 months')
    GROUP BY t.cod_transporte
    ORDER BY COUNT(i.cod_ingreso) ASC, t.cod_transporte ASC
    LIMIT 1;

    IF v_transporte IS NULL THEN
        RAISE NOTICE 'AVISO: No hay transportistas cargados en la BD. Omitiendo inserción.';
    ELSE
        INSERT INTO transportista_localidad (cod_transporte, cod_postal)
        VALUES (v_transporte, '5501');
        RAISE NOTICE 'ÉXITO: Cobertura insertada para transportista %', v_transporte;
    END IF;
END $$;
-- Control posterior (mostrará la fila si se insertó, o vacío si no había datos)
SELECT * FROM transportista_localidad WHERE cod_postal = '5501';
ROLLBACK;


-- ------------------------------------------------------------------------------
-- Crear maridaje "cordero al disco" si existe vino tinto >= 14° y asociarlo
-- ------------------------------------------------------------------------------
BEGIN;
DO $$
DECLARE
    v_id_maridaje INT;
    v_vinos_afectados INT;
BEGIN
    -- 1. Control previo: Verificar existencia de la condición
    IF EXISTS (SELECT 1 FROM vino WHERE tipo = 'tinto' AND graduacion >= 14.00) THEN
        
        -- Insertar el nuevo maridaje y capturar su ID autogenerado
        INSERT INTO maridaje (nombre, temperatura_servicio)
        VALUES ('cordero al disco', 18)
        RETURNING id_maridaje INTO v_id_maridaje;

        RAISE NOTICE 'Maridaje "cordero al disco" creado con ID: %', v_id_maridaje;

        -- Asociarlo a todos los vinos que cumplen la condición
        INSERT INTO vino_maridaje (cod_vino, id_maridaje)
        SELECT cod_vino, v_id_maridaje
        FROM vino
        WHERE tipo = 'tinto' AND graduacion >= 14.00;

        GET DIAGNOSTICS v_vinos_afectados = ROW_COUNT;
        RAISE NOTICE 'ÉXITO: Se asoció el maridaje a % vinos.', v_vinos_afectados;
    ELSE
        RAISE NOTICE 'AVISO: No existen vinos tintos >= 14°. No se creó el maridaje.';
    END IF;
END $$;
-- Control posterior
SELECT * FROM maridaje WHERE nombre = 'cordero al disco';
ROLLBACK;


-- ------------------------------------------------------------------------------
-- Crear comprobante con 3 renglones para un cliente dado en sala 1
-- ------------------------------------------------------------------------------
BEGIN;
DO $$
DECLARE
    v_nro_comprobante INT;
    v_id_cliente INT;
    v_renglones INT;
BEGIN
    -- Tomar un cliente cualquiera para la prueba
    SELECT id_cliente INTO v_id_cliente FROM cliente LIMIT 1;
    
    IF v_id_cliente IS NULL THEN
        RAISE NOTICE 'AVISO: No hay clientes en la BD. Omitiendo generación de comprobante.';
    ELSE
        -- Insertar cabecera del comprobante
        INSERT INTO comprobante (id_cliente, id_sala, fecha)
        VALUES (v_id_cliente, 1, CURRENT_DATE)
        RETURNING nro_comprobante INTO v_nro_comprobante;
        
        RAISE NOTICE 'Comprobante creado con Nro: %', v_nro_comprobante;

        -- Insertar 3 renglones (buscando vinos que sí tengan stock en la sala 1)
        INSERT INTO renglon_comprobante (nro_comprobante, cod_vino, cantidad, precio_unitario, descuento)
        SELECT
            v_nro_comprobante,
            ss.cod_vino,
            1,
            v.precio,
            fn_descuento_cliente(v_id_cliente)
        FROM stock_sala ss
        JOIN vino v ON v.cod_vino = ss.cod_vino
        WHERE ss.id_sala = 1 AND ss.cantidad >= 1
        LIMIT 3;

        GET DIAGNOSTICS v_renglones = ROW_COUNT;
        
        IF v_renglones = 0 THEN
            RAISE NOTICE 'AVISO: No hay stock suficiente en la sala 1 para armar los renglones.';
        ELSE
            RAISE NOTICE 'ÉXITO: Se insertaron % renglones. Los triggers ya descontaron stock y actualizaron totales.', v_renglones;
        END IF;
    END IF;
END $$;
-- Control posterior (traemos el último comprobante creado en la transacción para verificar)
SELECT nro_comprobante, id_cliente, total FROM comprobante ORDER BY nro_comprobante DESC LIMIT 1;
ROLLBACK;

-- ------------------------------------------------------------------------------
-- Insertar una nueva bodega
-- Estrategia: Inserción validando existencia y respetando el dominio cuit_dom
-- ------------------------------------------------------------------------------
BEGIN;
DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM bodega WHERE cuit = '30112233445') THEN
        RAISE NOTICE 'AVISO: La bodega con CUIT 30112233445 ya existe. Omitiendo inserción.';
    ELSE
        INSERT INTO bodega (cuit, razon_social, domicilio)
        VALUES ('30112233445', 'Bodega Los Toneles Etapa 5', 'Ruta Nacional 143 Km 15');
        RAISE NOTICE 'ÉXITO: Bodega "Los Toneles Etapa 5" insertada respetando dominios y unique constraints.';
    END IF;
END $$;
-- Control posterior
SELECT cuit, razon_social, domicilio FROM bodega WHERE cuit = '30112233445';
ROLLBACK;


-- ------------------------------------------------------------------------------
-- Insertar una nueva sala de venta
-- Estrategia: Buscar localidad existente para la FK. Respetar numero > 0 y tipo ENUM.
-- ------------------------------------------------------------------------------
BEGIN;
DO $$
DECLARE
    v_cp VARCHAR(10);
BEGIN
    -- Buscamos una localidad cualquiera existente para no violar la FK
    SELECT cod_postal INTO v_cp FROM localidad LIMIT 1;
    
    IF v_cp IS NULL THEN
        RAISE NOTICE 'AVISO: No hay localidades en la BD. Omitiendo inserción de sala de venta.';
    ELSE
        INSERT INTO sala_venta (calle, numero, dia_cierre, cod_postal)
        -- Usamos 'lunes' respetando el ENUM dia_semana y 1200 respetando CHECK numero > 0
        VALUES ('Avenida Mitre', 1200, 'lunes', v_cp);
        
        RAISE NOTICE 'ÉXITO: Sala de venta insertada en la localidad con CP %', v_cp;
    END IF;
END $$;
-- Control posterior
SELECT * FROM sala_venta WHERE calle = 'Avenida Mitre' AND numero = 1200;
ROLLBACK;


-- ------------------------------------------------------------------------------
-- Crear un ingreso en confección de 120 botellas de un vino determinado
-- Estrategia: Insertar cabecera con estado 'en_confeccion' (RN-10) y luego el renglón.
-- El trigger RN-12 debe permitirlo sin error porque no está 'ingresado'.
-- ------------------------------------------------------------------------------
BEGIN;
DO $$
DECLARE
    v_bodega VARCHAR(15);
    v_transporte INT;
    v_vino INT;
    v_ingreso INT;
BEGIN
    -- Buscamos IDs existentes para no romper las Foreign Keys
    SELECT cuit INTO v_bodega FROM bodega LIMIT 1;
    SELECT cod_transporte INTO v_transporte FROM transportista LIMIT 1;
    SELECT cod_vino INTO v_vino FROM vino LIMIT 1;

    IF v_bodega IS NULL OR v_transporte IS NULL OR v_vino IS NULL THEN
        RAISE NOTICE 'AVISO: Faltan datos maestros (Bodega, Transporte o Vino). Omitiendo ingreso.';
    ELSE
        -- Insertar cabecera en estado 'en_confeccion'
        INSERT INTO ingreso (fecha, estado, cod_transporte, cuit_bodega)
        VALUES (CURRENT_DATE, 'en_confeccion', v_transporte, v_bodega)
        RETURNING cod_ingreso INTO v_ingreso;

        -- Insertar el renglón con las 120 botellas
        INSERT INTO renglon_ingreso (cod_ingreso, cod_vino, cantidad)
        VALUES (v_ingreso, v_vino, 120);

        RAISE NOTICE 'ÉXITO: Ingreso Nro % creado con 120 botellas. El trigger RN-12 permitió la carga porque el estado es "en_confeccion".', v_ingreso;
    END IF;
END $$;
-- Control posterior: verificamos la cabecera y el detalle insertados
SELECT i.cod_ingreso, i.estado, r.cantidad, r.cod_vino 
FROM ingreso i 
JOIN renglon_ingreso r ON i.cod_ingreso = r.cod_ingreso 
ORDER BY i.cod_ingreso DESC LIMIT 1;
ROLLBACK;