import { io } from "socket.io-client";

const websocketUrl = process.env.NEXT_PUBLIC_WEBSOCKET_URL || "ws://129.123.61.22:3060";
export const socket = io(websocketUrl);