import React, { useEffect, useState } from 'react';
import { api } from '../services/api';
import { ErrorAlert } from '../components/ErrorAlert';

const formatoMoneda = new Intl.NumberFormat('es-AR', {
  style: 'currency',
  currency: 'ARS',
});

const formatoNumero = new Intl.NumberFormat('es-AR');

const tarjeta = {
  background: '#ffffff',
  border: '1px solid #e2e8f0',
  borderRadius: '12px',
  padding: '24px',
  marginBottom: '24px',
};

export function TableroReportes() {
  const [topVinos, setTopVinos] = useState([]);
  const [ventas, setVentas] = useState([]);
  const [salas, setSalas] = useState([]);
  const [salaSeleccionada, setSalaSeleccionada] = useState('');
  const [vinosSinStock, setVinosSinStock] = useState([]);

  const [cargando, setCargando] = useState(true);
  const [cargandoStock, setCargandoStock] = useState(false);
  const [error, setError] = useState(null);
  const [errorStock, setErrorStock] = useState(null);

  // Cargar los reportes principales y las salas disponibles.
  useEffect(() => {
    let activo = true;

    async function cargarTablero() {
      try {
        const [ranking, ventasPorSala, listadoSalas] = await Promise.all([
          api.getTopVinos(),
          api.getVentasPorSala(),
          api.getSalas(),
        ]);

        if (!activo) return;

        setTopVinos(ranking);
        setVentas(ventasPorSala);
        setSalas(listadoSalas);

        if (listadoSalas.length > 0) {
          setSalaSeleccionada(String(listadoSalas[0].id_sala));
        }
      } catch (err) {
        if (activo) setError(err);
      } finally {
        if (activo) setCargando(false);
      }
    }

    cargarTablero();

    return () => {
      activo = false;
    };
  }, []);

  // Actualizar el reporte de stock cuando cambia la sala.
  useEffect(() => {
    if (!salaSeleccionada) return;

    let activo = true;

    async function cargarStock() {
      setCargandoStock(true);
      setErrorStock(null);

      try {
        const resultado = await api.getVinosSinStock(salaSeleccionada);

        if (activo) {
          setVinosSinStock(resultado);
        }
      } catch (err) {
        if (activo) {
          setErrorStock(err);
          setVinosSinStock([]);
        }
      } finally {
        if (activo) setCargandoStock(false);
      }
    }

    cargarStock();

    return () => {
      activo = false;
    };
  }, [salaSeleccionada]);

  // Escala visual del gráfico. No recalcula importes.
  const maxVenta = Math.max(
    0,
    ...ventas.map((sala) => Number(sala.monto_total_trimestre))
  );

  if (cargando) {
    return (
      <div className="screen-container">
        <p className="loading-state">Cargando reportes desde PostgreSQL...</p>
      </div>
    );
  }

  return (
    <div className="screen-container">

      <div className="screen-header">
        <h2>📊 Tablero de Reportes</h2>
        <span className="screen-badge">
          Datos obtenidos desde PostgreSQL
        </span>
      </div>

      <ErrorAlert
        error={error}
        onClose={() => setError(null)}
      />

      {/* REPORTE S1 */}
      <section style={tarjeta}>
        <h3>🏆 Los 10 vinos más vendidos</h3>
        <p>Ranking por cantidad de botellas vendidas en toda la red.</p>

        {topVinos.length === 0 ? (
          <p className="empty-state">No hay ventas registradas.</p>
        ) : (
          <div className="table-wrapper">
            <table className="data-table">
              <thead>
                <tr>
                  <th>Posición</th>
                  <th>Código</th>
                  <th>Vino</th>
                  <th>Botellas vendidas</th>
                </tr>
              </thead>

              <tbody>
                {topVinos.map((vino, index) => (
                  <tr key={vino.cod_vino}>
                    <td>{index + 1}</td>
                    <td>#{vino.cod_vino}</td>
                    <td>{vino.nombre}</td>
                    <td>
                      <strong>
                        {formatoNumero.format(Number(vino.total_botellas))}
                      </strong>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </section>

      {/* REPORTE S8 */}
      <section style={tarjeta}>
        <h3>📈 Ventas por sala — Últimos 3 meses</h3>
        <p>
          Comparación de la facturación obtenida desde los comprobantes.
        </p>

        {ventas.length === 0 ? (
          <p className="empty-state">
            No hay ventas registradas durante este período.
          </p>
        ) : (
          <div>
            {ventas.map((sala) => {
              const monto = Number(sala.monto_total_trimestre);

              const porcentajeVisual = maxVenta > 0
                ? (monto / maxVenta) * 100
                : 0;

              return (
                <div
                  key={sala.id_sala}
                  style={{
                    marginBottom: '18px',
                  }}
                >
                  <div
                    style={{
                      display: 'flex',
                      justifyContent: 'space-between',
                      gap: '12px',
                      flexWrap: 'wrap',
                      marginBottom: '6px',
                    }}
                  >
                    <strong>Sala #{sala.id_sala}</strong>
                    <span>{formatoMoneda.format(monto)}</span>
                  </div>

                  <div
                    style={{
                      background: '#f1f5f9',
                      borderRadius: '8px',
                      height: '24px',
                      overflow: 'hidden',
                    }}
                  >
                    <div
                      role="img"
                      aria-label={`Sala ${sala.id_sala}: ${formatoMoneda.format(monto)}`}
                      style={{
                        width: `${porcentajeVisual}%`,
                        height: '100%',
                        background: '#8b3a46',
                        borderRadius: '8px',
                      }}
                    />
                  </div>
                </div>
              );
            })}
          </div>
        )}
      </section>

      {/* REPORTE S6 */}
      <section style={tarjeta}>
        <h3>📦 Vinos sin stock por sala</h3>

        <p>
          Vinos agotados en la sala seleccionada, pero disponibles
          en el depósito central.
        </p>

        <div className="form-field" style={{ maxWidth: '400px' }}>
          <label htmlFor="sala-reporte">
            Seleccionar sala de venta
          </label>

          <select
            id="sala-reporte"
            value={salaSeleccionada}
            onChange={(event) => {
              setSalaSeleccionada(event.target.value);
              setVinosSinStock([]);
            }}
          >
            {salas.map((sala) => (
              <option key={sala.id_sala} value={sala.id_sala}>
                Sala #{sala.id_sala} — {sala.calle} {sala.numero}
              </option>
            ))}
          </select>
        </div>

        <ErrorAlert
          error={errorStock}
          onClose={() => setErrorStock(null)}
        />

        {cargandoStock ? (
          <p className="loading-state">Consultando existencias...</p>
        ) : errorStock ? null : salas.length === 0 ? (
          <p className="empty-state">
            No hay salas disponibles.
          </p>
        ) : vinosSinStock.length === 0 ? (
          <p className="empty-state">
            No se encontraron vinos agotados en esta sala
            que tengan existencias disponibles en el depósito.
          </p>
        ) : (
          <div className="table-wrapper">
            <table className="data-table">
              <thead>
                <tr>
                  <th>Código</th>
                  <th>Vino</th>
                  <th>Botellas disponibles en depósito</th>
                </tr>
              </thead>

              <tbody>
                {vinosSinStock.map((vino) => (
                  <tr key={vino.cod_vino}>
                    <td>#{vino.cod_vino}</td>
                    <td>{vino.nombre}</td>
                    <td>
                      {formatoNumero.format(Number(vino.stock_deposito))}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </section>

    </div>
  );
}