# Informe Etapa 3 (H3): Carga Masiva de Datos, Triggers y Respaldo

**Proyecto:** Bodegas del Atuel  
**Responsable de QA y Documentación H3:** Juan Manuel  

---

## 1. Definición del Orden Topológico de Inserción

Se estableció el orden estricto de inserción de datos según las dependencias de las claves foráneas (`FOREIGN KEY`) definidas en `001_esquema.sql`, evitando rechazos por integridad referencial durante la carga masiva. La secuencia se organiza en cinco niveles:

    [Nivel 1: Catálogos Raíz (CSV / Sin FK)]
     ├── localidad
     ├── cepa
     ├── maridaje
     ├── bodega
     └── transportista
           │
           ▼
    [Nivel 2: Entidades Geográficas, Estructurales y Supertipo]
     ├── sala_venta (FK -> localidad)
     ├── empleado (FK -> sala_venta)
     ├── finca
     ├── transportista_localidad (FK -> transportista, localidad)
     └── cliente (FK -> localidad)
           │
           ▼
    [Nivel 3: Subtipos y Entidades de Producción]
     ├── cliente_socio (FK -> cliente)
     ├── cliente_distribuidor (FK -> cliente)
     ├── cliente_exportador (FK -> cliente)
     │    └── permiso_exportacion (FK -> cliente_exportador)
     ├── parcela (FK -> finca, cepa)
     │    └── lote_uva (FK -> parcela, bodega)
     │         └── analisis_calidad (FK -> lote_uva)
     └── vino (FK -> bodega)
          └── auditoria_precio (FK -> vino)
           │
           ▼
    [Nivel 4: Cruces N:M e Inventario Inicial]
     ├── composicion_vino (FK -> vino, cepa)
     ├── vino_maridaje (FK -> vino, maridaje)
     ├── stock_deposito (FK -> vino)
     └── stock_sala (FK -> sala_venta, vino)
           │
           ▼
    [Nivel 5: Documentos Transaccionales (Cabeceras y Renglones)]
     ├── ingreso (FK -> transportista, bodega)
     │    └── renglon_ingreso (FK -> ingreso, vino)
     ├── transferencia (FK -> sala_venta)
     │    └── renglon_transferencia (FK -> transferencia, vino)
     └── comprobante (FK -> cliente, sala_venta)
          └── renglon_comprobante (FK -> comprobante, vino)

---

## 2. Estrategia de Manejo de Triggers durante la Carga Masiva

### 2.1 Problema: Choque entre la carga histórica y los Triggers de la Etapa 2
Durante la operación normal del sistema, los triggers de `005_triggers.sql` protegen las reglas de negocio en tiempo real. Sin embargo, al inyectar el historial de 58 meses (enero 2022 a octubre 2026, con 150.000 comprobantes y 600.000 renglones), mantener todos los triggers activos genera dos inconvenientes:

1. **Bloqueo lógico de datos históricos válidos:**
   * **RN-11 (Fecha actual en transferencias):** El trigger `BEFORE INSERT` (`trg_fecha_confeccion_transferencia`) fuerza `fecha_confeccion = CURRENT_DATE`. Si permaneciera activo durante la carga histórica, sobrescribiría la fecha de todas las transferencias pasadas con la fecha actual, arruinando la distribución temporal requerida para las consultas de la Etapa 5 (ej. S4).
   * **RN-12 (Inmutabilidad de documentos cerrados):** El trigger sobre `renglon_ingreso` y `renglon_transferencia` rechaza inserciones si la cabecera ya figura en estado `'terminado'` o `'procesado'`.
   * **RN-09 (Validación contra stock actual):** Validar ventas históricas de hace años contra la foto final de `stock_sala` rechazaría operaciones válidas si no se simula la secuencia cronológica.
2. **Degradación de rendimiento:**
   * Ejecutar validaciones y recálculos fila por fila sobre 600.000 registros de `renglon_comprobante` multiplica las lecturas y escrituras sobre las tablas de cabecera y stock.

### 2.2 Decisión Técnica: `DISABLE TRIGGER USER` y Excepción Controlada
En PostgreSQL existen dos variantes para desactivar triggers:
* `ALTER TABLE ... DISABLE TRIGGER ALL`: Desactiva tanto los triggers de negocio como los triggers internos del motor que implementan las `FOREIGN KEY` (`RI_ConstraintTrigger`), y exige permisos de `SUPERUSER` (incompatible con entornos gestionados en la nube en la Etapa 8).
* `ALTER TABLE ... DISABLE TRIGGER USER` (**Opción Elegida**): Desactiva únicamente los triggers definidos por el grupo en la Etapa 2, **manteniendo activas todas las restricciones `PRIMARY KEY`, `FOREIGN KEY`, `UNIQUE` y `CHECK`**.

