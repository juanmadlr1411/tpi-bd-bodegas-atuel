# Diccionario de Datos — Bodegas del Atuel

## 1. Dominios y Tipos Enumerados (Responsable: Delgado)

| Objeto | Tipo Base / Valores | Restricción | Descripción |
| :--- | :--- | :--- | :--- |
| `cuit_dom` | `CHAR(11)` | `CHECK (VALUE ~ '^[0-9]{11}$')` | Dominio para CUIT de 11 dígitos numéricos |
| `estado_documento` | `ENUM` | `'en_confeccion'`, `'terminado'`, `'procesado'` | Estados válidos de ingresos y transferencias (RN-10, RN-11) |
| `tipo_vino` | `ENUM` | `'tinto'`, `'blanco'`, `'rosado'`, `'espumante'` | Clasificación comercial del vino |
| `tipo_cepa` | `ENUM` | `'tinta'`, `'blanca'` | Clasificación ampelográfica de la cepa |
| `tipo_cliente_enum` | `ENUM` | `'socio'`, `'distribuidor'`, `'exportador'` | Discriminador de la jerarquía de clientes |
| `dia_semana` | `ENUM` | `'lunes'` .. `'domingo'` | Día de cierre semanal de cada sala de venta |

---

## 2. Subdominio Geografía, Salas y Producción de Uva (Responsable: Gonzalo)

