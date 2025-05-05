// Backend URL configuration
export const LOCAL_BACKEND_URL = "http://0.0.0.0:8000";
export const PRODUCTION_BACKEND_URL_APP = "https://vidgenai-qp38.onrender.com";
export const PRODUCTION_BACKEND_URL_DOCKER = "https://vidgenai-new.onrender.com";
export const PRODUCTION_BACKEND_URL = PRODUCTION_BACKEND_URL_DOCKER

// MANUAL TOGGLE: Set to true to use production backend, false to use local
export const USE_PRODUCTION_BACKEND = true;

// Helper function to determine which backend URL to use
export const getBackendUrl = () => {
  // For browser environment, use empty base URL to leverage Next.js API routing
  if (typeof window !== 'undefined') {
    return '';
  }
  
  // For server-side calls, use the actual backend URL based on the toggle
  return USE_PRODUCTION_BACKEND ? PRODUCTION_BACKEND_URL : LOCAL_BACKEND_URL;
};