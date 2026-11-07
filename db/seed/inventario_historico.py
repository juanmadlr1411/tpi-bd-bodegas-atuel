from dataclasses import dataclass, field
from datetime import date


@dataclass
class InventarioHistorico:

    # Existencias del depósito central.
    deposito: dict[int, int] = field(default_factory=dict)

    # Existencias de cada vino en cada sala.
    salas: dict[tuple[int, int], int] = field(default_factory=dict)

    # Fecha del último movimiento.
    ultima_fecha: date | None = None

    def validar_movimiento(self, fecha, cantidad):

        if cantidad <= 0:
            raise ValueError("La cantidad debe ser positiva.")

        if self.ultima_fecha is not None:
            if fecha < self.ultima_fecha:
                raise ValueError(
                    "No se pueden registrar movimientos fuera de orden."
                )

    def ingresar(self, fecha, cod_vino, cantidad):

        self.validar_movimiento(fecha, cantidad)

        self.deposito[cod_vino] = (
            self.deposito.get(cod_vino, 0) + cantidad
        )

        self.ultima_fecha = fecha

    def ingresar_documento(self, fecha, renglones):
        """
        Registra un ingreso con varios vinos.

        Valida todos los renglones antes de modificar
        el inventario.
        """

        if not renglones:
            raise ValueError(
                "El ingreso debe contener al menos un renglón."
            )

        vinos_utilizados = set()

        # 1. Validar el documento completo.
        for cod_vino, cantidad in renglones:

            self.validar_movimiento(fecha, cantidad)

            if cod_vino in vinos_utilizados:
                raise ValueError(
                    f"El vino {cod_vino} está repetido."
                )

            vinos_utilizados.add(cod_vino)

        # 2. Registrar las existencias.
        for cod_vino, cantidad in renglones:

            self.deposito[cod_vino] = (
                self.deposito.get(cod_vino, 0) + cantidad
            )

        self.ultima_fecha = fecha

    def transferir(self, fecha, id_sala, cod_vino, cantidad):

        self.validar_movimiento(fecha, cantidad)

        disponible = self.deposito.get(cod_vino, 0)

        if disponible < cantidad:
            raise ValueError(
                f"Stock insuficiente en depósito para vino {cod_vino}."
            )

        # Descontar del depósito.
        self.deposito[cod_vino] -= cantidad

        # Sumar a la sala.
        clave = (id_sala, cod_vino)

        self.salas[clave] = (
            self.salas.get(clave, 0) + cantidad
        )

        self.ultima_fecha = fecha

    def transferir_documento(self, fecha, id_sala, renglones):
        """
        Transfiere varios vinos del depósito a una sala.

        Valida el documento completo antes de modificar
        las existencias.
        """

        if not renglones:
            raise ValueError(
                "La transferencia debe tener al menos un renglón."
            )

        vinos_utilizados = set()

        # PRIMERA ETAPA: validar todos los renglones.
        for cod_vino, cantidad in renglones:

            self.validar_movimiento(fecha, cantidad)

            if cod_vino in vinos_utilizados:
                raise ValueError(
                    f"El vino {cod_vino} está repetido."
                )

            vinos_utilizados.add(cod_vino)

            disponible = self.deposito.get(cod_vino, 0)

            if disponible < cantidad:
                raise ValueError(
                    f"Stock insuficiente del vino {cod_vino}. "
                    f"Disponible: {disponible}, solicitado: {cantidad}."
                )

        # SEGUNDA ETAPA: ejecutar la transferencia.
        for cod_vino, cantidad in renglones:

            # Descontar del depósito.
            self.deposito[cod_vino] -= cantidad

            # Sumar a la sala.
            clave = (id_sala, cod_vino)

            self.salas[clave] = (
                self.salas.get(clave, 0) + cantidad
            )

        self.ultima_fecha = fecha

    def vender(self, fecha, id_sala, cod_vino, cantidad):

        self.validar_movimiento(fecha, cantidad)

        clave = (id_sala, cod_vino)

        disponible = self.salas.get(clave, 0)

        if disponible < cantidad:
            raise ValueError(
                f"Stock insuficiente en sala {id_sala} "
                f"para vino {cod_vino}."
            )

        # Descontar la venta.
        self.salas[clave] -= cantidad

        self.ultima_fecha = fecha

    def vender_comprobante(self, fecha, id_sala, renglones):
        """
        Registra una venta con varios vinos.

        Todos los renglones deben ser válidos antes
        de descontar cualquier botella.
        """

        if not renglones:
            raise ValueError(
                "El comprobante debe tener al menos un renglón."
            )

        vinos_utilizados = set()

        # PRIMERA ETAPA: validar todos los renglones.
        for cod_vino, cantidad in renglones:

            self.validar_movimiento(fecha, cantidad)

            if cod_vino in vinos_utilizados:
                raise ValueError(
                    f"El vino {cod_vino} está repetido."
                )

            vinos_utilizados.add(cod_vino)

            disponible = self.salas.get(
                (id_sala, cod_vino), 0
            )

            if disponible < cantidad:
                raise ValueError(
                    f"Stock insuficiente del vino {cod_vino}. "
                    f"Disponible: {disponible}, solicitado: {cantidad}."
                )

        # SEGUNDA ETAPA: descontar las existencias.
        for cod_vino, cantidad in renglones:

            clave = (id_sala, cod_vino)

            self.salas[clave] -= cantidad

        self.ultima_fecha = fecha
    def stock_total(self):

        return (
            sum(self.deposito.values())
            + sum(self.salas.values())
        )


