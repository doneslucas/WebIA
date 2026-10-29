const configuredApiUrl = import.meta.env.VITE_API_URL?.trim();

const defaultApiUrl = import.meta.env.DEV
  ? "http://127.0.0.1:8000"
  : "/api";

const API_URL = (
  configuredApiUrl || defaultApiUrl
).replace(/\/+$/, "");

export default API_URL;