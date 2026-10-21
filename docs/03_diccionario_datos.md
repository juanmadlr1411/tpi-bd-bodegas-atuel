# Diccionario de Datos — Bodegas del Atuel

## 1. Dominios y Tipos Enumerados (Responsable: Delgado)

| Objeto | Tipo Base / Valores | Restricción | Descripción |
| :--- | :--- | :--- | :--- |
| `cuit_dom` | `CHAR(11)` | `CHECK (VALUE ~ '^[0-9]{11}$')` | Dominio para CUIT de 11 dígitos numéricos |
| `estado_documento` | `ENUM` | `'en_confeccion'`, `'terminado'`, `'procesado'` | Estados válidos de ingresos y transferencias (RN-10, RN-11) |
| `tipo_vino` | `ENUM` | `'tinto'`, `'blanco'`, `'rosado'`, `'espumante'` | Clasificación comercial del vino |
| `tipo_cepa` | `ENUM` | `'tinta'`, `'blanca'` | Clasificación ampelográfica de la cepa |
| `tipo_cliente_enum` | `ENUM` | `'socio'`, `'distribuidor'`, `'exportador'` | Discriminador de la jerarquía de clientes |
| `dia_semana` | `ENUM` | `'lunes'` .. `'domingo'` | Día de cierre semanal de cada sala de venta |

---

## 2. Subdominio Geografía, Salas y Producción de Uva (Responsable: Gonzalo)

| Tabla | Columna | Tipo de Dato | Nulos | Restricciones | Descripción |
| :--- | :--- | :--- | :---: | :--- | :--- |
<!-- Gonzalo: Completar filas de tus 8 tablas -->

---

## 3. Subdominio Bodegas, Vinos y Clientes (Responsable: Manuel)

| Tabla | Columna | Tipo de Dato | Nulos | Restricciones | Descripción |
| :--- | :--- | :--- | :---: | :--- | :--- |
<!-- Manuel: Completar filas de tus 10 tablas -->

---

## 4. Subdominio Ventas, Logística, Stock y Auditoría (Responsable: Bruno)

| Tabla | Columna | Tipo de Dato | Nulos | Restricciones | Descripción |
| :--- | :--- | :--- | :---: | :--- | :--- |
<!-- Bruno: Completar filas de tus 11 tablas -->
