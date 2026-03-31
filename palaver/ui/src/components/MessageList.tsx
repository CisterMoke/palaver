import Message from "./Message";
import type { ChatMessage } from "../api";

interface MessageListProps {
  messages: ChatMessage[];
  resolveAgentName: (idOrName: string) => string;
}

export default function MessageList({ messages, resolveAgentName }: MessageListProps) {
  return (
    <div className="flex-1 flex flex-col gap-2">
      {messages.map((msg) => {
        const sender = resolveAgentName(msg.sender);
        const recipient = msg.recipient && msg.recipient.toUpperCase() !== "USER"
          ? resolveAgentName(msg.recipient)
          : undefined;

        return (
          <Message
            key={msg.id}
            text={msg.content}
            sender={sender}
            recipient={recipient}
            role={msg.role}
            status={msg.status}
          />
        );
      })}
    </div>
  );
}
