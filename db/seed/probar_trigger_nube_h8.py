#!/usr/bin/env python3
"""
=============================================================================
TPI BASES DE DATOS — UTN FRSR (2026)
Etapa 8 (H8): Verificación de Trigger Vivo en la Nube (RN-09)
Responsable: Gonzalo
Uso: python db/seed/probar_trigger_nube_h8.py
=============================================================================
Demuestra que el motor PostgreSQL alojado en Neon rechaza de manera atómica
una venta que supere las existencias físicas disponibles en sala, disparando la
excepción de negocio definida en el trigger `trg_validar_stock_venta`.
"""

import os
import sys
from dotenv import load_dotenv
import psycopg

load_dotenv()

TARGET_URL = os.getenv("TARGET_DATABASE_URL") or os.getenv("NEON_DATABASE_URL")

if not TARGET_URL:
    print("[ERROR] No se configuró NEON_DATABASE_URL en el entorno o .env", file=sys.stderr)
    sys.exit(1)


def probar_trigger_stock_insuficiente():
    print("=" * 75)
    print(" PRUEBA DE TRIGGER VIVO EN NUBE — BODEGAS DEL ATUEL (ETAPA 8)")
    print(f" Servidor Cloud: {TARGET_URL.split('@')[-1].split('?')[0]}")
    print("=" * 75)

    with psycopg.connect(TARGET_URL) as conn:
        with conn.cursor() as cur:
            # 1. Obtener una sala y vino con stock conocido
            cur.execute("""
                SELECT s.id_sala, s.cod_vino, v.nombre, s.cantidad
                FROM stock_sala s
                JOIN vino v ON v.cod_vino = s.cod_vino
                WHERE s.cantidad > 0
                ORDER BY s.cantidad DESC
                LIMIT 1;
            """)
            fila = cur.fetchone()
            if not fila:
                print("[ERROR] No se encontraron registros con stock en stock_sala")
                return False

            id_sala, cod_vino, vino_nombre, stock_disponible = fila
            cantidad_excedente = stock_disponible + 1000

            print(f" [1] Datos de prueba seleccionados:")
            print(f"     - Sala de Venta: ID {id_sala}")
            print(f"     - Vino: ID {cod_vino} ('{vino_nombre}')")
            print(f"     - Stock Físico Disponible: {stock_disponible:,} botellas")
            print(f"     - Cantidad solicitada en venta: {cantidad_excedente:,} botellas (EXCEDENTE)")

            # 2. Iniciar transacción e intentar la venta excedente
            try:
                cur.execute("""
                    INSERT INTO comprobante (fecha, id_cliente, id_sala)
                    VALUES (CURRENT_DATE, 1, %s)
                    RETURNING nro_comprobante;
                """, (id_sala,))
                nro_comprobante = cur.fetchone()[0]
                print(f"\n [2] Cabecera de comprobante #{nro_comprobante} abierta en transacción.")

                print(f" [3] Insertando renglón con {cantidad_excedente:,} unidades...")
                cur.execute("""
                    INSERT INTO renglon_comprobante (nro_comprobante, cod_vino, cantidad, precio_unitario, descuento)
                    VALUES (%s, %s, %s, 1500.00, 0);
                """, (nro_comprobante, cod_vino, cantidad_excedente))

                conn.commit()
                print(" [ERROR CRÍTICO] La venta fue permitida. El trigger falló.")
                return False

            except psycopg.Error as exc:
                conn.rollback()
                print("\n [4] RESULTADO DE LA EJECUCIÓN DEL TRIGGER EN EL MOTOR:")
                print("     -----------------------------------------------------------------")
                print(f"     Código SQLSTATE : {exc.diag.sqlstate}")
                print(f"     Función PL/pgSQL: {exc.diag.context.strip() if exc.diag.context else 'N/A'}")
                print(f"     Mensaje de Error: {exc.diag.message_primary}")
                print("     -----------------------------------------------------------------")

                # 3. Verificar que la transacción se canceló limpiamente sin dejar cabecera huérfana
                cur.execute("SELECT COUNT(*) FROM comprobante WHERE nro_comprobante = %s;", (nro_comprobante,))
                huerfanos = cur.fetchone()[0]
                print(f" [5] Control de Atomicidad: Comprobantes residuales en BD = {huerfanos} (Esperado: 0)")

                if exc.diag.sqlstate == "P0001" and huerfanos == 0:
                    print("\n" + "=" * 75)
                    print(" ✓ CERTIFICACIÓN: REGLA RN-09 ACTIVA Y PROTEGIENDO LA BD EN LA NUBE")
                    print("=" * 75)
                    return True
                else:
                    print("\n ✗ Error inesperado en la validación.")
                    return False


if __name__ == "__main__":
    exito = probar_trigger_stock_insuficiente()
    sys.exit(0 if exito else 1)

