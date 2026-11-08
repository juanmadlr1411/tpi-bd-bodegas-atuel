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

## 2. Decisión implementada: triggers en maestros y transacciones

El proyecto mantiene `ALTER TABLE ... DISABLE TRIGGER USER` para la **carga de
maestros** mediante `db/seed/01_preparar_motor_pre_carga.sql`; esto preserva
las claves foráneas del motor. A continuación se ejecuta
`db/seed/02_restaurar_motor_post_carga.sql` para **rehabilitar los triggers**.

**Durante la carga histórica transaccional** (`carga_h3_final.py`) se conserva
activo el motor de negocio: RN-08 (totales y descuentos), RN-09 (stock),
RN-10/RN-11 (transiciones de estado), RN-12 y las validaciones pertinentes.
Se desactiva temporalmente **solo** `trg_fecha_confeccion_transferencia` dentro
de la transacción de carga para insertar fechas antiguas; se habilita de
nuevo antes del `COMMIT`, de forma que la operación normal siga protegida.

No se desactivan los triggers de ventas durante el seed histórico. Desactivarlos
sin sustituir sus efectos dejaría **totales de comprobantes y stock incorrectos**.
Una futura modalidad rápida requeriría calcular y persistir explícitamente
esos efectos y someterlos a una validación equivalente antes de adoptarla.

**Tiempo observado con esta estrategia:** 19.342,15 segundos (aprox. 5 h 22 min)
para los 58 meses. No se afirma que el lote actual pueda ejecutarse en segundos.
La comparación de inserciones individuales y por lotes se realiza aparte con
`db/seed/medir_inserciones_h3.py`, sobre una tabla temporal sin triggers; ver
`docs/informe_h3.md`, sección 4.

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