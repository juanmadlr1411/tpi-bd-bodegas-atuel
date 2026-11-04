# Demostración de Concurrencia - Bodegas del Atuel

## Objetivo
Demostrar el comportamiento de PostgreSQL ante dos transacciones simultáneas compitiendo por el mismo recurso (la última botella de un vino), contrastando el escenario con y sin bloqueos explícitos.

## Nivel de Aislamiento
El nivel de aislamiento utilizado es el predeterminado por PostgreSQL: **Read Committed**. Bajo este nivel, una transacción solo ve los datos "comiteados" antes de que la consulta comience. Sin embargo, para evitar condiciones de carrera al descontar stock, se utiliza el bloqueo explícito a nivel de fila `SELECT ... FOR UPDATE` en el procedimiento almacenado.

---

## 1. Escenario SIN bloqueo (Error de Concurrencia)
Dos sesiones intentan vender el mismo vino al mismo tiempo usando un `SELECT` simple y luego un `UPDATE`. 

* **Comportamiento observado:** Ambas sesiones leen que hay 1 botella disponible. Ambas restan 1 y guardan. El stock final queda inconsistente (o negativo), rompiendo la integridad.
* **Capturas:**
  > [Insertar captura de las dos terminales leyendo el mismo stock inicial]

---

## 2. Escenario CON bloqueo (SELECT ... FOR UPDATE)
El procedimiento transaccional `sp_procesar_transferencia` / `sp_procesar_ingreso` utiliza bloqueo a nivel de fila.

* **Comportamiento observado:** 
  1. La **Sesión A** inicia la venta y ejecuta `FOR UPDATE`. PostgreSQL bloquea la fila del vino.
  2. La **Sesión B** intenta comprar el mismo vino. Queda en estado de espera (colgada) porque la fila está bloqueada por A.
  3. La **Sesión A** termina la transacción (`COMMIT`).
  4. La **Sesión B** se desbloquea, lee el stock actualizado (0 botellas) y el trigger de validación de stock rechaza su operación.
* **Capturas:**
  > [Insertar captura de Sesión A bloqueando la fila]
  > [Insertar captura de Sesión B "colgada" esperando el bloqueo]
  > [Insertar captura del error de stock insuficiente en Sesión B tras el COMMIT de A]
