import { socket } from "@/defaults/web_socket";

export type HeatmapPayload = {
  points: number[][];
};

export type ConnectionStatus =
  | "connected"
  | "disconnected_by_server"
  | "disconnected_by_client"
  | "connection_lost"
  | "connection_error";

type ConnectionProps = {
  setConnectionStatus: React.Dispatch<React.SetStateAction<ConnectionStatus>>;
};

const DISCONNECT_REASON_MAP: Record<string, ConnectionStatus> = {
  "io server disconnect": "disconnected_by_server",
  "io client disconnect": "disconnected_by_client",
  "ping timeout": "connection_lost",
  "transport close": "connection_lost",
  "transport error": "connection_error",
};

export const CONNECTION_STATUS_MESSAGES: Record<ConnectionStatus, string> = {
  connected: "Connected to server.",
  disconnected_by_server: "Disconnected: the server closed the connection.",
  disconnected_by_client: "Disconnected: client initiated disconnect.",
  connection_lost: "Connection lost. The server may be unreachable.",
  connection_error: "A transport error occurred. Check your network.",
};

export const create_connection_listeners = ({
  setConnectionStatus,
}: ConnectionProps) => {
  socket.on("connect", () => {
    setConnectionStatus("connected");
  });

  socket.on("disconnect", (reason) => {
    const status =
      DISCONNECT_REASON_MAP[reason] ?? "connection_lost";
    setConnectionStatus(status);
  });
};

type Props1 = {
  handleManualMove: (lat: number, lng: number, zoom: number) => void;
  setAI_objects: React.Dispatch<React.SetStateAction<any[]>>;
  setHeatmapData: (data: {
    points: number[][];
  }) => void;
};

export const create_map_functions = ({
  handleManualMove,
  setAI_objects,
  setHeatmapData,
}: Props1) => {
  socket.on("set_map_position", (data) => {
    console.log("set map position", data);
    handleManualMove(data.lat, data.lon, data.zoom);
  });

  socket.on("draw_rectangle", (data) => {
    setAI_objects((prev) => [...prev, { type: "rectangle", data }]);
    console.log("set AI objects", data);
  });

  socket.on("draw_circle", (data) => {
    console.log("set AI objects", data);
    setAI_objects((prev) => [...prev, { type: "circle", data }]);
  });

  socket.on("draw_line", (data) => {
    console.log("set AI objects", data);
    setAI_objects((prev) => [...prev, { type: "line", data }]);
  });

  socket.on("set_heatmap", (data: HeatmapPayload) => {
    console.log("set heatmap", data);
    setHeatmapData({points: data.points || []});
  });
};