# Informe Etapa 8 (H8): Despliegue en la Nube, Seguridad y Operación

**Proyecto:** Bodegas del Atuel  
**Asignatura:** Bases de Datos — UTN FRSR (2026)  
**Equipo:** Gonzalo, Manuel, Bruno, Juan Manuel, Santiago  



## 1. Introducción y Objetivos de la Etapa

El objetivo fundamental de la **Etapa 8** es llevar el sistema integral de **Bodegas del Atuel** a un entorno de producción real en la nube, garantizando las medidas de seguridad, confidencialidad, integridad y disponibilidad exigidas para arquitecturas empresariales:

1. **Base de Datos PostgreSQL 16 en la nube:** Despliegue en un proveedor gestionado con cifrado de transporte forzado (`sslmode=require`) y esquemas relacionales completos.
2. **Carga masiva íntegra:** Sincronización de los 58 meses históricos de datos (+790.000 filas) sin omisiones y validando la paridad con el entorno local.
3. **Mínimos privilegios y roles:** Separación estricta de perfiles (`admin_atuel` / `neondb_owner`, `operador_atuel` para backend y `auditor_atuel` para consultas).
4. **Verificación de reglas de negocio y triggers en vivo:** Evidencia fehaciente de que las reglas de negocio (especialmente RN-09: control de stock físico) continúan protegiendo los datos en el servidor cloud ante intentos de evasión.
5. **Procedimiento de respaldo y restauración (Disaster Recovery):** Generación de volcado con `pg_dump`, restauración en base testigo y prueba de consistencia 1:1.
6. **Seguridad y Cero Secretos:** Inexistencia de contraseñas o tokens en el código fuente o historial de Git.

---

## 2. Infraestructura de Base de Datos en la Nube (Manuel - Pelu)

### 2.1 Comparación de Proveedores y Decisión

| Criterio de Selección | Neon (Elegido) | Supabase | Render PostgreSQL |
| :--- | :--- | :--- | :--- |
| **Versión PostgreSQL** | **16.15 nativa** | 15.x / 16.x | 16.x |
| **Almacenamiento Gratuito** | 500 MB (nuestra base pesa 113 MB) | 500 MB | 1 GB (expira a los 30 días) |
| **Cifrado en Tránsito (SSL)** | **Obligatorio por defecto** (`sslmode=require`) | Opcional / Habilitado | Habilitado |
| **Región Geográfica** | **AWS São Paulo (`sa-east-1`)** | AWS us-east-1 (N. Virginia) | Oregon / Frankfurt |
| **Latencia desde Argentina** | **35 - 50 ms** | 140 - 180 ms | 160 - 200 ms |

**Justificación:** Se seleccionó **Neon** debido a su compatibilidad nativa con PostgreSQL 16, su baja latencia al contar con datacenter en São Paulo (`sa-east-1`), y la obligatoriedad estricta de TLS/SSL en todas las conexiones entrantes.

### 2.2 Migraciones y Esquema en Nube
Se ejecutaron secuencialmente todas las migraciones del repositorio (`001_esquema.sql` a `008_indices.sql`), estableciendo las 29 tablas base y las 2 vistas del sistema.

### 2.3 Roles y Seguridad
Se aprovisionaron los roles de negocio con credenciales robustas:
* `operador_atuel`: Rol asignado a la API REST con permisos de lectura y escritura (`SELECT`, `INSERT`, `UPDATE`, `DELETE`) en tablas operativas y secuencias, sin permisos de modificación de esquema (`DDL`).
* `auditor_atuel`: Rol de solo lectura (`SELECT`).

![Consola de Neon](capturas_h8/neon_database_deploy.png)

---

## 3. Carga Masiva de Datos y Secuencias (Gonzalo - Onza)

Para evitar la latencia excesiva que ocasionaría insertar 793.769 filas mediante comandos individuales a través de internet, se implementó el script de sincronización `db/seed/migrar_a_nube_h8.py` basado en el protocolo binario de PostgreSQL:

```bash
python db/seed/migrar_a_nube_h8.py
```

