## 1. Índices sobre Claves Foráneas (FK) - Responsable: Manuel

A diferencia de las claves primarias (PK), PostgreSQL **no indexa automáticamente** las claves foráneas (FK). Esto significa que cualquier cruce (`JOIN`) o verificación de integridad referencial obliga al motor a realizar un costoso escaneo secuencial completo (`Seq Scan`) de la tabla. Esto es especialmente crítico en operaciones de borrado (`ON DELETE RESTRICT`), donde se debe recorrer toda la tabla dependiente para asegurar que no haya registros vinculados.

Para evitar estos escaneos secuenciales y optimizar el rendimiento para la Etapa 5, se implementaron los siguientes índices B-Tree:

* **`idx_fk_comprobante_cliente`**: Evita escaneos completos al cruzar la tabla de clientes con los más de 150.000 comprobantes. Optimiza drásticamente las consultas **S3** y **S12**, las sentencias de eliminación **D1** y **D4**, y acelera los chequeos de `ON DELETE RESTRICT`.
* **`idx_fk_renglon_transf_vino`**: Optimiza los filtros y agrupaciones directas por vino sobre los 15.004 renglones de transferencia, impactando de forma directa en el rendimiento de la consulta **S4**.
* **`idx_fk_ingreso_transporte`**: Acelera los cruces por empresa transportista, reduciendo el costo de las agrupaciones necesarias para la consulta **S7** y la inserción **I1**.

*(Nota: La creación del índice sobre `renglon_comprobante(cod_vino)` fue omitida intencionalmente en esta sección, ya que será abordada mediante un índice Covering con cláusula `INCLUDE` en el bloque correspondiente a Santiago).*

---

## 2. Índice Compuesto, Índice Parcial e Índice Descartado - Responsable: Gonzalo

### 2.1 Índice Compuesto (`idx_comprobante_sala_fecha`) y Justificación del Orden de Columnas
Se implementó el índice compuesto B-Tree sobre la tabla `comprobante` (150.000 registros):

```sql
CREATE INDEX IF NOT EXISTS idx_comprobante_sala_fecha
    ON comprobante (id_sala, fecha);
```

* **Justificación del orden `(id_sala, fecha)` frente a `(fecha, id_sala)` (Paso 6):**
  * **Regla de Igualdad antes que Rango:** En un árbol B-Tree multicolumna, las columnas evaluadas por igualdad (`WHERE id_sala = 1`) deben ubicarse a la izquierda y las evaluadas por rango (`AND fecha >= CURRENT_DATE - INTERVAL '7 days'`) a la derecha. Con `(id_sala, fecha)`, el motor navega directamente a la sub-rama de la sala buscada y recorre de forma contigua las hojas ordenadas cronológicamente dentro de esa sala.
  * **Qué ocurriría si se invirtiera a `(fecha, id_sala)`:** Al aplicar primero una condición de rango sobre `fecha`, el segundo nivel del índice (`id_sala`) deja de estar globalmente ordenado para todas las fechas del intervalo. El planificador tendría que inspeccionar todas las entradas del rango de fechas de todas las salas de la red y filtrar `id_sala` entrada por entrada.
  * **Reutilización por prefijo izquierdo:** Al estar `id_sala` en primer lugar, este mismo índice también sirve como índice de clave foránea para joins o agrupaciones únicamente por `id_sala` (como en **S8**), evitando crear un segundo índice separado sobre `comprobante (id_sala)`.

### 2.2 Índice Parcial con Cláusula `WHERE` (`idx_transferencia_pendientes`)
Se implementó un índice parcial sobre la tabla `transferencia` (5.004 registros):

```sql
CREATE INDEX IF NOT EXISTS idx_transferencia_pendientes
    ON transferencia (id_sala, fecha_confeccion)
    WHERE estado <> 'procesado';
```

* **Justificación técnica:** En la operación del sistema, más del 99,9 % del historial de transferencias (5.000 de 5.004 filas) se encuentra en su estado final `'procesado'` (inmutable por **RN-11**). Sin embargo, las consultas operativas en tiempo real —como la vista `vw_documentos_pendientes` y la consulta **S5** (*salas con menor cantidad de transferencias pendientes*)— solo buscan documentos en `'en_confeccion'` o `'terminado'`. El predicado `WHERE estado <> 'procesado'` excluye del árbol B-Tree todo el historial cerrado, reduciendo el tamaño del índice en más de un 99 % y evitando su mantenimiento cuando un documento ya está procesado.

### 2.3 Índice Evaluado y Descartado (Paso 6)
Durante el análisis se evaluó crear un índice B-Tree sobre el tipo de vino:

```sql
-- ÍNDICE DESCARTADO (No incluido en 008_indices.sql)
CREATE INDEX idx_vino_tipo ON vino (tipo);
```

