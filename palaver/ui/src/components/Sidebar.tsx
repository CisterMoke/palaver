import { useEffect, useRef, useState } from "preact/hooks";
import { fetchChatrooms, fetchAgents, deleteAgent } from "../api";
import type { Chatroom, AgentInfo } from "../api";
import AgentModal from "./AgentModal";
import CreateChatroomModal from "./CreateChatroomModal";
import { getBotAvatarUrl } from "../utils/avatar";

interface SidebarProps {
  activeChatroomId: string | null;
  onSelectChatroom: (id: string) => void;
}

export default function Sidebar({ activeChatroomId, onSelectChatroom }: SidebarProps) {
  const [chatrooms, setChatrooms] = useState<Chatroom[]>([]);
  const [agents, setAgents] = useState<AgentInfo[]>([]);
  const [showChatroomModal, setShowChatroomModal] = useState(false);
  const [showAgentModal, setShowAgentModal] = useState(false);
  const [editingAgent, setEditingAgent] = useState<AgentInfo | null>(null);
  const [chatroomsPaneSize, setChatroomsPaneSize] = useState(50);
  const [isResizing, setIsResizing] = useState(false);
  const splitContainerRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    loadData();
  }, []);

  const loadData = async () => {
    try {
      const [rooms, fetchedAgents] = await Promise.all([
        fetchChatrooms(),
        fetchAgents()
      ]);
      setChatrooms(rooms);
      setAgents(fetchedAgents);
      if (rooms.length > 0 && !activeChatroomId) {
        onSelectChatroom(rooms[0].id);
      }
    } catch (err) {
      console.error(err);
    }
  };

  const handleChatroomCreated = async (chatroomId: string) => {
    await loadData();
    onSelectChatroom(chatroomId);
  };

  const handleAgentCreated = () => {
    // Refresh the list after an agent is created or updated
    setEditingAgent(null);
    loadData();
  };

  const handleAgentDeleted = async (agent: AgentInfo) => {
    if (confirm(`Are you sure you want to delete the agent '${agent.name}'?`)) {
      try {
        await deleteAgent(agent.id);
        loadData();
      } catch (err) {
        console.error("Failed to delete agent", err);
      }
    }
  };

  useEffect(() => {
    if (!isResizing) return;

    const handlePointerMove = (event: PointerEvent) => {
      const container = splitContainerRef.current;
      if (!container) return;

      const bounds = container.getBoundingClientRect();
      const relativeY = event.clientY - bounds.top;
      const nextSize = (relativeY / bounds.height) * 100;
      const constrainedSize = Math.min(80, Math.max(20, nextSize));

      setChatroomsPaneSize(constrainedSize);
    };

    const handlePointerUp = () => {
      setIsResizing(false);
    };

    document.body.style.userSelect = "none";
    document.body.style.cursor = "row-resize";
    window.addEventListener("pointermove", handlePointerMove);
    window.addEventListener("pointerup", handlePointerUp);

    return () => {
      document.body.style.userSelect = "";
      document.body.style.cursor = "";
      window.removeEventListener("pointermove", handlePointerMove);
      window.removeEventListener("pointerup", handlePointerUp);
    };
  }, [isResizing]);

  return (
    <div className="w-1/4 max-w-fit border-r border-gray-300 p-4 bg-gray-50 flex flex-col h-full text-black">
      <div
        ref={splitContainerRef}
        className={`flex-1 min-h-0 flex flex-col ${isResizing ? "cursor-row-resize" : ""}`}
      >
        <div style={{ flexBasis: `${chatroomsPaneSize}%` }} className="min-h-0 flex flex-col">
          <div className="flex items-center justify-between mb-4">
            <h2 className="font-bold text-xl">Chatrooms</h2>
            <button
              onClick={() => setShowChatroomModal(true)}
              className="text-xs bg-blue-500 hover:bg-blue-600 text-white px-2 py-1 rounded transition-colors"
            >
              + Add
            </button>
          </div>
          <div className="flex-1 min-h-0 overflow-y-auto pr-1">
            {chatrooms.length === 0 ? (
              <p className="text-gray-500 text-sm mb-4">No chatrooms found</p>
            ) : (
              <ul className="space-y-1">
                {chatrooms.map((room) => (
                  <li
                    key={room.id}
                    onClick={() => onSelectChatroom(room.id)}
                    className={`p-2 rounded cursor-pointer transition-colors ${
                      activeChatroomId === room.id
                        ? "bg-blue-100 text-blue-800 font-medium"
                        : "hover:bg-gray-200"
                    }`}
                  >
                    {room.name}
                  </li>
                ))}
              </ul>
            )}
          </div>
        </div>

        <button
          type="button"
          aria-label="Resize chatrooms and agents sections"
          onPointerDown={(event) => {
            event.preventDefault();
            setIsResizing(true);
          }}
          className="h-5 flex items-center justify-center cursor-row-resize touch-none"
        >
          <span className="h-px w-12 bg-gray-300 rounded" />
        </button>

        <div className="flex-1 min-h-0 flex flex-col">
          <div className="flex items-center justify-between mb-4">
            <h2 className="font-bold text-xl">Agents</h2>
            <button
              onClick={() => setShowAgentModal(true)}
              className="text-xs bg-green-500 hover:bg-green-600 text-white px-2 py-1 rounded transition-colors"
            >
              + Add
            </button>
          </div>

          <div className="flex-1 min-h-0 overflow-y-auto pr-1">
            {agents.length === 0 ? (
              <p className="text-gray-500 text-sm">No agents available.</p>
            ) : (
              <ul className="space-y-1">
                {agents.map((agent) => (
                  <li
                    key={agent.id}
                    className="p-2 rounded bg-white border border-gray-200 shadow-sm flex flex-col gap-1 relative group"
                  >
                    <div className="flex justify-between items-start">
                      <div className="flex items-center gap-2 min-w-0">
                        <img
                          src={getBotAvatarUrl(agent.name, 28)}
                          alt={`${agent.name} avatar`}
                          className="w-7 h-7 rounded-full border border-gray-200 bg-gray-100 shrink-0"
                          loading="lazy"
                        />
                        <div className="font-medium text-gray-800 truncate">{agent.name}</div>
                      </div>
                      <div className="flex gap-1 opacity-0 group-hover:opacity-100 transition-opacity">
                        <button onClick={() => setEditingAgent(agent)} className="text-gray-400 hover:text-blue-500" title="Edit Agent">
                          <svg xmlns="http://www.w3.org/2000/svg" className="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15.232 5.232l3.536 3.536m-2.036-5.036a2.5 2.5 0 113.536 3.536L6.5 21.036H3v-3.572L16.732 3.732z" />
                          </svg>
                        </button>
                        <button onClick={() => handleAgentDeleted(agent)} className="text-gray-400 hover:text-red-500" title="Delete Agent">
                          <svg xmlns="http://www.w3.org/2000/svg" className="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" />
                          </svg>
                        </button>
                      </div>
                    </div>
                    {agent.description && (
                      <div className="text-xs text-gray-500 truncate">{agent.description}</div>
                    )}
                    <div className="text-[10px] text-gray-400 font-mono mt-1">@{agent.id}</div>
                  </li>
                ))}
              </ul>
            )}
          </div>
        </div>
      </div>

      {showChatroomModal && (
        <CreateChatroomModal
          agents={agents}
          onClose={() => setShowChatroomModal(false)}
          onSuccess={handleChatroomCreated}
        />
      )}

      {(showAgentModal || editingAgent) && (
        <AgentModal 
          existingAgent={editingAgent}
          onClose={() => {
            setShowAgentModal(false);
            setEditingAgent(null);
          }} 
          onSuccess={handleAgentCreated} 
        />
      )}
    </div>
  );
}
