# Esquema Relacional — Bodegas del Atuel

Convención: **<u>PK subrayada y en negrita</u>**, *FK en cursiva*, `[UNIQUE]` entre corchetes.

## 1. Subdominio Geografía, Salas y Producción de Uva (Responsable: Gonzalo)

1. **LOCALIDAD** (**<u>cod_postal</u>**, nombre, provincia, encargado_regional)
2. **SALA_VENTA** (**<u>id_sala</u>**, calle, numero, dia_cierre, *cod_postal*)
   - Clave Foránea: *cod_postal* referencia a **LOCALIDAD**(cod_postal).
3. **EMPLEADO** (**<u>cuit</u>**, nombre, fecha_ingreso, salario, *id_sala*)
   - Clave Foránea: *id_sala* referencia a **SALA_VENTA**(id_sala).
4. **FINCA** (**<u>id_finca</u>**, nombre `[UNIQUE]`, superficie_ha, departamento, provincia)
   - Clave Candidata (UNIQUE): (nombre).
5. **CEPA** (**<u>id_cepa</u>**, nombre `[UNIQUE]`, tipo)
   - Clave Candidata (UNIQUE): (nombre).
6. **PARCELA** (**<u>*id_finca*, nro_parcela</u>**, superficie_ha, anio_plantacion, *id_cepa*)
   - Clave Foránea 1: *id_finca* referencia a **FINCA**(id_finca) *(entidad débil)*.
   - Clave Foránea 2: *id_cepa* referencia a **CEPA**(id_cepa).
7. **LOTE_UVA** (**<u>nro_lote</u>**, *id_finca*, *nro_parcela*, campania, fecha_cosecha, kilos, *cuit_bodega*) `[UNIQUE: (id_finca, nro_parcela, campania)]`
   - Clave Foránea 1 (compuesta): (*id_finca*, *nro_parcela*) referencia a **PARCELA**(id_finca, nro_parcela).
   - Clave Foránea 2: *cuit_bodega* referencia a **BODEGA**(cuit).
   - Clave Candidata (UNIQUE): (id_finca, nro_parcela, campania) *(RN-04: una cosecha por parcela y campaña)*.
8. **ANALISIS_CALIDAD** (**<u>id_analisis</u>**, *nro_lote*, fecha, grado_brix, ph, acidez_total)
   - Clave Foránea: *nro_lote* referencia a **LOTE_UVA**(nro_lote).

---

## 2. Subdominio Bodegas, Vinos y Clientes (Responsable: Manuel)

1. **BODEGA** (**<u>cuit</u>**, razon_social `[UNIQUE]`, domicilio)
   - Clave Candidata (UNIQUE): (razon_social).
2. **VINO** (**<u>cod_vino</u>**, nombre, tipo, anada, volumen_ml, graduacion, precio, *cuit_bodega*) `[UNIQUE: (nombre, anada, volumen_ml)]`
   - Clave Foránea: *cuit_bodega* referencia a **BODEGA**(cuit).
   - Clave Candidata (UNIQUE): (nombre, anada, volumen_ml).
3. **COMPOSICION_VINO** (**<u>*cod_vino*, *id_cepa*</u>**, porcentaje)
   - Clave Foránea 1: *cod_vino* referencia a **VINO**(cod_vino).
   - Clave Foránea 2: *id_cepa* referencia a **CEPA**(id_cepa).
4. **MARIDAJE** (**<u>id_maridaje</u>**, nombre `[UNIQUE]`, temperatura_servicio)
   - Clave Candidata (UNIQUE): (nombre).
5. **VINO_MARIDAJE** (**<u>*cod_vino*, *id_maridaje*</u>**)
   - Clave Foránea 1: *cod_vino* referencia a **VINO**(cod_vino).
   - Clave Foránea 2: *id_maridaje* referencia a **MARIDAJE**(id_maridaje).
6. **CLIENTE** (**<u>id_cliente</u>**, nombre_razon_social, tipo_documento, nro_documento, direccion, *cod_postal*, fecha_alta, tipo_cliente, porcentaje_descuento) `[UNIQUE: (tipo_documento, nro_documento)]`
   - Clave Foránea: *cod_postal* referencia a **LOCALIDAD**(cod_postal).
   - Clave Candidata (UNIQUE): (tipo_documento, nro_documento).
