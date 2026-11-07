import random
from datetime import date
from decimal import Decimal, ROUND_HALF_UP

from plan_carga import ConfiguracionCarga, planificar_carga
from inventario_historico import InventarioHistorico
from datos_maestros import obtener_datos_maestros, obtener_disponibles
from carga_transaccional import conectar


def simular_mes(
    periodo,
    datos,
    inventario,
    rng,
    emitir_ingreso=None,
    emitir_transferencia=None,
    emitir_comprobante=None
):

    anio = periodo["anio"]
    mes = periodo["mes"]

    fecha_ingreso = date(anio, mes, 5)
    fecha_transferencia = date(anio, mes, 15)
    fecha_venta = date(anio, mes, 20)

    # Obtener datos maestros válidos para el período.
    _, vinos_por_bodega = obtener_disponibles(
        datos, fecha_ingreso
    )

    clientes, _ = obtener_disponibles(
        datos, fecha_venta
    )

    bodegas = sorted(vinos_por_bodega)

    # Diccionario de precios de los vinos.
    precios_vinos = {
        cod_vino: precio
        for cod_vino, cuit_bodega, anada, precio
        in datos["vinos"]
    }

    if not bodegas or not clientes:
        raise RuntimeError(
            f"Faltan datos maestros en {anio}-{mes:02d}"
        )

    # Estadísticas del mes.
    resultado = {
        "ingresos": periodo["ingresos"],
        "renglones_ingreso": 0,
        "transferencias": periodo["transferencias"],
        "renglones_transferencia": 0,
        "comprobantes": periodo["comprobantes"],
        "renglones_venta": 0,
        "botellas_ingresadas": 0,
        "botellas_transferidas": 0,
        "botellas_vendidas": 0,
    }

    # --------------------------------------------------
    # 1. INGRESOS
    # --------------------------------------------------

    for indice_ingreso in range(periodo["ingresos"]):

        bodega = rng.choice(bodegas)

        vinos_disponibles = vinos_por_bodega[bodega]

        cantidad_renglones = min(
            3, len(vinos_disponibles)
        )

        vinos_elegidos = rng.sample(
            vinos_disponibles,
            cantidad_renglones
        )

        renglones = [
            (cod_vino, rng.randint(100, 200))
            for cod_vino, precio in vinos_elegidos
        ]

        inventario.ingresar_documento(
            fecha_ingreso,
            renglones
        )
        # Preparar un documento compatible con las
        # columnas de ingreso y renglon_ingreso.
        cod_transporte = datos["transportistas"][
            indice_ingreso % len(datos["transportistas"])
        ]

        documento = {
            "fecha": fecha_ingreso,
            "cod_transporte": cod_transporte,
            "cuit_bodega": bodega,
            "renglones": [
                {
                    "cod_vino": cod_vino,
                    "cantidad": cantidad
                }
                for cod_vino, cantidad in renglones
            ]
        }

        if emitir_ingreso is not None:
            emitir_ingreso(documento)

        resultado["renglones_ingreso"] += len(renglones)

        resultado["botellas_ingresadas"] += sum(
            cantidad for _, cantidad in renglones
        )

    # --------------------------------------------------
    # 2. TRANSFERENCIAS
    # --------------------------------------------------

    for _ in range(periodo["transferencias"]):

        vinos_disponibles = [
            (cod_vino, stock)
            for cod_vino, stock in inventario.deposito.items()
            if stock >= 50
        ]

        if not vinos_disponibles:
            raise RuntimeError(
                f"Sin stock para transferencias: {anio}-{mes:02d}"
            )

        id_sala = rng.choice(datos["salas"])

        if len(vinos_disponibles) < 3:
            raise RuntimeError(
                f"No hay tres vinos con stock suficiente "
                f"en {anio}-{mes:02d}. "
                f"Disponibles: {len(vinos_disponibles)}"
            )
        cantidad_renglones = 3

        vinos_elegidos = rng.sample(
            vinos_disponibles,
            cantidad_renglones
        )

        renglones = [
            (cod_vino, rng.randint(50, min(100, stock)))
            for cod_vino, stock in vinos_elegidos
        ]

        inventario.transferir_documento(
            fecha_transferencia,
            id_sala,
            renglones
        )
        # Construir el documento de transferencia.
        documento = {
            "fecha_confeccion": fecha_transferencia,
            "id_sala": id_sala,
            "renglones": [
                {
                    "cod_vino": cod_vino,
                    "cantidad": cantidad
                }
                for cod_vino, cantidad in renglones
            ]
        }

        # Entregar el documento si hay una función receptora.
        if emitir_transferencia is not None:
            emitir_transferencia(documento)

        resultado["renglones_transferencia"] += len(renglones)

        resultado["botellas_transferidas"] += sum(
            cantidad for _, cantidad in renglones
        )

    # --------------------------------------------------
    # 3. VENTAS
    # --------------------------------------------------

    for numero in range(1, periodo["comprobantes"] + 1):

        salas_disponibles = {}

        for (id_sala, cod_vino), stock in sorted(
            inventario.salas.items()
        ):
            if stock > 0:
                salas_disponibles.setdefault(
                    id_sala, []
                ).append((cod_vino, stock))

        salas_aptas = {
            id_sala: vinos
            for id_sala, vinos in salas_disponibles.items()
            if len(vinos) >= 4
        }

        if not salas_aptas:
            raise RuntimeError(
                f"Sin sala con cuatro vinos disponibles "
                f"en {anio}-{mes:02d}, venta {numero}"
            )

        salas = sorted(salas_aptas)

        pesos = [
            sum(stock for _, stock in salas_aptas[sala])
            for sala in salas
        ]

        id_sala = rng.choices(
            salas,
            weights=pesos,
            k=1
        )[0]

        # Cliente válido para la fecha de venta.
        id_cliente = rng.choice(clientes)

        vinos_disponibles = [
            cod_vino
            for cod_vino, stock in salas_aptas[id_sala]
        ]

        vinos_elegidos = rng.sample(
            vinos_disponibles,
            4
        )

        renglones = [
            (cod_vino, 1)
            for cod_vino in vinos_elegidos
        ]

        inventario.vender_comprobante(
            fecha_venta,
            id_sala,
            renglones
        )

        # Construir el documento de venta.
        detalle = []

        for cod_vino, cantidad in renglones:

            precio = precios_vinos[cod_vino]
            descuento = datos["descuentos_clientes"][id_cliente]
            subtotal = (
                precio * cantidad *
                (Decimal("1") - descuento / Decimal("100"))
            ).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)

            detalle.append({
                "cod_vino": cod_vino,
                "cantidad": cantidad,
                "precio_unitario": precio,
                "descuento": descuento,
                "subtotal": subtotal
            })

        documento = {
            "fecha": fecha_venta,
            "id_cliente": id_cliente,
            "id_sala": id_sala,
            "renglones": detalle
        }

        # Entregar el documento si hay un receptor.
        if emitir_comprobante is not None:
            emitir_comprobante(documento)

        resultado["renglones_venta"] += len(renglones)

        resultado["botellas_vendidas"] += sum(
            cantidad for _, cantidad in renglones
        )

    return resultado


