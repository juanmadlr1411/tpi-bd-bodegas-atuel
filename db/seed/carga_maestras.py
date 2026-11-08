import os
import csv
import random
from datetime import date, timedelta
import psycopg
from faker import Faker
from dotenv import load_dotenv

load_dotenv()

# Semilla fija obligatoria (Etapa 3 - Paso 3: reproducibilidad exacta)
SEMILLA_MAESTRAS = 42
random.seed(SEMILLA_MAESTRAS)
Faker.seed(SEMILLA_MAESTRAS)
fake = Faker('es_AR')
fake.seed_instance(SEMILLA_MAESTRAS)

def buscar_archivo(opciones):
    """Busca la ubicación de un archivo en db/seed/ o en la raíz."""
    for nombre in opciones:
        ruta1 = os.path.join('db', 'seed', nombre)
        if os.path.exists(ruta1):
            return ruta1
        if os.path.exists(nombre):
            return nombre
    return None

def generar_cuit():
    """Genera un CUIT válido de 11 dígitos numéricos para dominios cuit_dom."""
    prefijo = random.choice(['20', '23', '27', '30'])
    cuerpo = fake.numerify('#########')
    return f"{prefijo}{cuerpo}"

# -----------------------------------------------------------------------------
# 1. CARGA DE CATÁLOGOS FIJOS (CSV)
# -----------------------------------------------------------------------------

def cargar_localidades(cursor):
    ruta = buscar_archivo(['departamentos.csv', 'departamento.csv', 'localidades.csv', 'localidad.csv'])
    if not ruta:
        print("  [!] Omitiendo localidad: No se encontró departamentos.csv")
        return []

    print("  [i] Cargando 'localidad' desde departamentos.csv...")
    codigos_postales = []
    with open(ruta, mode='r', encoding='utf-8') as f:
        reader = csv.reader(f)
        headers = next(reader)
        idx_nom = headers.index('nombre') if 'nombre' in headers else 0
        idx_prov = headers.index('provincia') if 'provincia' in headers else 1

        for i, row in enumerate(reader):
            nombre = row[idx_nom].strip()
            provincia = row[idx_prov].strip() if len(row) > idx_prov else 'Mendoza'
            cod_postal = f"55{i:02d}"
            encargado = fake.name()

            cursor.execute("""
                INSERT INTO localidad (cod_postal, nombre, provincia, encargado_regional)
                VALUES (%s, %s, %s, %s)
                ON CONFLICT (cod_postal) DO NOTHING
            """, (cod_postal, nombre, provincia, encargado))
            codigos_postales.append(cod_postal)

    print(f"  [✓] localidad: {len(codigos_postales)} registros insertados.")
    return codigos_postales

def cargar_cepas(cursor):
    ruta = buscar_archivo(['cepas.csv', 'cepa.csv'])
    if not ruta:
        print("  [!] Omitiendo cepa: No se encontró cepas.csv")
        return []

    print("  [i] Cargando 'cepa' desde cepas.csv...")
    cepas_ids = []
    with open(ruta, mode='r', encoding='utf-8') as f:
        reader = csv.reader(f)
        headers = next(reader)
        for row in reader:
            nombre = row[0].strip()
            tipo = row[1].strip().lower()
            cursor.execute("""
                INSERT INTO cepa (nombre, tipo)
                VALUES (%s, %s)
                ON CONFLICT (nombre) DO NOTHING
                RETURNING id_cepa
            """, (nombre, tipo))
            res = cursor.fetchone()
            if res:
                cepas_ids.append(res[0])
            else:
                cursor.execute("SELECT id_cepa FROM cepa WHERE nombre = %s", (nombre,))
                cepas_ids.append(cursor.fetchone()[0])

    print(f"  [✓] cepa: {len(cepas_ids)} cepas cargadas.")
    return cepas_ids

