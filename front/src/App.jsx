import React, { useState } from 'react';
import { Navbar } from './components/Navbar';
import { CatalogoVinos } from './screens/CatalogoVinos';
import { AltaVino } from './screens/AltaVino';
import { NuevaVenta } from './screens/NuevaVenta';
import { Transferencias } from './screens/Transferencias';

export function App() {
  const [activeTab, setActiveTab] = useState('catalogo');

  return (
    <div className="app-root">
      <Navbar activeTab={activeTab} onTabChange={setActiveTab} />

      <main className="main-content">
        {/* Pantallas asignadas a Onza (Gonzalo) */}
        {activeTab === 'catalogo' && <CatalogoVinos />}
        {activeTab === 'alta-vino' && (
          <AltaVino onVinoCreado={() => setActiveTab('catalogo')} />
        )}

        {/* Espacios reservados para que cada integrante monte su componente */}
        {activeTab === 'nueva-venta' && <NuevaVenta />}
        {activeTab === 'transferencias' && <Transferencias />}
        {activeTab === 'tablero' && (
          <div className="placeholder-card">
            <h3>📊 Tablero de Reportes y Vistas</h3>
            <p>Módulo reservado para reportes analíticos de la Sección 8.</p>
          </div>
        )}
      </main>
    </div>
  );
}

export default App;
