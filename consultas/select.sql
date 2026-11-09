-- =============================================================================
-- TPI BASES DE DATOS - UTN FRSR (2026)
-- Etapa 5: Consultas SQL (select.sql)
-- =============================================================================

-- =============================================================================
-- BLOQUE 1: CONSULTAS BÁSICAS S1 A S6 (Responsable: Bruno)
-- =============================================================================

-- === S1 ===
-- Enunciado: Ranking de los 10 vinos con mayor cantidad de botellas vendidas en
--            toda la red de salas.
-- Estrategia: JOIN entre vino y renglon_comprobante, agrupando por código y
--             nombre de vino, sumando las cantidades vendidas y ordenando en
--             forma descendente con LIMIT 10. El desempate por cod_vino garantiza
--             un resultado estable si dos vinos tienen el mismo total.
SELECT
    v.cod_vino,
    v.nombre,
    SUM(rc.cantidad) AS total_botellas
FROM vino v
JOIN renglon_comprobante rc
    ON rc.cod_vino = v.cod_vino
GROUP BY v.cod_vino, v.nombre
ORDER BY total_botellas DESC, v.cod_vino
LIMIT 10;

-- === S2 ===
-- Enunciado: Listar códigos y nombres de los vinos que se vendieron en TODAS
--            las salas (división relacional).
-- Estrategia: División relacional por cardinalidad. Se cruzan vino, renglon_comprobante
--             y comprobante para obtener las salas distintas donde se vendió cada
--             vino; el HAVING exige que esa cantidad sea igual al total de salas
--             registradas en sala_venta. Equivale a la formulación clásica con doble
--             NOT EXISTS, pero resuelta con agregación y una subconsulta escalar.
SELECT
    v.cod_vino,
    v.nombre
FROM vino v
JOIN renglon_comprobante rc
    ON rc.cod_vino = v.cod_vino
JOIN comprobante co
    ON co.nro_comprobante = rc.nro_comprobante
GROUP BY v.cod_vino, v.nombre
HAVING COUNT(DISTINCT co.id_sala) = (SELECT COUNT(*) FROM sala_venta)
ORDER BY v.cod_vino;

-- === S3 ===
-- Enunciado: Cantidad de clientes de cada tipo que compraron en una sala
--            determinada en la última semana.
-- Parámetro: id_sala = 1 (sala de Tupungato).
-- Estrategia: JOIN entre comprobante y cliente, filtro temporal dinámico con
--             CURRENT_DATE - INTERVAL '7 days' y agrupación por tipo_cliente.
--             COUNT(DISTINCT c.id_cliente) evita contar dos veces al mismo cliente
--             si emitió más de un comprobante en el período.
SELECT
    c.tipo_cliente,
    COUNT(DISTINCT c.id_cliente) AS cantidad_clientes
FROM comprobante co
JOIN cliente c
    ON c.id_cliente = co.id_cliente
WHERE co.id_sala = 1
  AND co.fecha >= CURRENT_DATE - INTERVAL '7 days'
GROUP BY c.tipo_cliente
ORDER BY c.tipo_cliente;

-- === S4 ===
-- Enunciado: Top 5 de las salas que solicitaron mayor cantidad de un vino
--            determinado mediante transferencias en los últimos 15 días.
-- Parámetro: cod_vino = 1 (primer vino del catálogo cargado).
-- Estrategia: JOIN entre transferencia, renglon_transferencia y sala_venta,
--             filtro temporal dinámico con CURRENT_DATE - INTERVAL '15 days',
--             suma de rt.cantidad y ordenamiento descendente con LIMIT 5.
SELECT
    s.id_sala,
    s.calle,
    s.numero,
    SUM(rt.cantidad) AS botellas_transferidas
FROM transferencia t
JOIN renglon_transferencia rt
    ON rt.nro_transferencia = t.nro_transferencia
JOIN sala_venta s
    ON s.id_sala = t.id_sala
WHERE rt.cod_vino = 1
  AND t.fecha_confeccion >= CURRENT_DATE - INTERVAL '15 days'
GROUP BY s.id_sala, s.calle, s.numero
ORDER BY botellas_transferidas DESC, s.id_sala
LIMIT 5;