def cargar_maridajes(cursor):
    ruta = buscar_archivo(['maridajes.csv', 'maridaje.csv'])
    if not ruta:
        print("  [!] Omitiendo maridaje: No se encontró maridajes.csv")
        return []

    print("  [i] Cargando 'maridaje' desde maridajes.csv...")
    maridajes_ids = []
    with open(ruta, mode='r', encoding='utf-8') as f:
        reader = csv.reader(f)
        headers = next(reader)
        for row in reader:
            nombre = row[0].strip()
            temp = int(row[1].strip())
            cursor.execute("""
                INSERT INTO maridaje (nombre, temperatura_servicio)
                VALUES (%s, %s)
                ON CONFLICT (nombre) DO NOTHING
                RETURNING id_maridaje
            """, (nombre, temp))
            res = cursor.fetchone()
            if res:
                maridajes_ids.append(res[0])
            else:
                cursor.execute("SELECT id_maridaje FROM maridaje WHERE nombre = %s", (nombre,))
                maridajes_ids.append(cursor.fetchone()[0])

    print(f"  [✓] maridaje: {len(maridajes_ids)} maridajes cargados.")
    return maridajes_ids

# -----------------------------------------------------------------------------
# 2. GENERACIÓN DINÁMICA CON FAKER (ENTIDADES MAESTRAS)
# -----------------------------------------------------------------------------

def generar_bodegas(cursor, cantidad=10):
    print(f"\nIniciando generación de {cantidad} bodegas...")
    cuits = []
    for _ in range(cantidad):
        cuit = generar_cuit()
        razon_social = f"Bodega {fake.company()}"
        domicilio = fake.address().replace('\n', ', ')
        cursor.execute("""
            INSERT INTO bodega (cuit, razon_social, domicilio)
            VALUES (%s, %s, %s)
            ON CONFLICT (razon_social) DO NOTHING
            RETURNING cuit
        """, (cuit, razon_social, domicilio))
        res = cursor.fetchone()
        if res:
            cuits.append(res[0])
    print(f"  [✓] bodega: {len(cuits)} bodegas insertadas.")
    return cuits

def generar_fincas_y_parcelas(cursor, cepas_ids, cantidad_fincas=12):
    print(f"\nIniciando generación de {cantidad_fincas} fincas y parcelas...")
    fincas_parcelas = []
    departamentos = ['San Rafael', 'General Alvear', 'Malargüe', 'Luján de Cuyo', 'Maipú', 'Tupungato', 'Tunuyán']

    for i in range(cantidad_fincas):
        nombre_finca = f"Finca {fake.last_name()} {i+1}"
        superficie_finca = round(random.uniform(20.0, 150.0), 2)
        depto = random.choice(departamentos)

        cursor.execute("""
            INSERT INTO finca (nombre, superficie_ha, departamento, provincia)
            VALUES (%s, %s, %s, %s)
            ON CONFLICT (nombre) DO NOTHING
            RETURNING id_finca
        """, (nombre_finca, superficie_finca, depto, 'Mendoza'))
        res = cursor.fetchone()
        if not res:
            continue
        id_finca = res[0]

        for nro_parcela in range(1, 4):
            superficie_parc = round(superficie_finca / 4.0, 2)
            anio_plan = random.randint(1995, 2020)
            id_cepa = random.choice(cepas_ids)

            cursor.execute("""
                INSERT INTO parcela (id_finca, nro_parcela, superficie_ha, anio_plantacion, id_cepa)
                VALUES (%s, %s, %s, %s, %s)
            """, (id_finca, nro_parcela, superficie_parc, anio_plan, id_cepa))

            fincas_parcelas.append((id_finca, nro_parcela))

    print(f"  [✓] finca y parcela: {cantidad_fincas} fincas y {len(fincas_parcelas)} parcelas insertadas.")
    return fincas_parcelas

