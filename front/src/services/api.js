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

    let detailText = null;
    if (Array.isArray(errorData.detail)) {
      detailText = errorData.detail
        .map((item) => {
          const campo = Array.isArray(item.loc) ? item.loc.slice(1).join('.') : '';
          return campo ? `${campo}: ${item.msg}` : item.msg || JSON.stringify(item);
        })
        .join(' | ');
    } else if (typeof errorData.detail === 'string') {
      detailText = errorData.detail;
    }

    const message =
      errorData.message ||
      detailText ||
      errorData.error ||
      'Error en la operación';
    const err = new Error(message);
    err.status = response.status;
    err.sqlstate = errorData.sqlstate || null;
    err.detail = errorData.message && detailText ? detailText : null;
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

  // Salas de venta
  getSalas: () => request('/salas'),

  // Comprobantes (Ventas)
  crearComprobante: (comprobanteData) =>
    request('/comprobantes', { method: 'POST', body: JSON.stringify(comprobanteData) }),
  getComprobante: (nroComprobante) => request(`/comprobantes/${nroComprobante}`),

  // Transferencias
  crearTransferencia: (data) =>
    request('/transferencias', { method: 'POST', body: JSON.stringify(data) }),
  getTransferencia: (nro) =>
    request(`/transferencias/${nro}`),
  agregarRenglonTransferencia: (nro, data) =>
    request(`/transferencias/${nro}/renglones`, { method: 'POST', body: JSON.stringify(data) }),
  terminarTransferencia: (nro) =>
    request(`/transferencias/${nro}/terminar`, { method: 'POST' }),
  procesarTransferencia: (nro) =>
    request(`/transferencias/${nro}/procesar`, { method: 'POST' }),

  // Ingresos
  crearIngreso: (data) =>
    request('/ingresos', { method: 'POST', body: JSON.stringify(data) }),
  getIngreso: (cod) =>
    request(`/ingresos/${cod}`),
  agregarRenglonIngreso: (cod, data) =>
    request(`/ingresos/${cod}/renglones`, { method: 'POST', body: JSON.stringify(data) }),
  terminarIngreso: (cod) =>
    request(`/ingresos/${cod}/terminar`, { method: 'POST' }),
  procesarIngreso: (cod) =>
    request(`/ingresos/${cod}/procesar`, { method: 'POST' }),

  // Reportes
  getTopVinos: () => request('/reportes/top-vinos'),
  getVentasPorSala: () => request('/reportes/ventas-por-sala'),
  getVinosSinStock: (idSala) => request(`/reportes/vinos-sin-stock?id_sala=${idSala}`),
};
