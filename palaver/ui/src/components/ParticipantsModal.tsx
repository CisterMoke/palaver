import { useEffect, useState } from "preact/hooks";
import { fetchAgents, fetchChatroomParticipants, addChatroomParticipant, removeChatroomParticipant } from "../api";
import type { Agent } from "../api";

interface ParticipantsModalProps {
  chatroomId: string;
  onClose: () => void;
  onChanged: () => void;
}

export default function ParticipantsModal({ chatroomId, onClose, onChanged }: ParticipantsModalProps) {
  const [agents, setAgents] = useState<Agent[]>([]);
  const [participantIds, setParticipantIds] = useState<string[]>([]);
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState<string | null>(null); // agent id currently being toggled

  useEffect(() => {
    loadData();
  }, [chatroomId]);

  const loadData = async () => {
    setLoading(true);
    try {
      const [allAgents, ids] = await Promise.all([
        fetchAgents(),
        fetchChatroomParticipants(chatroomId),
      ]);
      setAgents(allAgents);
      setParticipantIds(ids);
    } catch (e) {
      console.error("Failed to load participants", e);
    } finally {
      setLoading(false);
    }
  };

  const toggle = async (agent: Agent) => {
    if (busy) return;
    setBusy(agent.id);
    try {
      if (participantIds.includes(agent.id)) {
        await removeChatroomParticipant(chatroomId, agent.id);
        setParticipantIds((prev) => prev.filter((id) => id !== agent.id));
      } else {
        await addChatroomParticipant(chatroomId, agent.id);
        setParticipantIds((prev) => [...prev, agent.id]);
      }
      onChanged();
    } catch (e) {
      console.error("Failed to toggle participant", e);
    } finally {
      setBusy(null);
    }
  };

  return (
    <div
      className="fixed inset-0 bg-black/50 flex items-center justify-center z-50"
      onClick={(e) => e.target === e.currentTarget && onClose()}
    >
      <div className="bg-white rounded-xl shadow-2xl w-full max-w-md mx-4 overflow-hidden">
        {/* Header */}
        <div className="flex items-center justify-between px-6 py-4 border-b border-gray-200">
          <h2 className="text-lg font-semibold text-gray-800">Manage Participants</h2>
          <button
            onClick={onClose}
            className="text-gray-400 hover:text-gray-600 transition-colors p-0 border-0 bg-transparent text-xl leading-none"
            title="Close"
          >
            ✕
          </button>
        </div>

        {/* Body */}
        <div className="p-6 max-h-96 overflow-y-auto">
          {loading ? (
            <p className="text-gray-500 text-sm text-center py-4">Loading agents…</p>
          ) : agents.length === 0 ? (
            <p className="text-gray-500 text-sm text-center py-4">No agents available. Create one first.</p>
          ) : (
            <ul className="space-y-2">
              {agents.map((agent) => {
                const isParticipant = participantIds.includes(agent.id);
                const isBusy = busy === agent.id;
                return (
                  <li
                    key={agent.id}
                    className="flex items-center justify-between p-3 rounded-lg border border-gray-200 hover:border-gray-300 transition-colors"
                  >
                    <div className="flex flex-col min-w-0">
                      <span className="font-medium text-gray-800 text-sm">{agent.name}</span>
                      {agent.description && (
                        <span className="text-xs text-gray-400 truncate">{agent.description}</span>
                      )}
                    </div>
                    <button
                      onClick={() => toggle(agent)}
                      disabled={!!busy}
                      className={`ml-3 shrink-0 px-3 py-1 rounded-full text-xs font-medium border transition-all ${
                        isBusy
                          ? "opacity-50 cursor-wait bg-gray-100 text-gray-400 border-gray-200"
                          : isParticipant
                          ? "bg-red-50 text-red-600 border-red-200 hover:bg-red-100"
                          : "bg-green-50 text-green-600 border-green-200 hover:bg-green-100"
                      }`}
                    >
                      {isBusy ? "…" : isParticipant ? "Remove" : "Add"}
                    </button>
                  </li>
                );
              })}
            </ul>
          )}
        </div>

        {/* Footer */}
        <div className="px-6 py-4 border-t border-gray-200 flex justify-end">
          <button
            onClick={onClose}
            className="px-4 py-2 text-sm bg-gray-100 hover:bg-gray-200 text-gray-700 rounded-lg transition-colors border-0"
          >
            Done
          </button>
        </div>
      </div>
    </div>
  );
}
