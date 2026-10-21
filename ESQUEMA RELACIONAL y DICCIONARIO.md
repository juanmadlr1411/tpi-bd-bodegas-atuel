**ESQUEMA RELACIONAL – BODEGAS Y VINOS / CLIENTES Y VENTAS**  
**1. BODEGA** (**cuit**, razon_social, domicilio)  
- Clave Candidata (UNIQUE): (razon_social).  
**2. VINO** (**cod_vino**, nombre, tipo, anada, volumen_ml, graduacion, precio, *cuit_bodega*)  
- Clave Foránea: *cuit_bodega* referencia a **BODEGA**(cuit).  
- Clave Candidata (UNIQUE): (nombre, anada, volumen_ml).  
**3. COMPOSICION_VINO** (***cod_vino***, ***id_cepa***, porcentaje)  
- Clave Foránea 1: *cod_vino* referencia a **VINO**(cod_vino).  
- Clave Foránea 2: *id_cepa* referencia a **CEPA**(id_cepa).  
**4. MARIDAJE** (**id_maridaje**, nombre, temperatura_servicio)  
- Clave Candidata (UNIQUE): (nombre).  
**5. VINO_MARIDAJE** (***cod_vino***, ***id_maridaje***)  
- Clave Foránea 1: *cod_vino* referencia a **VINO**(cod_vino).  
- Clave Foránea 2: *id_maridaje* referencia a **MARIDAJE**(id_maridaje).  
**6. CLIENTE** (**id_cliente**, nombre_razon_social, tipo_documento, nro_documento, direccion, *cod_postal*, fecha_alta, tipo_cliente, porcentaje_descuento)  
- Clave Foránea: *cod_postal* referencia a **LOCALIDAD**(cod_postal).  
- Clave Candidata (UNIQUE): (tipo_documento, nro_documento).  
**7. CLIENTE_SOCIO** (***id_cliente***)  
- Clave Foránea: *id_cliente* referencia a **CLIENTE**(id_cliente).  
**8. CLIENTE_DISTRIBUIDOR** (***id_cliente***, zona_cobertura, nro_habilitacion)  
- Clave Foránea: *id_cliente* referencia a **CLIENTE**(id_cliente).  
- Clave Candidata (UNIQUE): (nro_habilitacion).  
**9. CLIENTE_EXPORTADOR** (***id_cliente***, pais_destino)  
- Clave Foránea: *id_cliente* referencia a **CLIENTE**(id_cliente).  
**10. PERMISO_EXPORTACION** (**cod_permiso**, *id_cliente*, fecha_emision, fecha_vencimiento)  
- Clave Foránea: *id_cliente* referencia a **CLIENTE_EXPORTADOR**(id_cliente).  
**11. COMPROBANTE** (**nro_comprobante**, fecha, *id_cliente*, *id_sala*, subtotal, descuento, total)  
- Clave Foránea 1: *id_cliente* referencia a **CLIENTE**(id_cliente).  
- Clave Foránea 2: *id_sala* referencia a **SALA_VENTA**(id_sala).  
**12. RENGLON_COMPROBANTE** (***nro_comprobante***, ***cod_vino***, cantidad, precio_unitario, descuento, subtotal)  
- Clave Foránea 1: *nro_comprobante* referencia a **COMPROBANTE**(nro_comprobante).  
- Clave Foránea 2: *cod_vino* referencia a **VINO**(cod_vino).  
**Justificación del Mapeo de la Jerarquía de Clientes**  
En el modelo conceptual (ERE), la entidad **CLIENTE** presenta una jerarquía de especialización **Total y Exclusiva (Disyunta)** hacia los subtipos **SOCIO**, **DISTRIBUIDOR** y **EXPORTADOR**. Es **Total** porque todo cliente registrado en el sistema pertenece obligatoriamente a una de las tres categorías, y es **Exclusiva** porque un cliente no puede pertenecer a más de un subtipo simultáneamente, dado que cada categoría define un único porcentaje de descuento aplicable según la regla de negocio **RN-06** (10%, 20% o 30%).  
Para transformar esta jerarquía al esquema relacional se evaluaron las tres estrategias posibles:  
- **Opción 1: Tabla única con columna discriminadora de tipo.**  
  - *Ventaja:* Simplifica las consultas al no requerir uniones (JOIN) para leer los datos de cualquier cliente.  
  - *Desventaja:* Genera abundantes valores nulos (NULL) en las columnas específicas (zona_cobertura, nro_habilitacion y pais_destino) para los subtipos a los que no les corresponden. Además, impide garantizar mediante una clave foránea declarativa que solo los clientes exportadores posean permisos de exportación.  
