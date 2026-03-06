import Message from "./Message";
import type { ChatMessage } from "../api";

interface MessageListProps {
  messages: ChatMessage[];
}

export default function MessageList({ messages }: MessageListProps) {
  return (
    <div className="flex-1 flex flex-col gap-2">
      {messages.map((msg) => (
        <Message key={msg.id} text={msg.content} sender={msg.sender} role={msg.role} status={msg.status} />
      ))}
    </div>
  );
}