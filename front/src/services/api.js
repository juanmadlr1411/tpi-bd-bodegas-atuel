/**
 * Cliente centralizado para comunicación con la API REST de Bodegas del Atuel.
 * Cumple con el requisito de tener la URL base configurable mediante variables de entorno.
 */
const BASE_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000';

async function request(endpoint, options = {}) {
  const url = `${BASE_URL}${endpoint}`;
  const headers = {
    'Content-Type': 'application/json',
    ...options.headers,
  };

  let response;
  try {
    response = await fetch(url, { ...options, headers });
  } catch (networkError) {
    const err = new Error(`No se pudo conectar con la API en ${BASE_URL}. Asegúrate de que el backend esté corriendo.`);
    err.isNetworkError = true;
    throw err;
  }

  if (!response.ok) {
    let errorData = {};
    try {
      errorData = await response.json();
    } catch {
      errorData = { message: `Error HTTP ${response.status}: ${response.statusText}` };
    }

    const message = errorData.message || errorData.detail || errorData.error || 'Error en la operación';
    const err = new Error(message);
    err.status = response.status;
    err.sqlstate = errorData.sqlstate || null;
    err.detail = errorData.detail || null;
    err.raw = errorData;
    throw err;
  }

  if (response.status === 204) {
    return null;
  }

  return response.json();
}

export const api = {
  // Salud
  getSalud: () => request('/salud'),

  // Vinos
  getVinos: (params = {}) => {
    const query = new URLSearchParams();
    if (params.limit !== undefined) query.set('limit', params.limit);
    if (params.offset !== undefined) query.set('offset', params.offset);
    if (params.tipo) query.set('tipo', params.tipo);
    if (params.cepa) query.set('cepa', params.cepa);
    if (params.bodega) query.set('bodega', params.bodega);
    if (params.anada) query.set('anada', params.anada);
    const qs = query.toString();
    return request(`/vinos${qs ? `?${qs}` : ''}`);
  },
  getVino: (codVino) => request(`/vinos/${codVino}`),
  crearVino: (vinoData) => request('/vinos', { method: 'POST', body: JSON.stringify(vinoData) }),
  actualizarVino: (codVino, vinoData) => request(`/vinos/${codVino}`, { method: 'PUT', body: JSON.stringify(vinoData) }),
  eliminarVino: (codVino) => request(`/vinos/${codVino}`, { method: 'DELETE' }),

  // Clientes
  getClientes: (params = {}) => {
    const query = new URLSearchParams();
    if (params.limit !== undefined) query.set('limit', params.limit);
    if (params.offset !== undefined) query.set('offset', params.offset);
    if (params.tipo_cliente) query.set('tipo_cliente', params.tipo_cliente);
    const qs = query.toString();
    return request(`/clientes${qs ? `?${qs}` : ''}`);
  },
  getCliente: (idCliente) => request(`/clientes/${idCliente}`),

  // Comprobantes (Ventas)
  crearComprobante: (comprobanteData) =>
    request('/comprobantes', { method: 'POST', body: JSON.stringify(comprobanteData) }),
  getComprobante: (nroComprobante) => request(`/comprobantes/${nroComprobante}`),

  // Transferencias e Ingresos (listos para cuando se conecten los endpoints)
  crearTransferencia: (data) => request('/transferencias', { method: 'POST', body: JSON.stringify(data) }),
  getTransferencia: (nro) => request(`/transferencias/${nro}`),

  // Reportes
  getTopVinos: () => request('/reportes/top-vinos'),
  getVentasPorSala: () => request('/reportes/ventas-por-sala'),
  getVinosSinStock: (idSala) => request(`/reportes/vinos-sin-stock?id_sala=${idSala}`),
};