def main():

    inventario = InventarioHistorico()

    # 1. Una bodega entrega 100 botellas.
    inventario.ingresar(
        date(2022, 1, 10),
        cod_vino=1,
        cantidad=100
    )

    # 2. Se transfieren 30 botellas a una sala.
    inventario.transferir(
        date(2022, 1, 12),
        id_sala=1,
        cod_vino=1,
        cantidad=30
    )

    # 3. La sala vende 7 botellas.
    inventario.vender(
        date(2022, 1, 15),
        id_sala=1,
        cod_vino=1,
        cantidad=7
    )

    print("INVENTARIO HISTÓRICO")
    print("-" * 40)

    print("Depósito:", inventario.deposito)
    print("Salas:", inventario.salas)

    print("Stock total:", inventario.stock_total())

    # Comprobar los resultados esperados.
    assert inventario.deposito[1] == 70
    assert inventario.salas[(1, 1)] == 23
    assert inventario.stock_total() == 93

    print("Validación: correcta.")

    # 4. Intentar vender más botellas de las disponibles.
    try:
        inventario.vender(
            date(2022, 1, 20),
            id_sala=1,
            cod_vino=1,
            cantidad=25
        )

    except ValueError as error:
        print("Venta inválida rechazada:", error)

    else:
        raise AssertionError(
            "El sistema permitió una venta sin stock suficiente."
        )

    assert inventario.stock_total() == 93

    print("Stock conservado después del rechazo.")

def probar_comprobante_multiple():

    inventario = InventarioHistorico()

    # Ingresar dos vinos al depósito.
    inventario.ingresar(date(2022, 1, 5), 1, 100)
    inventario.ingresar(date(2022, 1, 5), 2, 80)

    # Transferir ambos vinos a la sala 1.
    inventario.transferir(date(2022, 1, 15), 1, 1, 30)
    inventario.transferir(date(2022, 1, 15), 1, 2, 20)

    # Primera venta: ambos renglones son válidos.
    inventario.vender_comprobante(
        date(2022, 1, 20),
        id_sala=1,
        renglones=[
            (1, 3),
            (2, 2)
        ]
    )

    assert inventario.salas[(1, 1)] == 27
    assert inventario.salas[(1, 2)] == 18

    print("\nVenta con múltiples renglones: correcta.")

    # Segunda venta: el segundo renglón es inválido.
    try:
        inventario.vender_comprobante(
            date(2022, 1, 20),
            id_sala=1,
            renglones=[
                (1, 1),
                (2, 99)
            ]
        )

    except ValueError as error:
        print("Venta inválida rechazada:", error)

    else:
        raise AssertionError(
            "Se aceptó una venta sin stock suficiente."
        )

    # Comprobar que no se descontó ningún renglón.
    assert inventario.salas[(1, 1)] == 27
    assert inventario.salas[(1, 2)] == 18

    print("Atomicidad verificada correctamente.")

if __name__ == "__main__":
    main()
    probar_comprobante_multiple()