def generar_lotes_y_analisis(cursor, fincas_parcelas, bodegas_cuits):
    print("\nIniciando generación de lotes de uva (5 campañas) y análisis de calidad...")
    campanias = [2022, 2023, 2024, 2025, 2026]
    lotes_count = 0
    analisis_count = 0

    for id_finca, nro_parcela in fincas_parcelas:
        for camp in campanias:
            mes_cosecha = random.choice([2, 3, 4])
            dia_cosecha = random.randint(1, 28)
            fecha_cos = date(camp, mes_cosecha, dia_cosecha)
            kilos = round(random.uniform(4500.0, 22000.0), 2)
            cuit_bod = random.choice(bodegas_cuits)

            cursor.execute("""
                INSERT INTO lote_uva (id_finca, nro_parcela, campania, fecha_cosecha, kilos, cuit_bodega)
                VALUES (%s, %s, %s, %s, %s, %s)
                ON CONFLICT (id_finca, nro_parcela, campania) DO NOTHING
                RETURNING nro_lote
            """, (id_finca, nro_parcela, camp, fecha_cos, kilos, cuit_bod))
            res = cursor.fetchone()
            if not res:
                continue
            nro_lote = res[0]
            lotes_count += 1

            for offset_dias in (0, 2):
                fecha_an = fecha_cos + timedelta(days=offset_dias)
                brix = round(random.uniform(21.0, 26.5), 2)
                ph = round(random.uniform(3.20, 3.85), 2)
                acidez = round(random.uniform(4.50, 7.50), 2)
                cursor.execute("""
                    INSERT INTO analisis_calidad (nro_lote, fecha, grado_brix, ph, acidez_total)
                    VALUES (%s, %s, %s, %s, %s)
                """, (nro_lote, fecha_an, brix, ph, acidez))
                analisis_count += 1

    print(f"  [✓] lote_uva y analisis_calidad: {lotes_count} lotes y {analisis_count} análisis insertados.")

def generar_salas_y_empleados(cursor, codigos_postales, cantidad_salas=6):
    print(f"\nIniciando generación de {cantidad_salas} salas de venta y empleados...")
    dias = ['lunes', 'martes', 'miercoles', 'jueves', 'viernes', 'sabado', 'domingo']
    salas_ids = []

    for _ in range(cantidad_salas):
        calle = fake.street_name()
        numero = random.randint(100, 3500)
        dia_cierre = random.choice(dias)
        cp = random.choice(codigos_postales)

        cursor.execute("""
            INSERT INTO sala_venta (calle, numero, dia_cierre, cod_postal)
            VALUES (%s, %s, %s, %s) RETURNING id_sala
        """, (calle, numero, dia_cierre, cp))
        id_sala = cursor.fetchone()[0]
        salas_ids.append(id_sala)

        for _ in range(3):
            cuit_emp = generar_cuit()
            nombre_emp = fake.name()
            fecha_ing = fake.date_between(start_date='-8y', end_date='today')
            salario = round(random.uniform(700000.0, 1400000.0), 2)

            cursor.execute("""
                INSERT INTO empleado (cuit, nombre, fecha_ingreso, salario, id_sala)
                VALUES (%s, %s, %s, %s, %s)
                ON CONFLICT (cuit) DO NOTHING
            """, (cuit_emp, nombre_emp, fecha_ing, salario, id_sala))

    print(f"  [✓] sala_venta y empleado: {len(salas_ids)} salas y sus empleados insertados.")
    return salas_ids

def generar_transportistas(cursor, codigos_postales, cantidad=5):
    print(f"\nIniciando generación de {cantidad} transportistas y cobertura...")
    trans_ids = []
    for _ in range(cantidad):
        razon_social = f"Transportes {fake.company()}"
        cuit = generar_cuit()
        email = fake.company_email()
        telefono = fake.phone_number()
        domicilio = fake.address().replace('\n', ', ')

        cursor.execute("""
            INSERT INTO transportista (razon_social, cuit, email, telefono, domicilio)
            VALUES (%s, %s, %s, %s, %s)
            ON CONFLICT (razon_social) DO NOTHING
            RETURNING cod_transporte
        """, (razon_social, cuit, email, telefono, domicilio))
        res = cursor.fetchone()
        if res:
            cod_t = res[0]
            trans_ids.append(cod_t)
            for cp in random.sample(codigos_postales, min(3, len(codigos_postales))):
                cursor.execute("""
                    INSERT INTO transportista_localidad (cod_transporte, cod_postal)
                    VALUES (%s, %s) ON CONFLICT DO NOTHING
                """, (cod_t, cp))

    print(f"  [✓] transportista y cobertura: {len(trans_ids)} empresas cargadas.")
    return trans_ids