* **Motivos del descarte:**
  1. **Baja selectividad (baja cardinalidad):** El tipo enumerado `tipo_vino` solo admite 4 valores (`'tinto'`, `'blanco'`, `'rosado'`, `'espumante'`), distribuidos de manera uniforme (~25 % de la tabla por cada valor). Cuando un filtro devuelve una fracción tan alta de las filas, a PostgreSQL le resulta más costoso recorrer el índice y realizar saltos aleatorios al *heap* que leer las páginas secuencialmente.
  2. **Bajo volumen de la tabla (`vino` tiene 300 filas):** Los 300 registros completos de `vino` caben en apenas 4 páginas de disco de 8 KB. El optimizador de costos siempre elegirá un `Seq Scan` en memoria, por lo que el índice jamás sería utilizado en planes de lectura y solo agregaría sobrecarga de escritura y almacenamiento.

---

## 3. Costo de Escritura y Almacenamiento de los Índices (Paso 7) - Responsable: Bruno

### 3.1 Objetivo y metodología

Los índices aceleran las lecturas, pero **no son gratuitos**: cada `INSERT`, `UPDATE` y `DELETE` debe mantener actualizadas las estructuras auxiliares. Para cuantificar ese costo se agregó el script reproducible `db/seed/medir_costo_escritura_h4.py`, que inserta **exactamente el mismo lote determinista** (semilla `2026`) en dos escenarios:

* **Escenario A (solo `PRIMARY KEY`):** se eliminan dentro de la transacción todos los índices definidos en `008_indices.sql`.
* **Escenario B (`PRIMARY KEY` + índices de `008_indices.sql`):** se crean dentro de la transacción los cinco índices del archivo (B-Tree sobre FK, B-Tree compuesto y B-Tree parcial).

La base local de la medición no tenía otros índices secundarios sobre `comprobante` ni `renglon_comprobante`, por lo que el escenario A quedó efectivamente con **solo las claves primarias**. Si existieran índices ajenos a `008_indices.sql`, el script los detecta y advierte que permanecen activos en ambos escenarios.

El lote está formado por **50.000 comprobantes** y **50.000 renglones** (un renglón por comprobante), enviados en lotes de 5.000 filas mediante `INSERT` multirregistro. Para aislar el costo de mantenimiento de índices, el script deshabilita **solo los triggers de usuario** de `comprobante` y `renglon_comprobante` dentro de la transacción (`ALTER TABLE ... DISABLE TRIGGER USER`). Las claves primarias, claves foráneas, restricciones `CHECK`/`UNIQUE` y los triggers internos de integridad referencial permanecen activos.

Ambos escenarios finalizan con **`ROLLBACK`**: no se conservan filas, índices ni cambios de activación de triggers. La medición se repitió **5 veces** y se informa la **mediana** para reducir el ruido de una máquina con carga concurrente. El script requiere las migraciones `001` a `007` y los datos maestros cargados; **no requiere que `008_indices.sql` esté aplicado**, porque crea y elimina esos índices dentro de la transacción.

```bash
python db/seed/medir_costo_escritura_h4.py \
    --filas 50000 --repeticiones 5 --lote 5000 \
    --salida-json /tmp/medicion_h4.json
```

> Si el puerto `5432` está ocupado por otro PostgreSQL del host, ejecutar con
> `POSTGRES_PORT=5433 python db/seed/medir_costo_escritura_h4.py ...`.

### 3.2 Resultados de tiempo de escritura

Medición local sobre PostgreSQL 16.15 (contenedor Docker), con los datos maestros cargados y las tablas `comprobante`/`renglon_comprobante` vacías antes de cada repetición. El lote es idéntico en ambos escenarios.

| Operación | Escenario A (solo PK) | Escenario B (PK + 008) | Sobrecarga |
| :--- | ---: | ---: | ---: |
| `INSERT` de 50.000 comprobantes | **12,8783 s** | **13,6820 s** | **+6,24 %** |
| `INSERT` de 50.000 renglones (control) | 15,6054 s | 15,5745 s | -0,20 % (ruido) |
| **Total del lote (100.000 filas)** | **28,5805 s** | **29,2565 s** | **+2,37 %** |

La fila de `renglon_comprobante` funciona como **control**: esa tabla no recibe ningún índice nuevo en `008_indices.sql`, por lo que su tiempo debe permanecer estable. La diferencia observada (-0,20 %) está dentro del ruido de la máquina y confirma que la sobrecarga proviene de los dos índices nuevos sobre `comprobante`, no del método de inserción.

### 3.3 Resultados de almacenamiento en disco

El script mide `pg_relation_size` (heap) y `pg_indexes_size` (todos los índices de la tabla), y además el tamaño individual de cada índice con `pg_relation_size(indexrelid)`. La siguiente tabla muestra el **incremento atribuible al lote de 50.000 comprobantes** y el tamaño total de cada índice de `008_indices.sql` en la base medida:

