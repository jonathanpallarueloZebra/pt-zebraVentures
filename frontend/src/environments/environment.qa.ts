export const environment = {
  production: true,
  // Ruta relativa, igual que environment.docker.ts: el nginx del frontend hace
  // de proxy de /api/ hacia el backend. Antes apuntaba al backend de QA de
  // Cabrero, de donde salio este repo.
  apiUrl: '/api',
};
