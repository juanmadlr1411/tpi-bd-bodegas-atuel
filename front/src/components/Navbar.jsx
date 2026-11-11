import React, { useEffect, useState } from 'react';
import { api } from '../services/api';

export function Navbar({ activeTab, onTabChange }) {
  const [dbStatus, setDbStatus] = useState('checking'); // 'checking' | 'connected' | 'error'

  useEffect(() => {
    api.getSalud()
      .then((data) => {
        if (data.status === 'ok') setDbStatus('connected');
        else setDbStatus('error');
      })
      .catch(() => setDbStatus('error'));
  }, []);

  const tabs = [
    { id: 'catalogo', label: 'Catálogo de Vinos', icon: '🍷', author: 'Gonzalo' },
    { id: 'alta-vino', label: 'Alta y Corte', icon: '➕', author: 'Gonzalo' },
    { id: 'nueva-venta', label: 'Nueva Venta', icon: '🧾', author: 'Bruno' },
    { id: 'transferencias', label: 'Transferencias', icon: '🚚', author: 'Manuel' },
    { id: 'tablero', label: 'Tablero', icon: '📊', author: 'Santiago' },
  ];

  return (
    <header className="navbar">
      <div className="navbar-brand">
        <span className="brand-logo">🍷</span>
        <div>
          <h1 className="brand-title">Bodegas del Atuel</h1>
          <span className="brand-subtitle">TPI Bases de Datos · Etapa 7: Front</span>
        </div>
      </div>

      <nav className="navbar-tabs">
        {tabs.map((tab) => (
          <button
            key={tab.id}
            className={`tab-button ${activeTab === tab.id ? 'active' : ''}`}
            onClick={() => onTabChange(tab.id)}
          >
            <span className="tab-icon">{tab.icon}</span>
            <span className="tab-label">{tab.label}</span>
          </button>
        ))}
      </nav>

      <div className="navbar-status">
        <span
          className={`status-indicator ${dbStatus}`}
          title={`Base de datos: ${dbStatus === 'connected' ? 'Conectada (operador_atuel)' : dbStatus}`}
        >
          ● BD {dbStatus === 'connected' ? 'Online' : dbStatus === 'checking' ? 'Conectando...' : 'Offline'}
        </span>
      </div>
    </header>
  );
}

