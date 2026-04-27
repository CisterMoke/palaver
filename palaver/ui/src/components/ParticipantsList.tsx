import { useEffect, useState } from "preact/hooks";
import type { AgentInfo } from "../api";

interface ParticipantsListProps {
  agents: AgentInfo[];
  initialSelectedIds?: string[];
  loading?: boolean;
  disabled?: boolean;
  loadingText?: string;
  emptyText?: string;
  onSelectionChange?: (selectedIds: string[]) => void;
}

export default function ParticipantsList({
  agents,
  initialSelectedIds = [],
  loading = false,
  disabled = false,
  loadingText = "Loading agents…",
  emptyText = "No agents available. Create one first.",
  onSelectionChange,
}: ParticipantsListProps) {
  const [selectedIds, setSelectedIds] = useState<string[]>(initialSelectedIds);

  useEffect(() => {
    setSelectedIds((current) => {
      if (
        current.length === initialSelectedIds.length
        && current.every((id, index) => id === initialSelectedIds[index])
      ) {
        return current;
      }
      return initialSelectedIds;
    });
  }, [initialSelectedIds]);

  useEffect(() => {
    onSelectionChange?.(selectedIds);
  }, [selectedIds, onSelectionChange]);

  const toggle = (agentId: string) => {
    if (disabled) return;
    setSelectedIds((prev) =>
      prev.includes(agentId) ? prev.filter((id) => id !== agentId) : [...prev, agentId]
    );
  };

  if (loading) {
    return <p className="text-gray-500 text-sm text-center py-4">{loadingText}</p>;
  }

  if (agents.length === 0) {
    return <p className="text-gray-500 text-sm text-center py-4">{emptyText}</p>;
  }

  return (
    <ul className="space-y-2">
      {agents.map((agent) => {
        const isParticipant = selectedIds.includes(agent.id);
        return (
          <li
            key={agent.id}
            className="flex items-center justify-between p-3 rounded-lg border border-gray-200 hover:border-gray-300 transition-colors"
          >
            <div className="flex flex-col min-w-0 grow">
              <span className="font-medium text-gray-800 text-sm">{agent.name}</span>
              {agent.description && (
                <span className="text-xs text-gray-400 truncate">{agent.description}</span>
              )}
            </div>
            <button
              type="button"
              onClick={() => toggle(agent.id)}
              disabled={disabled}
              className={`ml-3 shrink-0 px-3 py-1 rounded-full text-xs font-medium border transition-all ${
                disabled
                  ? "opacity-50 cursor-not-allowed bg-gray-100 text-gray-400 border-gray-200"
                  : isParticipant
                  ? "bg-red-50 text-red-600 border-red-200 hover:bg-red-100"
                  : "bg-green-50 text-green-600 border-green-200 hover:bg-green-100"
              }`}
            >
              {isParticipant ? "Remove" : "Add"}
            </button>
          </li>
        );
      })}
    </ul>
  );
}