| Índice | Tabla | Tipo | Tamaño total | Incremento por el lote |
| :--- | :--- | :--- | ---: | ---: |
| `idx_fk_comprobante_cliente` | `comprobante` | B-Tree (FK) | 0,54 MB | **0,53 MB** |
| `idx_comprobante_sala_fecha` | `comprobante` | B-Tree compuesto | 0,75 MB | **0,74 MB** |
| `idx_fk_renglon_transf_vino` | `renglon_transferencia` | B-Tree (FK) | 0,01 MB | no participa del lote |
| `idx_fk_ingreso_transporte` | `ingreso` | B-Tree (FK) | 0,01 MB | no participa del lote |
| `idx_transferencia_pendientes` | `transferencia` | B-Tree parcial | 0,01 MB | no participa del lote |
| **Total índices de 008** | | | **1,32 MB** | **1,27 MB sobre `comprobante`** |

El heap del lote ocupó 2,88 MB en `comprobante` y 3,23 MB en `renglon_comprobante`. Es decir, los dos índices nuevos agregaron **1,27 MB**, aproximadamente un **44 % adicional** respecto del heap de la cabecera (2,88 MB). En la base histórica completa, el tamaño total de los índices escala con las 150.000 filas de `comprobante`; lo que se mide aquí es el **costo marginal por lote**, que se mantiene aunque cambie el volumen previo.

> En la base local de esta medición, `transferencia`, `ingreso` y `renglon_transferencia` también estaban vacías, por eso sus índices muestran 0,01 MB. En la base histórica completa (5.000 ingresos, 5.000 transferencias y 15.000 renglones de transferencia) esos índices serán mayores, aunque no participan del lote de comprobantes y no afectan la comparación de escritura.

### 3.4 Por qué cada operación debe actualizar las hojas de los índices

#### `INSERT`

Cada fila nueva debe generar una entrada en **todos** los índices cuyas columnas clave sean afectadas:

* **B-Tree:** el motor desciende desde la raíz comparando la clave hasta ubicar la **página hoja** correspondiente y inserta el par `(clave, TID)` en orden. Si la hoja está llena, se produce un **page split**: se asigna una página nueva, se mueven aproximadamente la mitad de las entradas y se propaga una clave separadora al nivel superior; el split puede ascender hasta la raíz. Por eso el costo por fila es `O(log n)` por índice, pero con escrituras aleatorias y posibles divisiones de página. En el lote medido, `comprobante` recibe 50.000 entradas nuevas en la PK, 50.000 en `idx_fk_comprobante_cliente` y 50.000 en `idx_comprobante_sala_fecha`; `renglon_comprobante` recibe 50.000 en su PK.
* **Índice compuesto:** `idx_comprobante_sala_fecha` almacena `(id_sala, fecha)` en cada hoja. La entrada es más ancha que la de un índice de una sola columna, por eso ocupa más (0,74 MB frente a 0,53 MB) y su mantenimiento es algo más costoso. A cambio, sirve tanto para filtros por `(id_sala, fecha)` como por el prefijo `id_sala`, evitando un índice separado sobre `id_sala`.
* **Índice parcial:** `idx_transferencia_pendientes` solo indexa las filas que cumplen `estado <> 'procesado'`. Un `INSERT` de una transferencia ya procesada **no crea entrada** en este índice; por eso su costo de escritura y su tamaño son mínimos. En la medición no se insertaron transferencias, de ahí su tamaño de 0,01 MB.
* **BRIN (no usado en 008):** un BRIN no guarda una entrada por fila, sino **resúmenes de rangos de bloques** (mínimo/máximo). Un `INSERT` solo actualiza el resumen del rango donde cae la fila, y únicamente si el valor amplía el mínimo o el máximo. Es mucho más barato y pequeño que un B-Tree, pero solo resulta útil cuando la tabla está físicamente ordenada por la columna indexada y las consultas filtran por rangos. Para joins por FK, búsquedas puntuales y datos desordenados como los de este esquema, el B-Tree es la estructura adecuada; por eso `008_indices.sql` no crea BRIN.

#### `UPDATE`

PostgreSQL implementa MVCC: un `UPDATE` crea una **nueva versión de la fila** en el heap. Luego, para cada índice:

* Si las columnas indexadas **no cambian**, el motor puede intentar un **HOT update** (Heap-Only Tuple): reutiliza la entrada de índice existente si la nueva versión cabe en la misma página del heap. En ese caso no se escribe una entrada nueva en los índices.
* Si las columnas indexadas **sí cambian** (por ejemplo, `comprobante.id_cliente`, `id_sala` o `fecha`), el índice B-Tree debe **insertar una entrada nueva** y marcar la anterior como muerta. La entrada vieja no desaparece físicamente hasta que `VACUUM` la reclama. Por eso los `UPDATE` sobre columnas indexadas generan más escrituras y **hinchazón** (*bloat*) del índice.
* En el índice parcial, la pertenencia depende del predicado: al pasar de `'terminado'` a `'procesado'`, la fila deja de cumplir `estado <> 'procesado'` y su entrada **se elimina** del índice parcial. Al revés, un documento que vuelve a un estado pendiente (si las reglas lo permitieran) tendría que insertarse. Esto demuestra que un buen predicado reduce el mantenimiento: las transferencias ya procesadas no se indexan ni se actualizan.

