# Informe Etapa 6 (H6): API REST, Capa DAL, Transacciones y Mapeo de Errores

**Proyecto:** Bodegas del Atuel  
**Asignatura:** Bases de Datos — UTN FRSR (2026)  
**Equipo:** Gonzalo (Onza), Santiago (Bando), Bruno (Br1), Manuel (Pelu), Juan Manuel (Delgado)  

---

## 1. Introducción y Objetivos de la Etapa

El objetivo principal de la Etapa 6 es exponer el modelo relacional de **Bodegas del Atuel** mediante una API REST moderna y robusta, **sin ocultar el SQL ni duplicar en el backend las reglas que ya residen en el motor de base de datos**.

Bajo esta premisa, la API actúa como una compuerta transaccional y de comunicación estricta que:
1. Conecta a la base mediante el driver nativo **`psycopg` (versión 3)** con consultas **100 % parametrizadas**, erradicando cualquier riesgo de inyección SQL.
2. Utiliza una **capa de acceso a datos propia (DAL)** que centraliza las consultas en módulos desacoplados de los controladores.
3. Administra un **pool de conexiones** y controla explícitamente las transacciones atómicas (`BEGIN`, `COMMIT`, `ROLLBACK`) en operaciones compuestas.
4. Opera bajo el **rol de base de datos no privilegiado (`operador_atuel`)**, impidiendo accesos destructivos o de administración.
5. Traduce de forma unificada los códigos de error internos de PostgreSQL (**SQLSTATE**) a estados HTTP semánticos (409, 422, 400, 503).
6. Expone los reportes analíticos de la Sección 8 y el catálogo con filtros dinámicos y paginación.
7. Cuenta con una batería de **36 pruebas automáticas** que validan tanto los circuitos operativos exitosos como las violaciones deliberadas de reglas de negocio.

---

## 2. Arquitectura del Proyecto Backend

La estructura del código en la carpeta `api/` sigue el patrón de separación de responsabilidades:

```text
api/
├── config.py              # Variables de entorno y configuración centralizada (Pydantic Settings)
├── database.py            # Pool de conexiones psycopg_pool y context managers transaccionales
├── exceptions.py          # Manejador global de excepciones PostgreSQL (SQLSTATE -> HTTP)
├── main.py                # Aplicación FastAPI, lifespan, middleware CORS y registro de routers
├── dal/                   # Capa de Acceso a Datos (Data Access Layer - SQL nativo puro)
│   ├── clientes.py
│   ├── comprobantes.py
│   ├── ingresos.py
│   ├── reportes.py
│   ├── salas.py
│   ├── transferencias.py
│   └── vinos.py
├── routers/               # Controladores HTTP y endpoints REST
│   ├── clientes.py
│   ├── comprobantes.py
│   ├── ingresos.py
│   ├── reportes.py
│   ├── salas.py
│   ├── salud.py
│   ├── transferencias.py
│   └── vinos.py
└── schemas/               # Esquemas de validación y serialización (Pydantic v2)
    ├── clientes.py
    ├── comprobantes.py
    ├── ingresos.py
    ├── reportes.py
    ├── salas.py
    ├── transferencias.py
    └── vinos.py
```

### 2.1 Pool de Conexiones y Ciclo de Vida (`database.py`)
Se implementó un pool de conexiones administrado mediante `psycopg_pool.ConnectionPool`:
* **Apertura y Cierre:** El pool se inicializa al arrancar la aplicación en el hook `@asynccontextmanager lifespan` de FastAPI y se libera de forma ordenada al apagarse el servidor.
* **Tamaño del Pool:** Configurable vía variables de entorno (`DB_POOL_MIN_SIZE=2`, `DB_POOL_MAX_SIZE=10`).
* **Row Factory:** Se configura `row_factory=dict_row` para devolver directamente diccionarios indexables por nombre de columna.
* **Manejo Transaccional:** El context manager `with conn.transaction():` asegura atomicidad total en operaciones de varias sentencias. Si cualquier sentencia genera una excepción de PostgreSQL, el bloque emite un `ROLLBACK` inmediato y libera la conexión hacia el pool.

---

## 3. Seguridad y Modelo de Roles (RN-07 / Privilegios Restringidos)

