import { useEffect, useState } from "preact/hooks";
import { fetchAgents, fetchChatroomParticipants, addChatroomParticipant, removeChatroomParticipant } from "../api";
import type { AgentInfo } from "../api";
import ParticipantsList from "./ParticipantsList";

interface ParticipantsModalProps {
  chatroomId: string;
  onClose: () => void;
  onChanged: () => void;
}

export default function ParticipantsModal({ chatroomId, onClose, onChanged }: ParticipantsModalProps) {
  const [agents, setAgents] = useState<AgentInfo[]>([]);
  const [participantIds, setParticipantIds] = useState<string[]>([]);
  const [selectedParticipantIds, setSelectedParticipantIds] = useState<string[]>([]);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);

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
      setSelectedParticipantIds(ids);
    } catch (e) {
      console.error("Failed to load participants", e);
    } finally {
      setLoading(false);
    }
  };

  const handleDone = async () => {
    if (loading || saving) return;

    const toAdd = selectedParticipantIds.filter((id) => !participantIds.includes(id));
    const toRemove = participantIds.filter((id) => !selectedParticipantIds.includes(id));

    if (toAdd.length === 0 && toRemove.length === 0) {
      onClose();
      return;
    }

    setSaving(true);
    try {
      const results = await Promise.allSettled([
        ...toAdd.map((agentId) => addChatroomParticipant(chatroomId, agentId)),
        ...toRemove.map((agentId) => removeChatroomParticipant(chatroomId, agentId)),
      ]);

      const failedCount = results.filter((result) => result.status === "rejected").length;
      if (failedCount > 0) {
        console.error(`Failed to update ${failedCount} participant(s).`);
      }

      onChanged();
      onClose();
    } catch (e) {
      console.error("Failed to update participants", e);
    } finally {
      setSaving(false);
    }
  };

  return (
    <div
      className="fixed inset-0 bg-black/50 flex items-start justify-center z-50 p-4 overflow-y-auto"
      onClick={(e) => e.target === e.currentTarget && onClose()}
    >
      <div className="bg-white rounded-xl shadow-2xl w-full max-w-md overflow-hidden max-h-[calc(100vh-2rem)] flex flex-col">
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
        <div className="p-6 flex-1 overflow-y-auto">
          <ParticipantsList
            agents={agents}
            initialSelectedIds={participantIds}
            loading={loading}
            disabled={saving}
            onSelectionChange={setSelectedParticipantIds}
          />
        </div>

        {/* Footer */}
        <div className="px-6 py-4 border-t border-gray-200 flex justify-end">
          <button
            onClick={handleDone}
            className="px-4 py-2 text-sm bg-gray-100 hover:bg-gray-200 text-gray-700 rounded-lg transition-colors border-0"
            disabled={loading || saving}
          >
            {saving ? "Saving..." : "Done"}
          </button>
        </div>
      </div>
    </div>
  );
}
