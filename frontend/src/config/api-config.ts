// Backend URL configuration
export const LOCAL_BACKEND_URL = "http://0.0.0.0:8000";
export const PRODUCTION_BACKEND_URL_APP = "https://vidgenai-qp38.onrender.com";
export const PRODUCTION_BACKEND_URL_DOCKER = "https://vidgenai-new.onrender.com";
export const PRODUCTION_BACKEND_URL_DIGITAL_OCEAN = "https://lionfish-app-gb5xd.ondigitalocean.app";
export const PRODUCTION_BACKEND_URL = PRODUCTION_BACKEND_URL_DIGITAL_OCEAN

// MANUAL TOGGLE: Set to true to use production backend, false to use local
export const USE_PRODUCTION_BACKEND = true;

// Helper function to determine which backend URL to use
export const getBackendUrl = () =>
  USE_PRODUCTION_BACKEND ? PRODUCTION_BACKEND_URL : LOCAL_BACKEND_URL;