| Tabla | Columna | Tipo de Dato | Nulos | Restricciones | Descripción |
| :--- | :--- | :--- | :---: | :--- | :--- |
| **localidad** | `cod_postal` | `VARCHAR(10)` | NO | `PK` | Código postal identificador de la localidad. |
| **localidad** | `nombre` | `VARCHAR(80)` | NO | `NOT NULL` | Nombre de la localidad o ciudad. |
| **localidad** | `provincia` | `VARCHAR(60)` | NO | `NOT NULL, DEFAULT 'Mendoza'` | Provincia a la que pertenece la localidad. |
| **localidad** | `encargado_regional` | `VARCHAR(100)` | NO | `NOT NULL` | Único responsable comercial de todas las salas de la localidad (RN-02). |
| **sala_venta** | `id_sala` | `INTEGER` | NO | `PK, IDENTITY` | Identificador único autogenerado de la sala de venta. |
| **sala_venta** | `calle` | `VARCHAR(100)` | NO | `NOT NULL` | Nombre de la calle donde se ubica la sala. |
| **sala_venta** | `numero` | `INTEGER` | NO | `NOT NULL, CHECK (numero > 0)` | Altura o número de puerta de la dirección. |
| **sala_venta** | `dia_cierre` | `dia_semana` | NO | `NOT NULL` | Día de cierre semanal de la sala de venta. |
| **sala_venta** | `cod_postal` | `VARCHAR(10)` | NO | `FK -> localidad(cod_postal), NOT NULL` | Localidad donde está radicada la sala (RN-02, ON DELETE RESTRICT). |
| **empleado** | `cuit` | `cuit_dom` | NO | `PK, DOMAIN` | CUIT de 11 dígitos numéricos del empleado. |
| **empleado** | `nombre` | `VARCHAR(100)` | NO | `NOT NULL` | Apellido y nombre completo del empleado. |
| **empleado** | `fecha_ingreso` | `DATE` | NO | `NOT NULL` | Fecha de ingreso laboral a la empresa. |
| **empleado** | `salario` | `NUMERIC(12,2)` | NO | `NOT NULL, CHECK (salario > 0)` | Remuneración mensual positiva del empleado (RN-15). |
| **empleado** | `id_sala` | `INTEGER` | NO | `FK -> sala_venta(id_sala), NOT NULL` | Única sala de venta en la que trabaja el empleado (RN-03, ON DELETE RESTRICT). |
| **finca** | `id_finca` | `INTEGER` | NO | `PK, IDENTITY` | Identificador único autogenerado de la finca productora. |
| **finca** | `nombre` | `VARCHAR(80)` | NO | `UNIQUE, NOT NULL` | Nombre del establecimiento o finca vitivinícola. |
| **finca** | `superficie_ha` | `NUMERIC(8,2)` | NO | `NOT NULL, CHECK (superficie_ha > 0)` | Superficie total de la finca en hectáreas (RN-15). |
| **finca** | `departamento` | `VARCHAR(60)` | NO | `NOT NULL` | Departamento donde se ubica la finca (ej. San Rafael). |
| **finca** | `provincia` | `VARCHAR(60)` | NO | `NOT NULL, DEFAULT 'Mendoza'` | Provincia donde se ubica la finca. |
| **cepa** | `id_cepa` | `INTEGER` | NO | `PK, IDENTITY` | Identificador único autogenerado de la cepa. |
| **cepa** | `nombre` | `VARCHAR(60)` | NO | `UNIQUE, NOT NULL` | Nombre varietal de la uva (ej. Malbec, Chardonnay). |
| **cepa** | `tipo` | `tipo_cepa` | NO | `NOT NULL` | Clasificación de la uva: `'tinta'` o `'blanca'`. |
| **parcela** | `id_finca` | `INTEGER` | NO | `PK, FK -> finca(id_finca)` | Finca propietaria de la parcela (entidad débil, ON DELETE CASCADE). |
| **parcela** | `nro_parcela` | `SMALLINT` | NO | `PK, CHECK (nro_parcela > 0)` | Número correlativo de parcela dentro de su finca. |
| **parcela** | `superficie_ha` | `NUMERIC(8,2)` | NO | `NOT NULL, CHECK (superficie_ha > 0)` | Superficie cultivada de la parcela en hectáreas (RN-15). |
| **parcela** | `anio_plantacion` | `SMALLINT` | NO | `NOT NULL, CHECK (1900..2100)` | Año en que fue plantada la parcela. |
| **parcela** | `id_cepa` | `INTEGER` | NO | `FK -> cepa(id_cepa), NOT NULL` | Única cepa plantada en la parcela (RN-04, ON DELETE RESTRICT). |
| **lote_uva** | `nro_lote` | `INTEGER` | NO | `PK, IDENTITY` | Número identificador único del lote de uva cosechado. |
| **lote_uva** | `id_finca` | `INTEGER` | NO | `FK -> parcela, NOT NULL, UNIQUE (comp.)` | Finca de la parcela cosechada (ON DELETE RESTRICT). |
| **lote_uva** | `nro_parcela` | `SMALLINT` | NO | `FK -> parcela, NOT NULL, UNIQUE (comp.)` | Número de parcela cosechada (ON DELETE RESTRICT). |
| **lote_uva** | `campania` | `SMALLINT` | NO | `NOT NULL, CHECK (1990..2100), UNIQUE (comp.)` | Año de campaña agrícola; máximo una cosecha por parcela y campaña (RN-04). |
| **lote_uva** | `fecha_cosecha` | `DATE` | NO | `NOT NULL` | Fecha en que se efectuó la cosecha del lote. |
| **lote_uva** | `kilos` | `NUMERIC(10,2)` | NO | `NOT NULL, CHECK (kilos > 0)` | Cantidad de kilos cosechados en el lote (RN-15). |
| **lote_uva** | `cuit_bodega` | `cuit_dom` | NO | `FK -> bodega(cuit), NOT NULL` | Bodega elaboradora a la que se entregó el lote (ON DELETE RESTRICT). |
| **analisis_calidad** | `id_analisis` | `INTEGER` | NO | `PK, IDENTITY` | Identificador único autogenerado del análisis de laboratorio. |
| **analisis_calidad** | `nro_lote` | `INTEGER` | NO | `FK -> lote_uva(nro_lote), NOT NULL` | Lote de uva evaluado (ON DELETE CASCADE). |
| **analisis_calidad** | `fecha` | `DATE` | NO | `NOT NULL` | Fecha de realización del análisis de calidad. |
| **analisis_calidad** | `grado_brix` | `NUMERIC(4,2)` | NO | `NOT NULL, CHECK (grado_brix > 0)` | Contenido de azúcar medido en grados Brix. |
| **analisis_calidad** | `ph` | `NUMERIC(4,2)` | NO | `NOT NULL, CHECK (ph > 0 AND ph <= 14)` | Nivel de pH registrado en el análisis. |
| **analisis_calidad** | `acidez_total` | `NUMERIC(5,2)` | NO | `NOT NULL, CHECK (acidez_total > 0)` | Acidez total expresada en gramos por litro (g/L). |

---

## 3. Subdominio Bodegas, Vinos y Clientes (Responsable: Manuel)

