/**
 * Configuración por defecto (build de producción).
 *
 * `apiUrl` vacío = el backend se sirve desde el MISMO origen que el frontend
 * (por ejemplo detrás de un reverse proxy). Si tu backend vive en otro dominio,
 * pon aquí su URL antes de compilar. En desarrollo se usa
 * `environment.development.ts` (ver `fileReplacements` en angular.json).
 */
export const environment = {
  production: true,
  apiUrl: '',
};