#### `DELETE`

* Un `DELETE` no borra físicamente la fila: la marca como muerta en el heap y marca como muertas sus entradas en **todos los índices**. El espacio se recupera recién con `VACUUM`; hasta entonces el índice conserva entradas muertas que ocupan páginas y pueden degradar los recorridos.
* En un B-Tree, la eliminación puede provocar rebalanceos o fusiones de páginas, aunque PostgreSQL suele dejar las entradas muertas para que `VACUUM` las limpie. En un índice parcial, si la fila borrada no cumplía el predicado, no hay entrada que marcar.
* Los índices sobre FK también participan en los borrados: cuando se elimina una fila referenciada, PostgreSQL usa el índice de la columna referenciante para verificar `ON DELETE RESTRICT` o para ejecutar el `CASCADE`. En este esquema, borrar un `comprobante` dispara el `ON DELETE CASCADE` de `renglon_comprobante`, por lo que se marcan como muertas las entradas de la PK de los renglones y las de los índices de la cabecera.

### 3.5 Interpretación y conclusión

* **Sobrecarga medida:** los dos índices nuevos sobre `comprobante` agregan un **6,24 %** al tiempo de inserción de la cabecera y un **2,37 %** al lote completo de 100.000 filas. La sobrecarga es moderada porque el trabajo dominante sigue siendo el heap, el WAL y las verificaciones de FK; aun así, es un costo real y creciente con la cantidad de índices.
* **Almacenamiento:** 1,27 MB para 50.000 comprobantes, equivalentes a unos **26 bytes por fila** entre ambos índices. En la base completa de 150.000 comprobantes, el tamaño total de estos índices escala proporcionalmente.
* **Diseño:** el índice parcial demuestra que se puede reducir drásticamente el costo de escritura indexando solo la fracción activa; el índice compuesto reutiliza el prefijo `id_sala` y evita un índice adicional; los índices de FK son necesarios para evitar `Seq Scan` en joins y en las verificaciones de `ON DELETE RESTRICT`. La contrapartida es que **cada escritura debe mantener todas las estructuras afectadas**, por lo que solo deben crearse índices justificados por consultas frecuentes o por integridad referencial.
* **Alcance de la medición:** los triggers de negocio se desactivaron únicamente para aislar el costo de los índices. En producción, un `INSERT` de venta también ejecuta los triggers de totales y stock (RN-08/RN-09), cuyo costo es independiente del mantenimiento de índices y no forma parte de esta comparación.

---

## 4. Análisis de Rendimiento e Índices (EXPLAIN) - Responsable: Integración

### 4.1 Objetivo y Metodología
Para verificar empíricamente el impacto de los índices propuestos en `008_indices.sql`, se analizaron los planes de ejecución (`EXPLAIN (ANALYZE, BUFFERS)`) de dos consultas críticas sobre el dataset histórico (150.000 comprobantes, 600.000 renglones de venta, 5.000 transferencias y 15.000 renglones de transferencia). Las mediciones comparan el comportamiento del planificador de PostgreSQL antes y después de aplicar los índices.

### 4.2 Tabla Comparativa de Rendimiento

| Consulta | Estado | Tiempo de Ejecución | Buffers Leídos (Hit+Read) | Filas Descartadas (Removed) | Método de Acceso Principal | Mejora de Tiempo |
| :--- | :--- | ---: | ---: | ---: | :--- | ---: |
| **C1: Reporte por Sala** | Sin Índices | 11.67 ms | 1.402 bloques | 149.582 filas | `Seq Scan` | - |
| **C1: Reporte por Sala** | **Con Índices** | **1.82 ms** | **27 bloques** | **0 filas** | `Bitmap Heap Scan` | **84,4 %** |
| **C2: Transf. Pendientes** | Sin Índices | 0.64 ms | 82 bloques | 5.000 filas | `Seq Scan` | - |
| **C2: Transf. Pendientes** | **Con Índices** | **0.25 ms** | **2 bloques** | **0 filas** | `Bitmap Heap Scan` | **60,9 %** |

*(Nota: La reducción drástica en la lectura de buffers y filas descartadas demuestra que el motor dejó de barrer las tablas enteras y pasó a acceder de forma quirúrgica a las páginas de disco necesarias).*

### 4.3 Análisis de Resultados

