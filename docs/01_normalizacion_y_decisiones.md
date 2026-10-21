# Etapa 1 (H1): Decisiones de Diseño y Verificación de Normalización (3FN)

## 1. Justificación de las Cinco Decisiones de Diseño

### 1.1. Estrategia de Mapeo de la Jerarquía de Clientes (ERE a Relacional)
* **Naturaleza de la jerarquía:** En el dominio de *Bodegas del Atuel*, la entidad `CLIENTE` se especializa en tres subtipos: `SOCIO` (consumidor final, 10% de descuento), `DISTRIBUIDOR` (20% de descuento, zona de cobertura y número de habilitación) y `EXPORTADOR` (30% de descuento, país de destino y permisos de exportación). Semánticamente, la jerarquía es **Total y Exclusiva (Disyunta)**: todo cliente debe pertenecer a una categoría y solo a una, ya que la regla **RN-06** asigna un único porcentaje de descuento fijo según su categoría comercial.
* **Alternativas evaluadas:**
  1. *Tabla única con discriminador:* Concentra todos los atributos en `cliente`, dejando en `NULL` `zona_cobertura`, `nro_habilitacion` y `pais_destino` cuando no aplican. **Desventaja crítica:** No permite restringir mediante una `FOREIGN KEY` pura que la tabla `permiso_exportacion` apunte exclusivamente a exportadores.
  2. *Una tabla por subtipo (sin tabla padre):* Obliga a triplicar los atributos comunes y rompe la integridad referencial en `comprobante`, ya que una factura no tendría una única tabla `cliente` a la cual referenciar su `id_cliente`.
  3. *Supertipo + Subtipos (Opción seleccionada):* Se modela la tabla padre `cliente` con los atributos comunes y tres tablas hijas (`cliente_socio`, `cliente_distribuidor`, `cliente_exportador`) cuya clave primaria `id_cliente` es simultáneamente clave foránea (`ON DELETE CASCADE`) hacia `cliente(id_cliente)`.
* **Justificación de la elección:** Evita atributos nulos, permite que `comprobante` referencie limpiamente a `cliente(id_cliente)` y garantiza por estructura referencial que `permiso_exportacion(id_cliente)` apunte únicamente a `cliente_exportador(id_cliente)`, haciendo imposible asociar un permiso de exportación a un socio o distribuidor (**RN-07**).

### 1.2. Claves Naturales vs. Claves Subrogadas y Claves Compuestas
* **Claves naturales (`cuit`, `cod_postal`, `cod_permiso`):** Se conservaron en `bodega(cuit)`, `empleado(cuit)`, `localidad(cod_postal)` y `permiso_exportacion(cod_permiso)`. El CUIT y el código postal son estándares legales inmutables, cortos y unívocos en Argentina, validados mediante el dominio `cuit_dom`.
* **Claves subrogadas (`INTEGER GENERATED ALWAYS AS IDENTITY`):** Se adoptaron en entidades operativas y transaccionales (`sala_venta`, `finca`, `cepa`, `lote_uva`, `analisis_calidad`, `vino`, `maridaje`, `cliente`, `comprobante`, `transportista`, `ingreso`, `transferencia`, `auditoria_precio`). Un identificador entero de 4 bytes reduce el tamaño de las páginas de índice B-Tree y acelera los `JOIN` en tablas de alto volumen (como `renglon_comprobante`, que superará las 500.000 filas). Para preservar la integridad semántica, se acompañan de restricciones `UNIQUE` sobre las claves candidatas de negocio: `UNIQUE (nombre, anada, volumen_ml)` en `vino`, `UNIQUE (tipo_documento, nro_documento)` en `cliente` y `UNIQUE (cuit)` en `transportista`.
* **Claves primarias compuestas:**
  * En la entidad débil `parcela(id_finca, nro_parcela)`: el número de parcela solo tiene identidad dentro de la finca a la que pertenece.
  * En tablas asociativas y renglones (`composicion_vino`, `vino_maridaje`, `renglon_comprobante`, `renglon_ingreso`, `renglon_transferencia`, `stock_sala`, `transportista_localidad`): garantizan a nivel de índice primario que un mismo vino no pueda repetirse en dos renglones del mismo documento ni duplicar su registro de stock en una misma sala.