def generar_vinos(cursor, bodegas_cuits, cepas_ids, maridajes_ids, cantidad=40):
    print(f"\nIniciando generación de {cantidad} vinos, composición, maridajes y auditoría de precios...")
    vinos_ids = []
    varietales = ["Malbec", "Cabernet Sauvignon", "Chardonnay", "Torrontés", "Bonarda", "Syrah", "Merlot", "Pinot Noir"]
    lineas = ["Gran Reserva", "Reserva", "Estate", "Single Vineyard", "Especial"]
    volumenes = [375, 750, 1500]
    tipos = ['tinto', 'blanco', 'rosado', 'espumante']

    wines_set = set()

    for i in range(cantidad):
        nombre = f"Vino {random.choice(lineas)} {random.choice(varietales)} Nro {i+1}"
        tipo = random.choice(tipos)
        anada = random.randint(2018, 2024)
        volumen = random.choice(volumenes)

        key = (nombre, anada, volumen)
        if key in wines_set:
            continue
        wines_set.add(key)

        graduacion = round(random.uniform(11.5, 15.0), 2)
        precio_inicial = round(random.uniform(3000.0, 24000.0), 2)
        precio_actual = round(precio_inicial * 1.15, 2)
        cuit_bod = random.choice(bodegas_cuits)

        cursor.execute("""
            INSERT INTO vino (nombre, tipo, anada, volumen_ml, graduacion, precio, cuit_bodega)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
            RETURNING cod_vino
        """, (nombre, tipo, anada, volumen, graduacion, precio_actual, cuit_bod))
        cod_vino = cursor.fetchone()[0]
        vinos_ids.append(cod_vino)

        # Registro de historial en auditoria_precio (RN-13)
        cursor.execute("""
            INSERT INTO auditoria_precio (cod_vino, precio_anterior, precio_nuevo)
            VALUES (%s, %s, %s)
        """, (cod_vino, precio_inicial, precio_actual))

        # RN-05: La composición de cepas debe sumar exactamente 100.00%
        cepas_seleccionadas = random.sample(cepas_ids, k=random.choice([1, 2]))
        if len(cepas_seleccionadas) == 1:
            cursor.execute("""
                INSERT INTO composicion_vino (cod_vino, id_cepa, porcentaje)
                VALUES (%s, %s, %s)
            """, (cod_vino, cepas_seleccionadas[0], 100.00))
        else:
            p1 = round(random.uniform(55.0, 80.0), 2)
            p2 = round(100.00 - p1, 2)
            cursor.execute("INSERT INTO composicion_vino (cod_vino, id_cepa, porcentaje) VALUES (%s, %s, %s)", (cod_vino, cepas_seleccionadas[0], p1))
            cursor.execute("INSERT INTO composicion_vino (cod_vino, id_cepa, porcentaje) VALUES (%s, %s, %s)", (cod_vino, cepas_seleccionadas[1], p2))

        if maridajes_ids:
            maridaje_sel = random.choice(maridajes_ids)
            cursor.execute("""
                INSERT INTO vino_maridaje (cod_vino, id_maridaje)
                VALUES (%s, %s) ON CONFLICT DO NOTHING
            """, (cod_vino, maridaje_sel))

    print(f"  [✓] vino, composición, maridaje y auditoria_precio: {len(vinos_ids)} vinos generados.")
    return vinos_ids