7. **CLIENTE_SOCIO** (**<u>*id_cliente*</u>**)
   - Clave Foránea: *id_cliente* referencia a **CLIENTE**(id_cliente).
8. **CLIENTE_DISTRIBUIDOR** (**<u>*id_cliente*</u>**, zona_cobertura, nro_habilitacion `[UNIQUE]`)
   - Clave Foránea: *id_cliente* referencia a **CLIENTE**(id_cliente).
   - Clave Candidata (UNIQUE): (nro_habilitacion).
9. **CLIENTE_EXPORTADOR** (**<u>*id_cliente*</u>**, pais_destino)
   - Clave Foránea: *id_cliente* referencia a **CLIENTE**(id_cliente).
10. **PERMISO_EXPORTACION** (**<u>cod_permiso</u>**, *id_cliente*, fecha_emision, fecha_vencimiento)
    - Clave Foránea: *id_cliente* referencia a **CLIENTE_EXPORTADOR**(id_cliente) *(RN-07)*.

---

## 3. Subdominio Ventas, Logística, Stock y Auditoría (Responsable: Bruno)

1. **COMPROBANTE** (**<u>nro_comprobante</u>**, fecha, *id_cliente*, *id_sala*, subtotal, descuento, total)
   - Clave Foránea 1: *id_cliente* referencia a **CLIENTE**(id_cliente).
   - Clave Foránea 2: *id_sala* referencia a **SALA_VENTA**(id_sala).
2. **RENGLON_COMPROBANTE** (**<u>*nro_comprobante*, *cod_vino*</u>**, cantidad, precio_unitario, descuento, subtotal)
   - Clave Foránea 1: *nro_comprobante* referencia a **COMPROBANTE**(nro_comprobante).
   - Clave Foránea 2: *cod_vino* referencia a **VINO**(cod_vino).
3. **TRANSPORTISTA** (**<u>cod_transporte</u>**, razon_social [UNIQUE], cuit [UNIQUE], email, telefono, domicilio)
4. **TRANSPORTISTA_LOCALIDAD** (**<u>*cod_transporte*, *cod_postal*</u>**)
   - Clave Foránea 1: *cod_transporte* referencia a **TRANSPORTISTA**(cod_transporte).
   - Clave Foránea 2: *cod_postal* referencia a **LOCALIDAD**(cod_postal).
5. **INGRESO** (**<u>cod_ingreso</u>**, fecha, estado, *cod_transporte*, *cuit_bodega*)
   - Clave Foránea 1: *cod_transporte* referencia a **TRANSPORTISTA**(cod_transporte).
   - Clave Foránea 2: *cuit_bodega* referencia a **BODEGA**(cuit).
6. **RENGLON_INGRESO** (**<u>*cod_ingreso*, *cod_vino*</u>**, cantidad)
   - Clave Foránea 1: *cod_ingreso* referencia a **INGRESO**(cod_ingreso).
   - Clave Foránea 2: *cod_vino* referencia a **VINO**(cod_vino).
7. **TRANSFERENCIA** (**<u>nro_transferencia</u>**, *id_sala*, fecha_confeccion, estado)
   - Clave Foránea 1: *id_sala* referencia a **SALA_VENTA**(id_sala).
8. **RENGLON_TRANSFERENCIA** (**<u>*nro_transferencia*, *cod_vino*</u>**, cantidad)
   - Clave Foránea 1: *nro_transferencia* referencia a **TRANSFERENCIA**(nro_transferencia).
   - Clave Foránea 2: *cod_vino* referencia a **VINO**(cod_vino).
9. **STOCK_SALA** (**<u>*id_sala*, *cod_vino*</u>**, cantidad)
   - Clave Foránea 1: *id_sala* referencia a **SALA_VENTA**(id_sala).
   - Clave Foránea 2: *cod_vino* referencia a **VINO**(cod_vino).
10. **STOCK_DEPOSITO** (**<u>*cod_vino*</u>**, cantidad)
    - Clave Foránea 1: *cod_vino* referencia a **VINO**(cod_vino).
11. **AUDITORIA_PRECIO** (**<u>id_auditoria</u>**, *cod_vino*, precio_anterior, precio_nuevo, fecha_hora, usuario)
    - Clave Foránea 1: *cod_vino* referencia a **VINO**(cod_vino).