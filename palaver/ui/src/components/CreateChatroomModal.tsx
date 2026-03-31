import { useState } from "preact/hooks";
import type { TargetedEvent } from "preact";
import { addChatroomParticipant, createChatroom } from "../api";
import type { AgentInfo } from "../api";

interface CreateChatroomModalProps {
  agents: AgentInfo[];
  onClose: () => void;
  onSuccess: (chatroomId: string) => void | Promise<void>;
}

export default function CreateChatroomModal({ agents, onClose, onSuccess }: CreateChatroomModalProps) {
  const [name, setName] = useState("");
  const [description, setDescription] = useState("");
  const [selectedAgentIds, setSelectedAgentIds] = useState<string[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  const toggleAgent = (agentId: string) => {
    setSelectedAgentIds((prev) =>
      prev.includes(agentId)
        ? prev.filter((id) => id !== agentId)
        : [...prev, agentId]
    );
  };

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
      const room = await createChatroom(trimmedName, description.trim());

      if (selectedAgentIds.length > 0) {
        const participantResults = await Promise.allSettled(
          selectedAgentIds.map((agentId) => addChatroomParticipant(room.id, agentId))
        );

        const failedCount = participantResults.filter((result) => result.status === "rejected").length;
        if (failedCount > 0) {
          console.error(`Created chatroom '${room.name}', but failed to add ${failedCount} participant(s).`);
        }
      }

      await onSuccess(room.id);
      onClose();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to create chatroom");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div
      className="fixed inset-0 bg-black/50 flex items-center justify-center z-50"
      onClick={(event) => event.target === event.currentTarget && onClose()}
    >
      <div className="bg-white rounded-xl shadow-2xl w-full max-w-lg mx-4 overflow-hidden">
        <div className="flex items-center justify-between px-6 py-4 border-b border-gray-200">
          <h2 className="text-lg font-semibold text-gray-800">Create Chatroom</h2>
          <button
            type="button"
            onClick={onClose}
            className="text-gray-400 hover:text-gray-600 transition-colors p-0 border-0 bg-transparent text-xl leading-none"
            title="Close"
          >
            ✕
          </button>
        </div>

        <form onSubmit={handleSubmit} className="p-6 flex flex-col gap-4">
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
            <label htmlFor="chatroom-description-input" className="block text-sm font-medium text-gray-700 mb-1">
              Description
            </label>
            <input
              id="chatroom-description-input"
              type="text"
              className="w-full border rounded p-2 focus:ring-2 focus:ring-blue-500 focus:outline-none"
              value={description}
              onChange={(event) => setDescription(event.currentTarget.value)}
              placeholder="Optional description"
              disabled={loading}
            />
          </div>

          <div>
            <div className="flex items-center justify-between mb-2">
              <label className="block text-sm font-medium text-gray-700">Add agents</label>
              <span className="text-xs text-gray-500">{selectedAgentIds.length} selected</span>
            </div>

            {agents.length === 0 ? (
              <p className="text-sm text-gray-500 border border-dashed border-gray-300 rounded p-3">
                No agents available yet.
              </p>
            ) : (
              <div className="max-h-44 overflow-y-auto border border-gray-200 rounded p-2 space-y-1">
                {agents.map((agent) => {
                  const checked = selectedAgentIds.includes(agent.id);
                  return (
                    <label
                      key={agent.id}
                      className="flex items-center justify-between gap-2 rounded px-2 py-1.5 hover:bg-gray-50 cursor-pointer"
                    >
                      <div className="min-w-0">
                        <div className="text-sm font-medium text-gray-800 truncate">{agent.name}</div>
                        <div className="text-[10px] text-gray-400 font-mono truncate">@{agent.id}</div>
                      </div>
                      <input
                        type="checkbox"
                        checked={checked}
                        onChange={() => toggleAgent(agent.id)}
                        className="h-4 w-4"
                        disabled={loading}
                      />
                    </label>
                  );
                })}
              </div>
            )}
          </div>

          <div className="flex justify-end gap-3 pt-2 border-t border-gray-200">
            <button
              type="button"
              onClick={onClose}
              className="px-4 py-2 text-gray-700 hover:bg-gray-100 rounded"
              disabled={loading}
            >
              Cancel
            </button>
            <button
              type="submit"
              className="px-4 py-2 bg-blue-600 text-white rounded hover:bg-blue-700 disabled:opacity-50"
              disabled={loading}
            >
              {loading ? "Creating..." : "Create Chatroom"}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}
