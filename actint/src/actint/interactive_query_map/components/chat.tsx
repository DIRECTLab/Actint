import React, { useEffect, useState } from 'react';
import '@chatscope/chat-ui-kit-styles/dist/default/styles.css';
import { socket } from "@/defaults/web_socket";

import {
MainContainer,
ChatContainer,
MessageList,
Message,
MessageInput,
TypingIndicator,
} from '@chatscope/chat-ui-kit-react';


type Props = {  
    setMapCenter: React.Dispatch<React.SetStateAction<[number, number]>>,
    setMapZoom: React.Dispatch<React.SetStateAction<number>>,
}




export function Chat({ setMapCenter, setMapZoom }: Props) {
const [messages, setMessages] = useState<any[]>([]);
const [isTyping, setIsTyping] = useState(false);

const handleSendMessage = (messageText: string) => {
    const newMessage = {
        message: messageText,
        sentTime: 'just now',
        sender: 'user',
        direction: 'outgoing',
        position: 'single',
    };

    socket.emit("recieve_message", newMessage);

    //It may be a good idea for the future to implement chat storage so store chats.

    //send a message to the server and wait for a response.

    setMessages([...messages, newMessage]);
    setIsTyping(true);

};
useEffect(() => {
    socket.on("send_response", (data) => {
        setIsTyping(false);
        console.log(data);
        setMessages((prev) => [...prev, data]);
        setIsTyping(false);
    });

    socket.on("set_map_position", (data) => {
        console.log("set map position", data);
        setMapCenter([data.lat, data.lon]);
        setMapZoom(data.zoom);
    })
}, []);


return (
    <div style={{ position: 'relative', height: '1000px', width: '25%' }}>
        <MainContainer>
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
                    placeholder="Type message here..."
                    onSend={handleSendMessage}
                />
            </ChatContainer>
        </MainContainer>
    </div>
);
}