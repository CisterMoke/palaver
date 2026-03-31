import { useState, useRef, useEffect, useMemo } from "preact/hooks";
import MessageList from "./MessageList";
import MessageInput from "./MessageInput";
import ParticipantsModal from "./ParticipantsModal";
import { fetchChatroomMessages, fetchChatroomParticipants, fetchAgents } from "../api";
import type { ChatMessage, AgentInfo } from "../api";

interface ChatWindowProps {
  chatroomId: string;
}

export default function ChatWindow({ chatroomId }: ChatWindowProps) {
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [text, setText] = useState("");
  const [showParticipants, setShowParticipants] = useState(false);
  const [participantIds, setParticipantIds] = useState<string[]>([]);
  const [agentMap, setAgentMap] = useState<Record<string, AgentInfo>>({});
  const bottomRef = useRef<HTMLDivElement>(null);
  const messagesRef = useRef<ChatMessage[]>([]);
  const redactionFramesRef = useRef<Record<string, number>>({});
  const wsRef = useRef<WebSocket | null>(null);

  const cancelRedaction = (messageId: string) => {
    const frameId = redactionFramesRef.current[messageId];
    if (frameId === undefined) return;
    cancelAnimationFrame(frameId);
    delete redactionFramesRef.current[messageId];
  };

  const cancelAllRedactions = () => {
    Object.values(redactionFramesRef.current).forEach((frameId) => cancelAnimationFrame(frameId));
    redactionFramesRef.current = {};
  };

  const startRedaction = (messageId: string) => {
    cancelRedaction(messageId);

    const message = messagesRef.current.find((entry) => entry.id === messageId);
    if (!message || !message.content) return;

    const originalText = message.content;
    const totalChars = originalText.length;
    if (totalChars === 0) return;

    const FIXED_ANIMATION_MS = 700;
    const MIN_ERASE_CHARS_PER_SECOND = 24;
    const eraseDurationMs = Math.min(
      FIXED_ANIMATION_MS,
      Math.max(1, (totalChars / MIN_ERASE_CHARS_PER_SECOND) * 1000)
    );

    const startedAt = performance.now();

    const animate = (now: number) => {
      const elapsed = now - startedAt;
      const progress = Math.min(1, elapsed / eraseDurationMs);
      const keepChars = Math.max(0, Math.ceil(totalChars * (1 - progress)));

      setMessages((prev) =>
        prev.map((entry) =>
          entry.id === messageId
            ? { ...entry, content: originalText.slice(0, keepChars) }
            : entry
        )
      );

      if (elapsed < FIXED_ANIMATION_MS) {
        redactionFramesRef.current[messageId] = requestAnimationFrame(animate);
      } else {
        setMessages((prev) =>
          prev.map((entry) => (entry.id === messageId ? { ...entry, content: "" } : entry))
        );
        delete redactionFramesRef.current[messageId];
      }
    };

    redactionFramesRef.current[messageId] = requestAnimationFrame(animate);
  };

  useEffect(() => {
    messagesRef.current = messages;
  }, [messages]);

  // Load agent map once
  useEffect(() => {
    fetchAgents()
      .then((agents) => {
        const map: Record<string, AgentInfo> = {};
        agents.forEach((a) => { map[a.id] = a; });
        setAgentMap(map);
      })
      .catch(console.error);
  }, []);

  // Refresh participant list
  const refreshParticipants = () => {
    fetchChatroomParticipants(chatroomId)
      .then(setParticipantIds)
      .catch(console.error);
  };

  // Load history, participants, and connect WS when chatroomId changes
  useEffect(() => {
    let active = true;

    async function load() {
      try {
        const [history, ids] = await Promise.all([
          fetchChatroomMessages(chatroomId),
          fetchChatroomParticipants(chatroomId),
        ]);
        if (active) {
          setMessages(history);
          setParticipantIds(ids);
        }
      } catch (e) {
        console.error("Failed to load history", e);
      }
    }
    load();

    const ws = new WebSocket(`ws://localhost:8000/ws/${chatroomId}`);
    wsRef.current = ws;

    ws.onmessage = (event) => {
      if (!active) return;

      const data = JSON.parse(event.data) as { type?: string; [key: string]: unknown };
      const asString = (value: unknown): string | undefined =>
        typeof value === "string" ? value : undefined;

      if (data.type === "chat_message") {
        setMessages((prev) => {
          const messageId = asString(data.id);
          const exists = messageId ? prev.some((msg) => msg.id === messageId) : false;

          if (exists) {
            return prev.map((msg) => (msg.id === messageId ? { ...msg, status: undefined } : msg));
          }

          return [
            ...prev,
            {
              id: messageId ?? asString(data.timestamp) ?? Date.now().toString(),
              chatroom_id: chatroomId,
              sender: asString(data.sender) ?? "unknown",
              role: data.role === "assistant" || data.role === "system" ? data.role : "user",
              content: asString(data.content) ?? "",
              timestamp: asString(data.timestamp) ?? new Date().toISOString(),
            },
          ];
        });
      } else if (data.type === "agent_response_start") {
        const messageId = asString(data.message_id);
        if (!messageId) return;
        cancelRedaction(messageId);

        setMessages((prev) => [
          ...prev.filter((entry) => entry.id !== messageId),
          {
            id: messageId,
            chatroom_id: chatroomId,
            sender: asString(data.agent_id) ?? "unknown",
            recipient: asString(data.recipient),
            role: "assistant",
            content: "",
            timestamp: new Date().toISOString(),
          }
        ]);
      } else if (data.type === "agent_response_chunk") {
        const messageId = asString(data.message_id);
        if (!messageId) return;
        cancelRedaction(messageId);

        const delta = asString(data.delta) ?? "";
        setMessages((prev) =>
          prev.map((msg) =>
            msg.id === messageId
              ? {
                  ...msg,
                  recipient: asString(data.recipient) ?? msg.recipient,
                  content: msg.content + delta,
                }
              : msg
          )
        );
      } else if (data.type === "agent_response_complete") {
        const messageId = asString(data.message_id);
        if (!messageId) return;
        cancelRedaction(messageId);

        setMessages((prev) =>
          prev.map((msg) =>
            msg.id === messageId
              ? {
                  ...msg,
                  recipient: asString(data.recipient) ?? msg.recipient,
                  content: asString(data.content) ?? msg.content,
                }
              : msg
          )
        );
      } else if (data.type === "agent_response_error") {
        // Display error as a system message in the chat
        setMessages((prev) => [
          ...prev,
          {
            id: `err-${Date.now()}`,
            chatroom_id: chatroomId,
            sender: asString(data.agent_id) ?? "unknown",
            role: "system" as const,
            content: `⚠️ Error: ${data.error}`,
            timestamp: new Date().toISOString(),
            status: "error" as const,
          },
        ]);
      } else if (data.type === "redact_agent_response") {
        const messageId = asString(data.message_id);
        if (!messageId) return;
        startRedaction(messageId);
      }
    };

    return () => {
      active = false;
      cancelAllRedactions();
      ws.close();
    };
  }, [chatroomId]);

  useEffect(() => () => cancelAllRedactions(), []);

  // Auto-scroll to bottom
  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  const sendMessage = async () => {
    if (!text.trim()) return;

    const content = text.trim();
    setText("");

    const tempId = `temp-${Date.now()}`;
    const tempMessage: ChatMessage = {
      id: tempId,
      chatroom_id: chatroomId,
      sender: "ruben",
      role: "user",
      content: content,
      timestamp: new Date().toISOString(),
      status: "sending"
    };

    setMessages((prev) => [...prev, tempMessage]);

    const targets = content.match(/@(\w+)/g)?.map((t) => t.slice(1)) || [];
    console.log(targets)
    console.log(content.match(/@(\w+)/g))

    try {
      const response = await fetch(`http://localhost:8000/api/chatrooms/${chatroomId}/messages`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          sender: "ruben",
          role: "user",
          content: content,
          target_agent_ids: targets.length > 0 ? targets : null
        })
      });
      if (response.ok) {
        const newMessage = await response.json();
        setMessages((prev) => {
          if (prev.some(m => m.id === newMessage.id)) {
            return prev.filter(m => m.id !== tempId);
          }
          return prev.map(msg => msg.id === tempId ? { ...newMessage, status: "sent" } : msg);
        });
      } else {
        setMessages((prev) => prev.map(msg => msg.id === tempId ? { ...msg, status: "error" } : msg));
      }
    } catch (e) {
      console.error("Failed to send message", e);
      setMessages((prev) => prev.map(msg => msg.id === tempId ? { ...msg, status: "error" } : msg));
    }
  };

  const agentNameMap = useMemo(() => {
    const map: Record<string, AgentInfo> = {};
    Object.values(agentMap).forEach((agent) => {
      map[agent.name] = agent;
    });
    return map;
  }, [agentMap]);

  const resolveAgentName = (idOrName: string) => {
    return agentMap[idOrName]?.name ?? agentNameMap[idOrName]?.name ?? idOrName;
  };

  // Resolve participant names from the agent map
  const participantNames = participantIds
    .map((id) => resolveAgentName(id))
    .join(", ");

  return (
    <div className="flex-1 flex flex-col h-full bg-white shadow-sm rounded-lg overflow-hidden m-4">
      {/* Header */}
      <div className="p-4 border-b border-gray-200 bg-gray-50 flex justify-between items-center gap-4">
        <div className="min-w-0">
          <h3 className="font-semibold text-gray-700 leading-tight">Chatroom</h3>
          {participantNames ? (
            <p className="text-xs text-gray-400 truncate mt-0.5">
              👥 {participantNames}
            </p>
          ) : (
            <p className="text-xs text-gray-400 mt-0.5">No participants yet</p>
          )}
        </div>
        <button
          onClick={() => setShowParticipants(true)}
          className="shrink-0 flex items-center gap-1.5 px-3 py-1.5 text-sm bg-gray-100 hover:bg-gray-200 text-gray-600 rounded-lg border-0 transition-colors"
          title="Manage participants"
        >
          <svg xmlns="http://www.w3.org/2000/svg" className="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M17 20h5v-2a3 3 0 00-5.356-1.857M17 20H7m10 0v-2c0-.656-.126-1.283-.356-1.857M7 20H2v-2a3 3 0 015.356-1.857M7 20v-2c0-.656.126-1.283.356-1.857m0 0a5.002 5.002 0 019.288 0M15 7a3 3 0 11-6 0 3 3 0 016 0z" />
          </svg>
          Participants
        </button>
      </div>

      <div className="flex-1 overflow-y-auto p-4 overflow-x-hidden">
        <MessageList messages={messages} resolveAgentName={resolveAgentName} />
        <div ref={bottomRef} />
      </div>
      <div className="p-4 bg-gray-50 border-t border-gray-200">
        <MessageInput value={text} onChange={setText} onSend={sendMessage} />
      </div>

      {showParticipants && (
        <ParticipantsModal
          chatroomId={chatroomId}
          onClose={() => setShowParticipants(false)}
          onChanged={refreshParticipants}
        />
      )}
    </div>
  );
}
