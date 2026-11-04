# Tabla de Trazabilidad - Etapa 2

| Regla de Negocio (RN) | Mecanismo de Implementación | Caso de Prueba (`tests/db_tests.sql`) |
| :--- | :--- | :--- |
| **RN-05:** Suma de porcentajes de corte | `CONSTRAINT TRIGGER DEFERRABLE` en `composicion_vino` | **Test:** Inserción de cepas que suman 100% (Éxito) y distinto de 100% (Falla). |
| **RN-08 y RN-09:** Stock y totales | Trigger `AFTER INSERT` en `renglon_comprobante` | **Test:** Venta con stock suficiente (Éxito). |
| **RN-09:** Validación de stock previo | Trigger `BEFORE INSERT` en `renglon_comprobante` | **Test:** Venta superando stock de sala (Falla). |
| **RN-10 y RN-11:** Estados de documentos | Triggers en `ingreso` y `transferencia` | **Test:** Intento de retroceso de estado (Falla). |
| **RN-11:** Fecha de confección | Trigger `BEFORE INSERT/UPDATE` | **Test:** Modificación de fecha de confección (Falla). |
| **RN-12:** Bloqueo de renglones | Trigger `BEFORE INSERT/UPDATE/DELETE` en renglones | **Test:** Cambio en documento procesado (Falla). |
| **RN-13:** Auditoría de precio | Trigger `AFTER UPDATE` en `vino` | **Test:** Cambio de precio genera registro histórico. |
| **Generales:** Tipos y Restricciones | `CHECK`, `NOT NULL`, `DOMAIN` (CUIT), `ENUM` | **Test:** Precio negativo o CUIT inválido (Fallas). |
