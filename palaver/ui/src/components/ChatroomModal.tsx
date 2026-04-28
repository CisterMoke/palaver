import { useEffect, useState } from "preact/hooks";
import type { TargetedEvent } from "preact";
import { createChatroom, fetchChatroom, setChatroomParticipants, updateChatroom } from "../api";
import type { AgentInfo, RoutingType } from "../api";
import ParticipantsList from "./ParticipantsList";

interface ChatroomModalProps {
  agents: AgentInfo[];
  chatroomId?: string | null;
  onClose: () => void;
  onSuccess: (chatroomId: string) => void | Promise<void>;
}

export default function ChatroomModal({
  agents,
  chatroomId,
  onClose,
  onSuccess,
}: ChatroomModalProps) {
  const isEditing = !!chatroomId;
  const [name, setName] = useState("");
  const [selectedAgentIds, setSelectedAgentIds] = useState<string[]>([]);
  const [routingType, setRoutingType] = useState<RoutingType>("round_robin");
  const [limitSubagentCalls, setLimitSubagentCalls] = useState(true);
  const [maxSubagentCalls, setMaxSubagentCalls] = useState(3);
  const [maxMessageHistory, setMaxMessageHistory] = useState(20);
  const [initializing, setInitializing] = useState(isEditing);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => {
    let active = true;

    if (!chatroomId) {
      setName("");
      setSelectedAgentIds([]);
      setRoutingType("round_robin");
      setLimitSubagentCalls(true);
      setMaxSubagentCalls(3);
      setMaxMessageHistory(20);
      setError("");
      setInitializing(false);
      return () => {
        active = false;
      };
    }

    setInitializing(true);
    setError("");

    fetchChatroom(chatroomId)
      .then((chatroom) => {
        if (!active) return;
        setName(chatroom.name);
        setSelectedAgentIds(chatroom.agents);
        setRoutingType(chatroom.routing_type);
        setLimitSubagentCalls(chatroom.limit_subagent_calls);
        setMaxSubagentCalls(chatroom.max_subagent_calls);
        setMaxMessageHistory(chatroom.max_message_history);
      })
      .catch((err) => {
        if (!active) return;
        setError(err instanceof Error ? err.message : "Failed to load chatroom");
      })
      .finally(() => {
        if (!active) return;
        setInitializing(false);
      });

    return () => {
      active = false;
    };
  }, [chatroomId]);

  const handleSubmit = async (event: TargetedEvent) => {
    event.preventDefault();

    const trimmedName = name.trim();
    if (!trimmedName) {
      setError("Name is required");
      return;
    }

    if (initializing) return;

    setLoading(true);
    setError("");

    try {
      const payload = {
        name: trimmedName,
        routing_type: routingType,
        limit_subagent_calls: limitSubagentCalls,
        max_subagent_calls: maxSubagentCalls,
        max_message_history: maxMessageHistory,
      };

      let roomId: string;
      if (chatroomId) {
        await updateChatroom(chatroomId, payload);
        roomId = chatroomId;
      } else {
        const room = await createChatroom(payload);
        roomId = room.id;
      }

      await setChatroomParticipants(roomId, selectedAgentIds);

      await onSuccess(roomId);
      onClose();
    } catch (err) {
      setError(
        err instanceof Error
          ? err.message
          : chatroomId
          ? "Failed to update chatroom"
          : "Failed to create chatroom"
      );
    } finally {
      setLoading(false);
    }
  };

  return (
    <div
      className="fixed inset-0 bg-black/50 flex items-start justify-center z-50 p-4 overflow-y-auto"
    >
      <div className="bg-white rounded-xl shadow-2xl w-full max-w-lg overflow-hidden max-h-[calc(100vh-2rem)] flex flex-col">
        <div className="flex items-center justify-between px-6 py-4 border-b border-gray-200">
          <h2 className="text-lg font-semibold text-gray-800">
            {isEditing ? "Edit Chatroom" : "Create Chatroom"}
          </h2>
        </div>

        <form onSubmit={handleSubmit} className="flex-1 flex flex-col overflow-hidden">
          <div className="p-6 flex-1 overflow-y-auto flex flex-col gap-4">
            {error && (
              <div className="p-3 bg-red-100 border border-red-300 text-red-700 rounded text-sm">
                {error}
              </div>
            )}

            <div>
            <label htmlFor="chatroom-name-input" className="block text-sm font-medium text-gray-700 mb-1">
              Name *
            </label>
            <input
              id="chatroom-name-input"
              type="text"
              className="w-full border rounded p-2 focus:ring-2 focus:ring-blue-500 focus:outline-none"
              value={name}
              onChange={(event) => setName(event.currentTarget.value)}
              placeholder="e.g. Product Team"
              required
               disabled={loading || initializing}
            />
            </div>

            <div>
            <label htmlFor="chatroom-routing-type-input" className="block text-sm font-medium text-gray-700 mb-1">
              Routing type
            </label>
            <select
              id="chatroom-routing-type-input"
              className="w-full border rounded p-2 focus:ring-2 focus:ring-blue-500 focus:outline-none"
              value={routingType}
              onChange={(event) => setRoutingType(event.currentTarget.value as RoutingType)}
               disabled={loading || initializing}
            >
              <option value="round_robin">Round robin</option>
              <option value="autonomous">Autonomous</option>
              <option value="single">Single</option>
              <option value="incognito">Incognito</option>
            </select>
            </div>

            <div className="flex items-center justify-between rounded border border-gray-200 px-3 py-2">
            <label htmlFor="chatroom-limit-subagent-calls" className="text-sm font-medium text-gray-700">
              Limit subagent calls
            </label>
            <input
              id="chatroom-limit-subagent-calls"
              type="checkbox"
              checked={limitSubagentCalls}
              onChange={(event) => setLimitSubagentCalls(event.currentTarget.checked)}
              className="h-4 w-4"
               disabled={loading || initializing}
            />
            </div>

            <div>
            <label htmlFor="chatroom-max-subagent-calls-input" className="block text-sm font-medium text-gray-700 mb-1">
              Max subagent calls
            </label>
            <input
              id="chatroom-max-subagent-calls-input"
              type="number"
              min={1}
              className="w-full border rounded p-2 focus:ring-2 focus:ring-blue-500 focus:outline-none disabled:bg-gray-100 disabled:text-gray-500"
              value={maxSubagentCalls}
              onChange={(event) => setMaxSubagentCalls(Math.max(1, Number(event.currentTarget.value || 1)))}
               disabled={loading || initializing || !limitSubagentCalls}
            />
            </div>

            <div>
            <label htmlFor="chatroom-max-message-history-input" className="block text-sm font-medium text-gray-700 mb-1">
              Max message history
            </label>
            <input
              id="chatroom-max-message-history-input"
              type="number"
              min={1}
              className="w-full border rounded p-2 focus:ring-2 focus:ring-blue-500 focus:outline-none"
              value={maxMessageHistory}
              onChange={(event) => setMaxMessageHistory(Math.max(1, Number(event.currentTarget.value || 1)))}
               disabled={loading || initializing}
            />
            </div>

            <div>
              <div className="flex items-center justify-between mb-2">
                <label className="block text-sm font-medium text-gray-700">Add agents</label>
                <span className="text-xs text-gray-500">{selectedAgentIds.length} selected</span>
              </div>

              <div className="auto border border-gray-200 rounded p-2">
                <ParticipantsList
                  agents={agents}
                  initialSelectedIds={selectedAgentIds}
                  disabled={loading || initializing}
                  emptyText="No agents available yet."
                  onSelectionChange={setSelectedAgentIds}
                />
              </div>
            </div>
          </div>

          <div className="px-6 py-4 flex justify-end gap-3 border-t border-gray-200">
            <button
              type="button"
              onClick={onClose}
              className="px-4 py-2 rounded"
               disabled={loading || initializing}
            >
              Cancel
            </button>
            <button
              type="submit"
              className="px-4 py-2 rounded disabled:opacity-50"
               disabled={loading || initializing}
            >
              {initializing
                ? "Loading..."
                : loading
                ? chatroomId
                  ? "Saving..."
                  : "Creating..."
                : chatroomId
                ? "Save Chatroom"
                : "Create Chatroom"}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}