- **Opción 2: Una tabla independiente por cada subtipo (sin tabla supertipo).**  
  - *Ventaja:* Elimina por completo las columnas con valores nulos.  
  - *Desventaja:* Duplica la estructura de los atributos comunes en tres tablas distintas. Asimismo, complica la integridad referencial en la tabla **COMPROBANTE**, ya que una venta no podría apuntar mediante una única clave foránea a una sola tabla de clientes.  
- **Opción 3: Supertipo más subtipos (Estrategia Elegida).**  
  - *Implementación:* Se definió la tabla padre **CLIENTE** con los atributos comunes (id_cliente, nombre_razon_social, tipo_documento, nro_documento, direccion, cod_postal, fecha_alta, tipo_cliente, porcentaje_descuento) y tres tablas hijas (**CLIENTE_SOCIO**, **CLIENTE_DISTRIBUIDOR** y **CLIENTE_EXPORTADOR**) cuya clave primaria es id_cliente, actuando a la vez como clave foránea hacia **CLIENTE**.  
  - *Ventaja y justificación de la elección:* Evita el uso de campos NULL innecesarios, mantiene los atributos comunes en un único lugar y permite que **COMPROBANTE** referencie limpiamente a CLIENTE(id_cliente). Fundamentalmente, permite que la tabla **PERMISO_EXPORTACION** apunte su clave foránea de manera exclusiva a CLIENTE_EXPORTADOR(id_cliente), asegurando por diseño estructural el cumplimiento de la regla **RN-07** (ningún socio ni distribuidor puede registrar permisos de exportación).  
  - *Desventaja asumida:* Requiere realizar un JOIN por clave primaria cuando se necesitan consultar los atributos específicos de un distribuidor o exportador.  
**Paso 4: Verificación de Normalización hasta 3FN (Bodegas, Vinos, Clientes y Ventas)**  
**1. Dependencias Funcionales () Relevantes del Subdominio**  
Se listan las dependencias funcionales identificadas en las relaciones del subdominio, donde indica que el atributo o conjunto de atributos determina unívocamente a :  
- **BODEGA:**  
- **VINO:**  
- **COMPOSICION_VINO:**  
- **MARIDAJE y VINO_MARIDAJE:**  
  - *(clave compuesta sin atributos no clave)*  
- **CLIENTE y Subtipos:**  
- **PERMISO_EXPORTACION:**  
- **COMPROBANTE y RENGLON_COMPROBANTE:**  
**2. Verificación de Primera Forma Normal (1FN)**  
Una relación se encuentra en **1FN** cuando todos sus atributos contienen valores atómicos (indivisibles) y no existen atributos multivalorados ni grupos repetitivos.  
- **Composición y maridajes de vinos:** Como un vino puede estar compuesto por varias cepas y tener múltiples maridajes recomendados, dichos conjuntos no se almacenan como listas dentro de **VINO**, sino en las tablas **COMPOSICION_VINO** y **VINO_MARIDAJE**, donde cada fila registra un único valor atómico.  
- **Permisos de exportación:** Dado que un exportador puede poseer varios permisos, estos se separaron en la tabla **PERMISO_EXPORTACION**, evitando atributos multivalorados en el cliente.  
- **Detalle de ventas:** Los múltiples vinos incluidos en una venta se desglosaron en la tabla **RENGLON_COMPROBANTE**, garantizando la atomicidad de cada ítem facturado.  
**3. Verificación de Segunda Forma Normal (2FN)**  
Una relación está en **2FN** si cumple 1FN y ningún atributo no clave depende parcialmente de una parte de una clave primaria compuesta.  
- **Tablas con clave primaria simple:** Las relaciones **BODEGA**, **VINO**, **MARIDAJE**, **CLIENTE**, **CLIENTE_SOCIO**, **CLIENTE_DISTRIBUIDOR**, **CLIENTE_EXPORTADOR**, **PERMISO_EXPORTACION** y **COMPROBANTE** poseen claves primarias formadas por un único atributo, por lo que cumplen **2FN** de manera directa al no poder existir dependencias parciales.  
- **Tablas con clave primaria compuesta:**  
  - En **COMPOSICION_VINO** (), el atributo porcentaje depende de la combinación completa de ambos identificadores, ya que un vino tiene distintos porcentajes por cepa y una cepa participa en distintos porcentajes según el vino. Los datos propios del vino o de la cepa se mantienen en sus respectivas tablas maestras.  
  - En **VINO_MARIDAJE** (), no existen atributos adicionales fuera de la clave primaria compuesta (la temperatura_servicio depende solo de id_maridaje y reside en **MARIDAJE**), cumpliendo **2FN**.  
  - En **RENGLON_COMPROBANTE** (), los atributos cantidad, precio_unitario, descuento y subtotal dependen de la clave compuesta completa. Tanto precio_unitario como descuento representan los valores históricos vigentes en el momento exacto de esa venta particular (ya que el precio de catálogo del vino o el descuento del cliente pueden modificarse posteriormente, según las reglas **RN-13**, **U3** y **U6**), mientras que los datos que dependen solo de nro_comprobante (fecha, id_cliente, id_sala) se encuentran en la cabecera **COMPROBANTE**.  