#### Consulta 1: Reporte mensual de comprobantes por tipo de cliente
*(Ventas en sala 1 desde octubre de 2026).*
*   **Antes:** El planificador resolvió mediante un *Sequential Scan* sobre la tabla `comprobante`, leyendo 1.402 buffers de memoria y descartando 149.582 filas inútiles mediante el filtro `WHERE`, tardando 11.67 ms.
*   **Después:** Gracias al índice compuesto `idx_comprobante_sala_fecha (id_sala, fecha)` y al de clave foránea `idx_fk_comprobante_cliente`, el motor cambió a un *Bitmap Heap Scan*. La lectura de buffers bajó drásticamente a 27 bloques y el tiempo a 1.82 ms. (Reducción de I/O de disco/memoria del 98%).

#### Consulta 2: Transferencias Pendientes
*(Transferencias en estado distinto a 'procesado').*
*   **Antes:** El motor realizó un escaneo secuencial sobre toda la tabla `transferencia`, leyendo 82 buffers y descartando 5.000 filas históricas.
*   **Después:** Al aplicar el índice parcial `idx_transferencia_pendientes (estado) WHERE estado <> 'procesado'`, el motor ejecutó un escaneo por mapa de bits leyendo solo 2 bloques en la tabla principal, saltando directamente a las 4 transferencias pendientes en 0.25 ms.

---

### Anexo: Planes de Ejecución (EXPLAIN)

<details>
<summary><b>Ver planes de ejecución completos (Antes y Después)</b></summary>

