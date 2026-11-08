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
