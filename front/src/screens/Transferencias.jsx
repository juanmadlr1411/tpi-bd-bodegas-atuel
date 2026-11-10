import React, { useEffect, useState } from 'react';
import { api } from '../services/api';
import { ErrorAlert } from '../components/ErrorAlert';

const SALAS_BASE = [
  { id_sala: 1, descripcion: 'Sala #1 — Destino Principal' },
  { id_sala: 2, descripcion: 'Sala #2 — Sucursal Regional' },
  { id_sala: 3, descripcion: 'Sala #3 — Punto de Venta' },
];

const ESTILOS_BADGE_ESTADO = {
  en_confeccion: {
    label: 'EN CONFECCIÓN',
    backgroundColor: '#fef3c7',
    color: '#92400e',
    border: '1px solid #f59e0b',
  },
  terminado: {
    label: 'TERMINADO',
    backgroundColor: '#dbeafe',
    color: '#1e40af',
    border: '1px solid #3b82f6',
  },
  procesado: {
    label: 'PROCESADO',
    backgroundColor: '#d1fae5',
    color: '#065f46',
    border: '1px solid #10b981',
  },
};

async function cargarTodosVinos() {
  const limit = 100;
  let offset = 0;
  let total = 0;
  const acumulado = [];

  do {
    const data = await api.getVinos({ limit, offset });
    const items = Array.isArray(data) ? data : data.items || [];
    acumulado.push(...items);
    total = Array.isArray(data) ? items.length : data.total || 0;
    offset += limit;
    if (items.length === 0) break;
  } while (offset < total);

  return acumulado;
}

/**
 * Pantalla 4: Transferencias de Stock y Control Visual de Estados (RN-11 / RN-12)
 * Circuito: en_confeccion (amarillo) -> terminado (azul) -> procesado (verde, invoca sp_procesar_transferencia).
 */
