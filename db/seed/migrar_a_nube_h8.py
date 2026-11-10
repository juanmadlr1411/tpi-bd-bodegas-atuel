#!/usr/bin/env python3
"""
=============================================================================
TPI BASES DE DATOS — UTN FRSR (2026)
Etapa 8 (H8): Migración Masiva de Datos a PostgreSQL en la Nube (Neon)
Responsable: Gonzalo
Uso: python db/seed/migrar_a_nube_h8.py
=============================================================================
Transfiere el dataset histórico completo (58 meses, +790.000 filas) desde el
contenedor local hacia la instancia cloud (Neon.tech) mediante streaming binario
de PostgreSQL (COPY BINARY), desactivando triggers de usuario temporalmente y
sincronizando secuencias y controles de integridad (RN-01 a RN-15).
"""

import os
import sys
import time
from dotenv import load_dotenv
import psycopg

# Cargar variables de entorno locales
load_dotenv()

LOCAL_URL = os.getenv(
    "LOCAL_DATABASE_URL",
    f"postgresql://{os.getenv('POSTGRES_USER', 'admin_atuel')}:{os.getenv('POSTGRES_PASSWORD', 'cambiar_en_local')}@{os.getenv('POSTGRES_HOST', 'localhost')}:{os.getenv('POSTGRES_PORT', '5432')}/{os.getenv('POSTGRES_DB', 'bodegas_atuel')}"
)

TARGET_URL = os.getenv("TARGET_DATABASE_URL") or os.getenv("NEON_DATABASE_URL")

if not TARGET_URL:
    print("[ERROR] No se configuró NEON_DATABASE_URL ni TARGET_DATABASE_URL en el entorno o .env", file=sys.stderr)
    sys.exit(1)

# Orden topológico estricto de tablas para preservar integridad referencial (FK)
TABLAS_TOPOLOGICAS = [
    # Nivel 1: Catálogos Raíz
    "localidad",
    "cepa",
    "maridaje",
    "bodega",
    "transportista",
    # Nivel 2: Entidades Geográficas, Estructurales y Supertipo
    "sala_venta",
    "empleado",
    "finca",
    "transportista_localidad",
    "cliente",
    # Nivel 3: Subtipos y Entidades de Producción
    "cliente_socio",
    "cliente_distribuidor",
    "cliente_exportador",
    "permiso_exportacion",
    "parcela",
    "lote_uva",
    "analisis_calidad",
    "vino",
    "auditoria_precio",
    # Nivel 4: Cruces N:M e Inventario Inicial
    "composicion_vino",
    "vino_maridaje",
    "stock_deposito",
    "stock_sala",
    # Nivel 5: Documentos Transaccionales (Cabeceras y Renglones)
    "ingreso",
    "renglon_ingreso",
    "transferencia",
    "renglon_transferencia",
    "comprobante",
    "renglon_comprobante",
]


def deshabilitar_triggers_usuario(cur_target):
    print(" -> Deshabilitando triggers de usuario en Neon...")
    cur_target.execute("""
        DO $do$
        DECLARE
            r RECORD;
        BEGIN
            FOR r IN (SELECT tablename FROM pg_tables WHERE schemaname = 'public') LOOP
                EXECUTE 'ALTER TABLE public.' || quote_ident(r.tablename) || ' DISABLE TRIGGER USER;';
            END LOOP;
        END $do$;
    """)


def habilitar_triggers_usuario(cur_target):
    print(" -> Rehabilitando triggers de usuario en Neon...")
    cur_target.execute("""
        DO $do$
        DECLARE
            r RECORD;
        BEGIN
            FOR r IN (SELECT tablename FROM pg_tables WHERE schemaname = 'public') LOOP
                EXECUTE 'ALTER TABLE public.' || quote_ident(r.tablename) || ' ENABLE TRIGGER USER;';
            END LOOP;
        END $do$;
    """)


def vaciar_tablas_target(cur_target):
    print(" -> Vaciando tablas destino en Neon con TRUNCATE CASCADE...")
    tablas_str = ", ".join([f'public."{t}"' for t in TABLAS_TOPOLOGICAS])
    cur_target.execute(f"TRUNCATE TABLE {tablas_str} CASCADE;")


def sincronizar_secuencias(cur_local, cur_target):
    print("\n -> Sincronizando valores de secuencias (SERIAL / IDENTITY)...")
    cur_local.execute("""
        SELECT sequencename, last_value 
        FROM pg_sequences 
        WHERE schemaname = 'public';
    """)
    secuencias = cur_local.fetchall()
    for seq_name, last_val in secuencias:
        if last_val is not None:
            cur_target.execute(f"SELECT setval('{seq_name}', %s, true);", (last_val,))
            print(f"    - {seq_name} -> {last_val}")


