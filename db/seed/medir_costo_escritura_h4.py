"""Mide el costo de escritura y almacenamiento de los indices de 008_indices.sql.

Escenario A: solo PRIMARY KEY sobre las tablas medidas.
Escenario B: PRIMARY KEY + indices definidos en 008_indices.sql.

Ambos escenarios insertan exactamente el mismo lote sobre comprobante y
renglon_comprobante, con los triggers de usuario deshabilitados dentro de la
transaccion para aislar el mantenimiento de indices. Todo termina con ROLLBACK:
no se conservan filas, indices ni cambios de triggers.
"""

import argparse
import json
import random
import re
import statistics
from datetime import date, timedelta
from decimal import Decimal, ROUND_HALF_UP
from pathlib import Path
from time import perf_counter

from conexion import conectar

RAIZ_PROYECTO = Path(__file__).resolve().parents[2]
ARCHIVO_INDICES = RAIZ_PROYECTO / "db" / "migrations" / "008_indices.sql"
FECHA_DESDE = date(2022, 1, 1)
FECHA_HASTA = date(2026, 10, 31)
TABLAS_MEDIDAS = ("comprobante", "renglon_comprobante")
PATRON_INDICE = re.compile(
    r"CREATE\s+(?:UNIQUE\s+)?INDEX\s+(?:IF\s+NOT\s+EXISTS\s+)?(\w+)\s+ON\s+(\w+)",
    re.IGNORECASE,
)
PATRON_INICIO_INDICE = re.compile(r"CREATE\s+(?:UNIQUE\s+)?INDEX", re.IGNORECASE)

SQL_COMPROBANTE = """
    INSERT INTO comprobante (nro_comprobante, fecha, id_cliente, id_sala)
    OVERRIDING SYSTEM VALUE
"""

SQL_RENGLON = """
    INSERT INTO renglon_comprobante
        (nro_comprobante, cod_vino, cantidad, precio_unitario, descuento, subtotal)
"""

COLUMNAS_COMPROBANTE = 4
COLUMNAS_RENGLON = 6


def cargar_indices_008():
    """Extrae las sentencias CREATE INDEX de 008_indices.sql sin ejecutar el archivo."""
    texto = ARCHIVO_INDICES.read_text(encoding="utf-8")
    sin_comentarios = "\n".join(
        linea.split("--", 1)[0] for linea in texto.splitlines()
    )
    sentencias = [s.strip() for s in sin_comentarios.split(";") if s.strip()]
    indices = []
    for sentencia in sentencias:
        if PATRON_INICIO_INDICE.match(sentencia) is None:
            continue
        if "CONCURRENTLY" in sentencia.upper():
            raise RuntimeError(
                "008_indices.sql contiene CREATE INDEX CONCURRENTLY; "
                "no puede ejecutarse dentro de una transaccion con ROLLBACK."
            )
        coincidencia = PATRON_INDICE.search(sentencia)
        if coincidencia is None:
            raise RuntimeError(f"No se pudo interpretar la sentencia: {sentencia}")
        indices.append(
            {
                "nombre": coincidencia.group(1),
                "tabla": coincidencia.group(2),
                "sql": sentencia,
            }
        )
    if not indices:
        raise RuntimeError(f"No se encontraron indices en {ARCHIVO_INDICES}")
    return indices


def leer_datos_maestros(cur):
    cur.execute("SELECT id_cliente FROM cliente ORDER BY id_cliente")
    clientes = [fila[0] for fila in cur.fetchall()]
    cur.execute("SELECT id_sala FROM sala_venta ORDER BY id_sala")
    salas = [fila[0] for fila in cur.fetchall()]
    cur.execute("SELECT cod_vino, precio FROM vino ORDER BY cod_vino")
    vinos = cur.fetchall()
    if not clientes or not salas or not vinos:
        raise RuntimeError(
            "Faltan datos maestros (cliente, sala_venta o vino) para generar el lote."
        )
    return clientes, salas, vinos