| Tabla | Columna | Tipo de Dato | Nulos | Restricciones | Descripción |
| :--- | :--- | :--- | :---: | :--- | :--- |
| **bodega** | `cuit` | `cuit_dom` | NO | `PK, DOMAIN` | CUIT de 11 dígitos numéricos de la bodega elaboradora. |
| **bodega** | `razon_social` | `VARCHAR(100)` | NO | `UNIQUE, NOT NULL` | Nombre legal o razón social de la bodega. |
| **bodega** | `domicilio` | `VARCHAR(150)` | NO | `NOT NULL` | Dirección física de la bodega. |
| **vino** | `cod_vino` | `INTEGER` | NO | `PK, IDENTITY` | Código identificador autogenerado del vino. |
| **vino** | `nombre` | `VARCHAR(80)` | NO | `NOT NULL, UNIQUE (comp.)` | Nombre comercial de la etiqueta. |
| **vino** | `tipo` | `tipo_vino` | NO | `NOT NULL` | Clasificación: tinto, blanco, rosado o espumante. |
| **vino** | `anada` | `SMALLINT` | NO | `NOT NULL, CHECK (1990..2100), UNIQUE (comp.)` | Año de cosecha del vino. |
| **vino** | `volumen_ml` | `INTEGER` | NO | `NOT NULL, CHECK (187,375,750,1500,3000), UNIQUE (comp.)` | Capacidad de la botella en mililitros. |
| **vino** | `graduacion` | `NUMERIC(4,2)` | NO | `NOT NULL, CHECK (5..20)` | Graduación alcohólica en grados (RN-15). |
| **vino** | `precio` | `NUMERIC(12,2)` | NO | `NOT NULL, CHECK (precio > 0)` | Precio de venta único en toda la red de salas (RN-01). |
| **vino** | `cuit_bodega` | `cuit_dom` | NO | `FK -> bodega(cuit), NOT NULL` | Bodega del grupo que elabora el vino (ON DELETE RESTRICT). |
| **composicion_vino** | `cod_vino` | `INTEGER` | NO | `PK, FK -> vino(cod_vino)` | Código del vino al que pertenece el corte (ON DELETE CASCADE). |
| **composicion_vino** | `id_cepa` | `INTEGER` | NO | `PK, FK -> cepa(id_cepa)` | Cepa que integra la composición del vino (ON DELETE RESTRICT). |
| **composicion_vino** | `porcentaje` | `NUMERIC(5,2)` | NO | `NOT NULL, CHECK (> 0 AND <= 100)` | Porcentaje de la cepa en el vino; deben sumar 100 por vino (RN-05). |
| **maridaje** | `id_maridaje` | `INTEGER` | NO | `PK, IDENTITY` | Identificador único del maridaje recomendado. |
| **maridaje** | `nombre` | `VARCHAR(80)` | NO | `UNIQUE, NOT NULL` | Plato o acompañamiento sugerido (ej. carnes rojas). |
| **maridaje** | `temperatura_servicio` | `SMALLINT` | NO | `NOT NULL, CHECK (0..30)` | Temperatura de servicio recomendada en grados Celsius (°C). |
| **vino_maridaje** | `cod_vino` | `INTEGER` | NO | `PK, FK -> vino(cod_vino)` | Vino al que se asocia la recomendación (ON DELETE CASCADE). |
| **vino_maridaje** | `id_maridaje` | `INTEGER` | NO | `PK, FK -> maridaje(id_maridaje)` | Maridaje recomendado para dicho vino (ON DELETE RESTRICT). |
| **cliente** | `id_cliente` | `INTEGER` | NO | `PK, IDENTITY` | Identificador único del cliente (Supertipo). |
| **cliente** | `nombre_razon_social` | `VARCHAR(120)` | NO | `NOT NULL` | Apellido y nombre o razón social del cliente. |
| **cliente** | `tipo_documento` | `VARCHAR(10)` | NO | `NOT NULL, UNIQUE (comp.)` | Tipo de documento (DNI, CUIT, PAS). |
| **cliente** | `nro_documento` | `VARCHAR(20)` | NO | `NOT NULL, UNIQUE (comp.)` | Número de documento del cliente. |
| **cliente** | `direccion` | `VARCHAR(150)` | NO | `NOT NULL` | Domicilio del cliente. |
| **cliente** | `cod_postal` | `VARCHAR(10)` | NO | `FK -> localidad(cod_postal), NOT NULL` | Localidad de residencia del cliente (ON DELETE RESTRICT). |
| **cliente** | `fecha_alta` | `DATE` | NO | `NOT NULL, DEFAULT CURRENT_DATE` | Fecha en que el cliente fue dado de alta. |
| **cliente** | `tipo_cliente` | `tipo_cliente_enum` | NO | `NOT NULL` | Categoría del subtipo: socio, distribuidor o exportador. |
| **cliente** | `porcentaje_descuento` | `NUMERIC(5,2)` | NO | `NOT NULL, CHECK (0..100)` | Porcentaje de descuento según tipo: 10%, 20% o 30% (RN-06). |
| **cliente_socio** | `id_cliente` | `INTEGER` | NO | `PK, FK -> cliente(id_cliente)` | Subtipo socio del club / consumidor final (ON DELETE CASCADE). |
| **cliente_distribuidor** | `id_cliente` | `INTEGER` | NO | `PK, FK -> cliente(id_cliente)` | Subtipo cliente distribuidor (ON DELETE CASCADE). |
| **cliente_distribuidor** | `zona_cobertura` | `VARCHAR(100)` | NO | `NOT NULL` | Región o zona geográfica cubierta por el distribuidor. |
| **cliente_distribuidor** | `nro_habilitacion` | `VARCHAR(40)` | NO | `UNIQUE, NOT NULL` | Número de habilitación comercial del distribuidor. |
| **cliente_exportador** | `id_cliente` | `INTEGER` | NO | `PK, FK -> cliente(id_cliente)` | Subtipo cliente exportador (ON DELETE CASCADE). |
| **cliente_exportador** | `pais_destino` | `VARCHAR(80)` | NO | `NOT NULL` | País de destino principal de las exportaciones. |
| **permiso_exportacion** | `cod_permiso` | `VARCHAR(40)` | NO | `PK` | Código identificatorio del permiso de exportación. |
| **permiso_exportacion** | `id_cliente` | `INTEGER` | NO | `FK -> cliente_exportador(id_cliente), NOT NULL` | Exportador titular del permiso (RN-07, ON DELETE CASCADE). |
| **permiso_exportacion** | `fecha_emision` | `DATE` | NO | `NOT NULL` | Fecha de otorgamiento del permiso. |
| **permiso_exportacion** | `fecha_vencimiento` | `DATE` | NO | `NOT NULL, CHECK (fecha_vencimiento > fecha_emision)` | Fecha de expiración posterior a la emisión (RN-07). |

