import React, { useState } from 'react';
import { Navbar } from './components/Navbar';

export function App() {
  const [activeTab, setActiveTab] = useState('catalogo');

  return (
    <div className="app-root">
      <Navbar activeTab={activeTab} onTabChange={setActiveTab} />

      <main className="main-content">
        {activeTab === 'catalogo' && (
          <div className="placeholder-card">
            <h3>🍷 Catálogo de Vinos</h3>
            <p>Módulo asignado a Onza (Gonzalo).</p>
          </div>
        )}
        {activeTab === 'alta-vino' && (
          <div className="placeholder-card">
            <h3>➕ Alta de Vino con Corte (RN-05)</h3>
            <p>Módulo asignado a Onza (Gonzalo).</p>
          </div>
        )}
        {activeTab === 'nueva-venta' && (
          <div className="placeholder-card">
            <h3>🧾 Nueva Venta y Errores de Stock (RN-09)</h3>
            <p>Módulo asignado a Bruno (Br1).</p>
          </div>
        )}
        {activeTab === 'transferencias' && (
          <div className="placeholder-card">
            <h3>🚚 Transferencias y Estados (RN-11)</h3>
            <p>Módulo asignado a Manuel (Pelu) / Santiago (Bando).</p>
          </div>
        )}
        {activeTab === 'tablero' && (
          <div className="placeholder-card">
            <h3>📊 Tablero de Reportes y Vistas</h3>
            <p>Módulo asignado a Juan Manuel (Delgado) / Santiago (Bando).</p>
          </div>
        )}
      </main>
    </div>
  );
}

export default App;