def generar_lote(filas, renglones_por_comprobante, semilla, base_id, clientes, salas, vinos):
    rng = random.Random(semilla)
    dias = (FECHA_HASTA - FECHA_DESDE).days
    comprobantes = []
    renglones = []
    for i in range(filas):
        nro_comprobante = base_id + i + 1
        fecha = FECHA_DESDE + timedelta(days=rng.randrange(dias + 1))
        comprobantes.append(
            (nro_comprobante, fecha, rng.choice(clientes), rng.choice(salas))
        )
        cantidad_renglones = min(renglones_por_comprobante, len(vinos))
        for cod_vino, precio in rng.sample(vinos, k=cantidad_renglones):
            cantidad = rng.randint(1, 12)
            descuento = Decimal(rng.choice((0, 5, 10, 15, 20, 30)))
            subtotal = (
                Decimal(cantidad)
                * precio
                * (Decimal("1") - descuento / Decimal("100"))
            ).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
            renglones.append(
                (nro_comprobante, cod_vino, cantidad, precio, descuento, subtotal)
            )
    return comprobantes, renglones


def deshabilitar_triggers(cur):
    cur.execute("ALTER TABLE comprobante DISABLE TRIGGER USER")
    cur.execute("ALTER TABLE renglon_comprobante DISABLE TRIGGER USER")


def insertar_por_lotes(cur, sql, columnas, filas, lote):
    for inicio in range(0, len(filas), lote):
        bloque = filas[inicio:inicio + lote]
        marcadores = ", ".join(
            "(" + ", ".join(["%s"] * columnas) + ")" for _ in bloque
        )
        parametros = [valor for fila in bloque for valor in fila]
        cur.execute(f"{sql} VALUES {marcadores}", parametros)


def insertar_lote(cur, comprobantes, renglones, lote):
    t0 = perf_counter()
    insertar_por_lotes(cur, SQL_COMPROBANTE, COLUMNAS_COMPROBANTE, comprobantes, lote)
    t1 = perf_counter()
    insertar_por_lotes(cur, SQL_RENGLON, COLUMNAS_RENGLON, renglones, lote)
    t2 = perf_counter()
    return {
        "comprobante_seg": t1 - t0,
        "renglon_seg": t2 - t1,
        "total_seg": t2 - t0,
    }


def verificar_lote(cur, comprobantes, renglones):
    desde = comprobantes[0][0]
    hasta = comprobantes[-1][0]
    cur.execute(
        "SELECT COUNT(*) FROM comprobante WHERE nro_comprobante BETWEEN %s AND %s",
        (desde, hasta),
    )
    if cur.fetchone()[0] != len(comprobantes):
        raise RuntimeError("La cantidad de comprobantes insertados no coincide con el lote.")
    cur.execute(
        """
        SELECT COUNT(*) FROM renglon_comprobante
         WHERE nro_comprobante BETWEEN %s AND %s
        """,
        (desde, hasta),
    )
    if cur.fetchone()[0] != len(renglones):
        raise RuntimeError("La cantidad de renglones insertados no coincide con el lote.")


def tamano_relacion(cur, tabla):
    cur.execute(
        "SELECT pg_relation_size(%s::regclass), pg_indexes_size(%s::regclass)",
        (tabla, tabla),
    )
    heap, indices = cur.fetchone()
    return {"heap_bytes": heap, "indices_bytes": indices}


def tamanos_indices(cur, tabla):
    cur.execute(
        """
        SELECT c.relname, pg_relation_size(c.oid)
          FROM pg_index i
          JOIN pg_class c ON c.oid = i.indexrelid
         WHERE i.indrelid = %s::regclass
        """,
        (tabla,),
    )
    return {nombre: tamano for nombre, tamano in cur.fetchall()}


def indices_secundarios(cur, tabla):
    cur.execute(
        """
        SELECT c.relname
          FROM pg_index i
          JOIN pg_class c ON c.oid = i.indexrelid
         WHERE i.indrelid = %s::regclass
           AND NOT i.indisprimary
           AND NOT i.indisunique
         ORDER BY c.relname
        """,
        (tabla,),
    )
    return [fila[0] for fila in cur.fetchall()]


def medir_tamanos(cur):
    return {
        tabla: {
            "relacion": tamano_relacion(cur, tabla),
            "indices": tamanos_indices(cur, tabla),
        }
        for tabla in TABLAS_MEDIDAS
    }