---

## 4. Subdominio Ventas, Logística, Stock y Auditoría (Responsable: Bruno)

| Tabla | Columna | Tipo de Dato | Nulos | Restricciones | Descripción |
| :--- | :--- | :--- | :---: | :--- | :--- |
| **comprobante** | `nro_comprobante` | `INTEGER` | NO | `PK, IDENTITY` | Número único de comprobante de venta. |
| **comprobante** | `fecha` | `DATE` | NO | `NOT NULL, DEFAULT CURRENT_DATE` | Fecha de emisión del comprobante. |
| **comprobante** | `id_cliente` | `INTEGER` | NO | `FK -> cliente(id_cliente), NOT NULL` | Cliente comprador (ON DELETE RESTRICT). |
| **comprobante** | `id_sala` | `INTEGER` | NO | `FK -> sala_venta(id_sala), NOT NULL` | Sala de venta donde se realizó la operación (ON DELETE RESTRICT). |
| **comprobante** | `subtotal` | `NUMERIC(14,2)` | NO | `NOT NULL, DEFAULT 0, CHECK (>= 0)` | Suma de importes brutos de los renglones. |
| **comprobante** | `descuento` | `NUMERIC(14,2)` | NO | `NOT NULL, DEFAULT 0, CHECK (>= 0)` | Monto total descontado según el tipo de cliente. |
| **comprobante** | `total` | `NUMERIC(14,2)` | NO | `NOT NULL, DEFAULT 0, CHECK (>= 0)` | Importe neto final calculado por la base de datos (RN-08). |
| **renglon_comprobante** | `nro_comprobante` | `INTEGER` | NO | `PK, FK -> comprobante(nro_comprobante)` | Cabecera del comprobante al que pertenece (ON DELETE CASCADE). |
| **renglon_comprobante** | `cod_vino` | `INTEGER` | NO | `PK, FK -> vino(cod_vino)` | Vino incluido en el renglón de venta (ON DELETE RESTRICT). |
| **renglon_comprobante** | `cantidad` | `INTEGER` | NO | `NOT NULL, CHECK (> 0)` | Cantidad de botellas vendidas en el renglón (RN-15). |
| **renglon_comprobante** | `precio_unitario` | `NUMERIC(12,2)` | NO | `NOT NULL, CHECK (> 0)` | Precio unitario del vino vigente al momento de la venta. |
| **renglon_comprobante** | `descuento` | `NUMERIC(5,2)` | NO | `NOT NULL, CHECK (0..100)` | Porcentaje de descuento aplicado al renglón según el cliente. |
| **renglon_comprobante** | `subtotal` | `NUMERIC(14,2)` | NO | `NOT NULL, CHECK (> 0)` | Subtotal neto del renglón con el descuento aplicado. |
<!-- Bruno: Completar filas de las 9 tablas restantes -->