def main():

    config = ConfiguracionCarga()
    plan = planificar_carga(config)

    rng = random.Random(config.semilla)

    with conectar() as conn:
        datos = obtener_datos_maestros(conn)

    inventario = InventarioHistorico()

    totales = {
        "ingresos": 0,
        "renglones_ingreso": 0,
        "transferencias": 0,
        "renglones_transferencia": 0,
        "comprobantes": 0,
        "renglones_venta": 0,
        "botellas_ingresadas": 0,
        "botellas_transferidas": 0,
        "botellas_vendidas": 0,
    }

    print("SIMULACIÓN HISTÓRICA — DOCUMENTOS COMPLETOS")
    print("-" * 65)

    for periodo in plan:

        resultado = simular_mes(
            periodo,
            datos,
            inventario,
            rng
        )

        # Acumular las estadísticas.
        for clave, valor in resultado.items():
            totales[clave] += valor

        # Verificar las existencias al terminar cada mes.
        deposito = sum(inventario.deposito.values())
        salas = sum(inventario.salas.values())

        assert deposito == (
            totales["botellas_ingresadas"]
            - totales["botellas_transferidas"]
        )

        assert salas == (
            totales["botellas_transferidas"]
            - totales["botellas_vendidas"]
        )

        assert inventario.stock_total() == (
            totales["botellas_ingresadas"]
            - totales["botellas_vendidas"]
        )

        print(
            f"{periodo['anio']}-{periodo['mes']:02d} | "
            f"RI: {resultado['renglones_ingreso']:3d} | "
            f"RT: {resultado['renglones_transferencia']:3d} | "
            f"RV: {resultado['renglones_venta']:5d} | "
            f"Stock: {inventario.stock_total()}"
        )

    # Verificar los documentos previstos.
    assert totales["ingresos"] == config.ingresos
    assert totales["transferencias"] == config.transferencias
    assert totales["comprobantes"] == config.comprobantes

    # Cuatro renglones por comprobante.
    assert totales["renglones_venta"] == (
        config.comprobantes * 4
    )

    print("\nRESULTADOS FINALES")
    print("-" * 65)

    print(f"Meses simulados: {len(plan)}")

    print(f"\nIngresos: {totales['ingresos']}")
    print(f"Renglones de ingreso: {totales['renglones_ingreso']}")

    print(f"\nTransferencias: {totales['transferencias']}")
    print(
        f"Renglones de transferencia: "
        f"{totales['renglones_transferencia']}"
    )

    print(f"\nComprobantes: {totales['comprobantes']}")
    print(f"Renglones de venta: {totales['renglones_venta']}")

    print(f"\nBotellas ingresadas: {totales['botellas_ingresadas']}")
    print(f"Botellas transferidas: {totales['botellas_transferidas']}")
    print(f"Botellas vendidas: {totales['botellas_vendidas']}")

    print(f"\nStock depósito: {sum(inventario.deposito.values())}")
    print(f"Stock salas: {sum(inventario.salas.values())}")
    print(f"Stock total: {inventario.stock_total()}")

    print("\nSIMULACIÓN VALIDADA CORRECTAMENTE")
    print("No se modificó PostgreSQL.")


if __name__ == "__main__":
    main()