```text
=== CONSULTA 1 (ANTES) ===
GroupAggregate  (cost=3712.05..3716.13 rows=3 width=44) (actual time=10.745..10.924 rows=3 loops=1)
   Group Key: cl.tipo_cliente
   Buffers: shared hit=1421
   ->  Sort  (cost=3712.05..3713.06 rows=404 width=16) (actual time=10.435..10.526 rows=418 loops=1)
         Sort Key: cl.tipo_cliente, c.nro_comprobante
         Sort Method: quicksort  Memory: 44kB
         Buffers: shared hit=1421
         ->  Hash Join  (cost=41.50..3694.56 rows=404 width=16) (actual time=9.284..9.835 rows=418 loops=1)
               Hash Cond: (c.id_cliente = cl.id_cliente)
               Buffers: shared hit=1421
               ->  Seq Scan on comprobante c  (cost=0.00..3652.00 rows=404 width=16) (actual time=8.514..8.881 rows=418 loops=1)
                     Filter: ((fecha >= '2026-10-01'::date) AND (id_sala = 1))
                     Rows Removed by Filter: 149582
                     Buffers: shared hit=1402
               ->  Hash  (cost=29.00..29.00 rows=1000 width=8) (actual time=0.490..0.491 rows=1000 loops=1)
                     Buckets: 1024  Batches: 1  Memory Usage: 48kB
                     Buffers: shared hit=19
                     ->  Seq Scan on cliente cl  (cost=0.00..29.00 rows=1000 width=8) (actual time=0.022..0.225 rows=1000 loops=1)
                           Buffers: shared hit=19
 Planning Time: 4.088 ms
 Execution Time: 11.678 ms

=== CONSULTA 1 (DESPUES) ===
GroupAggregate  (cost=967.90..972.06 rows=3 width=44) (actual time=1.131..1.205 rows=3 loops=1)
   Group Key: cl.tipo_cliente
   Buffers: shared hit=52 read=2
   ->  Sort  (cost=967.90..968.93 rows=412 width=16) (actual time=1.001..1.026 rows=418 loops=1)
         Sort Key: cl.tipo_cliente, c.nro_comprobante
         Sort Method: quicksort  Memory: 44kB
         Buffers: shared hit=52 read=2
         ->  Hash Join  (cost=50.02..950.01 rows=412 width=16) (actual time=0.441..0.656 rows=418 loops=1)
               Hash Cond: (c.id_cliente = cl.id_cliente)
               Buffers: shared hit=44 read=2
               ->  Bitmap Heap Scan on comprobante c  (cost=8.52..907.43 rows=412 width=16) (actual time=0.086..0.203 rows=418 loops=1)
                     Recheck Cond: ((id_sala = 1) AND (fecha >= '2026-10-01'::date))
                     Heap Blocks: exact=25
                     Buffers: shared hit=25 read=2
                     ->  Bitmap Index Scan on idx_comprobante_sala_fecha  (cost=0.00..8.42 rows=412 width=0) (actual time=0.060..0.061 rows=418 loops=1)
                           Index Cond: ((id_sala = 1) AND (fecha >= '2026-10-01'::date))
                           Buffers: shared read=2
               ->  Hash  (cost=29.00..29.00 rows=1000 width=8) (actual time=0.324..0.325 rows=1000 loops=1)
                     Buckets: 1024  Batches: 1  Memory Usage: 48kB
                     Buffers: shared hit=19
                     ->  Seq Scan on cliente cl  (cost=0.00..29.00 rows=1000 width=8) (actual time=0.011..0.165 rows=1000 loops=1)
                           Buffers: shared hit=19
 Planning Time: 6.523 ms
 Execution Time: 1.822 ms

=== CONSULTA 2 (ANTES) ===
Sort  (cost=192.41..192.42 rows=4 width=24) (actual time=0.499..0.501 rows=4 loops=1)
   Sort Key: t.id_sala, t.fecha_confeccion
   Sort Method: quicksort  Memory: 25kB
   Buffers: shared hit=94
   ->  GroupAggregate  (cost=192.24..192.37 rows=4 width=24) (actual time=0.483..0.487 rows=4 loops=1)
         Group Key: t.nro_transferencia
         Buffers: shared hit=94
         ->  Sort  (cost=192.24..192.27 rows=12 width=20) (actual time=0.476..0.477 rows=4 loops=1)
               Sort Key: t.nro_transferencia
               Sort Method: quicksort  Memory: 25kB
               Buffers: shared hit=94
               ->  Nested Loop  (cost=0.29..192.02 rows=12 width=20) (actual time=0.425..0.434 rows=4 loops=1)
                     Buffers: shared hit=94
                     ->  Seq Scan on transferencia t  (cost=0.00..144.55 rows=4 width=16) (actual time=0.363..0.364 rows=4 loops=1)
                           Filter: (estado <> 'procesado'::estado_documento)
                           Rows Removed by Filter: 5000
                           Buffers: shared hit=82
                     ->  Index Scan using renglon_transferencia_pkey on renglon_transferencia rt  (cost=0.29..11.84 rows=3 width=8) (actual time=0.005..0.005 rows=1 loops=4)
                           Index Cond: (nro_transferencia = t.nro_transferencia)
                           Buffers: shared hit=12
 Planning Time: 1.232 ms
 Execution Time: 0.644 ms

=== CONSULTA 2 (DESPUES) ===
Sort  (cost=69.41..69.42 rows=4 width=24) (actual time=0.151..0.154 rows=4 loops=1)
   Sort Key: t.id_sala, t.fecha_confeccion
   Sort Method: quicksort  Memory: 25kB
   Buffers: shared hit=16 read=1
   ->  GroupAggregate  (cost=69.24..69.37 rows=4 width=24) (actual time=0.094..0.099 rows=4 loops=1)
         Group Key: t.nro_transferencia
         Buffers: shared hit=13 read=1
         ->  Sort  (cost=69.24..69.27 rows=12 width=20) (actual time=0.087..0.089 rows=4 loops=1)
               Sort Key: t.nro_transferencia
               Sort Method: quicksort  Memory: 25kB
               Buffers: shared hit=13 read=1
               ->  Nested Loop  (cost=8.44..69.02 rows=12 width=20) (actual time=0.064..0.075 rows=4 loops=1)
                     Buffers: shared hit=13 read=1
                     ->  Bitmap Heap Scan on transferencia t  (cost=8.15..21.55 rows=4 width=16) (actual time=0.037..0.038 rows=4 loops=1)
                           Recheck Cond: (estado <> 'procesado'::estado_documento)
                           Heap Blocks: exact=1
                           Buffers: shared hit=1 read=1
                           ->  Bitmap Index Scan on idx_transferencia_pendientes  (cost=0.00..8.15 rows=4 width=0) (actual time=0.030..0.031 rows=4 loops=1)
                                 Buffers: shared read=1
                     ->  Index Scan using renglon_transferencia_pkey on renglon_transferencia rt  (cost=0.29..11.84 rows=3 width=8) (actual time=0.007..0.007 rows=1 loops=4)
                           Index Cond: (nro_transferencia = t.nro_transferencia)
                           Buffers: shared hit=12
 Planning Time: 2.104 ms
 Execution Time: 0.254 ms
<!-- INICIO APORTE H4 SANTIAGO -->

## 5. Índices especiales INCLUDE y BRIN — Responsable: Santiago

### 5.1. Índice covering con `INCLUDE`

```sql
CREATE INDEX IF NOT EXISTS idx_rc_vino_include_cant
    ON renglon_comprobante (cod_vino)
    INCLUDE (cantidad, subtotal);
```

`cod_vino` es la clave de búsqueda de un B-Tree. Las columnas `cantidad` y `subtotal`
se almacenan como datos incluidos (no forman parte de la clave de ordenación). La consulta
que filtra `cod_vino = 10` y suma esos valores puede atenderse mayormente con el índice,
sin recorrer las 600.000 filas del heap. El plan observado es `Index Only Scan`, con
`Heap Fetches: 5`, por lo que **no** corresponde afirmar que hubo cero accesos al heap.
El mapa de visibilidad, actualizado con `VACUUM (ANALYZE)`, facilita ese tipo de recorrido.

Consulta 3:

```sql
SELECT cod_vino, SUM(cantidad) AS botellas_vendidas, SUM(subtotal) AS monto_total
FROM renglon_comprobante
WHERE cod_vino = 10
GROUP BY cod_vino;
```

### 5.2. Índice BRIN por fecha

```sql
CREATE INDEX IF NOT EXISTS idx_comprobante_fecha_brin
    ON comprobante USING brin (fecha);