**4. Verificación de Tercera Forma Normal (3FN)**  
Una relación está en **3FN** si se encuentra en 2FN y no existen dependencias funcionales transitivas (ningún atributo no clave depende de otro atributo no clave: ):  
- **Separación entre VINO y BODEGA:** En **VINO**, el código del vino determina a su bodega elaboradora (). La razón social y el domicilio de la bodega () se almacenan exclusivamente en la tabla **BODEGA**, evitando la dependencia transitiva dentro de **VINO** y previniendo anomalías de actualización.  
- **Separación entre CLIENTE y LOCALIDAD:** En **CLIENTE**, se registra únicamente la clave foránea cod_postal (). Los atributos determinados por el código postal () residen en la tabla **LOCALIDAD**, eliminando toda dependencia transitiva en los datos del cliente.  
- **Independencia en COMPROBANTE y PERMISO_EXPORTACION:** En **COMPROBANTE** solo se almacenan las claves foráneas id_cliente e id_sala, sin arrastrar atributos descriptivos del cliente ni de la sala de venta. De igual modo, en **PERMISO_EXPORTACION** solo se referencia a id_cliente, manteniendo el atributo pais_destino en **CLIENTE_EXPORTADOR**.  
- **Descuento en CLIENTE:** El atributo porcentaje_descuento depende funcionalmente de id_cliente (). Si bien al darse de alta se asigna según el tipo_cliente (**RN-06**: 10%, 20% o 30%), un exportador puede pasar a tener un 35% de descuento en función de la cantidad de permisos que posea (operación **U6**), por lo que el porcentaje pertenece directamente a la instancia del cliente, cumpliendo **3FN**.  
**DICCIONARIO DE DATOS**  
**Diccionario de Datos (Subdominio Bodegas, Vinos, Clientes y Ventas)**  
  