-- === S5 ===
-- Enunciado: Listado de las salas con menor cantidad de transferencias
--            pendientes (no procesadas).
-- Estrategia: LEFT JOIN desde sala_venta hacia transferencia aplicando en la
--             condición del JOIN el filtro estado <> 'procesado'. Así se conservan
--             las salas sin pendientes, que aparecen con 0 mediante COALESCE.
--             Se ordena en forma ascendente para mostrar primero las salas con
--             menor carga pendiente. La vista vw_documentos_pendientes también
--             expone estas transferencias, pero aquí se resume por sala.
SELECT
    s.id_sala,
    s.calle,
    s.numero,
    COALESCE(COUNT(t.nro_transferencia), 0) AS transferencias_pendientes
FROM sala_venta s
LEFT JOIN transferencia t
    ON t.id_sala = s.id_sala
   AND t.estado <> 'procesado'
GROUP BY s.id_sala, s.calle, s.numero
ORDER BY transferencias_pendientes ASC, s.id_sala;

-- === S6 ===
-- Enunciado: Para una sala determinada, listar los vinos sin stock en la sala
--            pero con stock en el depósito central.
-- Parámetro: id_sala = 1 (sala de Tupungato).
-- Estrategia: Se parte de stock_deposito cruzado con vino para considerar solo
--             vinos con existencias en el depósito central. Luego LEFT JOIN con
--             stock_sala restringido a id_sala = 1; el COALESCE(ss.cantidad, 0) = 0
--             cubre tanto los vinos sin fila de stock en la sala como los que
--             tienen cantidad cero.
SELECT
    v.cod_vino,
    v.nombre,
    sd.cantidad AS stock_deposito
FROM stock_deposito sd
JOIN vino v
    ON v.cod_vino = sd.cod_vino
LEFT JOIN stock_sala ss
    ON ss.cod_vino = sd.cod_vino
   AND ss.id_sala = 1
WHERE COALESCE(ss.cantidad, 0) = 0
  AND sd.cantidad > 0
ORDER BY v.cod_vino;


-- =============================================================================
-- BLOQUE 2: CONSULTAS AVANZADAS S7 A S12 Y EXPLAIN (Responsable: Juan Manuel)
-- =============================================================================

-- === S7 ===
-- Enunciado: ¿Cuál es la empresa de transporte con mayor actividad en el último mes?
-- Herramientas: Agrupación, Join, Filtro temporal dinámico, Ordenamiento y Límite.
-- Justificación: Se agrupan los ingresos por transportista filtrando dinámicamente el último mes con CURRENT_DATE.
SELECT t.cod_transporte, t.razon_social, COUNT(i.cod_ingreso) AS cantidad_traslados
FROM transportista t
JOIN ingreso i ON t.cod_transporte = i.cod_transporte
WHERE i.fecha >= CURRENT_DATE - INTERVAL '1 month'
GROUP BY t.cod_transporte, t.razon_social
ORDER BY cantidad_traslados DESC
LIMIT 1;

-- === S8 ===
-- Enunciado: Monto total de ventas por sala en el último trimestre, en orden descendente.
-- Herramientas: Agrupación, Join, Filtro temporal dinámico con INTERVAL.
-- Justificación: Se suma el campo total de los comprobantes asociados a cada sala en los últimos 3 meses.
SELECT s.id_sala, s.calle, s.numero, s.cod_postal, SUM(c.total) AS monto_total_trimestre
FROM sala_venta s
JOIN comprobante c ON s.id_sala = c.id_sala
WHERE c.fecha >= CURRENT_DATE - INTERVAL '3 months'
GROUP BY s.id_sala, s.calle, s.numero, s.cod_postal
ORDER BY monto_total_trimestre DESC;

