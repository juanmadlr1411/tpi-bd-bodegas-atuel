#!/usr/bin/env bash
# =============================================================================
# TPI BASES DE DATOS - UTN FRSR (2026)
# Archivo: db/seed/generar_dump.sh (Etapa 3 - H3: Volcado Completo)
# Responsable: Gonzalo
# Uso: bash db/seed/generar_dump.sh
# =============================================================================

set -e

CONTAINER_NAME="${DB_CONTAINER:-bodegas_atuel_db}"
DB_USER="${POSTGRES_USER:-admin_atuel}"
DB_NAME="${POSTGRES_DB:-bodegas_atuel}"
OUTPUT_FILE="db/seed/dump_completo.sql.gz"

echo "[1/2] Generando backup completo comprimido desde ${CONTAINER_NAME}..."
docker exec -i "${CONTAINER_NAME}" pg_dump -U "${DB_USER}" -d "${DB_NAME}" --clean --if-exists --no-owner --no-privileges | gzip -9 > "${OUTPUT_FILE}"

echo "[2/2] Backup generado exitosamente en: ${OUTPUT_FILE}"
ls -lh "${OUTPUT_FILE}"