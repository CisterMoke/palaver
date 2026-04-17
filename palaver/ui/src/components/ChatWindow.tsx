import { useState, useRef, useEffect, useMemo } from "preact/hooks";
import MessageList from "./MessageList";
import MessageInput from "./MessageInput";
import ParticipantsModal from "./ParticipantsModal";
import { fetchChatroomMessages, fetchChatroomParticipants, fetchAgents } from "../api";
import type { ChatMessage, AgentInfo } from "../api";

interface ChatWindowProps {
  chatroomId: string;
}

type PendingMessage = {
  tempId: string;
  payload: string;
  attempts: number;
};

type ConnectionStatus = "connecting" | "connected" | "reconnecting";

const MAX_PENDING_SEND_ATTEMPTS = 5;
const RECONNECT_BASE_DELAY_MS = 500;
const RECONNECT_MAX_DELAY_MS = 10_000;

export default function ChatWindow({ chatroomId }: ChatWindowProps) {
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [text, setText] = useState("");
  const [showParticipants, setShowParticipants] = useState(false);
  const [participantIds, setParticipantIds] = useState<string[]>([]);
  const [agentMap, setAgentMap] = useState<Record<string, AgentInfo>>({});
  const [connectionStatus, setConnectionStatus] = useState<ConnectionStatus>("connecting");
  const [reconnectAttemptDisplay, setReconnectAttemptDisplay] = useState(0);
  const bottomRef = useRef<HTMLDivElement>(null);
  const redactionFramesRef = useRef<Record<string, number>>({});
  const wsRef = useRef<WebSocket | null>(null);
  const reconnectTimerRef = useRef<number | null>(null);
  const reconnectAttemptRef = useRef(0);
  const pendingMessagesRef = useRef<PendingMessage[]>([]);

  const markMessagesAsError = (messageIds: string[]) => {
    if (messageIds.length === 0) return;
    const ids = new Set(messageIds);
    setMessages((prev) =>
      prev.map((msg) => (ids.has(msg.id) ? { ...msg, status: "error" } : msg))
    );
  };

  const bumpPendingAttemptsAndMarkFailures = () => {
    const failedIds: string[] = [];
    const survivors: PendingMessage[] = [];

    for (const pending of pendingMessagesRef.current) {
      const attempts = pending.attempts + 1;
      if (attempts >= MAX_PENDING_SEND_ATTEMPTS) {
        failedIds.push(pending.tempId);
      } else {
        survivors.push({ ...pending, attempts });
      }
    }

    pendingMessagesRef.current = survivors;
    markMessagesAsError(failedIds);
  };

  const startRedaction = (messageId: string) => {
    const message = messages.find((entry) => entry.id === messageId);
    if (!message || !message.content) return;

    const originalText = message.content;
    const totalChars = originalText.length;
    if (totalChars === 0) return;

    const FIXED_ANIMATION_MS = 1000;
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
          prev.filter((entry) => (entry.id !== messageId))
        );
        delete redactionFramesRef.current[messageId];
      }
    };

    redactionFramesRef.current[messageId] = requestAnimationFrame(animate);
  };

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
    reconnectAttemptRef.current = 0;
    setReconnectAttemptDisplay(0);
    setConnectionStatus("connecting");

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

    const scheduleReconnect = () => {
      if (!active) return;
      if (reconnectTimerRef.current !== null) {
        window.clearTimeout(reconnectTimerRef.current);
      }
      const delay = Math.min(
        RECONNECT_MAX_DELAY_MS,
        RECONNECT_BASE_DELAY_MS * (2 ** reconnectAttemptRef.current)
      );
      reconnectAttemptRef.current += 1;
      setReconnectAttemptDisplay(reconnectAttemptRef.current);
      setConnectionStatus("reconnecting");
      reconnectTimerRef.current = window.setTimeout(connect, delay);
    };

    const flushPendingMessages = (ws: WebSocket) => {
      if (pendingMessagesRef.current.length === 0) return;

      const queue = [...pendingMessagesRef.current];
      pendingMessagesRef.current = [];
      const failedIds: string[] = [];

      for (const pending of queue) {
        try {
          ws.send(pending.payload);
        } catch {
          const attempts = pending.attempts + 1;
          if (attempts >= MAX_PENDING_SEND_ATTEMPTS) {
            failedIds.push(pending.tempId);
          } else {
            pendingMessagesRef.current.push({ ...pending, attempts });
          }
        }
      }

      markMessagesAsError(failedIds);
    };

    const connect = () => {
      if (!active) return;

      setConnectionStatus(reconnectAttemptRef.current > 0 ? "reconnecting" : "connecting");

      const ws = new WebSocket(`ws://localhost:8000/ws/${chatroomId}`);
      wsRef.current = ws;

      ws.onopen = () => {
        reconnectAttemptRef.current = 0;
        setReconnectAttemptDisplay(0);
        setConnectionStatus("connected");
        flushPendingMessages(ws);
      };

      ws.onmessage = (event) => {
        if (!active) return;

        const data = JSON.parse(event.data) as { type?: string; [key: string]: unknown };
        const asString = (value: unknown): string | undefined =>
          typeof value === "string" ? value : undefined;

        if (data.type === "chat_message") {
          setMessages((prev) => {
            const messageId = asString(data.id);
            const sender = asString(data.sender) ?? "unknown";
            const role = data.role === "assistant" || data.role === "system" ? data.role : "user";
            const content = asString(data.content) ?? "";
            const timestamp = asString(data.timestamp) ?? new Date().toISOString();
            const exists = messageId ? prev.some((msg) => msg.id === messageId) : false;

            if (exists) {
              return prev.map((msg) => (msg.id === messageId ? { ...msg, status: "sent" } : msg));
            }

            const pendingIndex = prev.findIndex((msg) =>
              msg.status === "sending"
              && msg.role === "user"
              && msg.sender === sender
              && msg.content === content
            );

            if (pendingIndex !== -1) {
              const updated = [...prev];
              const current = updated[pendingIndex];
              updated[pendingIndex] = {
                ...current,
                id: messageId ?? current.id,
                chatroom_id: chatroomId,
                sender,
                role,
                content,
                timestamp,
                status: "sent",
              };
              return updated;
            }

            return [
              ...prev,
              {
                id: messageId ?? timestamp ?? Date.now().toString(),
                chatroom_id: chatroomId,
                sender,
                role,
                content,
                timestamp,
              },
            ];
          });
        } else if (data.type === "agent_response_start") {
          const messageId = asString(data.message_id);
          if (!messageId) return;

          setMessages((prev) => [
            ...prev.filter((entry) => entry.id !== messageId),
            {
              id: messageId,
              chatroom_id: chatroomId,
              sender: asString(data.agent_id) ?? "unknown",
              recipients: (
                asString(data.recipient) ? [asString(data.recipient)!] : []
              ),
              role: "assistant",
              content: "",
              timestamp: new Date().toISOString(),
            }
          ]);
        } else if (data.type === "agent_response_chunk") {
          const messageId = asString(data.message_id);
          if (!messageId) return;

          const delta = asString(data.delta) ?? "";
          setMessages((prev) =>
            prev.map((msg) =>
              msg.id === messageId
                ? {
                    ...msg,
                    recipients: (
                      asString(data.recipient) ? [asString(data.recipient)!] : msg.recipients
                    ),
                    content: msg.content + delta,
                  }
                : msg
            )
          );
        } else if (data.type === "agent_response_complete") {
          const messageId = asString(data.message_id);
          if (!messageId) return;

          setMessages((prev) =>
            prev.map((msg) =>
              msg.id === messageId
                ? {
                    ...msg,
                    recipients: (
                      asString(data.recipient) ? [asString(data.recipient)!] : msg.recipients
                    ),
                    content: asString(data.content) ?? msg.content,
                  }
                : msg
            )
          );
        } else if (data.type === "agent_response_error") {
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
        } else if (data.type === "command_result") {
          const status = asString(data.status);
          const name = asString(data.name);
          const payload = (typeof data.payload === "object" && data.payload !== null)
            ? data.payload as Record<string, unknown>
            : null;

          if (status === "ok") {
            fetchChatroomMessages(chatroomId)
              .then(setMessages)
              .catch((error) => console.error("Failed to refresh messages after slash command", error));

            if (name === "undo") {
              const restoreValue = payload?.restore_input;
              if (typeof restoreValue === "string") {
                setText(restoreValue);
              }
            }
            return;
          }

          console.error("Slash command failed:", asString(data.error) ?? "Unknown error");
        }
      };

      ws.onerror = () => {
        ws.close();
      };

      ws.onclose = () => {
        if (!active) return;
        bumpPendingAttemptsAndMarkFailures();
        scheduleReconnect();
      };
    };

    connect();

    return () => {
      active = false;
      if (reconnectTimerRef.current !== null) {
        window.clearTimeout(reconnectTimerRef.current);
      }
      wsRef.current?.close();
    };
  }, [chatroomId]);

  // Auto-scroll to bottom
  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  const sendMessage = async () => {
    if (!text.trim()) return;

    const content = text.trim();
    setText("");

    if (content.startsWith("/")) {
      const [commandName, ...rawArgs] = content.slice(1).trim().split(/\s+/).filter(Boolean);
      if (!commandName) return;

      const commandPayload = JSON.stringify({
        type: "slash_command",
        data: {
          name: commandName,
          args: rawArgs.length > 0 ? { raw: rawArgs.join(" ") } : {},
        },
      });

      try {
        const ws = wsRef.current;
        if (!ws || ws.readyState !== WebSocket.OPEN) {
          throw new Error("WebSocket is not connected");
        }
        ws.send(commandPayload);
      } catch (e) {
        console.error("Failed to send slash command", e);
        setText(content);
      }
      return;
    }
    
    const targets = content.match(/@(\w+)/g)?.map((t) => t.slice(1)) || [];

    const tempId = `temp-${Date.now()}`;
    const tempMessage: ChatMessage = {
      id: tempId,
      chatroom_id: chatroomId,
      sender: "USER",
      role: "user",
      content: content,
      recipients: targets.length > 0 ? targets : undefined,
      timestamp: new Date().toISOString(),
      status: "sending"
    };
    setMessages((prev) => [...prev, tempMessage]);

    const payload = JSON.stringify({
      type: "user_message",
      data: {
        sender: tempMessage.sender,
        role: tempMessage.role,
        content,
        recipients: tempMessage.recipients,
      }
    });


    try {
      const ws = wsRef.current;
      if (!ws || ws.readyState !== WebSocket.OPEN) {
        pendingMessagesRef.current.push({ tempId, payload, attempts: 0 });
        return;
      }

      ws.send(payload);
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

  const connectionLabel = connectionStatus === "connected"
    ? "Live"
    : connectionStatus === "connecting"
      ? "Connecting..."
      : `Reconnecting${reconnectAttemptDisplay > 0 ? ` (${reconnectAttemptDisplay})` : ""}...`;

  const connectionDotClass = connectionStatus === "connected"
    ? "bg-green-500"
    : connectionStatus === "connecting"
      ? "bg-yellow-500"
      : "bg-orange-500";

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
        <div className="shrink-0 flex flex-col items-end gap-1">
          <div className="flex items-center gap-1.5 text-xs text-gray-500">
            <span className={`h-2 w-2 rounded-full ${connectionDotClass}`} />
            <span>{connectionLabel}</span>
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