-- === S9 ===
-- Enunciado: Ficha de un vino (cepas con %, bodega, maridajes y stock total).
-- Herramientas: CTE (Common Table Expressions), STRING_AGG, Joins, subconsultas y cruce con Vista.
-- Justificación: Se usan CTEs para aislar la concatenación de relaciones 1:N (cepas y maridajes) y evitar productos cartesianos al cruzar con la vista de stock.
/* 
EXPLAIN (ANALYZE, BUFFERS) PLAN OBTENIDO:
Nested Loop Left Join  (cost=100.40..105.76 rows=6 width=128) (actual time=6.369..6.405 rows=1 loops=1)
   Buffers: shared hit=100
   ->  Nested Loop  (cost=3.24..8.33 rows=1 width=124) (actual time=1.478..1.512 rows=1 loops=1)
         Buffers: shared hit=6
   ->  GroupAggregate  (cost=97.16..97.31 rows=6 width=94) (actual time=4.867..4.869 rows=1 loops=1)
         Buffers: shared hit=94
Planning Time: 9.361 ms
Execution Time: 7.293 ms
*/
WITH CepasVino AS (
    SELECT cv.cod_vino, STRING_AGG(c.nombre || ' (' || cv.porcentaje || '%)', ', ') AS composicion
    FROM composicion_vino cv
    JOIN cepa c ON cv.id_cepa = c.id_cepa
    GROUP BY cv.cod_vino
),
MaridajesVino AS (
    SELECT vm.cod_vino, STRING_AGG(m.nombre, ', ') AS maridajes
    FROM vino_maridaje vm
    JOIN maridaje m ON vm.id_maridaje = m.id_maridaje
    GROUP BY vm.cod_vino
)
SELECT 
    v.cod_vino, 
    v.nombre AS vino, 
    b.razon_social AS bodega, 
    cv.composicion, 
    mv.maridajes, 
    vw.stock_total
FROM vino v
JOIN bodega b ON v.cuit_bodega = b.cuit
LEFT JOIN CepasVino cv ON v.cod_vino = cv.cod_vino
LEFT JOIN MaridajesVino mv ON v.cod_vino = mv.cod_vino
LEFT JOIN vw_stock_total_vino vw ON v.cod_vino = vw.cod_vino
WHERE v.cod_vino = 1;

-- === S10 ===
-- Enunciado: Rendimiento en kg/ha por parcela y campaña, identificando las que rinden menos que el promedio de su finca.
-- Herramientas: CTE, Función de Ventana (AVG OVER PARTITION).
-- Justificación: La CTE calcula el rendimiento individual. Luego la Window Function calcula el promedio por finca y campaña, permitiendo filtrar en la consulta principal las parcelas por debajo de la media.
/*
EXPLAIN (ANALYZE, BUFFERS) PLAN OBTENIDO:
Incremental Sort  (cost=15.54..24.48 rows=60 width=87) (actual time=0.521..0.631 rows=89 loops=1)
   Buffers: shared hit=7
   ->  Subquery Scan on promediofinca  (cost=15.36..22.41 rows=60 width=87) (actual time=0.416..0.565 rows=89 loops=1)
         Buffers: shared hit=4
Planning Time: 1.817 ms
Execution Time: 0.825 ms
*/
WITH RendimientoParcela AS (
    SELECT 
        p.id_finca, 
        f.nombre AS finca, 
        p.nro_parcela, 
        l.campania, 
        (l.kilos / p.superficie_ha) AS rinde_kg_ha
    FROM parcela p
    JOIN finca f ON p.id_finca = f.id_finca
    JOIN lote_uva l ON p.id_finca = l.id_finca AND p.nro_parcela = l.nro_parcela
),
PromedioFinca AS (
    SELECT 
        *, 
        AVG(rinde_kg_ha) OVER (PARTITION BY id_finca, campania) AS promedio_finca
    FROM RendimientoParcela
)
SELECT id_finca, finca, nro_parcela, campania, ROUND(rinde_kg_ha, 2) AS rinde_kg_ha, ROUND(promedio_finca, 2) AS promedio_finca
FROM PromedioFinca
WHERE rinde_kg_ha < promedio_finca
ORDER BY id_finca, campania, nro_parcela;

