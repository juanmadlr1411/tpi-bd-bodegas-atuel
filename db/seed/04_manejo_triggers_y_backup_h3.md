# Etapa 3 (H3): Estrategia de Manejo de Triggers en Carga Masiva y Backup

**Responsable:** Gonzalo

## 1. Problema: Por qué la carga histórica choca con los Triggers de la Etapa 2

Durante la operación normal del sistema, los triggers implementados en `005_triggers.sql` protegen las reglas de negocio en tiempo real. Sin embargo, al inyectar masivamente el historial de los últimos 5 años (+150.000 comprobantes y +500.000 renglones), mantener los triggers activos provoca dos problemas críticos:

1. **Bloqueo lógico de datos históricos válidos:**
   * **RN-11 (Fecha actual en transferencias):** El trigger `BEFORE INSERT` fuerza `fecha_confeccion = CURRENT_DATE`. Si estuviera activo durante la carga histórica, sobrescribiría la fecha de todas las transferencias pasadas con la fecha de hoy, destruyendo la distribución temporal requerida para las consultas de la Etapa 5 (ej. S4).
   * **RN-12 (Inmutabilidad de documentos cerrados):** El trigger sobre `renglon_ingreso` y `renglon_transferencia` impide insertar renglones cuando la cabecera ya está en estado `'terminado'` o `'procesado'`. Al cargar primero la tabla padre (`ingreso` / `transferencia` con sus estados históricos finales) y luego sus tablas hijas de renglones, el trigger rechazaría la inserción.
   * **RN-09 (Validación contra stock actual):** Validar ventas ocurridas hace 3 años contra la foto actual de `stock_sala` rechazaría ventas históricas legítimas.
2. **Degradación severa de rendimiento:**
   * Ejecutar `trg_validar_stock_venta` y el recálculo de cabeceras (`RN-08`) fila por fila sobre 500.000 registros de `renglon_comprobante` implica realizar más de un millón de lecturas y escrituras adicionales, multiplicando exponencialmente el tiempo de carga.

---

## 2. Decisión Técnica: `DISABLE TRIGGER USER` vs `DISABLE TRIGGER ALL`

En PostgreSQL existen dos variantes para desactivar triggers en una tabla:
* `ALTER TABLE ... DISABLE TRIGGER ALL`: Desactiva tanto los triggers definidos por el programador como los triggers internos del motor que implementan las restricciones `FOREIGN KEY` (`RI_ConstraintTrigger`). Además, exige privilegios de `SUPERUSER` (lo cual es incompatible con bases de datos gestionadas en la nube en la Etapa 8).
* `ALTER TABLE ... DISABLE TRIGGER USER` (**Opción Elegida**): Desactiva únicamente los triggers de negocio creados por el grupo en la Etapa 2, **manteniendo activas todas las `FOREIGN KEY`, `PRIMARY KEY`, `UNIQUE` y `CHECK`**.

### Flujo de Ejecución Implementado
1. **Pre-carga (`db/seed/01_preparar_motor_pre_carga.sql`):** Se ejecuta `ALTER TABLE ... DISABLE TRIGGER USER;` sobre las tablas operativas antes de correr los scripts de Python.
2. **Inyección por lotes (Python + `psycopg`):** Se cargan los catálogos maestros y los movimientos transaccionales con semilla fija (`seed`), calculando en origen los subtotales, totales, porcentajes de corte y stocks coherentes.
3. **Post-carga (`db/seed/02_restaurar_motor_post_carga.sql`):**
   * Se rehabilitan todos los triggers con `ALTER TABLE ... ENABLE TRIGGER USER;`.
   * Se actualiza la vista materializada de reportes (`REFRESH MATERIALIZED VIEW mv_ventas_mensuales_sala;`).
   * Se ejecuta `ANALYZE;` para actualizar las estadísticas del optimizador de PostgreSQL.

---

## 3. Riesgos Asumidos y Mitigación mediante Consultas de Control

Dado que `ALTER TABLE ... ENABLE TRIGGER USER` habilita los triggers hacia el futuro pero **no evalúa retroactivamente** las filas insertadas mientras estuvieron apagados, existe el riesgo de que un error en el script generador de Python introduzca datos que violen alguna regla de negocio.

| Riesgo durante la ventana sin triggers | Regla afectada | Mitigación (Consulta de control post-carga en Paso 7) |
| :--- | :---: | :--- |
| Vinos cuyos porcentajes en `composicion_vino` no sumen exactamente 100 | **RN-05** | Verificar con `GROUP BY cod_vino HAVING SUM(porcentaje) <> 100` (debe devolver 0 filas). |
| Cabeceras de `comprobante` cuyo `total` no coincida con la suma de sus renglones | **RN-08** | Comparar `c.total` contra `fn_total_comprobante(c.nro_comprobante)` (debe devolver 0 diferencias). |
| Existencias negativas en `stock_sala` o `stock_deposito` | **RN-09 / RN-15** | El `CHECK (cantidad >= 0)` permanece activo durante toda la carga y se verifica con `WHERE cantidad < 0`. |
| Ingresos o transferencias sin renglones asociados | **RN-10 / RN-11** | Verificar con `LEFT JOIN` que todo documento tenga al menos un renglón. |

---

## 4. Respaldo Reproducible (`pg_dump` y Restauración)

Una vez superadas las consultas de control, se genera el volcado comprimido mediante `db/seed/generar_dump.sh`:

```bash
# Generación del volcado comprimido con nivel máximo (-9)
docker exec -i bodegas_atuel_db pg_dump -U admin_atuel -d bodegas_atuel --clean --if-exists --no-owner --no-privileges | gzip -9 > db/seed/dump_completo.sql.gz