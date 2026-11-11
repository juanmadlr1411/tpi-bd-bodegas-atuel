import React, { useEffect, useState } from 'react';
import { api } from '../services/api';
import { ErrorAlert } from '../components/ErrorAlert';

const formatoMoneda = new Intl.NumberFormat('es-AR', {
  style: 'currency',
  currency: 'ARS',
  minimumFractionDigits: 2,
});

async function cargarTodos(fetcher) {
  const limit = 100;
  let offset = 0;
  let total = 0;
  const acumulado = [];

  do {
    const data = await fetcher({ limit, offset });
    const items = data.items || [];
    acumulado.push(...items);
    total = data.total || 0;
    offset += limit;
    if (items.length === 0) break;
  } while (offset < total);

  return acumulado;
}

/**
 * Pantalla 3: Nueva Venta (Responsable: Bruno)
 * El frontend solo envía cliente, sala y renglones. Los subtotales, descuentos,
 * total y stock son calculados/validados exclusivamente por la base de datos.
 */
export function NuevaVenta() {
  const [clientes, setClientes] = useState([]);
  const [salas, setSalas] = useState([]);
  const [vinos, setVinos] = useState([]);

  const [idCliente, setIdCliente] = useState('');
  const [idSala, setIdSala] = useState('');
  const [codVino, setCodVino] = useState('');
  const [cantidad, setCantidad] = useState(1);

  const [renglones, setRenglones] = useState([]);
  const [loadingCatalogos, setLoadingCatalogos] = useState(true);
  const [enviando, setEnviando] = useState(false);
  const [error, setError] = useState(null);
  const [aviso, setAviso] = useState(null);
  const [comprobante, setComprobante] = useState(null);

  useEffect(() => {
    let activo = true;

    Promise.all([
      cargarTodos(api.getClientes),
      cargarTodos(api.getVinos),
      api.getSalas(),
    ])
      .then(([clientesData, vinosData, salasData]) => {
        if (!activo) return;
        setClientes(clientesData);
        setVinos(vinosData);
        setSalas(salasData || []);
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

  const agregarRenglon = () => {
    setAviso(null);
    setError(null);

    const codigo = parseInt(codVino, 10);
    const cant = parseInt(cantidad, 10);

    if (!codigo) {
      setAviso('Seleccioná un vino del catálogo antes de agregarlo.');
      return;
    }
    if (!Number.isInteger(cant) || cant < 1) {
      setAviso('La cantidad debe ser un número entero mayor o igual a 1.');
      return;
    }
    if (renglones.some((r) => r.cod_vino === codigo)) {
      setAviso('Ese vino ya está en el carrito. Quitalo si querés cambiar la cantidad.');
      return;
    }

    const vino = vinos.find((v) => v.cod_vino === codigo);
    setRenglones((prev) => [
      ...prev,
      {
        cod_vino: codigo,
        nombre: vino?.nombre || `Vino #${codigo}`,
        anada: vino?.anada,
        tipo: vino?.tipo,
        cantidad: cant,
      },
    ]);
    setCodVino('');
    setCantidad(1);
  };

  const quitarRenglon = (codigo) => {
    setRenglones((prev) => prev.filter((r) => r.cod_vino !== codigo));
  };

  const confirmarVenta = async (e) => {
    e.preventDefault();
    setAviso(null);
    setError(null);
    setComprobante(null);

    if (!idCliente) {
      setAviso('Seleccioná un cliente para emitir el comprobante.');
      return;
    }
    if (!idSala) {
      setAviso('Seleccioná la sala de venta.');
      return;
    }
    if (renglones.length === 0) {
      setAviso('Agregá al menos un renglón al carrito.');
      return;
    }

    const payload = {
      id_cliente: parseInt(idCliente, 10),
      id_sala: parseInt(idSala, 10),
      renglones: renglones.map((r) => ({
        cod_vino: r.cod_vino,
        cantidad: r.cantidad,
      })),
    };

    setEnviando(true);
    try {
      const emitido = await api.crearComprobante(payload);
      setComprobante(emitido);
      setRenglones([]);
      setCodVino('');
      setCantidad(1);
    } catch (err) {
      // Se conserva intacto el formulario para que el usuario corrija la venta.
      setError(err);
    } finally {
      setEnviando(false);
    }
  };

  return (
    <div className="screen-container">
      <div className="screen-header">
        <h2>🧾 Nueva Venta</h2>
        <span className="screen-badge">Totales y stock calculados por la base de datos</span>
      </div>

      <ErrorAlert error={error} onClose={() => setError(null)} />

      {aviso && (
        <div className="notice-banner">
          <span>ℹ️</span>
          <p>{aviso}</p>
          <button className="btn-close" onClick={() => setAviso(null)} title="Cerrar">✕</button>
        </div>
      )}

      {comprobante && (
        <div className="comprobante-card">
          <div className="comprobante-header">
            <div>
              <h3>✅ Comprobante #{comprobante.nro_comprobante} emitido</h3>
              <p className="text-muted">
                {comprobante.cliente_nombre} · Sala #{comprobante.id_sala} · Fecha {comprobante.fecha}
              </p>
            </div>
            <div className="total-hero">
              <span className="total-hero-label">Total calculado por la BD</span>
              <span className="total-hero-value">{formatoMoneda.format(Number(comprobante.total))}</span>
            </div>
          </div>

          <div className="table-wrapper">
            <table className="data-table">
              <thead>
                <tr>
                  <th>Vino</th>
                  <th>Cantidad</th>
                  <th>Precio unitario</th>
                  <th>Descuento</th>
                  <th>Subtotal</th>
                </tr>
              </thead>
              <tbody>
                {(comprobante.renglones || []).map((r) => (
                  <tr key={r.cod_vino}>
                    <td>{r.nombre_vino || `Vino #${r.cod_vino}`}</td>
                    <td>{r.cantidad}</td>
                    <td>{formatoMoneda.format(Number(r.precio_unitario))}</td>
                    <td>{Number(r.descuento).toFixed(2)}%</td>
                    <td>{formatoMoneda.format(Number(r.subtotal))}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          <div className="totales-box">
            <div><span>Subtotal bruto: </span><strong>{formatoMoneda.format(Number(comprobante.subtotal))}</strong></div>
            <div><span>Descuento aplicado: </span><strong>{formatoMoneda.format(Number(comprobante.descuento))}</strong></div>
            <div className="total-destacado">Total neto: {formatoMoneda.format(Number(comprobante.total))}</div>
          </div>
        </div>
      )}

      <form className="form-card" onSubmit={confirmarVenta}>
        <div className="form-grid">
          <div className="form-field">
            <label htmlFor="venta-cliente">Cliente *</label>
            <select
              id="venta-cliente"
              value={idCliente}
              onChange={(e) => setIdCliente(e.target.value)}
              disabled={loadingCatalogos}
              required
            >
              <option value="">Seleccionar cliente...</option>
              {clientes.map((c) => (
                <option key={c.id_cliente} value={c.id_cliente}>
                  #{c.id_cliente} — {c.nombre_razon_social} ({c.tipo_cliente})
                </option>
              ))}
            </select>
          </div>

          <div className="form-field">
            <label htmlFor="venta-sala">Sala de Venta *</label>
            <select
              id="venta-sala"
              value={idSala}
              onChange={(e) => setIdSala(e.target.value)}
              disabled={loadingCatalogos}
              required
            >
              <option value="">Seleccionar sala...</option>
              {salas.map((s) => (
                <option key={s.id_sala} value={s.id_sala}>
                  Sala #{s.id_sala} — {s.calle} {s.numero} ({s.localidad_nombre})
                </option>
              ))}
            </select>
          </div>
        </div>

        <div className="venta-renglon-form">
          <div className="form-field venta-vino-field">
            <label htmlFor="venta-vino">Vino *</label>
            <select
              id="venta-vino"
              value={codVino}
              onChange={(e) => setCodVino(e.target.value)}
              disabled={loadingCatalogos}
            >
              <option value="">Seleccionar vino del catálogo...</option>
              {vinos.map((v) => (
                <option key={v.cod_vino} value={v.cod_vino}>
                  #{v.cod_vino} — {v.nombre} ({v.anada}) · {v.tipo}
                </option>
              ))}
            </select>
          </div>

          <div className="form-field venta-cantidad-field">
            <label htmlFor="venta-cantidad">Cantidad *</label>
            <input
              id="venta-cantidad"
              type="number"
              min="1"
              step="1"
              value={cantidad}
              onChange={(e) => setCantidad(e.target.value)}
            />
          </div>

          <button type="button" className="btn-secondary" onClick={agregarRenglon}>
            ➕ Agregar renglón
          </button>
        </div>

        <div className="cart-section">
          <div className="corte-header">
            <h4>🛒 Renglones de la venta</h4>
            <span className="screen-badge">{renglones.length} ítem(s)</span>
          </div>

          {renglones.length === 0 ? (
            <p className="empty-state">Todavía no agregaste vinos al carrito.</p>
          ) : (
            <div className="table-wrapper">
              <table className="data-table">
                <thead>
                  <tr>
                    <th>Código</th>
                    <th>Vino</th>
                    <th>Tipo</th>
                    <th>Añada</th>
                    <th>Cantidad</th>
                    <th>Acciones</th>
                  </tr>
                </thead>
                <tbody>
                  {renglones.map((r) => (
                    <tr key={r.cod_vino}>
                      <td><strong>#{r.cod_vino}</strong></td>
                      <td>{r.nombre}</td>
                      <td><span className={`tag-tipo ${r.tipo}`}>{r.tipo}</span></td>
                      <td>{r.anada}</td>
                      <td>{r.cantidad}</td>
                      <td>
                        <button
                          type="button"
                          className="btn-danger btn-sm"
                          onClick={() => quitarRenglon(r.cod_vino)}
                        >
                          🗑️ Quitar
                        </button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>

        <div className="venta-submit-row">
          <p className="text-muted">
            El frontend no calcula importes ni stock. El total y la disponibilidad los determina la base de datos.
          </p>
          <button type="submit" className="btn-primary" disabled={enviando || loadingCatalogos}>
            {enviando ? 'Confirmando en la base de datos...' : 'Confirmar Venta'}
          </button>
        </div>
      </form>
    </div>
  );
}