def generar_clientes(cursor, codigos_postales, cantidad=1000):
    print(f"\nIniciando generación de {cantidad} clientes, subtipos y permisos de exportación...")
    habilitaciones_usadas = set()
    permisos_count = 0

    for i in range(cantidad):
        tipo = ['socio', 'distribuidor', 'exportador'][i % 3]
        desc = 10.00 if tipo == 'socio' else (20.00 if tipo == 'distribuidor' else 30.00)

        nombre = fake.company()
        cuit = generar_cuit()
        direccion = fake.address().replace('\n', ', ')
        cp = random.choice(codigos_postales)
        fecha_alta = fake.date_between(start_date=date(2020, 1, 1), end_date=date(2021, 12, 31))

        cursor.execute("""
            INSERT INTO cliente (nombre_razon_social, tipo_documento, nro_documento, direccion, cod_postal, fecha_alta, tipo_cliente, porcentaje_descuento)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s) RETURNING id_cliente
        """, (nombre, 'CUIT', cuit, direccion, cp, fecha_alta, tipo, desc))

        id_cliente = cursor.fetchone()[0]

        if tipo == 'socio':
            cursor.execute("INSERT INTO cliente_socio (id_cliente) VALUES (%s)", (id_cliente,))
        elif tipo == 'distribuidor':
            while True:
                hab = fake.bothify(text='HAB-######')
                if hab not in habilitaciones_usadas:
                    habilitaciones_usadas.add(hab)
                    break
            cursor.execute("""
                INSERT INTO cliente_distribuidor (id_cliente, zona_cobertura, nro_habilitacion)
                VALUES (%s, %s, %s)
            """, (id_cliente, fake.city(), hab))
        elif tipo == 'exportador':
            cursor.execute("""
                INSERT INTO cliente_exportador (id_cliente, pais_destino)
                VALUES (%s, %s)
            """, (id_cliente, fake.country()))
            # RN-07: Permiso de exportación con fecha_vencimiento > fecha_emision
            permisos_count += 1
            cod_perm = f"PERM-EXP-{id_cliente:05d}-01"
            f_emi = date(2025, 1, 15)
            f_ven = date(2027, 1, 15)
            cursor.execute("""
                INSERT INTO permiso_exportacion (cod_permiso, id_cliente, fecha_emision, fecha_vencimiento)
                VALUES (%s, %s, %s, %s)
                ON CONFLICT (cod_permiso) DO NOTHING
            """, (cod_perm, id_cliente, f_emi, f_ven))

    print(f"  [✓] cliente, subtipos y permiso_exportacion ({permisos_count} permisos): {cantidad} clientes generados.")

# -----------------------------------------------------------------------------
# FLUJO PRINCIPAL
# -----------------------------------------------------------------------------

def main():
    try:
        print("Conectando a PostgreSQL...")
        conn = psycopg.connect(
            dbname=os.getenv('POSTGRES_DB', 'bodegas_atuel'),
            user=os.getenv('POSTGRES_USER', 'admin_atuel'),
            password=os.getenv('POSTGRES_PASSWORD', 'cambiar_en_local'),
            host=os.getenv('POSTGRES_HOST', 'localhost'),
            port=os.getenv('POSTGRES_PORT', '5432')
        )
        cursor = conn.cursor()

        ruta_pre = buscar_archivo(["01_preparar_motor_pre_carga.sql"])
        if ruta_pre:
            print("\nEjecutando script pre-carga (desactivación de triggers)...")
            with open(ruta_pre, "r", encoding="utf-8") as f:
                cursor.execute(f.read())
            conn.commit()

        print("\n--- 1. CARGA DE CATÁLOGOS CSV ---")
        cps = cargar_localidades(cursor)
        cepas = cargar_cepas(cursor)
        maridajes = cargar_maridajes(cursor)

        print("\n--- 2. GENERACIÓN DE ENTIDADES MAESTRAS ---")
        bodegas = generar_bodegas(cursor, 10)
        fincas_parcelas = generar_fincas_y_parcelas(cursor, cepas, 12)
        generar_lotes_y_analisis(cursor, fincas_parcelas, bodegas)
        generar_salas_y_empleados(cursor, cps, 6)
        generar_transportistas(cursor, cps, 5)
        generar_vinos(cursor, bodegas, cepas, maridajes, 40)
        generar_clientes(cursor, cps, 1000)

        conn.commit()
        print("\n¡Carga de las 21 tablas maestras/catálogo completada con éxito!")
        print("El script transaccional ya puede ejecutarse.")

    except Exception as e:
        if 'conn' in locals():
            conn.rollback()
        print(f"\n[X] Error durante la carga masiva. Transacción revertida (ROLLBACK).\nDetalle: {e}")
    finally:
        if 'cursor' in locals(): cursor.close()
        if 'conn' in locals(): conn.close()

if __name__ == '__main__':
    main()
