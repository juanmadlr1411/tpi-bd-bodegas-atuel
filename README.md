# Bodegas del Atuel - Trabajo Práctico Integrador (Bases de Datos 2026)

## Descripción
Sistema integral de gestión y distribución para "Bodegas del Atuel", una empresa vitivinícola que integra la producción de uva, elaboración de vinos, control de stock central y distribución a través de salas de venta. El proyecto implementa un modelo relacional normalizado en PostgreSQL, aplicando reglas de negocio transaccionales mediante constraints, funciones, procedimientos almacenados y triggers.

## Arquitectura y Enlaces de Producción
El sistema está desplegado en la nube utilizando una arquitectura de microservicios con separación de responsabilidades:
*   **Frontend (React):** Desplegado en Vercel.  
    URL Pública: https://bodegas-atuel.vercel.app
*   **Backend API (FastAPI):** Desplegado en Render.com con cifrado SSL/TLS y rol de privilegios mínimos (`operador_atuel`).  
    URL Pública: https://bodegas-atuel-api-ji2n.onrender.com  
    Swagger UI / Documentación: https://bodegas-atuel-api-ji2n.onrender.com/docs  
    Diagnóstico / Salud: https://bodegas-atuel-api-ji2n.onrender.com/salud
*   **Base de Datos (PostgreSQL 16):** Desplegada en Neon.tech (Serverless Postgres en AWS sa-east-1, SSL obligatorio).

## Integrantes del Equipo
*   Bruno
*   Gonzalo
*   Juan Manuel
*   Manuel
*   Santiago

## Requisitos Previos
*   Docker y Docker Compose
*   Git

## Ejecución en Entorno Local (Docker)
Para levantar la base de datos, la API y el Frontend localmente en un solo paso, ejecutar en la raíz del proyecto:

    docker compose up -d

Los servicios quedarán disponibles en:
*   Frontend: http://localhost:5173
*   API: http://localhost:8000
*   Base de Datos: localhost:5432

## Migraciones, Carga de Datos y Pruebas
1. **Migraciones (Esquema y Lógica):** Se deben ejecutar en estricto orden los scripts ubicados en db/migrations/ (001_esquema.sql al 008_indices.sql) sobre una base de datos vacía.
2. **Carga Masiva:** Posicionarse en db/seed/ y ejecutar el script generador en Python (basado en Faker y random con semilla fija para reproducibilidad).
3. **Pruebas de Base de Datos:** Ejecutar el archivo tests/db_tests.sql en el cliente SQL para validar el cumplimiento de las restricciones y triggers (RN-01 a RN-15).
4. **Pruebas de API:** Ejecutar pytest en el directorio de la API para correr la suite de pruebas unitarias y de integración.

## Operaciones de Mantenimiento en la Nube (Backup y Restore)
Para salvaguardar la integridad de los datos en Neon.tech, utilizar las herramientas nativas de PostgreSQL.

Generar un volcado de seguridad (Backup):

    pg_dump "host=ep-soft-morning-b6zm0btb.c-2.sa-east-1.aws.neon.tech port=5432 dbname=neondb user=neondb_owner sslmode=require" -Fc -f backup_bodegas.dump

Restaurar en una nueva instancia (Restore):

    pg_restore -d "host=<NUEVO_HOST> port=5432 dbname=<NUEVA_DB> user=<USUARIO> sslmode=require" -1 backup_bodegas.dump
