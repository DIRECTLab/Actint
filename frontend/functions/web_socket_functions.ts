import { socket } from "@/defaults/web_socket";
import { convertServerPatchToFullTree } from "next/dist/client/components/segment-cache/navigation";

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
  aiObjectsRef: any;
  setAI_objects: React.Dispatch<React.SetStateAction<any[]>>;
};

export const create_map_functions = ({
  handleManualMove,
  aiObjectsRef,
  setAI_objects,
}: Props1) => {
  socket.on("set_map_position", (data) => {
    console.log("set map position", data);
    handleManualMove(data.lat, data.lon, data.zoom);
  });

  socket.on("add_marker", (data) => {
    console.log(data)
    setAI_objects((prev) => [...prev, { type: "marker", data}])
  });

  socket.on("draw_vessel_trajectory", (data) => {
    setAI_objects((prev) => [...prev, { type: "trajectory", data}])
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

  socket.on("draw_polygon", (data) => {
    console.log(data);
    setAI_objects((prev) => [...prev, { type: "polygon", data }]);
  });

  socket.on("delete_object", (data) => {
    console.log("Deleting object", data)
    setAI_objects((prev) => prev.filter(obj => obj.id !== data.object_number));
  });

  socket.on("get_map_information", (data, callback) => {
    console.log("Map_objects retrieved")
    let clean_objects = []
    console.log(aiObjectsRef)

    callback(aiObjectsRef)
  });
};

export const remove_map_functions = () => {
  socket.off("set_map_position")
  socket.off("add_marker")
  socket.off("draw_vessel_trajectory")
  socket.off("draw_rectangle")
  socket.off("draw_circle")
  socket.off("draw_line")
  socket.off("draw_polygon")
  socket.off("delete_object")
  socket.off("get_map_information")
}

