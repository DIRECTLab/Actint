import { io } from "socket.io-client";

const websocketUrl = process.env.NEXT_PUBLIC_WEBSOCKET_URL || "ws://192.168.0.241:3050";
export const socket = io(websocketUrl);
