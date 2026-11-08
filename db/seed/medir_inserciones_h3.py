"""Compara execute() por fila y executemany() sobre una tabla temporal.

No carga datos reales ni altera el esquema permanente. La tabla temporal
carece de triggers y claves foráneas: la medición aísla el método de inserción,
no reemplaza el tiempo real del seed histórico.
"""

import argparse
import json
from datetime import date
from pathlib import Path
from time import perf_counter

from conexion import conectar


SQL_INSERT = "INSERT INTO tmp_h3_medicion (id, cod_vino, cantidad, fecha) VALUES (%s, %s, %s, %s)"


def medir(n):
    filas = [(i, (i % 40) + 1, (i % 4) + 1, date(2026, 10, 1)) for i in range(1, n + 1)]
    conn = conectar()
    try:
        with conn.cursor() as cur:
            cur.execute("""
                CREATE TEMP TABLE tmp_h3_medicion (
                    id INTEGER PRIMARY KEY, cod_vino INTEGER NOT NULL,
                    cantidad INTEGER NOT NULL, fecha DATE NOT NULL
                ) ON COMMIT DROP
            """)
            t0 = perf_counter()
            for fila in filas:
                cur.execute(SQL_INSERT, fila)
            individual = perf_counter() - t0
            cur.execute("SELECT COUNT(*) FROM tmp_h3_medicion")
            if cur.fetchone()[0] != n:
                raise RuntimeError("El conteo individual fue incorrecto")
            cur.execute("TRUNCATE tmp_h3_medicion")
            t0 = perf_counter()
            cur.executemany(SQL_INSERT, filas)
            lotes = perf_counter() - t0
            cur.execute("SELECT COUNT(*) FROM tmp_h3_medicion")
            if cur.fetchone()[0] != n:
                raise RuntimeError("El conteo por lotes fue incorrecto")
        conn.rollback()  # Revierte CREATE TEMP e INSERTs.
        return {"muestra": n, "individual_seg": round(individual, 6),
                "lotes_seg": round(lotes, 6), "total_historico_seg": 19342.15,
                "alcance": "tabla temporal sin triggers ni claves foraneas"}
    finally:
        if not conn.closed:
            conn.rollback()
        conn.close()


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--filas", type=int, default=1000)
    p.add_argument("--salida-json", type=Path, default=None)
    args = p.parse_args()
    if not 1 <= args.filas <= 10000:
        p.error("--filas debe estar entre 1 y 10000")
    datos = medir(args.filas)
    uno, lote = datos["individual_seg"], datos["lotes_seg"]
    print(f"Muestra: {datos['muestra']} filas (tabla temporal, sin triggers)")
    print(f"execute fila por fila: {uno:.4f} segundos")
    print(f"executemany por lotes: {lote:.4f} segundos")
    print(f"Relación de tiempos: {uno/lote:.2f}x" if lote else "Relación: no calculable")
    print(f"Carga real de los 58 meses (medición histórica): {datos['total_historico_seg']} s")
    print("ROLLBACK: ningún dato del proyecto modificado")
    if args.salida_json:
        args.salida_json.write_text(json.dumps(datos, indent=2, ensure_ascii=False), encoding="utf-8")
        print("Resultados guardados en:", args.salida_json)


if __name__ == "__main__":
    main()
