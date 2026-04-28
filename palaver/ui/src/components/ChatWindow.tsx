import { useState, useRef, useEffect, useMemo, useCallback } from "preact/hooks";
import MessageList from "./MessageList";
import MessageInput from "./MessageInput";
import ParticipantsModal from "./ParticipantsModal";
import { fetchChatroomMessages, fetchChatroomParticipants, fetchAgents } from "../api";
import type { SimpleMessage, AgentInfo, Chatroom } from "../api";

interface ChatWindowProps {
  chatroom: Chatroom;
}

type PendingMessage = {
  tempId: string;
  payload: string;
  attempts: number;
};

type AgentActivity = {
  active: boolean;
  writing: boolean;
  order: number;
};

type ConnectionStatus = "connecting" | "connected" | "reconnecting" | "running";
type SocketEventData = { type?: string; [key: string]: unknown };

const MAX_PENDING_SEND_ATTEMPTS = 5;
const RECONNECT_BASE_DELAY_MS = 500;
const RECONNECT_MAX_DELAY_MS = 10_000;

const asString = (value: unknown): string | undefined =>
  typeof value === "string" ? value : undefined;

export default function ChatWindow({ chatroom }: ChatWindowProps) {
  const [messages, setMessages] = useState<SimpleMessage[]>([]);
  const [text, setText] = useState("");
  const [showParticipants, setShowParticipants] = useState(false);
  const [participantIds, setParticipantIds] = useState<string[]>([]);
  const [activeAgentLoops, setActiveAgentLoops] = useState(0);
  const [agentActivityById, setAgentActivityById] = useState<Record<string, AgentActivity>>({});
  const [agentMap, setAgentMap] = useState<Record<string, AgentInfo>>({});
  const [connectionStatus, setConnectionStatus] = useState<ConnectionStatus>("connecting");
  const [reconnectAttemptDisplay, setReconnectAttemptDisplay] = useState(0);
  const bottomRef = useRef<HTMLDivElement>(null);
  const redactionFramesRef = useRef<Record<string, number>>({});
  const wsRef = useRef<WebSocket | null>(null);
  const reconnectTimerRef = useRef<number | null>(null);
  const reconnectAttemptRef = useRef(0);
  const pendingMessagesRef = useRef<PendingMessage[]>([]);
  const agentActivityOrderRef = useRef(0);
  const chatroomId = chatroom.id;

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

  const appendSystemMessage = (content: string) => {
    setMessages((prev) => [
      ...prev,
      {
        id: `sys-${Date.now()}-${Math.random().toString(36).slice(2, 8)}`,
        sender: "SYSTEM",
        role: "system",
        content,
      },
    ]);
  };

  const setAgentTypingActive = (agentId: string) => {
    setAgentActivityById((prev) => {
      const existing = prev[agentId];
      const order = existing?.order ?? ++agentActivityOrderRef.current;
      return {
        ...prev,
        [agentId]: {
          active: true,
          writing: false,
          order,
        },
      };
    });
  };

  const setAgentWritingState = (agentId: string, writing: boolean) => {
    setAgentActivityById((prev) => {
      const existing = prev[agentId];
      const order = existing?.order ?? ++agentActivityOrderRef.current;
      return {
        ...prev,
        [agentId]: {
          active: existing?.active ?? true,
          writing,
          order,
        },
      };
    });
  };

  const clearAgentTypingState = (agentId: string) => {
    setAgentActivityById((prev) => {
      const existing = prev[agentId];
      const order = existing?.order ?? ++agentActivityOrderRef.current;
      return {
        ...prev,
        [agentId]: {
          active: false,
          writing: false,
          order,
        },
      };
    });
  };

  const handleChatMessageEvent = (data: SocketEventData) => {
    setMessages((prev) => {
      const messageId = asString(data.id)!;
      const sender = asString(data.sender) ?? "unknown";
      const role = data.role === "assistant" || data.role === "system" ? data.role : "user";
      const content = asString(data.content) ?? "";
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
          sender,
          role,
          content,
          status: "sent",
        };
        return updated;
      }

      return [
        ...prev,
        {
          id: messageId,
          sender,
          role,
          content,
        },
      ];
    });
  };

  const handleAgentResponseStartEvent = (data: SocketEventData) => {
    const messageId = asString(data.message_id);
    if (!messageId) return;

    const agentId = asString(data.agent_id);
    if (agentId) {
      setAgentWritingState(agentId, true);
    }

    setMessages((prev) => [
      ...prev.filter((entry) => entry.id !== messageId),
      {
        id: messageId,
        sender: asString(data.agent_id) ?? "unknown",
        recipients: (
          asString(data.recipient) ? [asString(data.recipient)!] : []
        ),
        role: "assistant",
        content: "",
      }
    ]);
  };

  const handleAgentResponseChunkEvent = (data: SocketEventData) => {
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
  };

  const handleAgentResponseCompleteEvent = (data: SocketEventData) => {
    const messageId = asString(data.message_id);
    if (!messageId) return;

    const agentId = asString(data.agent_id);
    if (agentId) {
      setAgentWritingState(agentId, false);
    }

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
  };

  const handleAgentResponseErrorEvent = (data: SocketEventData) => {
    const agentId = asString(data.agent_id);
    if (agentId) {
      setAgentWritingState(agentId, false);
    }

    setMessages((prev) => [
      ...prev,
      {
        id: `err-${Date.now()}`,
        sender: asString(data.agent_id) ?? "unknown",
        role: "system" as const,
        content: `⚠️ Error: ${data.error}`,
        status: "error" as const,
      },
    ]);
  };

  const handleRedactAgentResponseEvent = (data: SocketEventData) => {
    const messageId = asString(data.message_id);
    if (!messageId) return;
    startRedaction(messageId);
  };

  const handleCommandResultEvent = (data: SocketEventData) => {
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
  };

  const handleAgentLoopStartEvent = () => {
    setActiveAgentLoops((current) => current + 1);
    setConnectionStatus("running");
  };

  const handleAgentLoopEndEvent = () => {
    setActiveAgentLoops((current) => Math.max(0, current - 1));
    if (activeAgentLoops <= 0) {
      setConnectionStatus("connected")
    }
  };

  const handleAgentStartEvent = (data: SocketEventData) => {
    const agentId = asString(data.agent_id);
    if (!agentId) return;
    setAgentTypingActive(agentId);
  };

  const handleAgentEndEvent = (data: SocketEventData) => {
    const agentId = asString(data.agent_id);
    if (!agentId) return;
    clearAgentTypingState(agentId);
  };

  const handleSystemMessageEvent = (data: SocketEventData) => {
    const message = asString(data.message);
    if (!message) return;

    appendSystemMessage(message);

    const subType = asString(data.sub_type);
    if (subType === "agent_left") {
      const agentId = asString(data.agent_id);
      if (agentId) {
        setParticipantIds((prev) => prev.filter((id) => id !== agentId));
      }
    }
  };

  const handleSocketEvent = (data: SocketEventData) => {
    if (data.type === "chat_message") {
      handleChatMessageEvent(data);
    } else if (data.type === "agent_response_start") {
      handleAgentResponseStartEvent(data);
    } else if (data.type === "agent_response_chunk") {
      handleAgentResponseChunkEvent(data);
    } else if (data.type === "agent_response_complete") {
      handleAgentResponseCompleteEvent(data);
    } else if (data.type === "agent_response_error") {
      handleAgentResponseErrorEvent(data);
    } else if (data.type === "redact_agent_response") {
      handleRedactAgentResponseEvent(data);
    } else if (data.type === "command_result") {
      handleCommandResultEvent(data);
    } else if (data.type === "agent_loop_start") {
      handleAgentLoopStartEvent();
    } else if (data.type === "agent_loop_end") {
      handleAgentLoopEndEvent();
    } else if (data.type === "agent_start" || data.type === "agent_start_event") {
      handleAgentStartEvent(data);
    } else if (data.type === "agent_end" || data.type === "agent_end_event") {
      handleAgentEndEvent(data);
    } else if (data.type === "system_message") {
      handleSystemMessageEvent(data);
    }
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
  const refreshParticipants = useCallback(() => {
    fetchChatroomParticipants(chatroomId)
      .then(setParticipantIds)
      .catch(console.error);
  }, [chatroomId]);

  useEffect(() => {
    const handleChatroomUpdated = (event: Event) => {
      const detail = (event as CustomEvent<{ chatroomId?: string }>).detail;
      if (!detail?.chatroomId || detail.chatroomId === chatroomId) {
        refreshParticipants();
      }
    };

    window.addEventListener("chatroom-updated", handleChatroomUpdated as EventListener);
    return () => {
      window.removeEventListener("chatroom-updated", handleChatroomUpdated as EventListener);
    };
  }, [chatroomId, refreshParticipants]);

  // Load history, participants, and connect WS when chatroomId changes
  useEffect(() => {
    let active = true;
    reconnectAttemptRef.current = 0;
    setActiveAgentLoops(0);
    setAgentActivityById({});
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
        const data = JSON.parse(event.data) as SocketEventData;
        handleSocketEvent(data);
      };

      ws.onerror = () => {
        ws.close();
      };

      ws.onclose = () => {
        if (!active) return;
        setActiveAgentLoops(0);
        setAgentActivityById({});
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
    const tempMessage: SimpleMessage = {
      id: tempId,
      sender: "USER",
      role: "user",
      content: content,
      recipients: targets.length > 0 ? targets : undefined,
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
    : connectionStatus === "running"
      ? "Running..."
      : connectionStatus === "connecting"
        ? "Connecting..."
        : `Reconnecting${reconnectAttemptDisplay > 0 ? ` (${reconnectAttemptDisplay})` : ""}...`;

  const connectionDotClass = connectionStatus === "connected"
    ? "bg-green-500"
    : connectionStatus === "running"
      ? "bg-blue-500"
      : connectionStatus === "connecting"
        ? "bg-yellow-500"
        : "bg-orange-500";

  const typingAgentNames = useMemo(() => {
    const sortedTypingAgents = Object.entries(agentActivityById)
      .filter(([, activity]) => activity.active && !activity.writing)
      .sort((a, b) => a[1].order - b[1].order)
      .map(([agentId]) => resolveAgentName(agentId));
    return sortedTypingAgents;
  }, [agentActivityById, resolveAgentName]);

  const typingLabel = useMemo(() => {
    if (typingAgentNames.length === 0) return null;
    if (typingAgentNames.length === 1) return `${typingAgentNames[0]} thinking...`;
    if (typingAgentNames.length === 2) return `${typingAgentNames[0]} and ${typingAgentNames[1]} thinking...`;
    return `${typingAgentNames[0]}, ${typingAgentNames[1]} +${typingAgentNames.length - 2} thinking...`;
  }, [typingAgentNames]);

  return (
    <div className="flex-1 flex flex-col h-full bg-white shadow-sm rounded-lg overflow-hidden m-1">
      {/* Header */}
      <div className="px-4 py-1 border-b border-gray-200 bg-gray-50 flex justify-between items-center gap-4">
        <div className="min-w-0 justify-items-start">
          <h3 className="font-semibold text-gray-700 leading-tight">
            Chatroom: {chatroom.name}
            <span className="text-xs"> [id={chatroom.id}, routing_type={chatroom.routing_type}]</span>
          </h3>
          <div className="flex gap-2">
            {participantNames ? (
              <span className="text-xs text-gray-400 truncate mt-0.5">
                👥 {participantNames}
              </span>
            ) : (
              <span className="text-xs text-gray-400 mt-0.5">No participants yet</span>
            )}
          </div>
        </div>
        <div className="shrink-0 flex flex-col items-end gap-1 text-black">
          <div className="flex items-center gap-1.5 text-xs text-gray-500">
            <span className={`h-2 w-2 rounded-full ${connectionDotClass}`} />
            <span>{connectionLabel}</span>
          </div>
        </div>
      </div>

      <div className="flex-1 overflow-y-auto p-4 overflow-x-hidden">
        <MessageList messages={messages} resolveAgentName={resolveAgentName} />
        <div ref={bottomRef} />
      </div>
      {typingLabel && (
        <div className="mx-3 mb-1 flex items-center gap-1.5 text-xs text-gray-500">
          <span className="h-2 w-2 rounded-full bg-gray-400 animate-pulse" />
          <span>{typingLabel}</span>
        </div>
      )}
      <div className="p-1 bg-gray-50 border-t border-gray-200">
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