En cumplimiento de los criterios de la cátedra:
* La API **nunca** se conecta como `admin_atuel` ni como `postgres`.
* Se conecta con el usuario **`operador_atuel`** creado en `007_roles.sql`:
  * Permisos concedidos: `CONNECT`, `USAGE ON SCHEMA public`, `SELECT, INSERT, UPDATE, DELETE ON ALL TABLES`, `USAGE ON ALL SEQUENCES`.
  * Permisos de ejecución: `GRANT EXECUTE` sobre funciones normativas (`fn_total_comprobante`, `fn_descuento_por_tipo`) y procedimientos almacenados (`sp_procesar_ingreso`, `sp_procesar_transferencia`).
  * Sin privilegios DDL: No puede alterar tablas, modificar triggers ni invocar comandos de administración de base de datos.
* Se agregó la protección en `tests/conftest.py` que aborta inmediatamente la suite de pruebas si se detecta una conexión indebida como superusuario.

---

## 4. Traducción Centralizada de Errores PostgreSQL (`exceptions.py`)

Cualquier error originado en el motor relacional (ya sea por una restricción declarativa o por un `RAISE EXCEPTION` en una función o trigger) es capturado de manera centralizada por el middleware `postgres_exception_handler`.

### Tabla de Traducción de SQLSTATE a Códigos HTTP:

| Situación en PostgreSQL | Código SQLSTATE | Código HTTP Retornado | Descripción / Respuesta Semántica |
|---|---|---|---|
| Clave única violada (UNIQUE) | `23505` | **409 Conflict** | Conflicto: Ya existe un registro con la misma clave única o primaria. |
| Clave foránea violada (FK) | `23503` | **409 Conflict** | Conflicto de clave foránea: Registro relacionado inexistente o con dependencias activas (RN-14). |
| Restricción CHECK violada | `23514` | **422 Unprocessable Entity** | Violación de restricción CHECK en los datos ingresados (RN-15). |
| Restricción NOT NULL violada | `23502` | **422 Unprocessable Entity** | Violación de valor requerido NOT NULL. |
| Regla de negocio en trigger/SP (`RAISE EXCEPTION`) | `P0001` | **409 Conflict** | Regla de negocio rechazada por la base de datos (RN-05, RN-09, RN-10, RN-11, RN-12). Conserva el mensaje original. |
| Formato de texto o tipo de dato inválido | `22P02` | **400 Bad Request** | Formato de datos o tipo de dato inválido para PostgreSQL. |
| Fallo de serialización concurrente | `40001` | **503 Service Unavailable** | Fallo de serialización en transacción concurrente. Reintente la operación. |
| Deadlock detectado | `40P01` | **503 Service Unavailable** | Deadlock detectado en la base de datos. Reintente la operación. |

---

## 5. Catálogo Completo de Endpoints Expuestos

### 5.1 Catálogo y CRUD de Vinos (`/vinos`)
* `GET /vinos`: Listado paginado (`limit`, `offset`) con filtros dinámicos combinables por `tipo` (enum), `cepa` (nombre o ID), `bodega` (razón social o CUIT) y `anada` (año de cosecha).
* `GET /vinos/{cod_vino}`: Detalle exhaustivo con composición porcentual de cepas y maridajes sugeridos.
* `POST /vinos`: Alta atómica de un vino con su corte de cepas y maridajes. La base de datos valida que la suma de porcentajes de corte sea exactamente 100 % (**RN-05**).
* `PUT /vinos/{cod_vino}`: Actualización de datos maestros. La modificación del campo `precio` dispara el trigger `trg_auditar_cambio_precio` registrando el historial en `auditoria_precio` (**RN-13**).
* `DELETE /vinos/{cod_vino}`: Baja física. Si el vino posee comprobantes, transferencias o existencias históricas, la clave foránea `ON DELETE RESTRICT` rechaza la solicitud devolviendo `409 Conflict` (**RN-14**).

### 5.2 Clientes (`/clientes`)
* `GET /clientes`: Catálogo paginado con filtro opcional por subtipo (`socio`, `distribuidor`, `exportador`).
* `GET /clientes/{id_cliente}`: Detalle con datos específicos del subtipo (zona de cobertura, número de habilitación o país destino).
* `POST /clientes`: Alta en transacción de la cabecera en `cliente` y su tabla de subtipo (`cliente_socio`, `cliente_distribuidor` o `cliente_exportador`). El trigger `trg_asignar_descuento_cliente` calcula y asigna automáticamente el descuento normativo (**RN-06**: Socio 10 %, Distribuidor 20 %, Exportador 30 %).
* `PUT /clientes/{id_cliente}`: Modificación de domicilio, razón social o datos de subtipo.
* `DELETE /clientes/{id_cliente}`: Eliminación condicionada por `ON DELETE RESTRICT` si posee compras históricas (**RN-14**).