### 1.3. Selección de Tipos de Datos
* **Importes monetarios y magnitudes decimales (`NUMERIC(p, s)` vs `FLOAT`):** Se prohíbe el uso de tipos de punto flotante (`REAL`, `DOUBLE PRECISION`) porque representan valores en base 2 (IEEE 754) y producen errores de redondeo inaceptables en contabilidad y control de porcentajes. Se utiliza `NUMERIC(12,2)` / `NUMERIC(14,2)` para precios, salarios y totales de comprobantes, y `NUMERIC(5,2)` para porcentajes de corte (que deben sumar exactamente `100.00` según **RN-05**) y descuentos.
* **Fechas y marcas de tiempo (`DATE` vs `TIMESTAMP`):** Se emplea `DATE` cuando la granularidad requerida por el negocio es diaria (cosechas, fechas de ingreso laboral, emisión de comprobantes, ingresos y transferencias) y `TIMESTAMP` en `auditoria_precio(fecha_hora)` para registrar el instante exacto de cada cambio de precio (**RN-13**).
* **Dominios y tipos enumerados (`DOMAIN` y `ENUM`):** Se define `cuit_dom` con expresión regular (`^[0-9]{11}$`) para centralizar la validación de CUIT en todo el esquema, y tipos `ENUM` (`estado_documento`, `tipo_vino`, `tipo_cepa`, `tipo_cliente_enum`, `dia_semana`) para acotar el dominio de valores válidos sin depender de cadenas libres propensas a errores de tipeo.

### 1.4. Tratamiento de Atributos Derivados (Almacenados vs. Calculados)
* **Atributos calculados dinámicamente (no almacenados):**
  * *Antigüedad del empleado:* Depende del paso del tiempo (`CURRENT_DATE - fecha_ingreso`); almacenarla violaría el diseño limpio al quedar desactualizada cada día. Se resuelve mediante la función `fn_antiguedad_anios` en la Etapa 2.
  * *Stock total por vino:* Es la agregación de `stock_deposito` más la sumatoria de `stock_sala`; se expone mediante vistas en la Etapa 2 para evitar redundancia.
* **Atributos derivados almacenados por integridad histórica (controlados por Triggers):**
  * En `renglon_comprobante` (`precio_unitario`, `descuento`, `subtotal`) y en `comprobante` (`subtotal`, `descuento`, `total`).
  * **Justificación:** El precio en `vino` y el porcentaje en `cliente` son valores vigentes actuales que pueden cambiar en el futuro (ej. actualizaciones de lista de precios o de descuentos). Un comprobante emitido es un documento comercial inmutable que debe conservar el precio y descuento exactos vigentes en el instante de la operación. Para evitar inconsistencias, estos campos no se cargan manualmente desde el cliente, sino que son calculados y mantenidos automáticamente por triggers en la base de datos (**RN-08**).

### 1.5. Políticas de Integridad Referencial (`ON DELETE` y `ON UPDATE`)
* **`ON DELETE RESTRICT` en maestros e historiales (**RN-14**):** Aplicado en todas las referencias hacia `bodega`, `vino`, `transportista`, `localidad`, `sala_venta`, `finca`, `cepa`, `parcela`, `lote_uva` y `cliente`. Impide eliminar registros maestros que posean ventas, cosechas o movimientos de stock asociados, preservando la trazabilidad histórica.
* **`ON DELETE CASCADE` en relaciones de composición fuerte (Cabecera-Detalle y Subtipos):** Aplicado desde `renglon_comprobante` hacia `comprobante`, `renglon_ingreso` hacia `ingreso`, `renglon_transferencia` hacia `transferencia`, `composicion_vino` y `vino_maridaje` hacia `vino`, `analisis_calidad` hacia `lote_uva`, `parcela` hacia `finca`, y desde los subtipos de cliente hacia `cliente`. Un renglón carece de sentido semántico sin su documento cabecera; si se depura un documento histórico completo, sus renglones se eliminan atómicamente.
* **`ON UPDATE CASCADE`:** Aplicado de forma general para permitir que eventuales correcciones administrativas sobre claves naturales (`cuit`, `cod_postal`) se propaguen sin romper referencias.

---

## 2. Verificación de Normalización (1FN, 2FN y 3FN)

### 2.1. Primera Forma Normal (1FN): Atomicidad y Eliminación de Grupos Repetitivos
Un esquema está en **1FN** si y solo si todos los dominios de sus atributos contienen únicamente valores atómicos (indivisibles) y no existen grupos repetitivos ni atributos multivaluados.
* **Dirección de salas de venta:** Se descompone en atributos atómicos `calle` y `numero` dentro de `sala_venta`.
* **Eliminación de atributos multivaluados:**
  * Las múltiples cepas que componen un vino se separaron en la relación `composicion_vino(cod_vino, id_cepa, porcentaje)`.
  * Los múltiples maridajes recomendados para un vino se separaron en `vino_maridaje(cod_vino, id_maridaje)`.
  * Las múltiples localidades cubiertas por un transportista se modelaron en `transportista_localidad(cod_transporte, cod_postal)`.
  * Los múltiples permisos de un exportador se modelaron en `permiso_exportacion(cod_permiso, id_cliente, ...)`.
  * Los renglones de ventas, ingresos y transferencias se separaron en sus respectivas tablas de detalle.

