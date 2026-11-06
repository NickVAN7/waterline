/// <reference types="vite/client" />

interface ImportMetaEnv {
  /** The PrimeUI license key (DL-135), from the repository's `.env` or CI's secret. */
  readonly VITE_PRIMEUI_LICENSE?: string
}
