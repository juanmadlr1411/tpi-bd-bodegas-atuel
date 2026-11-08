## 1. Índices sobre Claves Foráneas (FK) - Responsable: Manuel

A diferencia de las claves primarias (PK), PostgreSQL **no indexa automáticamente** las claves foráneas (FK). Esto significa que cualquier cruce (`JOIN`) o verificación de integridad referencial obliga al motor a realizar un costoso escaneo secuencial completo (`Seq Scan`) de la tabla. Esto es especialmente crítico en operaciones de borrado (`ON DELETE RESTRICT`), donde se debe recorrer toda la tabla dependiente para asegurar que no haya registros vinculados.

Para evitar estos escaneos secuenciales y optimizar el rendimiento para la Etapa 5, se implementaron los siguientes índices B-Tree:

* **`idx_fk_comprobante_cliente`**: Evita escaneos completos al cruzar la tabla de clientes con los más de 150.000 comprobantes. Optimiza drásticamente las consultas **S3** y **S12**, las sentencias de eliminación **D1** y **D4**, y acelera los chequeos de `ON DELETE RESTRICT`.
* **`idx_fk_renglon_transf_vino`**: Optimiza los filtros y agrupaciones directas por vino sobre los 15.004 renglones de transferencia, impactando de forma directa en el rendimiento de la consulta **S4**.
* **`idx_fk_ingreso_transporte`**: Acelera los cruces por empresa transportista, reduciendo el costo de las agrupaciones necesarias para la consulta **S7** y la inserción **I1**.

*(Nota: La creación del índice sobre `renglon_comprobante(cod_vino)` fue omitida intencionalmente en esta sección, ya que será abordada mediante un índice Covering con cláusula `INCLUDE` en el bloque correspondiente a Santiago).*