### 3.1 Estrategia de Inserción y Manejo de Triggers
1. **Desactivación temporal de triggers de usuario:**  
   Se ejecutó `ALTER TABLE ... DISABLE TRIGGER USER` sobre todas las tablas públicas. Esto permite insertar fechas históricas de transferencias (RN-11) y cabeceras cerradas (RN-12) sin bloqueos indebidos, conservando siempre activas las validaciones estructurales de integridad del motor (claves foráneas y checks).
2. **Orden topológico estricto:**  
   La migración respetó la jerarquía de cinco niveles de dependencias para garantizar consistencia referencial.
3. **Streaming Binario (`COPY BINARY`):**  
   Los datos fluyeron directamente desde la instancia local hacia Neon en representación binaria.
4. **Sincronización de Secuencias:**  
   Se actualizaron las 13 secuencias (`SERIAL` / `IDENTITY`) mediante `setval` con su `last_value` correspondiente, evitando colisiones de clave primaria al operar desde la API.

### 3.2 Métricas de Carga
* **Duración total:** **30,18 segundos**.
* **Volumen sincronizado:** **793.769 filas** (29 tablas).
  * `renglon_comprobante`: 600.022 filas
  * `comprobante`: 150.022 filas
  * `renglon_transferencia`: 15.109 filas
  * `renglon_ingreso`: 14.389 filas
  * Tablas maestras y catálogos: 14.227 filas

---

## 4. Consultas de Control Post-Carga (Auditoría de Integridad)

Tras rehabilitar los triggers de usuario (`ENABLE TRIGGER USER`), se ejecutaron las cuatro consultas de auditoría oficial de la Etapa 3 directamente sobre Neon:

| Regla de Negocio Auditada | Consulta de Control | Resultado Obtenido | Estado |
| :--- | :--- | :---: | :---: |
| **RN-05 (Cortes de vino)** | Vinos cuya suma en `composicion_vino` $\neq 100\,\%$ | **0 filas** | ✅ Cumple |
| **RN-08 (Totales de venta)** | Comprobantes con `total` $\neq$ `fn_total_comprobante()` | **0 diferencias** | ✅ Cumple |
| **RN-09 / RN-15 (Existencias)** | Existencias negativas en `stock_deposito` o `stock_sala` | **0 en depósito / 0 en salas** | ✅ Cumple |
| **RN-10 / RN-11 (Integridad)** | Comprobantes, ingresos o transferencias sin renglones | **0 huérfanos** | ✅ Cumple |

---

## 5. Prueba de Trigger Vivo en la Nube (Gonzalo - Onza)

Para certificar el cumplimiento del **Punto 9 de la Etapa 8**, se ejecutó la prueba automatizada `db/seed/probar_trigger_nube_h8.py` contra el motor en la nube:

### 5.1 Caso de Prueba: Intento de Venta sin Stock (RN-09)
* **Entorno de prueba:** Sala de Venta ID 3, Vino ID 10 (*Vino Estate Malbec Nro 10*).
* **Stock físico disponible:** **4.045 botellas**.
* **Operación ejecutada:** Intento de inserción de un renglón solicitando **5.045 botellas** (excedente no permitido).

### 5.2 Respuesta del Motor Remoto
El trigger `trg_validar_stock_venta` interceptó la operación antes de la confirmación:
```text
Código SQLSTATE : P0001
Función PL/pgSQL: PL/pgSQL function fn_trg_validar_stock_venta() line 42 at RAISE
Mensaje de Error: Stock insuficiente del vino 10 en la sala 3: disponible 4045, requerido 5045 (RN-09)
```

### 5.3 Control de Atomicidad (ACID)
Tras capturarse la excepción, se ejecutó `ROLLBACK`. La verificación posterior demostró:
```sql
SELECT COUNT(*) FROM comprobante WHERE nro_comprobante = 152646;
-- Resultado: 0 filas
```
No quedaron registros residuales ni cabeceras huérfanas, demostrando la consistencia transaccional del sistema.

---

## 6. Procedimiento de Respaldo y Restauración (Bruno - Br1)

