/// <reference types="vite/client" />

interface ImportMetaEnv {
  /** Backend address when the frontend is hosted separately (Vercel). Empty in development. */
  readonly VITE_API_BASE?: string;
}
