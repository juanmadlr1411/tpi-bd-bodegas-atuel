from dataclasses import dataclass


@dataclass(frozen=True)
class ConfiguracionCarga:
    anio_inicio: int = 2022
    mes_inicio: int = 1

    anio_fin: int = 2026
    mes_fin: int = 10

    ingresos: int = 5000
    transferencias: int = 5000
    comprobantes: int = 150000

    semilla: int = 2026
    tamano_lote: int = 1000


def generar_meses(config):
    meses = []

    for anio in range(config.anio_inicio, config.anio_fin + 1):
        for mes in range(1, 13):

            if (anio, mes) < (
                config.anio_inicio, config.mes_inicio
            ):
                continue

            if (anio, mes) > (
                config.anio_fin, config.mes_fin
            ):
                continue

            meses.append((anio, mes))

    return meses


def distribuir_registros(total, cantidad_meses):
    """
    Distribuye una cantidad total de registros entre
    varios meses sin perder registros.
    """

    base, resto = divmod(total, cantidad_meses)

    return [
        base + (1 if i < resto else 0)
        for i in range(cantidad_meses)
    ]


def planificar_carga(config):

    meses = generar_meses(config)
    cantidad_meses = len(meses)

    ingresos = distribuir_registros(
        config.ingresos, cantidad_meses
    )

    transferencias = distribuir_registros(
        config.transferencias, cantidad_meses
    )

    comprobantes = distribuir_registros(
        config.comprobantes, cantidad_meses
    )

    plan = []

    for i, (anio, mes) in enumerate(meses):

        plan.append({
            "anio": anio,
            "mes": mes,
            "ingresos": ingresos[i],
            "transferencias": transferencias[i],
            "comprobantes": comprobantes[i]
        })

    return plan


def main():

    config = ConfiguracionCarga()

    plan = planificar_carga(config)

    print("PLAN DE CARGA HISTÓRICA")
    print("-" * 45)

    for periodo in plan[:5]:
        print(periodo)

    print("...")

    print(f"\nMeses planificados: {len(plan)}")

    print(
        "Total ingresos:",
        sum(p["ingresos"] for p in plan)
    )

    print(
        "Total transferencias:",
        sum(p["transferencias"] for p in plan)
    )

    print(
        "Total comprobantes:",
        sum(p["comprobantes"] for p in plan)
    )


if __name__ == "__main__":
    main()