*(Sección a completar por Bruno con las evidencias de pg_dump, restauración en base testigo y tabla de conteo de filas).*

---

## 7. Despliegue de API y Frontend (Juan Manuel y Santiago)

### 7.1. Arquitectura del sistema en producción

El sistema Bodegas del Atuel se desplegó utilizando una arquitectura distribuida de tres componentes:

- **Frontend:** React y Vite, alojados en Vercel.
- **Backend:** API REST desarrollada con FastAPI, alojada en Render.
- **Base de datos:** PostgreSQL 16, alojada en Neon.

La comunicación sigue el flujo:

**React (Vercel) → FastAPI (Render) → PostgreSQL (Neon)**

Los servicios se comunican mediante conexiones HTTPS y, para la conexión con PostgreSQL, se utiliza SSL/TLS.

### 7.2. Despliegue del backend en Render

La API REST se encuentra disponible públicamente en:

**https://bodegas-atuel-api-ji2n.onrender.com**

Se verificó el endpoint `/salud`, que confirmó la conexión con PostgreSQL:

- Estado: `ok`.
- Base de datos: `connected`.
- Usuario: `operador_atuel`.
- Base de datos activa: `neondb`.

Durante las pruebas se observaron errores transitorios de conexiones PostgreSQL (`SQLSTATE 57P01`), que posteriormente se recuperaron. Se recomienda revisar el manejo de conexiones del pool para mejorar la estabilidad del servicio.

### 7.3. Despliegue del frontend en Vercel

El frontend se publicó mediante Vercel CLI, utilizando el código del directorio `front` del repositorio.

La configuración empleada fue:

- Framework: Vite.
- Directorio del proyecto: `front`.
- Comando de compilación: `vite build`.
- Directorio de salida: `dist`.
- Entorno de despliegue: Production.

La dirección pública es:

**https://bodegas-atuel.vercel.app**

El despliegue se completó correctamente y Vercel habilitó el acceso HTTPS.

### 7.4. Configuración de la comunicación con la API

Se configuró la siguiente variable de entorno de producción en Vercel:

`VITE_API_URL=https://bodegas-atuel-api-ji2n.onrender.com`

La aplicación utiliza esta variable mediante `import.meta.env.VITE_API_URL`, permitiendo separar la configuración de producción del entorno local.

No se incorporaron credenciales de PostgreSQL ni secretos de infraestructura al código fuente del frontend.

### 7.5. Verificación funcional

Se accedió al frontend público desde el navegador Brave y se verificó la visualización de las cinco pantallas del sistema:

1. Catálogo de Vinos: carga de registros, filtros y paginación.
2. Alta y Corte: visualización del formulario de registro de vinos.
3. Nueva Venta: carga de clientes, salas y vinos.
4. Transferencias: visualización del formulario correspondiente.
5. Tablero: ranking de vinos más vendidos, gráfico de ventas por sala y selector de salas.

También se comprobó el funcionamiento del filtro de añada utilizando el año 2024.

Durante la navegación de comprobación no se observaron errores de CORS en la consola del navegador.

Las verificaciones realizadas fueron principalmente de lectura y navegación. No se ejecutaron operaciones de escritura sobre la base de datos de producción.

### 7.6. Evidencias del despliegue

Las capturas del frontend publicado se almacenan en `docs/capturas_h8/`.

![Catálogo de Vinos](capturas_h8/frontend_catalogo.png)

![Alta y Corte](capturas_h8/frontend_alta_vino.png)

![Nueva Venta](capturas_h8/frontend_nueva_venta.png)

![Transferencias](capturas_h8/frontend_transferencias.png)

![Tablero de Reportes](capturas_h8/frontend_tablero.png)

### 7.7. Consideraciones operativas

El despliegue inicial de Vercel se realizó mediante CLI, sin habilitar la integración automática con GitHub.

En consecuencia, los cambios posteriores del frontend requieren un nuevo despliegue manual hasta que se configure la integración continua.

Las pruebas realizadas permiten confirmar el funcionamiento básico de la comunicación entre los tres servicios desplegados, aunque no sustituyen las pruebas completas de operaciones transaccionales y estabilidad.