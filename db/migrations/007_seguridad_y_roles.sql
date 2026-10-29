-- =======================================================================================
-- HITO 2: SEGURIDAD, ROLES Y CONTROL DE ACCESO (DCL)
-- Autor: Juan Manuel (Infraestructura y QA)
-- =======================================================================================

-- 1. CREACIÓN DE ROLES DE NEGOCIO
CREATE ROLE rol_gerencia WITH LOGIN PASSWORD 'Gerencia2026_Atuel';
CREATE ROLE rol_enologo WITH LOGIN PASSWORD 'Enologo2026_Atuel';
CREATE ROLE rol_ventas WITH LOGIN PASSWORD 'Ventas2026_Atuel';
CREATE ROLE rol_logistica WITH LOGIN PASSWORD 'Logistica2026_Atuel';

-- 2. PERMISOS DEL ENÓLOGO (Subdominio 1 y Producción)
-- Gestiona viñedos, uvas y la composición de los vinos, pero no tiene acceso a facturación.
GRANT SELECT, INSERT, UPDATE ON finca, parcela, cepa, lote_uva, composicion_vino, vino TO rol_enologo;
GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO rol_enologo;

-- 3. PERMISOS DE VENTAS (Subdominio 2 y 3 comercial)
-- Gestiona clientes y facturación, y puede consultar el stock de las salas y vinos.
GRANT SELECT, INSERT, UPDATE ON cliente, cliente_socio, cliente_distribuidor, cliente_exportador, comprobante, renglon_comprobante TO rol_ventas;
GRANT SELECT ON bodega, vino, sala_venta, localidad TO rol_ventas;
GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO rol_ventas;

-- 4. PERMISOS DE LOGÍSTICA (Subdominio 3 logístico)
-- Gestiona el movimiento físico de la mercadería.
GRANT SELECT, INSERT, UPDATE ON ingreso, transferencia, renglon_ingreso, renglon_transferencia, transportista TO rol_logistica;
GRANT SELECT ON bodega, sala_venta TO rol_logistica;
GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO rol_logistica;

-- 5. PERMISOS DE GERENCIA (Visualización Global)
-- Acceso de solo lectura a todas las tablas y vistas para reportes y auditoría, sin poder modificar datos.
GRANT SELECT ON ALL TABLES IN SCHEMA public TO rol_gerencia;