```

BRIN almacena resúmenes de valores por rangos de páginas, en lugar de una referencia
por fila. Resulta apropiado para el historial de comprobantes insertado por meses en
orden cronológico. En la consulta de agosto a octubre de 2026 el plan pasó de
`Parallel Seq Scan` a `Bitmap Index Scan` (BRIN) + `Bitmap Heap Scan`, con
`Heap Blocks: lossy=356` y **343 filas descartadas por reverificación**. Este
comportamiento es normal: BRIN localiza rangos de páginas aproximados y PostgreSQL
comprueba después la condición en las filas candidatas.

Consulta 4:

```sql
SELECT DATE_TRUNC('month', fecha)::DATE AS mes,
       COUNT(*) AS cant_ventas, SUM(total) AS facturacion
FROM comprobante
WHERE fecha BETWEEN DATE '2026-08-01' AND DATE '2026-10-31'
GROUP BY 1 ORDER BY 1;
```

### 5.3. Comparativa medida: consultas 3 y 4

Se utilizó `EXPLAIN (ANALYZE, BUFFERS)` antes de crear estos **dos** índices y
después de crearlos y ejecutar `VACUUM (ANALYZE)` sobre las tablas involucradas.
Los resultados corresponden a una base local de H3 con **600.000 renglones de venta**
y **150.000 comprobantes**. Las consultas 1 y 2 corresponden al aporte de Delgado.

| Consulta | Antes (ms) | Después (ms) | Acceso antes | Acceso después | Reducción observada | Buffers representativos antes → después |
|---|---:|---:|---|---|---:|---|
| 3 — Vino 10 | 23.935 | 5.973 | Parallel Seq Scan | Index Only Scan | 75.0 % | hit=32/read=4808 → hit=1/read=80 |
| 4 — Ago.–oct. 2026 | 109.491 | 15.155 | Parallel Seq Scan | Bitmap Heap Scan + BRIN | 86.2 % | hit=17/read=6627 → hit=171/read=196 |

En estas ejecuciones, la consulta 3 se aceleró **4.01×** y la consulta 4,
**7.22×**. Es una comparación observada, **no una garantía de mejora constante**:
la caché, lecturas de disco, paralelismo y estado de la máquina también influyen.

## 6. Caso de índice existente que el planificador decide no usar — Santiago

Con el índice `idx_comprobante_fecha_brin` **existente**, la consulta:

```sql
SELECT *
FROM comprobante
WHERE fecha >= DATE '2022-01-01';
```

recuperó **150.000 de 150.000 filas**. PostgreSQL escogió `Seq Scan on comprobante`
(**31.092 ms**), porque el filtro no descarta filas y recorrer el heap
secuencialmente resulta más conveniente que acceder mediante un índice.
No se alteró `enable_seqscan` ni se forzó ningún plan.

## Anexo H4 — Planes completos de consultas 3, 4 y caso de no uso (Santiago)

### Consulta 3 — ANTES (sin INCLUDE)

```text
QUERY PLAN
---------------------------------------------------------------------------------------------------------------------------------------------------
 Finalize GroupAggregate  (cost=1000.00..9001.28 rows=1 width=44) (actual time=21.068..23.523 rows=1 loops=1)
   Buffers: shared hit=32 read=4808
   ->  Gather  (cost=1000.00..9001.25 rows=2 width=44) (actual time=20.949..23.501 rows=3 loops=1)
         Workers Planned: 2
         Workers Launched: 2
         Buffers: shared hit=32 read=4808
         ->  Partial GroupAggregate  (cost=0.00..8001.05 rows=1 width=44) (actual time=16.791..16.791 rows=1 loops=3)
               Buffers: shared hit=32 read=4808
               ->  Parallel Seq Scan on renglon_comprobante  (cost=0.00..7965.00 rows=7208 width=16) (actual time=0.033..15.598 rows=5562 loops=3)
                     Filter: (cod_vino = 10)
                     Rows Removed by Filter: 194438
                     Buffers: shared hit=32 read=4808
 Planning:
   Buffers: shared hit=95 read=5
 Planning Time: 2.115 ms
 Execution Time: 23.935 ms
(16 rows)
```

### Consulta 3 — DESPUÉS (con INCLUDE)

```text
QUERY PLAN
--------------------------------------------------------------------------------------------------------------------------------------------------------------------
 GroupAggregate  (cost=0.42..680.13 rows=1 width=44) (actual time=5.866..5.868 rows=1 loops=1)
   Buffers: shared hit=1 read=80
   ->  Index Only Scan using idx_rc_vino_include_cant on renglon_comprobante  (cost=0.42..597.52 rows=16520 width=16) (actual time=0.144..3.190 rows=16686 loops=1)
         Index Cond: (cod_vino = 10)
         Heap Fetches: 5
         Buffers: shared hit=1 read=80
 Planning:
   Buffers: shared hit=118
 Planning Time: 1.205 ms
 Execution Time: 5.973 ms
