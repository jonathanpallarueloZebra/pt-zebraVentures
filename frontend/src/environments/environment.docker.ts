export const environment = {
  production: true,
  // Ruta relativa: las peticiones salen como /api/... y nginx hace el proxy
  // hacia el servicio `backend` del docker-compose. Sin URL absoluta en el front.
  apiUrl: '/api',
};