|  |  |  |  |  |  |  
| - | - | - | - | - | - |  
| **Tabla** |  **Columna** |  **Tipo de Dato** |  **Admite Nulos** |  **Restricciones** |  **Descripción** |  
| **bodega** |  cuit |  cuit_dom (CHAR(11)) |  NO |  PK, DOMAIN |  CUIT de 11 dígitos numéricos de la bodega elaboradora. |  
| **bodega** |  razon_social |  VARCHAR(100) |  NO |  UNIQUE, NOT NULL |  Nombre legal o razón social de la bodega. |  
| **bodega** |  domicilio |  VARCHAR(150) |  NO |  NOT NULL |  Dirección física de la bodega. |  
| **vino** |  cod_vino |  INTEGER |  NO |  PK, IDENTITY |  Código identificador autogenerado del vino. |  
| **vino** |  nombre |  VARCHAR(80) |  NO |  NOT NULL, UNIQUE (comp.) |  Nombre comercial de la etiqueta. |  
| **vino** |  tipo |  tipo_vino (ENUM) |  NO |  NOT NULL |  Clasificación: tinto, blanco, rosado o espumante. |  
| **vino** |  anada |  SMALLINT |  NO |  NOT NULL, CHECK (1990..2100), UNIQUE (comp.) |  Año de cosecha del vino. |  
| **vino** |  volumen_ml |  INTEGER |  NO |  NOT NULL, CHECK (187,375,750,1500,3000), UNIQUE (comp.) |  Capacidad de la botella en mililitros. |  
| **vino** |  graduacion |  NUMERIC(4,2) |  NO |  NOT NULL, CHECK (5..20) |  Graduación alcohólica en grados (RN-15). |  
| **vino** |  precio |  NUMERIC(12,2) |  NO |  NOT NULL, CHECK (> 0) |  Precio de venta único en toda la red de salas (RN-01). |  
| **vino** |  cuit_bodega |  cuit_dom (CHAR(11)) |  NO |  FK -> bodega(cuit), NOT NULL |  Bodega del grupo que elabora el vino (ON DELETE RESTRICT). |  
| **composicion_vino** |  cod_vino |  INTEGER |  NO |  PK, FK -> vino(cod_vino) |  Código del vino al que pertenece el corte (ON DELETE CASCADE). |  
| **composicion_vino** |  id_cepa |  INTEGER |  NO |  PK, FK -> cepa(id_cepa) |  Cepa que integra la composición del vino (ON DELETE RESTRICT). |  
| **composicion_vino** |  porcentaje |  NUMERIC(5,2) |  NO |  NOT NULL, CHECK (> 0 y <= 100) |  Porcentaje de la cepa en el vino; deben sumar 100 por vino (RN-05). |  
| **maridaje** |  id_maridaje |  INTEGER |  NO |  PK, IDENTITY |  Identificador único del maridaje recomendado. |  
| **maridaje** |  nombre |  VARCHAR(80) |  NO |  UNIQUE, NOT NULL |  Plato o acompañamiento sugerido (ej. carnes rojas). |  
| **maridaje** |  temperatura_servicio |  SMALLINT |  NO |  NOT NULL, CHECK (0..30) |  Temperatura de servicio recomendada en grados Celsius (°C). |  
| **vino_maridaje** |  cod_vino |  INTEGER |  NO |  PK, FK -> vino(cod_vino) |  Vino al que se asocia la recomendación (ON DELETE CASCADE). |  
| **vino_maridaje** |  id_maridaje |  INTEGER |  NO |  PK, FK -> maridaje(id_maridaje) |  Maridaje recomendado para dicho vino (ON DELETE RESTRICT). |  
| **cliente** |  id_cliente |  INTEGER |  NO |  PK, IDENTITY |  Identificador único del cliente (Supertipo). |  
| **cliente** |  nombre_razon_social |  VARCHAR(120) |  NO |  NOT NULL |  Apellido y nombre o razón social del cliente. |  
| **cliente** |  tipo_documento |  VARCHAR(10) |  NO |  NOT NULL, UNIQUE (comp.) |  Tipo de documento (DNI, CUIT, PAS). |  
| **cliente** |  nro_documento |  VARCHAR(20) |  NO |  NOT NULL, UNIQUE (comp.) |  Número de documento del cliente. |  
| **cliente** |  direccion |  VARCHAR(150) |  NO |  NOT NULL |  Domicilio del cliente. |  
| **cliente** |  cod_postal |  VARCHAR(10) |  NO |  FK -> localidad(cod_postal), NOT NULL |  Localidad de residencia del cliente (ON DELETE RESTRICT). |  
| **cliente** |  fecha_alta |  DATE |  NO |  NOT NULL, DEFAULT CURRENT_DATE |  Fecha en que el cliente fue dado de alta. |  
| **cliente** |  tipo_cliente |  tipo_cliente_enum |  NO |  NOT NULL |  Categoría del subtipo: socio, distribuidor o exportador. |  
| **cliente** |  porcentaje_descuento |  NUMERIC(5,2) |  NO |  NOT NULL, CHECK (0..100) |  Porcentaje de descuento según tipo: 10%, 20% o 30% (RN-06). |  
| **cliente_socio** |  id_cliente |  INTEGER |  NO |  PK, FK -> cliente(id_cliente) |  Subtipo socio del club / consumidor final (ON DELETE CASCADE). |  
| **cliente_distribuidor** |  id_cliente |  INTEGER |  NO |  PK, FK -> cliente(id_cliente) |  Subtipo cliente distribuidor (ON DELETE CASCADE). |  
| **cliente_distribuidor** |  zona_cobertura |  VARCHAR(100) |  NO |  NOT NULL |  Región o zona geográfica cubierta por el distribuidor. |  
| **cliente_distribuidor** |  nro_habilitacion |  VARCHAR(40) |  NO |  UNIQUE, NOT NULL |  Número de habilitación comercial del distribuidor. |  
| **cliente_exportador** |  id_cliente |  INTEGER |  NO |  PK, FK -> cliente(id_cliente) |  Subtipo cliente exportador (ON DELETE CASCADE). |  
| **cliente_exportador** |  pais_destino |  VARCHAR(80) |  NO |  NOT NULL |  País de destino principal de las exportaciones. |  
| **permiso_exportacion** |  cod_permiso |  VARCHAR(40) |  NO |  PK |  Código identificatorio del permiso de exportación. |  
| **permiso_exportacion** |  id_cliente |  INTEGER |  NO |  FK -> cliente_exportador(id_cliente), NOT NULL |  Exportador titular del permiso (RN-07, ON DELETE CASCADE). |  
| **permiso_exportacion** |  fecha_emision |  DATE |  NO |  NOT NULL |  Fecha de otorgamiento del permiso. |  
| **permiso_exportacion** |  fecha_vencimiento |  DATE |  NO |  NOT NULL, CHECK (fecha_vencimiento > fecha_emision) |  Fecha de expiración posterior a la emisión (RN-07). |  
| **comprobante** |  nro_comprobante |  INTEGER |  NO |  PK, IDENTITY |  Número único de comprobante de venta. |  
| **comprobante** |  fecha |  DATE |  NO |  NOT NULL, DEFAULT CURRENT_DATE |  Fecha de emisión del comprobante. |  
| **comprobante** |  id_cliente |  INTEGER |  NO |  FK -> cliente(id_cliente), NOT NULL |  Cliente comprador (ON DELETE RESTRICT). |  
| **comprobante** |  id_sala |  INTEGER |  NO |  FK -> sala_venta(id_sala), NOT NULL |  Sala de venta donde se realizó la operación (ON DELETE RESTRICT). |  
| **comprobante** |  subtotal |  NUMERIC(14,2) |  NO |  NOT NULL, DEFAULT 0, CHECK (>= 0) |  Suma de importes brutos de los renglones. |  
| **comprobante** |  descuento |  NUMERIC(14,2) |  NO |  NOT NULL, DEFAULT 0, CHECK (>= 0) |  Monto total descontado según el tipo de cliente. |  
| **comprobante** |  total |  NUMERIC(14,2) |  NO |  NOT NULL, DEFAULT 0, CHECK (>= 0) |  Importe neto final calculado por la base de datos (RN-08). |  
| **renglon_comprobante** |  nro_comprobante |  INTEGER |  NO |  PK, FK -> comprobante(nro_comprobante) |  Cabecera del comprobante al que pertenece (ON DELETE CASCADE). |  
| **renglon_comprobante** |  cod_vino |  INTEGER |  NO |  PK, FK -> vino(cod_vino) |  Vino incluido en el renglón de venta (ON DELETE RESTRICT). |  
| **renglon_comprobante** |  cantidad |  INTEGER |  NO |  NOT NULL, CHECK (> 0) |  Cantidad de botellas vendidas en el renglón (RN-15). |  
| **renglon_comprobante** |  precio_unitario |  NUMERIC(12,2) |  NO |  NOT NULL, CHECK (> 0) |  Precio unitario del vino vigente al momento de la venta. |  
| **renglon_comprobante** |  descuento |  NUMERIC(5,2) |  NO |  NOT NULL, CHECK (0..100) |  Porcentaje de descuento aplicado al renglón según el cliente. |  
| **renglon_comprobante** |  subtotal |  NUMERIC(14,2) |  NO |  NOT NULL, CHECK (> 0) |  Subtotal neto del renglón con el descuento aplicado. |  
  
   