(10 rows)
```

### Consulta 4 — ANTES (sin BRIN)

```text
QUERY PLAN
--------------------------------------------------------------------------------------------------------------------------------------------------
 Finalize GroupAggregate  (cost=8616.95..8632.81 rows=58 width=44) (actual time=105.325..109.262 rows=3 loops=1)
   Group Key: ((date_trunc('month'::text, (fecha)::timestamp with time zone))::date)
   Buffers: shared hit=17 read=6627
   ->  Gather Merge  (cost=8616.95..8630.49 rows=116 width=44) (actual time=105.309..109.240 rows=9 loops=1)
         Workers Planned: 2
         Workers Launched: 2
         Buffers: shared hit=17 read=6627
         ->  Sort  (cost=7616.93..7617.07 rows=58 width=44) (actual time=100.634..100.636 rows=3 loops=3)
               Sort Key: ((date_trunc('month'::text, (fecha)::timestamp with time zone))::date)
               Sort Method: quicksort  Memory: 25kB
               Buffers: shared hit=17 read=6627
               Worker 0:  Sort Method: quicksort  Memory: 25kB
               Worker 1:  Sort Method: quicksort  Memory: 25kB
               ->  Partial HashAggregate  (cost=7614.07..7615.23 rows=58 width=44) (actual time=100.593..100.595 rows=3 loops=3)
                     Group Key: (date_trunc('month'::text, (fecha)::timestamp with time zone))::date
                     Batches: 1  Memory Usage: 24kB
                     Buffers: shared hit=1 read=6627
                     Worker 0:  Batches: 1  Memory Usage: 24kB
                     Worker 1:  Batches: 1  Memory Usage: 24kB
                     ->  Parallel Seq Scan on comprobante  (cost=0.00..7589.78 rows=3238 width=12) (actual time=94.485..99.799 rows=2586 loops=3)
                           Filter: ((fecha >= '2026-08-01'::date) AND (fecha <= '2026-10-31'::date))
                           Rows Removed by Filter: 47414
                           Buffers: shared hit=1 read=6627
 Planning:
   Buffers: shared hit=98 read=3
 Planning Time: 1.085 ms
 Execution Time: 109.491 ms
(27 rows)
```

### Consulta 4 — DESPUÉS (con BRIN)

```text
QUERY PLAN
------------------------------------------------------------------------------------------------------------------------------------------------------
 Sort  (cost=7245.54..7245.68 rows=58 width=44) (actual time=14.959..14.961 rows=3 loops=1)
   Sort Key: ((date_trunc('month'::text, (fecha)::timestamp with time zone))::date)
   Sort Method: quicksort  Memory: 25kB
   Buffers: shared hit=171 read=196
   ->  HashAggregate  (cost=7242.68..7243.84 rows=58 width=44) (actual time=14.906..14.909 rows=3 loops=1)
         Group Key: (date_trunc('month'::text, (fecha)::timestamp with time zone))::date
         Batches: 1  Memory Usage: 24kB
         Buffers: shared hit=168 read=196
         ->  Bitmap Heap Scan on comprobante  (cost=14.03..7184.55 rows=7750 width=12) (actual time=0.862..12.840 rows=7758 loops=1)
               Recheck Cond: ((fecha >= '2026-08-01'::date) AND (fecha <= '2026-10-31'::date))
               Rows Removed by Index Recheck: 343
               Heap Blocks: lossy=356
               Buffers: shared hit=168 read=196
               ->  Bitmap Index Scan on idx_comprobante_fecha_brin  (cost=0.00..12.10 rows=8654 width=0) (actual time=0.143..0.144 rows=3560 loops=1)
                     Index Cond: ((fecha >= '2026-08-01'::date) AND (fecha <= '2026-10-31'::date))
                     Buffers: shared hit=8
 Planning:
   Buffers: shared hit=125
 Planning Time: 1.335 ms
 Execution Time: 15.155 ms
(20 rows)
```

### Caso de índice existente ignorado

```text
QUERY PLAN
--------------------------------------------------------------------------------------------------------------------
 Seq Scan on comprobante  (cost=0.00..8503.00 rows=150000 width=40) (actual time=0.268..24.201 rows=150000 loops=1)
   Filter: (fecha >= '2022-01-01'::date)
   Buffers: shared hit=6117 read=511
 Planning:
   Buffers: shared hit=91 dirtied=4
 Planning Time: 1.043 ms
 Execution Time: 31.092 ms
(7 rows)
```

<!-- FIN APORTE H4 SANTIAGO -->
