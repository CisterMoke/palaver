import { useState } from 'react';
import './app.css'

import Sidebar from "./components/Sidebar";
import ChatWindow from "./components/ChatWindow";

export function App() {
  const [activeChatroomId, setActiveChatroomId] = useState<string | null>(null);

  return (
    <div className="h-screen flex bg-gray-100 w-full font-sans">
      <Sidebar 
        activeChatroomId={activeChatroomId} 
        onSelectChatroom={setActiveChatroomId} 
      />
      <div className="w-3/4 flex-1 flex flex-col p-0">
        {activeChatroomId ? (
          <ChatWindow chatroomId={activeChatroomId} />
        ) : (
          <div className="flex-1 flex items-center justify-center text-gray-400">
            Select a chatroom to begin
          </div>
        )}
      </div>
    </div>
  );
}