### 5.3 Comprobantes y Ventas Transaccionales (`/comprobantes`)
* `POST /comprobantes`: Venta completa (cabecera y renglones) en **una única transacción**.
  * **La API no calcula subtotales, totales ni descuenta stock:** delega dicha responsabilidad al motor.
  * El trigger `trg_comprobante_renglon_descuento_stock` valida que la sala posea stock suficiente (**RN-09**) y lo descuenta.
  * Si el stock es insuficiente, PostgreSQL aborta la transacción con `RAISE EXCEPTION` (`P0001` -> `409 Conflict`), asegurando que **no queden datos a medias**.
  * El trigger `trg_actualizar_total_comprobante` calcula subtotales y total neto aplicando el descuento normativo del cliente mediante `fn_total_comprobante` (**RN-08**).
* `GET /comprobantes/{nro_comprobante}`: Consulta de cabecera con totales consolidados y renglones asociados.

### 5.4 Transferencias de Stock (`/transferencias`)
* `POST /transferencias`: Alta en estado inicial `en_confeccion` (**RN-11**).
* `POST /transferencias/{nro}/renglones`: Carga de renglones de vinos y cantidades mientras permanece en confección.
* `POST /transferencias/{nro}/terminar`: Transición de estado a `terminado`. A partir de este momento, el trigger bloquea cualquier modificación o agregado de renglones (**RN-12**).
* `POST /transferencias/{nro}/procesar`: Invoca al procedimiento almacenado `CALL sp_procesar_transferencia(%s)`. Valida existencias en el depósito central, descuenta del depósito e incrementa el stock de la sala de destino de forma atómica (**RN-11**). Si una botella de cualquier renglón no alcanza, se revierte toda la transferencia.
* `GET /transferencias/{nro}`: Detalle de cabecera, sala de destino, estado y renglones.

### 5.5 Ingresos de Producción (`/ingresos`)
* `POST /ingresos`: Alta en estado `en_confeccion` asignando transportista y bodega remitente (**RN-10**).
* `POST /ingresos/{cod}/renglones`: Carga de renglones mientras está en confección.
* `POST /ingresos/{cod}/terminar`: Transición a `terminado`, sellando la edición de renglones (**RN-12**).
* `POST /ingresos/{cod}/procesar`: Invoca al procedimiento almacenado `CALL sp_procesar_ingreso(%s)`, impactando el stock del depósito central (**RN-10**).
* `GET /ingresos/{cod}`: Detalle de cabecera, bodega, transportista y renglones.

### 5.6 Salas de Venta (`/salas`)
* `GET /salas`: Listado completo de salas de venta con calle, número, código postal, localidad y día de cierre comercial. Permite alimentar dinámicamente los selectores del frontend.

### 5.7 Reportes de la Sección 8 (`/reportes`)
Exposición directa de las consultas analíticas optimizadas de la Etapa 5:
* `GET /reportes/top-vinos`: Ranking de los vinos más vendidos en toda la red (Consulta **S1**).
* `GET /reportes/ventas-por-sala`: Facturación total por sala en el último trimestre en orden descendente (Consulta **S8**).
* `GET /reportes/vinos-sin-stock?id_sala={id}`: Vinos en quiebre de stock en una sala pero con existencias disponibles en el depósito central (Consulta **S6**).
* `GET /reportes/transportista-activo`: Empresa de transporte con mayor cantidad de ingresos en el último mes (Consulta **S7**).
* `GET /reportes/trazabilidad/{cod_vino}`: Ficha técnica integral de un vino con corte de cepas, bodega productora, maridajes sugeridos y stock total consolidado (Consulta **S9**).

### 5.8 Salud y Conectividad (`/salud`)
* `GET /salud`: Verifica la comunicación con PostgreSQL a través del pool, retornando `status: ok`, `database` y `usuario` activo (`operador_atuel`).

---

## 6. Demostración de Resistencia a Inyección SQL (Paso 9)

En cumplimiento estricto del Paso 9 de la consigna, se verificó el comportamiento de la API frente a vectores de ataque SQL inyectados en los parámetros de consulta:

### Prueba de Inyección en Filtro de Bodega:
* **Vector inyectado:**  
  `GET /vinos?bodega=' OR '1'='1`
* **Comportamiento esperado en código vulnerable (concatenación simple):**  
  La condición `'1'='1` alteraría la cláusula `WHERE`, devolviendo la totalidad del catálogo (más de 40 vinos).
