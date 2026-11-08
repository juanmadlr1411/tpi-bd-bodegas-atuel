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
