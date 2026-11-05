# Informe Etapa 3: Carga Masiva de Datos

**Proyecto:** Bodegas del Atuel
**Responsable del Mapeo y Auditoría:** Juan Manuel

## Definición del Orden Topológico de Inserción

Se estableció el orden estricto de inserción de datos para evitar violaciones de integridad referencial (`FOREIGN KEY`) durante la carga masiva. Se organizó la secuencia en cinco niveles de dependencia:

*   **Nivel 1: Catálogos Raíz (Sin claves foráneas).** Deben cargarse a partir de los CSV provistos en el Anexo B.
    *   `localidad`
    *   `cepa`
    *   `maridaje`
    *   `bodega`
    *   `transportista`

*   **Nivel 2: Entidades Geográficas y Estructurales (Dependen del Nivel 1).**
    *   `sala_venta` (depende de `localidad`)
    *   `empleado` (depende de `sala_venta`)
    *   `finca`
    *   `transportista_localidad` (depende de `transportista` y `localidad`)
    *   `cliente` (depende de `localidad`)

*   **Nivel 3: Subtipos y Entidades de Producción (Dependen de Niveles 1 y 2).**
    *   Subtipos de cliente: `cliente_socio`, `cliente_distribuidor`, `cliente_exportador`
    *   `permiso_exportacion` (depende de `cliente_exportador`)
    *   `parcela` (depende de `finca` y `cepa`)
    *   `lote_uva` (depende de `parcela` y `bodega`)
    *   `analisis_calidad` (depende de `lote_uva`)
    *   `vino` (depende de `bodega`)

*   **Nivel 4: Entidades de Cruce N:M e Inicialización de Stock.**
    *   `composicion_vino` (depende de `vino` y `cepa`)
    *   `vino_maridaje` (depende de `vino` y `maridaje`)
    *   `stock_deposito` (depende de `vino` - Inicializar en 0)
    *   `stock_sala` (depende de `sala_venta` y `vino` - Inicializar en 0)

*   **Nivel 5: Documentos Transaccionales (Cabeceras y Renglones).**
    *   Cabeceras: `comprobante`, `ingreso`, `transferencia`
    *   Detalles: `renglon_comprobante`, `renglon_ingreso`, `renglon_transferencia`