### 2.2. Segunda Forma Normal (2FN): Ausencia de Dependencias Funcionales Parciales
Un esquema en 1FN está en **2FN** si todo atributo no primo depende funcionalmente de la **totalidad** de cada clave candidata y no de un subconjunto propio de una clave compuesta.
Se verifican todas las tablas con clave primaria compuesta del modelo:
1. **`parcela` — PK: `(id_finca, nro_parcela)`**
   * Dependencia funcional válida: `{id_finca, nro_parcela} -> {superficie_ha, anio_plantacion, id_cepa}`.
   * Los datos propios de la finca (`id_finca -> {nombre, superficie_ha_total, departamento, provincia}`) no están en `parcela`, sino en `finca`. No existe dependencia parcial.
2. **`composicion_vino` — PK: `(cod_vino, id_cepa)`**
   * `{cod_vino, id_cepa} -> {porcentaje}`. El porcentaje de participación depende simultáneamente del vino y de la cepa. El nombre del vino depende solo de `cod_vino` (reside en `vino`) y el nombre/tipo de cepa depende solo de `id_cepa` (reside en `cepa`).
3. **`renglon_comprobante` — PK: `(nro_comprobante, cod_vino)`**
   * `{nro_comprobante, cod_vino} -> {cantidad, precio_unitario, descuento, subtotal}`. La cantidad vendida y las condiciones aplicadas en esa línea pertenecen a la intersección del comprobante y el vino; mientras que `{nro_comprobante} -> {fecha, id_cliente, id_sala}` reside en la cabecera `comprobante`.
4. **`renglon_ingreso`, `renglon_transferencia` y `stock_sala`:**
   * En las tres tablas, el único atributo no clave es `cantidad`, el cual depende de la clave compuesta completa (`(cod_ingreso, cod_vino)`, `(nro_transferencia, cod_vino)` e `(id_sala, cod_vino)` respectivamente).

### 2.3. Tercera Forma Normal (3FN): Ausencia de Dependencias Funcionales Transitivas
Un esquema en 2FN está en **3FN** si para toda dependencia funcional no trivial `X -> A`, o bien `X` es superclave, o bien `A` es un atributo primo (es decir, ningún atributo no clave determina a otro atributo no clave: `PK -> X -> A`).
Se verifican los casos críticos del dominio:

1. **Separación de `localidad` y `sala_venta` (Cumplimiento de RN-02):**
   * *Regla del dominio:* Cada localidad tiene un único encargado regional; si hay varias salas en la misma localidad, todas comparten el mismo encargado regional.
   * *Dependencias funcionales:*
     `id_sala -> cod_postal`
     `cod_postal -> {nombre_localidad, provincia, encargado_regional}`
   * *Análisis:* Si `encargado_regional` se hubiera colocado en `sala_venta`, existiría la dependencia transitiva `id_sala -> cod_postal -> encargado_regional`, provocando anomalías de actualización (cambiar el encargado de San Rafael obligaría a modificar múltiples filas de `sala_venta`) y anomalías de inserción/borrado. Al ubicar `encargado_regional` en `localidad(cod_postal)`, la dependencia transitiva desaparece y **RN-02** se garantiza por estructura en 3FN.

2. **Separación de `lote_uva`, `parcela` y `cepa` (Cumplimiento de RN-04):**
   * En `lote_uva`, cada lote proviene de una parcela en una campaña: `nro_lote -> {id_finca, nro_parcela, campania, fecha_cosecha, kilos, cuit_bodega}`.
   * Además, por **RN-04**, `{id_finca, nro_parcela, campania} -> nro_lote` es clave candidata alternativa (declarada `UNIQUE` en el DDL), por lo que ambas son superclaves de `lote_uva`.
   * La cepa cosechada en el lote no se duplica dentro de `lote_uva` porque `{id_finca, nro_parcela} -> id_cepa` ya está determinada en `parcela`, evitando la dependencia transitiva `nro_lote -> {id_finca, nro_parcela} -> id_cepa`.

3. **Separación de `vino` y `bodega`:**
   * En `vino`, `cod_vino -> cuit_bodega`. Los atributos descriptivos de la bodega (`cuit_bodega -> {razon_social, domicilio}`) se encuentran aislados en la tabla `bodega`, evitando redundancia y dependencias transitivas en el catálogo de vinos.
