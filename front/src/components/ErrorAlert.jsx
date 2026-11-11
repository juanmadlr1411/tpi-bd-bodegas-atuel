import React from 'react';

/**
 * Componente para mostrar mensajes de error de base de datos.
 * Criterio de aceptación H7:
 * "Mostrar al usuario los mensajes de error de las reglas de negocio tal como los devuelve la API,
 * sin ocultarlos ni reemplazarlos por un mensaje genérico."
 */
export function ErrorAlert({ error, onClose }) {
  if (!error) return null;

  const message =
    typeof error.message === 'string'
      ? error.message
      : typeof error === 'string'
        ? error
        : 'Ocurrió un error inesperado';
  const sqlstate = error.sqlstate;
  const detail =
    typeof error.detail === 'string'
      ? error.detail
      : Array.isArray(error.detail)
        ? error.detail.map((d) => d.msg || JSON.stringify(d)).join(' | ')
        : null;

  return (
    <div className="error-banner">
      <div className="error-header">
        <div className="error-title-row">
          <span className="error-icon">⚠️</span>
          <strong>Error de Base de Datos / Regla de Negocio</strong>
          {sqlstate && <span className="badge-sqlstate">SQLSTATE: {sqlstate}</span>}
          {error.status && <span className="badge-status">HTTP {error.status}</span>}
        </div>
        {onClose && (
          <button className="btn-close" onClick={onClose} title="Cerrar">
            ✕
          </button>
        )}
      </div>
      <div className="error-body">
        <p className="error-message">{message}</p>
        {detail && <p className="error-detail"><strong>Detalle PostgreSQL:</strong> {detail}</p>}
      </div>
    </div>
  );
}

