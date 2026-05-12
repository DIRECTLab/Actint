import React, { useEffect, useState } from "react";
import "@chatscope/chat-ui-kit-styles/dist/default/styles.css";
import { socket } from "@/defaults/web_socket";
import {
  create_connection_listeners,
  ConnectionStatus,
  CONNECTION_STATUS_MESSAGES,
} from "@/functions/web_socket_functions";

import {
  MainContainer,
  ChatContainer,
  MessageList,
  Message,
  MessageInput,
  TypingIndicator,
} from "@chatscope/chat-ui-kit-react";

export function Chat() {
  const [messages, setMessages] = useState<any[]>([]);
  const [isTyping, setIsTyping] = useState(false);
  const [connectionStatus, setConnectionStatus] =
    useState<ConnectionStatus>("connected");

  const isDisconnected = connectionStatus !== "connected";

  const handleSendMessage = (messageText: string) => {
    if (isDisconnected) return;

    const newMessage = {
      message: messageText,
      sentTime: "just now",
      sender: "user",
      direction: "outgoing",
      position: "single",
    };

    socket.emit("recieve_message", newMessage);
    setMessages((prev) => [...prev, newMessage]);
    setIsTyping(true);
  };

  useEffect(() => {
    create_connection_listeners({ setConnectionStatus });

    const handleResponse = (data: any) => {
      setIsTyping(false);
      console.log(data);
      setMessages((prev) => [...prev, data]);
    };

    socket.on("send_response", handleResponse);

    return () => {
      socket.off("send_response", handleResponse);
    };
  }, []);

  return (
    <div
        style={{
        display: "flex",
        flexDirection: "column",
        height: "100%",
        overflow: "hidden",
        }}
    >
        {isDisconnected && (
        <div
            style={{
            flexShrink: 0,
            background: "#b91c1c",
            color: "#fff",
            padding: "6px 12px",
            fontSize: "0.875rem",
            textAlign: "center",
            }}
        >
            {CONNECTION_STATUS_MESSAGES[connectionStatus]}
        </div>
        )}
        <div style={{ flex: 1, minHeight: 0, position: "relative" }}>
        <MainContainer style={{ height: "100%" }}>
            <ChatContainer>
            <MessageList>
                {messages.map((msg, idx) => (
                <Message
                    key={idx}
                    model={{
                    message: msg.message,
                    sentTime: msg.sentTime,
                    sender: msg.sender,
                    direction: msg.direction,
                    position: msg.position,
                    }}
                />
                ))}
                {isTyping && <TypingIndicator content="ChatBot is typing" />}
            </MessageList>
            <MessageInput
                placeholder={
                isDisconnected
                    ? "Disconnected from server..."
                    : "Type message here..."
                }
                onSend={handleSendMessage}
                disabled={isDisconnected}
            />
            </ChatContainer>
        </MainContainer>
        </div>
    </div>
    );
}