# Matriz de Trazabilidad y Testing - Etapa 2

**Proyecto:** Bodegas del Atuel
**Responsable QA e Integridad:** Juan Manuel

| Regla de Negocio (RN) | Mecanismo de BD Implementado | Objeto Físico (Constraint/Trigger/SP) | Referencia en Pruebas (`tests/db_tests.sql`) |
| :--- | :--- | :--- | :--- |
| **RN-05 (Suma cepas = 100%)** | `CONSTRAINT TRIGGER DEFERRABLE` | `trg_validar_composicion_vino` (Archivo `005`) | Test 5 (Falla por sumar 80%) |
| **RN-06 (Descuento Cliente)** | `CHECK` de rango y Trigger `BEFORE` | `chk_cliente_descuento`, `trg_asignar_descuento_cliente` | - (Probado indirectamente) |
| **RN-07 (Vencimiento posterior)** | `CHECK` y Trigger `BEFORE` | `chk_permiso_fechas`, `trg_validar_fechas_permiso` | Test 4 (Falla por fecha incongruente) |
| **RN-08 (Totales de Comprobante)** | Trigger `AFTER I/U/D` en renglones | `trg_actualizar_totales_comprobante` (Archivo `005`) | - |
| **RN-10 (Ingresos a Depósito)** | Procedimiento con Bloqueo Transaccional | `sp_procesar_ingreso` (Archivo `004`) | Test 6 (Ataja excepción controlada) |
| **RN-11 (Transferencias a Salas)** | Procedimiento Transaccional y Trigger | `sp_procesar_transferencia`, `trg_bloquear_transferencia_procesada` | Test 7 y Test 8 (Atajan bloqueos) |
| **RN-13 (Auditoría de Precio)** | Trigger `AFTER UPDATE` en precio de vino | `trg_auditar_cambio_precio` (Archivo `005`) | - |
| **RN-15 (Valores estrictamente positivos)** | Constraints `CHECK` múltiples | `chk_vino_precio`, `chk_vino_graduacion`, `chk_empleado_salario` | Test 2 y Test 3 (Falla al insertar negativos/fuera de rango) |
| **Seguridad: Principio de Menor Privilegio** | Asignación de Roles (`GRANT`/`REVOKE`) | `rol_reportes_ro`, `rol_api_rw`, `rol_propietario` (Archivo `007`) | Test 1 (Falla intento de inserción con rol de lectura) |
