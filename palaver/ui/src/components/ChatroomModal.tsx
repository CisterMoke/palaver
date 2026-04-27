import { useEffect, useState } from "preact/hooks";
import type { TargetedEvent } from "preact";
import { createChatroom, setChatroomParticipants, updateChatroom } from "../api";
import type { AgentInfo, Chatroom, RoutingType } from "../api";
import ParticipantsList from "./ParticipantsList";

interface CreateChatroomModalProps {
  agents: AgentInfo[];
  existingChatroom?: Chatroom | null;
  onClose: () => void;
  onSuccess: (chatroomId: string) => void | Promise<void>;
}

export default function ChatroomModal({
  agents,
  existingChatroom,
  onClose,
  onSuccess,
}: CreateChatroomModalProps) {
  const [name, setName] = useState(existingChatroom?.name ?? "");
  const [selectedAgentIds, setSelectedAgentIds] = useState<string[]>(existingChatroom?.agents ?? []);
  const [routingType, setRoutingType] = useState<RoutingType>(existingChatroom?.routing_type ?? "round_robin");
  const [limitSubagentCalls, setLimitSubagentCalls] = useState(existingChatroom?.limit_subagent_calls ?? true);
  const [maxSubagentCalls, setMaxSubagentCalls] = useState(existingChatroom?.max_subagent_calls ?? 3);
  const [maxMessageHistory, setMaxMessageHistory] = useState(existingChatroom?.max_message_history ?? 20);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => {
    setName(existingChatroom?.name ?? "");
    setSelectedAgentIds(existingChatroom?.agents ?? []);
    setRoutingType(existingChatroom?.routing_type ?? "round_robin");
    setLimitSubagentCalls(existingChatroom?.limit_subagent_calls ?? true);
    setMaxSubagentCalls(existingChatroom?.max_subagent_calls ?? 3);
    setMaxMessageHistory(existingChatroom?.max_message_history ?? 20);
  }, [existingChatroom]);

  const handleSubmit = async (event: TargetedEvent) => {
    event.preventDefault();

    const trimmedName = name.trim();
    if (!trimmedName) {
      setError("Name is required");
      return;
    }

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
      if (existingChatroom) {
        await updateChatroom(existingChatroom.id, payload);
        roomId = existingChatroom.id;
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
          : existingChatroom
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
      onClick={(event) => event.target === event.currentTarget && onClose()}
    >
      <div className="bg-white rounded-xl shadow-2xl w-full max-w-lg overflow-hidden max-h-[calc(100vh-2rem)] flex flex-col">
        <div className="flex items-center justify-between px-6 py-4 border-b border-gray-200">
          <h2 className="text-lg font-semibold text-gray-800">
            {existingChatroom ? "Edit Chatroom" : "Create Chatroom"}
          </h2>
          <button
            type="button"
            onClick={onClose}
            className="transition-colors p-0 border-0 bg-transparent text-xl leading-none"
            title="Close"
          >
            ✕
          </button>
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
              disabled={loading}
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
              disabled={loading}
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
              disabled={loading}
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
              disabled={loading || !limitSubagentCalls}
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
              disabled={loading}
            />
            </div>

            <div>
              <div className="flex items-center justify-between mb-2">
                <label className="block text-sm font-medium text-gray-700">Add agents</label>
                <span className="text-xs text-gray-500">{selectedAgentIds.length} selected</span>
              </div>

              <div className="max-h-44 overflow-y-auto border border-gray-200 rounded p-2">
                <ParticipantsList
                  agents={agents}
                  initialSelectedIds={selectedAgentIds}
                  disabled={loading}
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
              disabled={loading}
            >
              Cancel
            </button>
            <button
              type="submit"
              className="px-4 py-2 rounded disabled:opacity-50"
              disabled={loading}
            >
              {loading
                ? existingChatroom
                  ? "Saving..."
                  : "Creating..."
                : existingChatroom
                ? "Save Chatroom"
                : "Create Chatroom"}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}
