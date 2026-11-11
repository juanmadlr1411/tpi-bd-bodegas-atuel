import React, { useState } from 'react';
import { api } from '../services/api';
import { ErrorAlert } from '../components/ErrorAlert';

/**
 * Pantalla 2: Alta y Edición de Vino (Responsable: Gonzalo)
 * Formulario que incluye la composición de cepas; DEBE mostrar el error devuelto
 * por la base de datos cuando los porcentajes no suman 100% (RN-05).
 */
export function AltaVino({ onVinoCreado }) {
  const [formData, setFormData] = useState({
    nombre: '',
    tipo: 'tinto',
    anada: 2024,
    volumen_ml: 750,
    graduacion: 14.0,
    precio: '',
    cuit_bodega: '30708090123',
  });

  const [composicion, setComposicion] = useState([
    { id_cepa: 1, porcentaje: 70 },
    { id_cepa: 2, porcentaje: 30 },
  ]);

  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [successMsg, setSuccessMsg] = useState(null);

  const sumaPorcentajes = composicion.reduce((acc, c) => acc + (parseFloat(c.porcentaje) || 0), 0);

  const handleInputChange = (e) => {
    const { name, value } = e.target;
    setFormData((prev) => ({ ...prev, [name]: value }));
  };

  const handleCompChange = (index, field, value) => {
    setComposicion((prev) => {
      const next = [...prev];
      next[index] = { ...next[index], [field]: parseFloat(value) || value };
      return next;
    });
  };

  const agregarRenglonCepa = () => {
    setComposicion((prev) => [...prev, { id_cepa: 1, porcentaje: 0 }]);
  };

  const quitarRenglonCepa = (index) => {
    setComposicion((prev) => prev.filter((_, i) => i !== index));
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    setLoading(true);
    setError(null);
    setSuccessMsg(null);

    const payload = {
      nombre: formData.nombre,
      tipo: formData.tipo,
      anada: parseInt(formData.anada, 10),
      volumen_ml: parseInt(formData.volumen_ml, 10),
      graduacion: parseFloat(formData.graduacion),
      precio: parseFloat(formData.precio),
      cuit_bodega: formData.cuit_bodega,
      composicion: composicion.map((c) => ({
        id_cepa: parseInt(c.id_cepa, 10),
        porcentaje: parseFloat(c.porcentaje),
      })),
      maridajes: [],
    };

    try {
      const vinoCreado = await api.crearVino(payload);
      setSuccessMsg(`¡Vino "${vinoCreado.nombre}" creado exitosamente con código #${vinoCreado.cod_vino}!`);
      setFormData({
        nombre: '',
        tipo: 'tinto',
        anada: 2024,
        volumen_ml: 750,
        graduacion: 14.0,
        precio: '',
        cuit_bodega: '30708090123',
      });
      if (onVinoCreado) onVinoCreado(vinoCreado);
    } catch (err) {
      // Captura y muestra directamente el error de PostgreSQL (RN-05 corte != 100%, etc.)
      setError(err);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="screen-container">
      <div className="screen-header">
        <h2>➕ Alta de Nuevo Vino con Composición de Corte</h2>
      </div>

      <ErrorAlert error={error} onClose={() => setError(null)} />

      {successMsg && (
        <div className="success-banner">
          <span>✅</span>
          <p>{successMsg}</p>
        </div>
      )}

      <form className="form-card" onSubmit={handleSubmit}>
        <div className="form-grid">
          <div className="form-field full-width">
            <label>Nombre Comercial del Vino *</label>
            <input
              type="text"
              name="nombre"
              required
              placeholder="Ej: Gran Reserva Atuel Malbec"
              value={formData.nombre}
              onChange={handleInputChange}
            />
          </div>

          <div className="form-field">
            <label>Tipo de Vino *</label>
            <select name="tipo" value={formData.tipo} onChange={handleInputChange}>
              <option value="tinto">Tinto</option>
              <option value="blanco">Blanco</option>
              <option value="rosado">Rosado</option>
              <option value="espumante">Espumante</option>
            </select>
          </div>

          <div className="form-field">
            <label>Añada (Año de Cosecha) *</label>
            <input
              type="number"
              name="anada"
              required
              min="1990"
              max="2100"
              value={formData.anada}
              onChange={handleInputChange}
            />
          </div>

          <div className="form-field">
            <label>Volumen (ml) *</label>
            <select name="volumen_ml" value={formData.volumen_ml} onChange={handleInputChange}>
              <option value="187">187 ml</option>
              <option value="375">375 ml</option>
              <option value="750">750 ml</option>
              <option value="1500">1500 ml</option>
              <option value="3000">3000 ml</option>
            </select>
          </div>

          <div className="form-field">
            <label>Graduación Alcohólica (5° - 20°) *</label>
            <input
              type="number"
              step="0.1"
              name="graduacion"
              required
              min="5.0"
              max="20.0"
              value={formData.graduacion}
              onChange={handleInputChange}
            />
          </div>

          <div className="form-field">
            <label>Precio Unitario Oficial ($) *</label>
            <input
              type="number"
              step="0.01"
              name="precio"
              required
              min="0.01"
              placeholder="Ej: 8500.00"
              value={formData.precio}
              onChange={handleInputChange}
            />
          </div>

          <div className="form-field">
            <label>CUIT de Bodega *</label>
            <input
              type="text"
              name="cuit_bodega"
              required
              maxLength="11"
              value={formData.cuit_bodega}
              onChange={handleInputChange}
            />
          </div>
        </div>

        {/* Sección de Composición de Corte */}
        <div className="corte-section">
          <div className="corte-header">
            <h4>🍇 Composición Varietal (RN-05: La suma debe ser exactamente 100%)</h4>
            <span className={`corte-sum ${sumaPorcentajes === 100 ? 'valid' : 'invalid'}`}>
              Suma actual: {sumaPorcentajes}% {sumaPorcentajes === 100 ? '✅' : '❌ (Falla en BD)'}
            </span>
          </div>

          <div className="corte-rows">
            {composicion.map((item, idx) => (
              <div key={idx} className="corte-row">
                <div className="form-field">
                  <label>ID de Cepa</label>
                  <input
                    type="number"
                    min="1"
                    required
                    value={item.id_cepa}
                    onChange={(e) => handleCompChange(idx, 'id_cepa', e.target.value)}
                  />
                </div>
                <div className="form-field">
                  <label>Porcentaje (%)</label>
                  <input
                    type="number"
                    step="0.1"
                    min="1"
                    max="100"
                    required
                    value={item.porcentaje}
                    onChange={(e) => handleCompChange(idx, 'porcentaje', e.target.value)}
                  />
                </div>
                {composicion.length > 1 && (
                  <button
                    type="button"
                    className="btn-danger btn-sm"
                    onClick={() => quitarRenglonCepa(idx)}
                    title="Quitar cepa"
                  >
                    🗑️
                  </button>
                )}
              </div>
            ))}
          </div>

          <button type="button" className="btn-secondary btn-sm" onClick={agregarRenglonCepa}>
            ➕ Agregar otra cepa al corte
          </button>
        </div>

        <div className="form-submit">
          <button type="submit" className="btn-primary" disabled={loading}>
            {loading ? 'Guardando en Base de Datos...' : 'Registrar Vino'}
          </button>
        </div>
      </form>
    </div>
  );
}