* **Comportamiento real obtenido (consulta parametrizada con `%s`):**  
  PostgreSQL trata el valor `%' OR '1'='1%` estrictamente como una cadena literal de caracteres dentro del operador `ILIKE`. Al no existir ninguna bodega con ese texto en su razón social ni CUIT, el resultado es:
  ```json
  {
    "total": 0,
    "limit": 20,
    "offset": 0,
    "items": []
  }
  ```
  Código HTTP: `200 OK` (búsqueda sin coincidencias, sin alteración de la consulta).

### Prueba de Inyección de Comandos Apilados (Stacking Queries):
* **Vector inyectado:**  
  `GET /vinos?tipo=tinto'; DELETE FROM vino;--`
* **Resultado:**  
  FastAPI y Pydantic validan el tipo mediante `TipoVinoEnum`. La solicitud es rechazada inmediatamente en el borde con código **`422 Unprocessable Entity`**, sin siquiera interactuar con la base de datos.
* Si el payload se inyecta en un campo de texto libre, el driver `psycopg` envía la cadena completa como parámetro de datos binarios fuera del texto del query, imposibilitando la ejecución de sentencias concatenadas.

---

## 7. Resultados de la Suite de Pruebas Automáticas

La batería de tests automatizados construida con `pytest` y `TestClient` cuenta con **36 pruebas unitarias e integrales**, ejecutadas contra el dataset real en **1.41 segundos**:

```text
tests/test_clientes.py ......                                            [ 16%]
tests/test_comprobantes.py ...                                           [ 25%]
tests/test_reportes.py ......                                            [ 41%]
tests/test_salas.py .                                                    [ 44%]
tests/test_salud.py .                                                    [ 47%]
tests/test_seguridad_sql.py ...                                          [ 55%]
tests/test_transferencias_ingresos.py ........                           [ 77%]
tests/test_vinos.py ........                                             [100%]

======================== 36 passed, 1 warning in 1.41s =========================
```

### Cobertura de Violación de Reglas de Negocio en Tests:
1. **RN-05 (Corte de vino 100 %):** `test_crear_vino_corte_invalido_falla` -> Revisa rechazo con `409 Conflict` (SQLSTATE `P0001`).
2. **RN-09 (Stock insuficiente en venta):** `test_crear_venta_sin_stock_rechaza_y_revierte_transaccion` -> Valida rechazo con `409 Conflict`, mensaje de regla y verificación de que el stock no cambió y no se insertó comprobante.
3. **RN-10 (Transición de ingresos):** `test_1_circuito_feliz_ingreso` -> Valida rechazo con `409 Conflict` al intentar procesar dos veces el mismo ingreso.
4. **RN-11 (Stock insuficiente en transferencia):** `test_6_rn11_transferencia_stock_insuficiente` -> Valida que transferir más existencias de las disponibles en depósito central es rechazado con `409 Conflict` y preserva el estado `terminado`.
5. **RN-11 (Atomicidad y Rollback múltiple):** `test_7_atomicidad_transferencia_dos_vinos` -> Valida que si el segundo renglón no tiene stock, se revierte también el stock del primer vino.
6. **RN-12 (Bloqueo de documentos terminados):** `test_4_rn12_bloquear_renglones_transferencia_terminada` y `test_5_rn10_bloquear_renglones_ingreso_terminado` -> Verifican rechazo con `409 Conflict` al intentar agregar renglones a documentos cerrados.
7. **RN-13 (Auditoría automática de precio):** `test_actualizar_vino_audita_precio` -> Valida que modificar el precio mediante `PUT /vinos/{cod}` inserta el registro histórico en `auditoria_precio`.
8. **RN-14 (Borrado restrictivo):** `test_eliminar_vino_con_movimientos_falla` y `test_eliminar_cliente_con_comprobantes_falla` -> Verifican rechazo con `409 Conflict` (SQLSTATE `23503`).

---

## 8. Contenerización y Orquestación con Docker Compose

* **`Dockerfile`:** Imagen optimizada basada en `python:3.12-slim` que instala dependencias desde `requirements.txt` y expone el puerto 8000 con `uvicorn api.main:app`.
* **`docker-compose.yml`:** Un único comando (`docker compose up`) levanta la base de datos PostgreSQL 16 y el servicio de la API REST. El servicio `api` cuenta con dependencia de salud (`condition: service_healthy`) respecto de `db`, garantizando que la API solo inicie cuando el motor esté listo para recibir conexiones.
* **Documentación Interactiva:** La API expone automáticamente la especificación OpenAPI en:
  * Swagger UI: `http://localhost:8000/docs`
  * ReDoc: `http://localhost:8000/redoc`