def ejecutar_consultas_control(cur_target):
    print("\n" + "=" * 70)
    print(" AUDITORÍA POST-CARGA EN NEON — CONSULTAS DE CONTROL (RN-01 a RN-15)")
    print("=" * 70)

    # 1. Composición Varietal (RN-05)
    cur_target.execute("""
        SELECT COUNT(*) AS vinos_con_corte_invalido
        FROM (
            SELECT v.cod_vino, COALESCE(SUM(cv.porcentaje), 0) AS suma_porcentaje
            FROM public.vino v
            LEFT JOIN public.composicion_vino cv ON cv.cod_vino = v.cod_vino
            GROUP BY v.cod_vino
            HAVING COALESCE(SUM(cv.porcentaje), 0) <> 100.00
        ) sub;
    """)
    r1 = cur_target.fetchone()[0]
    print(f" [Control 1] Cortes varietales que no suman 100% (RN-05): {r1} (Esperado: 0) {'✓ OK' if r1 == 0 else '✗ ERROR'}")

    # 2. Consistencia de Totales (RN-08)
    cur_target.execute("""
        SELECT COUNT(*) AS comprobantes_descuadrados
        FROM public.comprobante c
        WHERE c.total <> public.fn_total_comprobante(c.nro_comprobante);
    """)
    r2 = cur_target.fetchone()[0]
    print(f" [Control 2] Comprobantes descuadrados vs fn_total_comprobante (RN-08): {r2} (Esperado: 0) {'✓ OK' if r2 == 0 else '✗ ERROR'}")

    # 3. Existencias Negativas (RN-09 y RN-15)
    cur_target.execute("""
        SELECT 
            (SELECT COUNT(*) FROM public.stock_deposito WHERE cantidad < 0) AS stock_deposito_negativo,
            (SELECT COUNT(*) FROM public.stock_sala WHERE cantidad < 0)     AS stock_sala_negativo;
    """)
    r3_dep, r3_sala = cur_target.fetchone()
    print(f" [Control 3] Stocks negativos (RN-09): Depósito={r3_dep}, Salas={r3_sala} (Esperado: 0, 0) {'✓ OK' if r3_dep == 0 and r3_sala == 0 else '✗ ERROR'}")

    # 4. Cabeceras Huérfanas (RN-10 y RN-11)
    cur_target.execute("""
        SELECT
            (SELECT COUNT(*) FROM public.comprobante c LEFT JOIN public.renglon_comprobante rc ON rc.nro_comprobante = c.nro_comprobante WHERE rc.nro_comprobante IS NULL),
            (SELECT COUNT(*) FROM public.ingreso i LEFT JOIN public.renglon_ingreso ri ON ri.cod_ingreso = i.cod_ingreso WHERE ri.cod_ingreso IS NULL),
            (SELECT COUNT(*) FROM public.transferencia t LEFT JOIN public.renglon_transferencia rt ON rt.nro_transferencia = t.nro_transferencia WHERE rt.nro_transferencia IS NULL);
    """)
    r4_comp, r4_ing, r4_tra = cur_target.fetchone()
    print(f" [Control 4] Documentos huérfanos sin renglón: Comprobantes={r4_comp}, Ingresos={r4_ing}, Transferencias={r4_tra} (Esperado: 0, 0, 0) {'✓ OK' if r4_comp == 0 and r4_ing == 0 and r4_tra == 0 else '✗ ERROR'}")


def main():
    inicio_total = time.time()
    print("=" * 70)
    print(" INICIO DE MIGRACIÓN DE DATOS A POSTGRESQL EN NEON (ETAPA 8)")
    print("=" * 70)
    print(f" Origen (Local):  {LOCAL_URL.split('@')[-1]}")
    print(f" Destino (Neon):   {TARGET_URL.split('@')[-1].split('?')[0]}")
    print("=" * 70)

    try:
        with psycopg.connect(LOCAL_URL) as conn_local, psycopg.connect(TARGET_URL) as conn_target:
            with conn_local.cursor() as cur_local, conn_target.cursor() as cur_target:
                # 1. Preparar motor destino
                deshabilitar_triggers_usuario(cur_target)
                vaciar_tablas_target(cur_target)
                conn_target.commit()

                # 2. Migración tabla por tabla en streaming binario
                print("\n -> Iniciando streaming binario tabla por tabla:")
                total_filas = 0
                for idx, tabla in enumerate(TABLAS_TOPOLOGICAS, start=1):
                    t0 = time.time()
                    copy_out_sql = f'COPY public."{tabla}" TO STDOUT (FORMAT BINARY)'
                    copy_in_sql = f'COPY public."{tabla}" FROM STDIN (FORMAT BINARY)'

                    with cur_local.copy(copy_out_sql) as copy_out:
                        with cur_target.copy(copy_in_sql) as copy_in:
                            for chunk in copy_out:
                                copy_in.write(chunk)

                    conn_target.commit()

                    cur_target.execute(f'SELECT COUNT(*) FROM public."{tabla}";')
                    filas = cur_target.fetchone()[0]
                    total_filas += filas
                    elapsed = time.time() - t0
                    print(f"    [{idx:02d}/29] {tabla:<26} -> {filas:>8,d} filas ({elapsed:>6.2f}s)")

                # 3. Sincronizar secuencias
                sincronizar_secuencias(cur_local, cur_target)
                conn_target.commit()

                # 4. Rehabilitar triggers
                habilitar_triggers_usuario(cur_target)
                conn_target.commit()

                # 5. Ejecutar auditoría de controles
                ejecutar_consultas_control(cur_target)

        duracion_total = time.time() - inicio_total
        print("\n" + "=" * 70)
        print(f" MIGRACIÓN COMPLETADA EXITOSAMENTE EN {duracion_total:.2f} SEGUNDOS")
        print(f" Total de filas sincronizadas en Neon: {total_filas:,}")
        print("=" * 70)

    except Exception as e:
        print(f"\n[FATAL ERROR] Falló la migración: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()