**Flujo implementado en el repositorio:**
1. **Pre-carga (`db/seed/01_preparar_motor_pre_carga.sql`):** Ejecuta `ALTER TABLE ... DISABLE TRIGGER USER;` antes de correr `carga_maestras.py`.
2. **Reactivación post-maestras (`db/seed/02_restaurar_motor_post_carga.sql`):** Rehabilita los triggers (`ENABLE TRIGGER USER`) una vez insertados los catálogos y maestros.
3. **Carga transaccional (`db/seed/carga_h3_final.py`):** Simula mes a mes los 58 meses de inventario. Desactiva de forma aislada `trg_fecha_confeccion_transferencia` dentro de la transacción para preservar las fechas históricas 2022–2026 y lo reactiva antes del `COMMIT`.
4. **Posprocesamiento:** Se ejecuta `REFRESH MATERIALIZED VIEW mv_ventas_mensuales_sala;` y `ANALYZE;` para actualizar las estadísticas del planificador.

---

## 3. Conteo Final de Filas (Las 29 Tablas del Esquema)

Se verificó la carga completa sobre la base de datos local, superando las exigencias de la cátedra (todas las tablas con registros, al menos 3 tablas con más de 10.000 filas y al menos 1 tabla superando las 100.000 filas):

| # | Subdominio | Tabla | Filas Cargadas | Criterio / Observación |
| :---: | :--- | :--- | ---: | :--- |
| 1 | Geografía y Salas | `localidad` | 18 | Catálogo CSV (Departamentos de Mendoza) |
| 2 | Geografía y Salas | `sala_venta` | 6 | 6 salas distribuidas en localidades |
| 3 | Geografía y Salas | `empleado` | 18 | 3 empleados por cada sala de venta |
| 4 | Producción de Uva | `finca` | 12 | Generadas en departamentos vitivinícolas |
| 5 | Producción de Uva | `cepa` | 12 | Catálogo CSV (7 tintas y 5 blancas) |
| 6 | Producción de Uva | `parcela` | 36 | Entidad débil (3 parcelas por finca) |
| 7 | Producción de Uva | `lote_uva` | 180 | 1 cosecha por parcela por campaña (5 años) |
| 8 | Producción de Uva | `analisis_calidad` | 360 | 2 análisis fisicoquímicos por lote de uva |
| 9 | Bodegas y Vinos | `bodega` | 10 | Elaboradoras del grupo |
| 10 | Bodegas y Vinos | `vino` | 40 | Catálogo de vinos por añada y presentación |
| 11 | Bodegas y Vinos | `composicion_vino` | 60 | Cortes varietales (1 a 2 cepas sumando 100%) |
| 12 | Bodegas y Vinos | `maridaje` | 8 | Catálogo CSV oficial |
| 13 | Bodegas y Vinos | `vino_maridaje` | 40 | Recomendaciones por vino |
| 14 | Clientes | `cliente` | 1.000 | Supertipo de la jerarquía ERE |
| 15 | Clientes | `cliente_socio` | 334 | Subtipo Socio (10% descuento) |
| 16 | Clientes | `cliente_distribuidor` | 333 | Subtipo Distribuidor (20% descuento) |
| 17 | Clientes | `cliente_exportador` | 333 | Subtipo Exportador (30% descuento) |
| 18 | Clientes | `permiso_exportacion` | 333 | Permisos vigentes asociados a exportadores |
| 19 | Logística y Stock | `transportista` | 5 | Empresas de transporte registradas |
| 20 | Logística y Stock | `transportista_localidad` | 15 | 3 localidades cubiertas por transportista |
| 21 | Logística y Stock | `stock_deposito` | 40 | Stock central inicializado y conciliado para los 40 vinos |
| 22 | Logística y Stock | `stock_sala` | 240 | Matriz de stock (6 salas × 40 vinos) |
| 23 | Movimientos Stock | `ingreso` | 5.000 | Cabeceras históricas (2022–2026) |
| 24 | Movimientos Stock | `renglon_ingreso` | 14.349 | **> 10.000 filas (Tabla #1 que supera 10k)** |
| 25 | Movimientos Stock | `transferencia` | 5.000 | Cabeceras históricas hacia salas |
| 26 | Movimientos Stock | `renglon_transferencia` | 15.000 | **> 10.000 filas (Tabla #2 que supera 10k)** |
| 27 | Ventas | `comprobante` | 150.000 | **> 100.000 filas (Tabla #3 que supera 10k y 100k)** |
| 28 | Ventas | `renglon_comprobante` | 600.000 | **> 500.000 filas (Supera meta recomendada)** |
| 29 | Auditoría | `auditoria_precio` | 40 | Registro de actualizaciones de precio (RN-13) |
| - | **TOTAL GENERAL** | **29 tablas** | **792.473** | **Volumen integral verificado** |

---

## 4. Comparación de inserción fila por fila versus por lotes (medición reproducible)

Se agregó el archivo `db/seed/medir_inserciones_h3.py`, que inserta **la misma
muestra de 1,000 filas** en una **tabla temporal** PostgreSQL,
primero con `cursor.execute()` individual y después con `cursor.executemany()`.
Tras cada método se comprueba el `COUNT(*)`. Todas las inserciones son
revertidas; no se modifican las tablas operativas.

| Método | Muestra | Tiempo medido |
|---|---:|---:|
| Fila por fila (`execute`) | 1,000 | **0.1131 s** |
| Por lotes (`executemany`) | 1,000 | **0.0139 s** |

Relación temporal de esta ejecución: **8.17x**.

**Alcance:** es una comparación del método de envío/inserción para una tabla
temporal **sin triggers ni claves foráneas**. Los resultados no deben
presentarse como tiempos de carga del esquema transaccional real ni
extrapolarse directamente a 789.349 filas.

**Tiempo real registrado de generación y persistencia histórica:**
**19.342,15 segundos (~5 h 22 min)** para 58 meses, con triggers de negocio
activos salvo la excepción transaccional del trigger de fecha RN-11.

**Documentos pendientes:** el generador principal crea automáticamente
los pendientes en futuras cargas definitivas; para una base ya cargada se
incorporó `db/seed/agregar_pendientes_h3.py`, que añade 2 ingresos y 2 transferencias
en `en_confeccion`, y la misma cantidad en `terminado`, siempre con renglones.
Estos movimientos no impactan stock porque no se procesan. La vista
`vw_documentos_pendientes` pasa a ofrecer 8 documentos para S5.
La tabla de conteos históricos de la sección anterior corresponde al lote
**antes de esta poscarga**. Después, el total transaccional pasa de 789.349
a **789.365 registros**.

---

## 5. Consultas SQL de Control Post-Carga (Paso 7)

Una vez finalizada la carga y reactivados todos los triggers de usuario, se ejecutaron las siguientes consultas de auditoría para certificar que no existan inconsistencias ni violaciones a las Reglas de Negocio:

### 5.1 Control de Composición Varietal (RN-05: 0 vinos que no sumen 100%)

    SELECT COUNT(*) AS vinos_con_corte_invalido
    FROM (
        SELECT v.cod_vino, COALESCE(SUM(cv.porcentaje), 0) AS suma_porcentaje
        FROM public.vino v
        LEFT JOIN public.composicion_vino cv ON cv.cod_vino = v.cod_vino
        GROUP BY v.cod_vino
        HAVING COALESCE(SUM(cv.porcentaje), 0) <> 100.00
    ) sub;

**Resultado obtenido:** `0` filas.

### 5.2 Control de Consistencia de Totales en Comprobantes (RN-08: 0 diferencias con `fn_total_comprobante`)

    SELECT COUNT(*) AS comprobantes_descuadrados
    FROM public.comprobante c
    WHERE c.total <> public.fn_total_comprobante(c.nro_comprobante);

**Resultado obtenido:** `0` diferencias.

### 5.3 Control de Existencias Negativas en Depósito y Salas (RN-09 y RN-15: 0 stocks negativos)

    SELECT 
        (SELECT COUNT(*) FROM public.stock_deposito WHERE cantidad < 0) AS stock_deposito_negativo,
        (SELECT COUNT(*) FROM public.stock_sala WHERE cantidad < 0)     AS stock_sala_negativo;

**Resultado obtenido:** `0` en depósito y `0` en salas.

### 5.4 Control de Filas Huérfanas y Cabeceras sin Renglones (RN-10 y RN-11: 0 filas huérfanas)

    SELECT
        (SELECT COUNT(*) FROM public.comprobante c LEFT JOIN public.renglon_comprobante rc ON rc.nro_comprobante = c.nro_comprobante WHERE rc.nro_comprobante IS NULL) AS comprobantes_sin_renglones,
        (SELECT COUNT(*) FROM public.ingreso i LEFT JOIN public.renglon_ingreso ri ON ri.cod_ingreso = i.cod_ingreso WHERE ri.cod_ingreso IS NULL) AS ingresos_sin_renglones,
        (SELECT COUNT(*) FROM public.transferencia t LEFT JOIN public.renglon_transferencia rt ON rt.nro_transferencia = t.nro_transferencia WHERE rt.nro_transferencia IS NULL) AS transferencias_sin_renglones;

**Resultado obtenido:** `0` comprobantes vacíos, `0` ingresos vacíos y `0` transferencias vacías.

---

## 6. Respaldo Reproducible (`pg_dump` y Restauración)

Certificada la integridad de los datos, se genera el volcado comprimido de la base de datos para que todo el equipo inicie la Etapa 4 (Índices y Rendimiento) con exactamente el mismo estado físico:

    # Generación del volcado comprimido con nivel máximo (-9)
    docker exec -i bodegas_atuel_db pg_dump -U admin_atuel -d bodegas_atuel --clean --if-exists --no-owner --no-privileges | gzip -9 > db/seed/dump_completo.sql.gz

    # Comando para restaurar el volcado en una base limpia
    gunzip -c db/seed/dump_completo.sql.gz | docker exec -i bodegas_atuel_db psql -U admin_atuel -d bodegas_atuel
