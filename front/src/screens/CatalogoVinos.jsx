import React, { useState, useEffect, useCallback } from 'react';
import { api } from '../services/api';
import { ErrorAlert } from '../components/ErrorAlert';

/**
 * Pantalla 1: Catálogo de Vinos (Asignada a Onza)
 * Listado paginado con filtros por tipo, cepa, bodega y añada; detalle con composición y maridajes.
 */
export function CatalogoVinos() {
  const [vinos, setVinos] = useState([]);
  const [total, setTotal] = useState(0);
  const [limit] = useState(10);
  const [offset, setOffset] = useState(0);

  // Inputs del formulario de filtros
  const [tipo, setTipo] = useState('');
  const [bodega, setBodega] = useState('');
  const [anada, setAnada] = useState('');
  const [cepa, setCepa] = useState('');

  // Filtros efectivamente aplicados a la consulta (evita disparar peticiones inválidas mientras se tipea el año)
  const [filtrosAplicados, setFiltrosAplicados] = useState({
    tipo: '',
    bodega: '',
    anada: undefined,
    cepa: '',
  });

  // Detalle
  const [vinoSeleccionado, setVinoSeleccionado] = useState(null);
  const [loadingDetalle, setLoadingDetalle] = useState(false);

  // Estados UI
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);

  const cargarVinos = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await api.getVinos({
        limit,
        offset,
        tipo: filtrosAplicados.tipo || undefined,
        bodega: filtrosAplicados.bodega || undefined,
        anada: filtrosAplicados.anada,
        cepa: filtrosAplicados.cepa || undefined,
      });
      setVinos(data.items || []);
      setTotal(data.total || 0);
    } catch (err) {
      setError(err);
    } finally {
      setLoading(false);
    }
  }, [limit, offset, filtrosAplicados]);

  useEffect(() => {
    cargarVinos();
  }, [cargarVinos]);

  const verDetalle = async (codVino) => {
    setLoadingDetalle(true);
    setError(null);
    try {
      const detalle = await api.getVino(codVino);
      setVinoSeleccionado(detalle);
    } catch (err) {
      setError(err);
    } finally {
      setLoadingDetalle(false);
    }
  };

  const handleBuscar = (e) => {
    e.preventDefault();
    const anadaTrim = String(anada).trim();
    let anadaNum = undefined;
    if (anadaTrim !== '') {
      anadaNum = parseInt(anadaTrim, 10);
      if (Number.isNaN(anadaNum) || anadaNum < 1990 || anadaNum > 2100) {
        setError({
          message: 'La añada debe ser un año válido entre 1990 y 2100.',
          status: 422,
        });
        return;
      }
    }
    setOffset(0);
    setFiltrosAplicados({
      tipo,
      bodega: bodega.trim(),
      anada: anadaNum,
      cepa: cepa.trim(),
    });
  };

  const limpiarFiltros = () => {
    setTipo('');
    setBodega('');
    setAnada('');
    setCepa('');
    setError(null);
    setOffset(0);
    setFiltrosAplicados({
      tipo: '',
      bodega: '',
      anada: undefined,
      cepa: '',
    });
  };

  return (
    <div className="screen-container">
      <div className="screen-header">
        <h2>🍷 Catálogo de Vinos</h2>
        <span className="screen-badge">Total registrados: {total}</span>
      </div>

      <ErrorAlert error={error} onClose={() => setError(null)} />

      {/* Barra de Filtros */}
      <form className="filters-card" onSubmit={handleBuscar}>
        <div className="filter-group">
          <label>Tipo de Vino</label>
          <select
            value={tipo}
            onChange={(e) => {
              const nuevoTipo = e.target.value;
              setTipo(nuevoTipo);
              setOffset(0);
              setFiltrosAplicados((prev) => ({ ...prev, tipo: nuevoTipo }));
            }}
          >
            <option value="">Todos los tipos</option>
            <option value="tinto">Tinto</option>
            <option value="blanco">Blanco</option>
            <option value="rosado">Rosado</option>
            <option value="espumante">Espumante</option>
          </select>
        </div>

        <div className="filter-group">
          <label>Bodega (Nombre o CUIT)</label>
          <input
            type="text"
            placeholder="Ej: Catena, 30..."
            value={bodega}
            onChange={(e) => setBodega(e.target.value)}
          />
        </div>

        <div className="filter-group">
          <label>Cepa</label>
          <input
            type="text"
            placeholder="Ej: Malbec, Cabernet..."
            value={cepa}
            onChange={(e) => setCepa(e.target.value)}
          />
        </div>

        <div className="filter-group">
          <label>Añada</label>
          <input
            type="number"
            min="1990"
            max="2100"
            placeholder="Ej: 2024"
            value={anada}
            onChange={(e) => setAnada(e.target.value)}
          />
        </div>

        <div className="filter-actions">
          <button type="submit" className="btn-primary">Filtrar</button>
          <button type="button" className="btn-secondary" onClick={limpiarFiltros}>Limpiar</button>
        </div>
      </form>

      {/* Listado de Vinos */}
      {loading ? (
        <div className="loading-state">Cargando catálogo desde la base de datos...</div>
      ) : vinos.length === 0 ? (
        <div className="empty-state">No se encontraron vinos con los filtros especificados.</div>
      ) : (
        <div className="table-wrapper">
          <table className="data-table">
            <thead>
              <tr>
                <th>Código</th>
                <th>Nombre</th>
                <th>Tipo</th>
                <th>Añada</th>
                <th>Volumen</th>
                <th>Graduación</th>
                <th>Precio Unitario</th>
                <th>Bodega</th>
                <th>Acciones</th>
              </tr>
            </thead>
            <tbody>
              {vinos.map((v) => (
                <tr key={v.cod_vino}>
                  <td><strong>#{v.cod_vino}</strong></td>
                  <td>{v.nombre}</td>
                  <td><span className={`tag-tipo ${v.tipo}`}>{v.tipo}</span></td>
                  <td>{v.anada}</td>
                  <td>{v.volumen_ml} ml</td>
                  <td>{v.graduacion}°</td>
                  <td><strong>${Number(v.precio).toFixed(2)}</strong></td>
                  <td>{v.bodega_razon_social || v.cuit_bodega}</td>
                  <td>
                    <button className="btn-sm" onClick={() => verDetalle(v.cod_vino)}>
                      Ver Detalle
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {/* Paginación */}
      <div className="pagination-bar">
        <span>Mostrando {vinos.length > 0 ? offset + 1 : 0} - {Math.min(offset + limit, total)} de {total} vinos</span>
        <div className="pagination-buttons">
          <button
            className="btn-secondary"
            disabled={offset === 0}
            onClick={() => setOffset((prev) => Math.max(0, prev - limit))}
          >
            ◀ Anterior
          </button>
          <button
            className="btn-secondary"
            disabled={offset + limit >= total}
            onClick={() => setOffset((prev) => prev + limit)}
          >
            Siguiente ▶
          </button>
        </div>
      </div>

      {/* Modal de Detalle con Composición Varietal y Maridajes */}
      {vinoSeleccionado && (
        <div className="modal-backdrop" onClick={() => setVinoSeleccionado(null)}>
          <div className="modal-content" onClick={(e) => e.stopPropagation()}>
            <div className="modal-header">
              <h3>🍷 {vinoSeleccionado.nombre} ({vinoSeleccionado.anada})</h3>
              <button className="btn-close" onClick={() => setVinoSeleccionado(null)}>✕</button>
            </div>
            <div className="modal-body">
              <p><strong>Tipo:</strong> {vinoSeleccionado.tipo} | <strong>Graduación:</strong> {vinoSeleccionado.graduacion}° | <strong>Volumen:</strong> {vinoSeleccionado.volumen_ml} ml</p>
              <p><strong>Precio Oficial:</strong> ${Number(vinoSeleccionado.precio).toFixed(2)}</p>
              <p><strong>Bodega:</strong> {vinoSeleccionado.bodega_razon_social} (CUIT: {vinoSeleccionado.cuit_bodega})</p>

              <h4>🍇 Composición de Corte (Corte Varietal)</h4>
              {vinoSeleccionado.composicion && vinoSeleccionado.composicion.length > 0 ? (
                <ul className="composition-list">
                  {vinoSeleccionado.composicion.map((c) => (
                    <li key={c.id_cepa} className="composition-item">
                      <span><strong>{c.nombre_cepa}</strong> ({c.tipo_cepa})</span>
                      <span className="badge-percentage">{c.porcentaje}%</span>
                    </li>
                  ))}
                </ul>
              ) : (
                <p className="text-muted">Sin corte detallado registrado.</p>
              )}

              <h4>🧀 Maridajes Recomendados</h4>
              {vinoSeleccionado.maridajes && vinoSeleccionado.maridajes.length > 0 ? (
                <div className="tags-container">
                  {vinoSeleccionado.maridajes.map((m) => (
                    <span key={m.id_maridaje} className="tag-maridaje">
                      {m.nombre} ({m.temperatura_servicio}°C)
                    </span>
                  ))}
                </div>
              ) : (
                <p className="text-muted">No posee maridajes cargados.</p>
              )}
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