def ejecutar_escenario(conn, nombre, indices, comprobantes, renglones, lote):
    try:
        with conn.cursor() as cur:
            deshabilitar_triggers(cur)
            if nombre == "A":
                for indice in indices:
                    cur.execute(f'DROP INDEX IF EXISTS "{indice["nombre"]}"')
            else:
                for indice in indices:
                    cur.execute(indice["sql"])

            antes = medir_tamanos(cur)
            tiempos = insertar_lote(cur, comprobantes, renglones, lote)
            verificar_lote(cur, comprobantes, renglones)
            despues = medir_tamanos(cur)

            tamanos_008 = {}
            if nombre == "B":
                for indice in indices:
                    cur.execute(
                        "SELECT pg_relation_size(%s::regclass)",
                        (indice["nombre"],),
                    )
                    tamanos_008[indice["nombre"]] = cur.fetchone()[0]

            return {
                "tiempos_seg": tiempos,
                "antes": antes,
                "despues": despues,
                "tamanos_008": tamanos_008,
            }
    finally:
        conn.rollback()


def resumir_escenario(resultados):
    resumen = {}
    for clave in ("comprobante_seg", "renglon_seg", "total_seg"):
        tiempos = [resultado["tiempos_seg"][clave] for resultado in resultados]
        resumen[clave] = {
            "tiempos": tiempos,
            "mediana": statistics.median(tiempos),
            "promedio": statistics.fmean(tiempos),
            "minimo": min(tiempos),
            "maximo": max(tiempos),
        }
    return resumen


def incrementos_por_indice(resultado):
    incrementos = {}
    for tabla in TABLAS_MEDIDAS:
        antes = resultado["antes"][tabla]
        despues = resultado["despues"][tabla]
        incrementos[tabla] = {
            "heap_bytes": despues["relacion"]["heap_bytes"] - antes["relacion"]["heap_bytes"],
            "indices_bytes": despues["relacion"]["indices_bytes"] - antes["relacion"]["indices_bytes"],
            "por_indice": {
                nombre: despues["indices"].get(nombre, 0) - antes["indices"].get(nombre, 0)
                for nombre in despues["indices"]
            },
            "indices_despues": despues["indices"],
        }
    return incrementos


def medir(args):
    indices = cargar_indices_008()
    conn = conectar()
    try:
        with conn.cursor() as cur:
            clientes, salas, vinos = leer_datos_maestros(cur)
            cur.execute("SELECT COALESCE(MAX(nro_comprobante), 0) FROM comprobante")
            base_id = cur.fetchone()[0]
            secundarios = {
                tabla: indices_secundarios(cur, tabla) for tabla in TABLAS_MEDIDAS
            }
        conn.rollback()

        comprobantes, renglones = generar_lote(
            args.filas,
            args.renglones_por_comprobante,
            args.semilla,
            base_id,
            clientes,
            salas,
            vinos,
        )

        resultados = {"A": [], "B": []}
        for _ in range(args.repeticiones):
            resultados["A"].append(
                ejecutar_escenario(conn, "A", indices, comprobantes, renglones, args.lote)
            )
            resultados["B"].append(
                ejecutar_escenario(conn, "B", indices, comprobantes, renglones, args.lote)
            )

        resumen_a = resumir_escenario(resultados["A"])
        resumen_b = resumir_escenario(resultados["B"])
        sobrecarga = {}
        for clave in ("comprobante_seg", "renglon_seg", "total_seg"):
            base = resumen_a[clave]["mediana"]
            sobrecarga[clave] = (
                (resumen_b[clave]["mediana"] - base) / base * 100
            )

        return {
            "filas_comprobante": len(comprobantes),
            "filas_renglon": len(renglones),
            "renglones_por_comprobante": args.renglones_por_comprobante,
            "repeticiones": args.repeticiones,
            "semilla": args.semilla,
            "lote": args.lote,
            "base_id": base_id,
            "indices_008": indices,
            "indices_secundarios": secundarios,
            "escenario_a": resumen_a,
            "escenario_b": resumen_b,
            "sobrecarga_pct": sobrecarga,
            "sobrecarga_comprobante_pct": sobrecarga["comprobante_seg"],
            "sobrecarga_total_pct": sobrecarga["total_seg"],
            "incrementos_b": incrementos_por_indice(resultados["B"][-1]),
            "tamanos_008_b": resultados["B"][-1]["tamanos_008"],
        }
    finally:
        if not conn.closed:
            conn.rollback()
        conn.close()


