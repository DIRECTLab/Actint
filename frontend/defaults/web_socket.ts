import { io } from "socket.io-client";

const getSocketConfig = () => {
  const envUrl = process.env.NEXT_PUBLIC_WEBSOCKET_URL;

  // Use explicit URL if provided at build time (Non-Docker mode)
  if (envUrl) {
    return { url: envUrl, path: "/socket.io" };
  }

  // Fallback to Proxy Mode (Docker/Nginx)
  if (typeof window !== "undefined") {
    return {
      url: window.location.origin, // e.g., http://192.168.1.50
      path: "/ws",                 // Matches the Nginx location /ws block
    };
  }

  // SSR Fallback (Non-Docker default)
  return { url: "http://129.123.61.22:3050", path: "/socket.io" };
};

const config = getSocketConfig();

export const socket = io(config.url, {
  path: config.path,
  transports: ["websocket", "polling"],
});