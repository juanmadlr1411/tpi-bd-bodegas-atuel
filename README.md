# Bodegas del Atuel — Sistema de Gestión Vitivinícola

Trabajo Práctico Integrador (TPI) — Bases de Datos  
Universidad Tecnológica Nacional — Facultad Regional San Rafael (UTN FRSR)  
Año: 2026

---

## 👥 Integrantes del Equipo

* **Gonzalo**
* **Manuel**
* **Bruno**
* **Juan Manuel**
* **Santiago**

---

## 🌐 Despliegue en Producción (Etapa 8)

El sistema se encuentra desplegado en la nube bajo una arquitectura distribuida de tres capas protegida por HTTPS y SSL/TLS:

* **Frontend (SPA React + Vite):** [https://bodegas-atuel.vercel.app](https://bodegas-atuel.vercel.app) (Alojado en Vercel)
* **Backend (API REST FastAPI):** [https://bodegas-atuel-api-ji2n.onrender.com](https://bodegas-atuel-api-ji2n.onrender.com) (Alojado en Render)
* **Documentación Interactiva (Swagger/OpenAPI):** [https://bodegas-atuel-api-ji2n.onrender.com/docs](https://bodegas-atuel-api-ji2n.onrender.com/docs)
* **Endpoint de Salud y Diagnóstico:** [https://bodegas-atuel-api-ji2n.onrender.com/salud](https://bodegas-atuel-api-ji2n.onrender.com/salud)
* **Base de Datos (PostgreSQL 16):** Instancia gestionada en Neon Serverless (AWS São Paulo `sa-east-1`), con cifrado obligatorio (`sslmode=require`).

---

## 🔐 Seguridad y Privilegios Mínimos

* **Principio de Mínimos Privilegios:** La API opera en producción utilizando el rol no privilegiado `operador_atuel` (permisos de `SELECT`, `INSERT`, `UPDATE`, `DELETE` en tablas de datos y secuencias, sin permisos de modificación de esquema `DDL`).
* **Cero Secretos en Repositorio:** Todas las credenciales, claves y URLs de conexión son inyectadas mediante variables de entorno en los paneles de los proveedores (Render y Vercel) y archivos `.env` ignorados por `.gitignore`.
* **Cifrado de Tránsito:** La comunicación entre clientes y frontend, frontend y backend, y backend hacia el motor de base de datos se realiza 100% cifrada bajo TLS 1.3 / SSL.

---

## 🚀 Puesta en Marcha en Entorno Local (Docker Compose)

### 1. Requisitos Previos

* Docker y Docker Compose
* Python 3.11+ (opcional para desarrollo local)
* Node.js 18+ (opcional para desarrollo front)

### 2. Configuración de Entorno

Copiar el archivo de variables de ejemplo:

```bash
cp .env.example .env
```

### 3. Levantar los Servicios

```bash
docker compose up -d
```

Esto iniciará de forma orquestada:
1. `bodegas_atuel_db`: Motor PostgreSQL 16 Alpine con las migraciones iniciales (`001` a `008`) ejecutadas automáticamente.
2. `api`: Backend FastAPI en puerto `8000` con recarga en vivo.
3. `front`: Frontend web servido en puerto `5173`.

### 4. Acceso Local

* **Frontend:** `http://localhost:5173`
* **API REST:** `http://localhost:8000`
* **Swagger UI:** `http://localhost:8000/docs`

---

## 🧪 Ejecución de Pruebas Automatizadas

El backend cuenta con una suite integral de 36 pruebas automatizadas (`pytest`) que validan endpoints, transacciones ACID y el disparo controlado de reglas de negocio:

```bash
# Con entorno virtual activo
pytest tests/ -v
```

---

## 💾 Respaldo y Restauración (Disaster Recovery)

Para respaldar la base de datos en formato custom comprimido:

```bash
pg_dump "$DATABASE_URL" -Fc -f backup_bodegas_atuel.dump
```

Para restaurar el respaldo de forma limpia en una base de datos nueva:

```bash
pg_restore -d "$TARGET_DATABASE_URL" --clean --if-exists --no-owner --no-privileges backup_bodegas_atuel.dump
```

La paridad de filas y consistencia 1:1 entre producción y la base testigo restaurada se encuentra certificada en `docs/informe_h8.md`.

---

## 📂 Estructura del Repositorio

* `api/`: Código fuente de la API REST FastAPI y capa de acceso a datos (`dal/`).
* `db/migrations/`: Scripts DDL de base de datos (`001_esquema.sql` a `008_indices.sql`).
* `db/seed/`: Scripts de carga masiva, benchmarking y utilitarios de migración a la nube.
* `docs/`: Informes técnicos formales de cada etapa y documentación del modelo relacional.
* `front/`: Código fuente del frontend SPA desarrollado en React + Vite.
* `tests/`: Batería de pruebas unitarias y de integración.
