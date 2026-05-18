import { useEffect, useRef, useState } from "preact/hooks";
import { fetchChatrooms, deleteChatroom, fetchAgents, deleteAgent } from "../api";
import type { Chatroom, AgentInfo } from "../api";
import AgentModal from "./AgentModal";
import ChatroomModal from "./ChatroomModal";
import { getBotAvatarUrl } from "../utils/avatar";
import icons from './../assets/feathericons.svg?no-inline';

interface SidebarProps {
  activeChatroom: Chatroom | null;
  onSelectChatroom: (id: Chatroom | null) => void;
}

export default function Sidebar({ activeChatroom, onSelectChatroom }: SidebarProps) {
  const [chatrooms, setChatrooms] = useState<Chatroom[]>([]);
  const [agents, setAgents] = useState<AgentInfo[]>([]);
  const [showChatroomModal, setShowChatroomModal] = useState(false);
  const [editingChatroomId, setEditingChatroomId] = useState<string | null>(null);
  const [showAgentModal, setShowAgentModal] = useState(false);
  const [editingAgent, setEditingAgent] = useState<AgentInfo | null>(null);
  const [chatroomsPaneSize, setChatroomsPaneSize] = useState(50);
  const [isResizing, setIsResizing] = useState(false);
  const splitContainerRef = useRef<HTMLDivElement>(null);
  const dividerStartYRef = useRef(0);
  const dividerStartHeightRef = useRef(0);

  useEffect(() => {
    loadData();
  }, []);

  const loadData = async (): Promise<Chatroom[]> => {
    try {
      const [rooms, fetchedAgents] = await Promise.all([
        fetchChatrooms(),
        fetchAgents()
      ]);
      setChatrooms(rooms);
      setAgents(fetchedAgents);
      if (rooms.length > 0 && !activeChatroom) {
        onSelectChatroom(rooms[0]);
      } else if (activeChatroom) {
        const refreshedActive = rooms.find((room) => room.id === activeChatroom.id) ?? null;
        onSelectChatroom(refreshedActive);
      }
      return rooms;
    } catch (err) {
      console.error(err);
      return [];
    }
  };

  const handleChatroomSaved = async (chatroomId: string) => {
    const rooms = await loadData();
    const refreshedChatroom = rooms.find((room) => room.id === chatroomId) ?? null;
    if (refreshedChatroom) {
      onSelectChatroom(refreshedChatroom);
    }
    window.dispatchEvent(new CustomEvent("chatroom-updated", { detail: { chatroomId } }));
    setEditingChatroomId(null);
  };

  const handleChatroomDeleted = async (chatroomId: string) => {
    if (confirm(`Are you sure you want to delete the chatroom?`)) {
      try {
        await deleteChatroom(chatroomId);
        onSelectChatroom(null);
        await loadData();
      } catch (err) {
        console.error("Failed to delete chatroom", err);
      }
    }
  };

  const handleAgentCreated = function() {
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
      const childStyle = window.getComputedStyle(container.firstElementChild!);

      const minPercent = parseFloat(childStyle.minHeight);
      const maxPercent = parseFloat(childStyle.maxHeight);

      const deltaY = event.clientY - dividerStartYRef.current;
      const deltaPercent = (deltaY / bounds.height) * 100;

      let nextSize = dividerStartHeightRef.current + deltaPercent;
      
      if (!isNaN(minPercent)) nextSize = Math.max(nextSize, minPercent);
      if (!isNaN(maxPercent)) nextSize = Math.min(nextSize, maxPercent);

      setChatroomsPaneSize(nextSize);
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
    <div className="max-w-1/5 w-fit border-r border-gray-300 p-4 bg-gray-50 flex flex-col h-full text-black">
      <div
        ref={splitContainerRef}
        className={`flex-1 h-full flex flex-col ${isResizing ? "cursor-row-resize" : ""}`}
      >
        <div style={{ height: `${chatroomsPaneSize}%` }} className="min-h-[20%] max-h-[60%] flex flex-col">
          <div className="flex items-center justify-between mb-4 gap-3">
            <h2 className="font-bold text-xl">Chatrooms</h2>
            <button
              onClick={() => {
                setEditingChatroomId(null);
                setShowChatroomModal(true);
              }}
              className="text-xs py-1! transition-colors"
            >
              + Add
            </button>
          </div>
          <div className="flex-1 min-h-0 overflow-y-auto pr-1 no-scrollbar">
            {chatrooms.length === 0 ? (
              <p className="text-gray-500 text-sm mb-4">No chatrooms found</p>
            ) : (
                <ul className="space-y-1">
                  {chatrooms.map((room) => (
                    <li
                      key={room.id}
                      onClick={() => onSelectChatroom(room)}
                      className={`pl-2 rounded cursor-pointer transition-colors ${
                        activeChatroom?.id === room.id
                          ? "bg-blue-100 text-blue-800 font-medium"
                          : "hover:bg-gray-200"
                      }`}
                    >
                      <div className="flex items-center justify-between gap-2 group">
                        <span className="truncate">{room.name}</span>
                        <div className="flex gap-1 opacity-0 group-hover:opacity-100 transition-opacity">
                          <span
                            className="hover:text-blue-500"
                            onClick={(event) => {
                              event.stopPropagation();
                              setEditingChatroomId(room.id);
                              setShowChatroomModal(true);
                            }}
                            title="Edit Chatroom"
                          >
                            <svg xmlns="http://www.w3.org/2000/svg" className="h-4 w-4">
                              <use href={`${icons}#edit`} />
                            </svg>
                          </span>
                          <span
                            className="hover:text-red-500"
                            onClick={() => handleChatroomDeleted(room.id)}
                            title="Delete Chatroom"
                          >
                            <svg xmlns="http://www.w3.org/2000/svg" className="h-4 w-4">
                              <use href={`${icons}#trash-2`} />
                            </svg>
                          </span>
                        </div>
                      </div>
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
            dividerStartYRef.current = event.clientY;
            dividerStartHeightRef.current = chatroomsPaneSize;
            setIsResizing(true);
          }}
          className="my-1 p-1! bg-transparent! w-full flex items-center justify-center cursor-row-resize touch-none"
        >
          <span className="h-px w-full bg-black" />
        </button>

        <div className="flex-1 min-h-0 flex flex-col">
          <div className="flex items-center justify-between mb-4 gap-3">
            <h2 className="font-bold text-xl">Agents</h2>
            <button
              onClick={() => setShowAgentModal(true)}
              className="text-xs py-1! transition-colors"
            >
              + Add
            </button>
          </div>

          <div className="flex-1 min-h-0 overflow-y-auto pr-1 no-scrollbar">
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
                        <span
                          onClick={() => setEditingAgent(agent)}
                          className="text-gray-500 hover:text-blue-500"
                          title="Edit Agent"
                        >
                          <svg xmlns="http://www.w3.org/2000/svg" className="h-4 w-4">
                            <use href={`${icons}#edit`} />
                          </svg>
                        </span>
                        <span
                          onClick={() => handleAgentDeleted(agent)}
                          className="text-gray-500 hover:text-red-500"
                          title="Delete Agent"
                        >
                          <svg xmlns="http://www.w3.org/2000/svg" className="h-4 w-4">
                            <use href={`${icons}#trash-2`} />
                          </svg>
                        </span>
                      </div>
                    </div>
                    {agent.description && (
                      <div className="text-xs text-gray-500 line-clamp-2">{agent.description}</div>
                    )}
                  </li>
                ))}
              </ul>
            )}
          </div>
        </div>
      </div>

      {showChatroomModal && (
        <ChatroomModal
          agents={agents}
          chatroomId={editingChatroomId}
          onClose={() => {
            setShowChatroomModal(false);
            setEditingChatroomId(null);
          }}
          onSuccess={handleChatroomSaved}
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