export function Transferencias() {
  const [vinos, setVinos] = useState([]);
  const [salas, setSalas] = useState(SALAS_BASE);
  const [loadingCatalogos, setLoadingCatalogos] = useState(true);

  // Estado para crear borrador o buscar transferencia existente
  const [idSala, setIdSala] = useState('1');
  const [nroBusqueda, setNroBusqueda] = useState('');

  // Documento activo de transferencia
  const [transferencia, setTransferencia] = useState(null);

  // Formulario de renglón
  const [codVino, setCodVino] = useState('');
  const [cantidad, setCantidad] = useState(1);

  // Estados de UI y mensajes
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [successMsg, setSuccessMsg] = useState(null);

  useEffect(() => {
    let activo = true;

    Promise.all([
      cargarTodosVinos(),
      api.getSalas().catch(() => null),
    ])
      .then(([vinosData, salasData]) => {
        if (!activo) return;
        setVinos(vinosData);
        if (Array.isArray(salasData) && salasData.length > 0) {
          setSalas(salasData);
        }
      })
      .catch((err) => {
        if (activo) setError(err);
      })
      .finally(() => {
        if (activo) setLoadingCatalogos(false);
      });

    return () => {
      activo = false;
    };
  }, []);

  const estadoActual = transferencia?.estado || null;
  const renglones = transferencia?.renglones || [];
  const esEnConfeccion = estadoActual === 'en_confeccion';
  const esTerminado = estadoActual === 'terminado';
  const esProcesado = estadoActual === 'procesado';

  // Condiciones de habilitación dinámica según máquina de estados (RN-11 y RN-12)
  const puedeAgregarRenglones = Boolean(transferencia && esEnConfeccion && !loading);
  const puedeTerminar = Boolean(transferencia && esEnConfeccion && renglones.length >= 1 && !loading);
  const puedeProcesar = Boolean(transferencia && esTerminado && !loading);

  // 1. Crear Borrador (POST /transferencias)
  const handleCrearBorrador = async (e) => {
    e.preventDefault();
    setLoading(true);
    setError(null);
    setSuccessMsg(null);

    try {
      const creada = await api.crearTransferencia({ id_sala: parseInt(idSala, 10) });
      setTransferencia({
        ...creada,
        renglones: creada.renglones || [],
      });
      setCodVino('');
      setCantidad(1);
      setSuccessMsg(
        `Borrador de transferencia #${creada.nro_transferencia} creado en estado "en_confeccion" para la Sala #${creada.id_sala}.`
      );
    } catch (err) {
      setError(err);
    } finally {
      setLoading(false);
    }
  };

  // Cargar transferencia existente por número
  const handleBuscarTransferencia = async (e) => {
    e.preventDefault();
    if (!nroBusqueda) return;
    setLoading(true);
    setError(null);
    setSuccessMsg(null);

    try {
      const encontrada = await api.getTransferencia(parseInt(nroBusqueda, 10));
      setTransferencia(encontrada);
      setIdSala(String(encontrada.id_sala));
      setSuccessMsg(`Transferencia #${encontrada.nro_transferencia} cargada correctamente.`);
    } catch (err) {
      setError(err);
    } finally {
      setLoading(false);
    }
  };

  // 2. Agregar Renglón (POST /transferencias/{nro}/renglones)
  const handleAgregarRenglon = async (e) => {
    e.preventDefault();
    if (!transferencia) return;

    const codigo = parseInt(codVino, 10);
    const cant = parseInt(cantidad, 10);
    if (!codigo || !Number.isInteger(cant) || cant < 1) return;

    setLoading(true);
    setError(null);
    setSuccessMsg(null);

    try {
      await api.agregarRenglonTransferencia(transferencia.nro_transferencia, {
        cod_vino: codigo,
        cantidad: cant,
      });
      const actualizada = await api.getTransferencia(transferencia.nro_transferencia);
      setTransferencia(actualizada);
      setCodVino('');
      setCantidad(1);
      setSuccessMsg(`Se agregaron ${cant} botella(s) del vino #${codigo} a la transferencia #${transferencia.nro_transferencia}.`);
    } catch (err) {
      setError(err);
    } finally {
      setLoading(false);
    }
  };

  // 3. Terminar Confección (POST /transferencias/{nro}/terminar)
  const handleTerminar = async () => {
    if (!transferencia) return;
    setLoading(true);
    setError(null);
    setSuccessMsg(null);

    try {
      const actualizada = await api.terminarTransferencia(transferencia.nro_transferencia);
      setTransferencia(actualizada);
      setSuccessMsg(
        `Transferencia #${transferencia.nro_transferencia} marcada como "terminado". La edición de renglones ha quedado bloqueada (RN-12).`
      );
    } catch (err) {
      setError(err);
    } finally {
      setLoading(false);
    }
  };

  // 4. Procesar Transferencia (POST /transferencias/{nro}/procesar -> CALL sp_procesar_transferencia)
  const handleProcesar = async () => {
    if (!transferencia) return;
    setLoading(true);
    setError(null);
    setSuccessMsg(null);

    try {
      const procesada = await api.procesarTransferencia(transferencia.nro_transferencia);
      setTransferencia(procesada);
      setSuccessMsg(
        `¡Transferencia #${transferencia.nro_transferencia} procesada exitosamente mediante sp_procesar_transferencia! Se descontó el stock del depósito central y se acreditó en la Sala #${procesada.id_sala}.`
      );
    } catch (err) {
      // Captura el error de PostgreSQL (falta de stock en depósito o transición inválida RN-11)
      setError(err);
    } finally {
      setLoading(false);
    }
  };

  const renderBadgeEstado = (estado) => {
    const cfg = ESTILOS_BADGE_ESTADO[estado] || {
      label: estado,
      backgroundColor: '#e5e7eb',
      color: '#374151',
      border: '1px solid #9ca3af',
    };

    return (
      <span
        className={`badge-estado estado-${estado}`}
        style={{
          display: 'inline-block',
          padding: '0.35rem 0.85rem',
          borderRadius: '9999px',
          fontWeight: 700,
          fontSize: '0.85rem',
          letterSpacing: '0.03em',
          backgroundColor: cfg.backgroundColor,
          color: cfg.color,
          border: cfg.border,
        }}
      >
        ● {cfg.label}
      </span>
    );
  };

  const totalBotellas = renglones.reduce((acc, r) => acc + Number(r.cantidad || 0), 0);

  return (
    <div className="screen-container">
      <div className="screen-header">
        <h2>🚚 Transferencias de Stock a Salas de Venta</h2>
        <span className="screen-badge">Ciclo de vida: en_confeccion → terminado → procesado (RN-11 / RN-12)</span>
      </div>

      {/* 5. Alerta de Errores de Base de Datos / Reglas de Negocio */}
      <ErrorAlert error={error} onClose={() => setError(null)} />

      {successMsg && (
        <div className="success-banner">
          <span>✅</span>
          <p>{successMsg}</p>
        </div>
      )}

      {/* Panel 1: Crear nuevo borrador o cargar transferencia existente */}
      <div className="form-card" style={{ marginBottom: '1.25rem' }}>
        <div className="corte-header" style={{ marginBottom: '0.75rem' }}>
          <h4>1️⃣ Iniciar Nueva Transferencia o Consultar Existente</h4>
        </div>

        <div className="form-grid">
          <form onSubmit={handleCrearBorrador} style={{ display: 'flex', gap: '0.75rem', alignItems: 'flex-end', flexWrap: 'wrap' }}>
            <div className="form-field" style={{ flex: '1 1 220px' }}>
              <label htmlFor="select-sala-destino">Sala de Destino *</label>
              <select
                id="select-sala-destino"
                value={idSala}
                onChange={(e) => setIdSala(e.target.value)}
                disabled={loading}
              >
                {salas.slice(0, 3).map((s) => (
                  <option key={s.id_sala} value={s.id_sala}>
                    {s.calle
                      ? `Sala #${s.id_sala} — ${s.calle} ${s.numero} (${s.localidad_nombre || 'Mendoza'})`
                      : s.descripcion || `Sala #${s.id_sala}`}
                  </option>
                ))}
              </select>
            </div>

            <button type="submit" className="btn-primary" disabled={loading}>
              📝 Crear Borrador
            </button>
          </form>

          <form onSubmit={handleBuscarTransferencia} style={{ display: 'flex', gap: '0.75rem', alignItems: 'flex-end', flexWrap: 'wrap' }}>
            <div className="form-field" style={{ flex: '1 1 160px' }}>
              <label htmlFor="input-buscar-nro">Buscar N° Transferencia</label>
              <input
                id="input-buscar-nro"
                type="number"
                min="1"
                placeholder="Ej: 5001"
                value={nroBusqueda}
                onChange={(e) => setNroBusqueda(e.target.value)}
                disabled={loading}
              />
            </div>

            <button type="submit" className="btn-secondary" disabled={loading || !nroBusqueda}>
              🔍 Cargar
            </button>
          </form>
        </div>
      </div>

      {/* Panel 2: Documento Activo, Renglones y Botones de Transición de Estado */}
      {transferencia && (
        <div className="form-card">
          <div
            className="comprobante-header"
            style={{
              display: 'flex',
              justifyContent: 'space-between',
              alignItems: 'center',
              flexWrap: 'wrap',
              gap: '1rem',
              paddingBottom: '1rem',
              marginBottom: '1rem',
              borderBottom: '1px solid #e5e7eb',
            }}
          >
            <div>
              <h3 style={{ margin: 0 }}>
                📦 Transferencia #{transferencia.nro_transferencia} — Sala Destino #{transferencia.id_sala}
              </h3>
              <p className="text-muted" style={{ margin: '0.25rem 0 0 0' }}>
                Fecha de confección: <strong>{transferencia.fecha_confeccion}</strong> · Renglones: <strong>{renglones.length}</strong> · Total botellas: <strong>{totalBotellas}</strong>
              </p>
            </div>

            <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem' }}>
              <span>Estado actual:</span>
              {renderBadgeEstado(transferencia.estado)}
            </div>
          </div>

          {/* 2. Carga de Renglones (Solo habilitado si está en_confeccion) */}
          <div className="corte-section" style={{ marginBottom: '1.25rem' }}>
            <div className="corte-header">
              <h4>2️⃣ Carga de Renglones de Vino (RN-12: Solo editable en confección)</h4>
              {!esEnConfeccion && (
                <span className="screen-badge">
                  🔒 Edición bloqueada (estado: {transferencia.estado})
                </span>
              )}
            </div>

            <form
              onSubmit={handleAgregarRenglon}
              className="venta-renglon-form"
              style={{ display: 'flex', gap: '0.75rem', alignItems: 'flex-end', flexWrap: 'wrap', marginTop: '0.75rem' }}
            >
              <div className="form-field venta-vino-field" style={{ flex: '2 1 260px' }}>
                <label htmlFor="transf-vino">Vino del Catálogo *</label>
                <select
                  id="transf-vino"
                  value={codVino}
                  onChange={(e) => setCodVino(e.target.value)}
                  disabled={!puedeAgregarRenglones || loadingCatalogos}
                  required
                >
                  <option value="">Seleccionar vino del catálogo...</option>
                  {vinos.map((v) => (
                    <option key={v.cod_vino} value={v.cod_vino}>
                      #{v.cod_vino} — {v.nombre} ({v.anada}) · {v.tipo} · {v.volumen_ml} ml
                    </option>
                  ))}
                </select>
              </div>

              <div className="form-field venta-cantidad-field" style={{ flex: '0 1 140px' }}>
                <label htmlFor="transf-cantidad">Cantidad Botellas *</label>
                <input
                  id="transf-cantidad"
                  type="number"
                  min="1"
                  step="1"
                  required
                  value={cantidad}
                  onChange={(e) => setCantidad(e.target.value)}
                  disabled={!puedeAgregarRenglones}
                />
              </div>

              <button
                type="submit"
                className="btn-secondary"
                disabled={!puedeAgregarRenglones || !codVino}
              >
                ➕ Agregar Renglón
              </button>
            </form>
          </div>

          {/* Tabla de Renglones Cargados */}
          <div className="cart-section" style={{ marginBottom: '1.5rem' }}>
            <div className="corte-header">
              <h4>📋 Renglones Cargados en la Transferencia #{transferencia.nro_transferencia}</h4>
              <span className="screen-badge">{renglones.length} renglón(es) · {totalBotellas} botella(s)</span>
            </div>

            {renglones.length === 0 ? (
              <div className="empty-state">
                Aún no se cargaron renglones. Agregá al menos un vino para poder terminar la confección.
              </div>
            ) : (
              <div className="table-wrapper">
                <table className="data-table">
                  <thead>
                    <tr>
                      <th>Código Vino</th>
                      <th>Nombre del Vino</th>
                      <th>Cantidad Solicitada (Botellas)</th>
                    </tr>
                  </thead>
                  <tbody>
                    {renglones.map((r) => (
                      <tr key={r.cod_vino}>
                        <td><strong>#{r.cod_vino}</strong></td>
                        <td>{r.nombre_vino || `Vino #${r.cod_vino}`}</td>
                        <td><strong>{r.cantidad}</strong></td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </div>

          {/* 3 y 4. Botonera de Transición de Estados */}
          <div
            className="corte-section"
            style={{
              display: 'flex',
              justifyContent: 'space-between',
              alignItems: 'center',
              flexWrap: 'wrap',
              gap: '1rem',
              paddingTop: '1rem',
              borderTop: '1px solid #e5e7eb',
            }}
          >
            <div style={{ display: 'flex', gap: '0.75rem', flexWrap: 'wrap' }}>
              <button
                type="button"
                className="btn-secondary"
                disabled={!puedeTerminar}
                onClick={handleTerminar}
                title="Pasa el documento de en_confeccion a terminado y bloquea sus renglones"
              >
                📘 Terminar Confección
              </button>

              <button
                type="button"
                className="btn-primary"
                disabled={!puedeProcesar}
                onClick={handleProcesar}
                title="Invoca CALL sp_procesar_transferencia en PostgreSQL (solo habilitado en estado terminado)"
              >
                ⚙️ Procesar Transferencia (SP)
              </button>
            </div>

            {/* Botón auxiliar para demostrar ante la cátedra el disparo de RN-11 si se intenta procesar en_confeccion */}
            {esEnConfeccion && (
              <button
                type="button"
                className="btn-danger btn-sm"
                disabled={loading}
                onClick={handleProcesar}
                title="Fuerza la llamada a /procesar estando en_confeccion para verificar el rechazo 409 P0001 de la BD"
              >
                🧪 Probar Violación RN-11 (Procesar sin terminar)
              </button>
            )}

            {esProcesado && (
              <span style={{ color: '#065f46', fontWeight: 600 }}>
                🔒 Documento finalizado e inmutable (Stock impactado en Depósito Central y Sala #{transferencia.id_sala}).
              </span>
            )}
          </div>
        </div>
      )}
    </div>
  );
}

export default Transferencias;
