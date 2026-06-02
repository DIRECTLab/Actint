import { io } from "socket.io-client";

const getSocketConfig = () => {
  const envUrl = process.env.NEXT_PUBLIC_WEBSOCKET_URL;

  if (envUrl) {
    return { url: envUrl, path: "/socket.io" };
  }

  if (typeof window !== "undefined") {
    return {
      url: window.location.origin,
      path: "/socket.io",
    };
  }

  return { url: "http://129.123.61.22:3050", path: "/socket.io" };
};

const config = getSocketConfig();

export const socket = io(config.url, {
  path: config.path,
  transports: ["websocket", "polling"],
});