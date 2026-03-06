import { useEffect, useState } from "preact/hooks";
import { fetchChatrooms, createChatroom, fetchAgents, deleteAgent } from "../api";
import type { Chatroom, Agent } from "../api";
import AgentModal from "./AgentModal";

interface SidebarProps {
  activeChatroomId: string | null;
  onSelectChatroom: (id: string) => void;
}

export default function Sidebar({ activeChatroomId, onSelectChatroom }: SidebarProps) {
  const [chatrooms, setChatrooms] = useState<Chatroom[]>([]);
  const [agents, setAgents] = useState<Agent[]>([]);
  const [newRoomName, setNewRoomName] = useState("");
  const [showAgentModal, setShowAgentModal] = useState(false);
  const [editingAgent, setEditingAgent] = useState<Agent | null>(null);

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

  const handleCreateChatroom = async () => {
    if (!newRoomName.trim()) return;
    try {
      const room = await createChatroom(newRoomName);
      setChatrooms([...chatrooms, room]);
      setNewRoomName("");
      onSelectChatroom(room.id);
    } catch (err) {
      console.error(err);
    }
  };

  const handleAgentCreated = () => {
    // Refresh the list after an agent is created or updated
    setEditingAgent(null);
    loadData();
  };

  const handleAgentDeleted = async (agent: Agent) => {
    if (confirm(`Are you sure you want to delete the agent '${agent.name}'?`)) {
      try {
        await deleteAgent(agent.id);
        loadData();
      } catch (err) {
        console.error("Failed to delete agent", err);
      }
    }
  };

  return (
    <div className="w-1/4 max-w-fit border-r border-gray-300 p-4 bg-gray-50 flex flex-col h-full text-black">
      <h2 className="font-bold mb-4 text-xl">Chatrooms</h2>
      
      <div className="flex-1 overflow-y-auto mb-4 min-h-0">
        {chatrooms.length === 0 ? (
          <p className="text-gray-500 text-sm mb-4">No chatrooms found</p>
        ) : (
          <ul className="space-y-1 mb-6">
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

        <div className="flex items-center justify-between mb-4 mt-6">
          <h2 className="font-bold text-xl">Agents</h2>
          <button 
            onClick={() => setShowAgentModal(true)}
            className="text-xs bg-green-500 hover:bg-green-600 text-white px-2 py-1 rounded transition-colors"
          >
            + Add
          </button>
        </div>
        
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
                  <div className="font-medium text-gray-800">{agent.name}</div>
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

      <div className="mt-auto border-t border-gray-300 pt-4 overflow-hidden">
        <h3 className="font-semibold text-sm mb-2">New Chatroom</h3>
        <div className="flex gap-2">
          <input
            type="text"
            className="min-w-0 flex-1 border rounded px-2 py-1 text-sm focus:outline-none focus:ring-1 focus:ring-blue-400"
            placeholder="Room name..."
            value={newRoomName}
            onChange={(e) => setNewRoomName(e.currentTarget.value)}
            onKeyDown={(e) => e.key === "Enter" && handleCreateChatroom()}
          />
          <button
            onClick={handleCreateChatroom}
            className="bg-blue-500 text-white px-3 py-1 rounded text-sm hover:bg-blue-600"
          >
            Add
          </button>
        </div>
      </div>

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