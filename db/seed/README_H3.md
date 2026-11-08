# H3 — Carga de datos transaccionales

## Resultado verificado (base local aislada)

Generación histórica: enero de 2022 a octubre de 2026 (58 meses).
Se completó la carga definitiva y una consulta posterior al `COMMIT` confirmó:

| Tabla | Cantidad |
|---|---:|
| `ingreso` | 5.000 |
| `renglon_ingreso` | 14.349 |
| `transferencia` | 5.000 |
| `renglon_transferencia` | 15.000 |
| `comprobante` | 150.000 |
| `renglon_comprobante` | 600.000 |
| **Total** | **789.349** |

Además se validaron RN-08 y RN-09, la conciliación de existencias y los importes/descuentos de ventas. Se refrescó la vista materializada `mv_ventas_mensuales_sala` y se ejecutó `ANALYZE`.

## Componentes

- `carga_maestras.py`: genera los datos maestros.
- `conexion.py`: conexión a PostgreSQL usando las variables de `.env`.
- `plan_carga.py`: distribución mensual de documentos.
- `datos_maestros.py`: consulta clientes, vinos, salas y transportistas.
- `inventario_historico.py`: modelo y validaciones de existencias.
- `simular_carga_58_meses.py`: construye los documentos históricos.
- `persistencia_transaccional.py`: inserción por lotes y consulta de existencias.
- `carga_h3_final.py`: orquestador, controles y modos de ejecución.

## Preparación de una base nueva y aislada

1. Crear una base PostgreSQL **vacía**, dedicada exclusivamente a H3. No utilizar la base compartida sin coordinación.
2. Aplicar en orden las migraciones `db/migrations/001_*.sql` hasta `006_*.sql`.
3. Ejecutar `db/seed/carga_maestras.py` apuntando a esa base.
4. **Obligatorio:** ejecutar `db/seed/02_restaurar_motor_post_carga.sql` para reactivar los triggers que desactiva el generador de maestros.
5. Comprobar el estado con los comandos de abajo.

Todos los comandos Python deben ejecutarse desde la raíz del repositorio, con el entorno virtual y `.env` configurados. Usar `POSTGRES_DB=nombre_de_base_aislada` para indicar el destino.

```bash
POSTGRES_DB=nombre_de_base_aislada python db/seed/carga_h3_final.py --verificar
POSTGRES_DB=nombre_de_base_aislada python db/seed/carga_h3_final.py --probar --meses 1
```

`--probar` realiza un `ROLLBACK` completo. Para cargar **una única vez**, únicamente sobre una base limpia y aislada:

```bash
POSTGRES_DB=nombre_de_base_aislada python db/seed/carga_h3_final.py --cargar --confirmo-carga-definitiva
```

El proceso tarda varias horas en equipos modestos. No volver a ejecutar `--cargar` sobre la base que ya contiene las transacciones. Al finalizar, exige el mensaje `COMMIT: carga definitiva conservada.` y contrastar las cantidades con una consulta posterior.

## Excepción controlada de fechas históricas

La regla RN-11 de producción fuerza `CURRENT_DATE` en nuevas transferencias. Durante la carga histórica, el generador **desactiva exclusivamente** `trg_fecha_confeccion_transferencia` dentro de su transacción para conservar fechas 2022–2026 y lo reactiva **antes de hacer `COMMIT`**. El resto de los triggers permanece activo; si la transacción falla, el cambio de activación se revierte con `ROLLBACK`.

Esta operación requiere permisos suficientes y una base aislada, porque `ALTER TABLE` afecta a toda la tabla. No debe ejecutarse mientras otras personas utilizan esa base.

## Posprocesamiento y respaldo

Después de la carga, refrescar `mv_ventas_mensuales_sala`, ejecutar `ANALYZE` y realizar un `pg_dump -Fc`. Guardar el respaldo **fuera de Git**; no subir `.env`, `.venv/`, dumps ni contraseñas.

La carga definitiva mencionada arriba ya fue realizada en una base local aislada. **Los registros no se transfieren automáticamente al repositorio GitHub**: los demás integrantes deben ejecutar el generador en su propia base o restaurar un respaldo acordado.

<!-- INICIO CORRECCIONES H3 2026-11 -->
## Correcciones H3: documentos pendientes y comparación de inserciones

**Pendientes:** el generador `carga_h3_final.py --cargar` crea el lote al final
de una carga nueva, después de validar el historial. Para la **base histórica ya
cargada**, se ejecuta una sola vez `db/seed/agregar_pendientes_h3.py` sobre
una **base aislada**. El programa crea dos ingresos y dos transferencias en
`en_confeccion`, más dos de cada tipo en `terminado`. Cada cabecera lleva un
renglón. Los 8 documentos **no se procesan**: no alteran las existencias y
aparecen en `vw_documentos_pendientes` para la consulta S5.

```bash
POSTGRES_DB=bodegas_atuel_h3_final python db/seed/agregar_pendientes_h3.py
POSTGRES_DB=bodegas_atuel_h3_final python db/seed/agregar_pendientes_h3.py --aplicar --confirmo-base-aislada
POSTGRES_DB=bodegas_atuel_h3_final python db/seed/agregar_pendientes_h3.py
```

El lote histórico original tenía **789.349** filas transaccionales. La poscarga
suma 8 cabeceras y 8 renglones: **789.365 filas** en la base ampliada
(ingresos 5.004, renglones de ingreso 14.353, transferencias 5.004,
renglones de transferencia 15.004; ventas sin cambios). Esos valores solo
aplican **después** de ejecutar el script de poscarga.

**Medición reproducible:** ejecutá `db/seed/medir_inserciones_h3.py` con la
base seleccionada. Crea una tabla temporal, inserta la misma muestra mediante
`cursor.execute()` fila por fila y `cursor.executemany()`, comprueba cantidades
y hace `ROLLBACK`. No toca tablas operativas. **No equivale** a medir la
persistencia histórica con triggers ni permite extrapolar su duración.

| Métrica | Valor medido |
|---|---:|
| Filas por método | 1,000 |
| `execute()` individual | 0.1131 s |
| `executemany()` | 0.0139 s |
| Carga real de 58 meses (con reglas de negocio activas) | 19.342,15 s (5 h 22 min aprox.) |

**Triggers:** `01_preparar_motor_pre_carga.sql` se aplica antes de maestros;
`02_restaurar_motor_post_carga.sql` los rehabilita antes de H3 transaccional.
Para preservar consistencia, el seed histórico conserva activos los triggers
RN-08/RN-09 y de estados. Desactiva **solo** el trigger de fecha histórica
de transferencias dentro de su transacción y lo reactiva antes de `COMMIT`.
Apagar también los de ventas exigiría implementar y validar en Python/SQL el
recálculo de totales y stock; **no forma parte de esta implementación**.
<!-- FIN CORRECCIONES H3 2026-11 -->
