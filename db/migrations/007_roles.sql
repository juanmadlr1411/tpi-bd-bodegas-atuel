-- =============================================================================
-- Migración 007: Creación de Roles y Permisos — Bodegas del Atuel
-- =============================================================================

DO $$ 
BEGIN
    -- Crear rol de Administrador si no existe
    IF NOT EXISTS (SELECT FROM pg_catalog.pg_roles WHERE rolname = 'admin_atuel') THEN
        CREATE ROLE admin_atuel LOGIN PASSWORD 'cambiar_en_local' SUPERUSER CREATEDB;
    END IF;

    -- Crear rol de Operador si no existe
    IF NOT EXISTS (SELECT FROM pg_catalog.pg_roles WHERE rolname = 'operador_atuel') THEN
        CREATE ROLE operador_atuel LOGIN PASSWORD 'operador_pass';
    END IF;

    -- Crear rol de Consultas / Auditoría si no existe
    IF NOT EXISTS (SELECT FROM pg_catalog.pg_roles WHERE rolname = 'auditor_atuel') THEN
        CREATE ROLE auditor_atuel LOGIN PASSWORD 'auditor_pass';
    END IF;
END $$;

-- Otorgar permisos básicos de conexión y uso sobre el esquema público
GRANT CONNECT ON DATABASE bodegas_atuel TO operador_atuel, auditor_atuel;
GRANT USAGE ON SCHEMA public TO operador_atuel, auditor_atuel;

-- Permisos para el Operador (Lectura y escritura transaccional en tablas operativas)
GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public TO operador_atuel;
GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO operador_atuel;

-- Permisos para el Auditor (Solo lectura en todo el esquema)
GRANT SELECT ON ALL TABLES IN SCHEMA public TO auditor_atuel;

-- Asegurar permisos por defecto para futuras tablas
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO operador_atuel;
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT SELECT ON TABLES TO auditor_atuel;

-- =============================================================================
-- H9: Restricción de ejecución de procedimientos operativos
-- =============================================================================

-- Evitar que cualquier usuario pueda ejecutar procedimientos
-- que modifican existencias y estados de documentos.
REVOKE EXECUTE ON PROCEDURE
    public.sp_procesar_ingreso(integer),
    public.sp_procesar_transferencia(integer)
FROM PUBLIC;

-- El operador puede ejecutar los procedimientos de negocio.
GRANT EXECUTE ON PROCEDURE
    public.sp_procesar_ingreso(integer),
    public.sp_procesar_transferencia(integer)
TO operador_atuel;

-- El auditor no debe ejecutar procedimientos operativos.
REVOKE EXECUTE ON PROCEDURE
    public.sp_procesar_ingreso(integer),
    public.sp_procesar_transferencia(integer)
FROM auditor_atuel;