def imprimir_resultados(datos):
    print("=" * 78)
    print("Costo de escritura y almacenamiento de los indices (008_indices.sql)")
    print("=" * 78)
    print(
        f"Lote: {datos['filas_comprobante']:,} comprobantes + "
        f"{datos['filas_renglon']:,} renglones"
    )
    print(f"Repeticiones: {datos['repeticiones']} (se informa la mediana)")
    print(f"Tamano de lote de envio: {datos['lote']:,} filas")
    print()
    for etiqueta, escenario in (("A (solo PRIMARY KEY)", "escenario_a"), ("B (PRIMARY KEY + 008)", "escenario_b")):
        resumen = datos[escenario]
        print(f"Escenario {etiqueta}:")
        print(f"  comprobante: {resumen['comprobante_seg']['mediana']:.4f} s")
        print(f"  renglon:     {resumen['renglon_seg']['mediana']:.4f} s")
        print(f"  total:       {resumen['total_seg']['mediana']:.4f} s")
    print()
    print(
        "Sobrecarga de escritura (B vs. A): "
        f"comprobante {datos['sobrecarga_pct']['comprobante_seg']:.2f} % | "
        f"total {datos['sobrecarga_pct']['total_seg']:.2f} %"
    )
    print()

    print("Incremento de espacio por el lote (escenario B):")
    for tabla, datos_tabla in datos["incrementos_b"].items():
        print(f"  {tabla}:")
        print(f"    heap:   {datos_tabla['heap_bytes'] / 1024 / 1024:8.2f} MB")
        print(f"    indices:{datos_tabla['indices_bytes'] / 1024 / 1024:8.2f} MB")
        for nombre, bytes_indice in datos_tabla["por_indice"].items():
            print(f"      {nombre}: {bytes_indice / 1024 / 1024:.2f} MB")
    print()

    print("Tamano total de cada indice de 008_indices.sql (escenario B):")
    for nombre, bytes_indice in datos["tamanos_008_b"].items():
        print(f"  {nombre}: {bytes_indice / 1024 / 1024:.2f} MB")
    print()

    avisos = {
        tabla: nombres
        for tabla, nombres in datos["indices_secundarios"].items()
        if nombres
    }
    if avisos:
        print("Aviso: existen indices secundarios ajenos a 008_indices.sql:")
        for tabla, nombres in avisos.items():
            print(f"  {tabla}: {', '.join(nombres)}")
        print("El escenario A no los elimina; la diferencia mide solo el costo de 008.")
        print()

    print("ROLLBACK: no se conservaron filas, indices ni cambios de triggers.")


def main():
    parser = argparse.ArgumentParser(
        description="Mide el costo de escritura y almacenamiento de 008_indices.sql."
    )
    parser.add_argument("--filas", type=int, default=50000)
    parser.add_argument("--renglones-por-comprobante", type=int, default=1)
    parser.add_argument("--repeticiones", type=int, default=5)
    parser.add_argument("--lote", type=int, default=5000)
    parser.add_argument("--semilla", type=int, default=2026)
    parser.add_argument("--salida-json", type=Path, default=None)
    args = parser.parse_args()

    if args.filas <= 0:
        parser.error("--filas debe ser mayor que cero")
    if args.renglones_por_comprobante <= 0:
        parser.error("--renglones-por-comprobante debe ser mayor que cero")
    if args.repeticiones <= 0:
        parser.error("--repeticiones debe ser mayor que cero")
    if args.lote <= 0:
        parser.error("--lote debe ser mayor que cero")
    if args.lote > 10000:
        parser.error("--lote no puede superar 10000 filas (limite de parametros de PostgreSQL)")

    datos = medir(args)
    imprimir_resultados(datos)

    if args.salida_json:
        args.salida_json.write_text(
            json.dumps(datos, indent=2, ensure_ascii=False, default=str),
            encoding="utf-8",
        )
        print("Resultados guardados en:", args.salida_json)


if __name__ == "__main__":
    main()