-- === S11 ===
-- Enunciado: Ranking de vinos por sala (S11-A) y ventas acumuladas mensuales por sala (S11-B).
-- Herramientas: Window Functions (RANK y SUM OVER PARTITION).
-- Justificación: Se resuelven en dos bloques distintos. S11-A usa RANK() particionando por sala. S11-B usa SUM() acumulativo particionando por sala y ordenando por el mes.
/*
EXPLAIN (ANALYZE, BUFFERS) PLAN OBTENIDO (S11-A):
Incremental Sort  (cost=18724.38..19430.25 rows=9600 width=56) (actual time=324.229..329.376 rows=240 loops=1)
   Buffers: shared hit=6311
Planning Time: 2.874 ms
Execution Time: 330.233 ms

EXPLAIN (ANALYZE, BUFFERS) PLAN OBTENIDO (S11-B):
Incremental Sort  (cost=4419.78..4482.77 rows=348 width=80) (actual time=41.837..45.926 rows=348 loops=1)
   Buffers: shared hit=1420
Planning Time: 0.817 ms
Execution Time: 46.286 ms
*/
-- S11-A: Ranking de vinos por botellas vendidas dentro de cada sala
SELECT 
    c.id_sala, 
    rc.cod_vino, 
    v.nombre, 
    SUM(rc.cantidad) AS botellas_vendidas,
    RANK() OVER (PARTITION BY c.id_sala ORDER BY SUM(rc.cantidad) DESC) AS ranking_en_sala
FROM comprobante c
JOIN renglon_comprobante rc ON c.nro_comprobante = rc.nro_comprobante
JOIN vino v ON rc.cod_vino = v.cod_vino
GROUP BY c.id_sala, rc.cod_vino, v.nombre
ORDER BY c.id_sala, ranking_en_sala;

-- S11-B: Facturación mensual y suma acumulada por sala
SELECT 
    id_sala, 
    DATE_TRUNC('month', fecha)::DATE AS mes, 
    SUM(total) AS facturacion_mes,
    SUM(SUM(total)) OVER (PARTITION BY id_sala ORDER BY DATE_TRUNC('month', fecha)) AS facturacion_acumulada
FROM comprobante
GROUP BY id_sala, DATE_TRUNC('month', fecha)
ORDER BY id_sala, mes;

-- === S12 ===
-- Enunciado: Clientes que compraron TODOS los vinos de una bodega, y clientes que NUNCA compraron tinto.
-- Herramientas: División relacional estricta (Doble NOT EXISTS) y Anti-Join (NOT EXISTS simple).
-- Justificación: Cumple el estándar de división relacional buscando "clientes para los cuales NO EXISTE un vino de la bodega que NO HAYAN comprado".
/*
EXPLAIN (ANALYZE, BUFFERS) PLAN OBTENIDO (S12-A):
Nested Loop Anti Join  (cost=0.00..380586.79 rows=500 width=22) (actual time=251.270..836.355 rows=1000 loops=1)
   Buffers: shared hit=1044088
Planning Time: 1.665 ms
Execution Time: 1413.117 ms

EXPLAIN (ANALYZE, BUFFERS) PLAN OBTENIDO (S12-B):
Nested Loop Anti Join  (cost=2.33..1575.42 rows=1 width=22) (actual time=4.006..4.008 rows=0 loops=1)
   Buffers: shared hit=7017
Planning Time: 1.534 ms
Execution Time: 4.111 ms
*/
-- S12-A: Compraron TODOS los vinos de la bodega 20624731781 (Bodega Ferreyra PLC)
SELECT c.id_cliente, c.nombre_razon_social
FROM cliente c
WHERE NOT EXISTS (
    SELECT 1 FROM vino v
    WHERE v.cuit_bodega = '20624731781'
    AND NOT EXISTS (
        SELECT 1 FROM comprobante comp
        JOIN renglon_comprobante rc ON comp.nro_comprobante = rc.nro_comprobante
        WHERE comp.id_cliente = c.id_cliente AND rc.cod_vino = v.cod_vino
    )
);

-- S12-B: NUNCA compraron vino tinto
SELECT c.id_cliente, c.nombre_razon_social
FROM cliente c
WHERE NOT EXISTS (
    SELECT 1 FROM comprobante comp
    JOIN renglon_comprobante rc ON comp.nro_comprobante = rc.nro_comprobante
    JOIN vino v ON rc.cod_vino = v.cod_vino
    WHERE comp.id_cliente = c.id_cliente AND v.tipo = 'tinto'
);
