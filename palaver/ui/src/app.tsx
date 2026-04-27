import { useState } from 'react';
import './app.css'

import Sidebar from "./components/Sidebar";
import ChatWindow from "./components/ChatWindow";
import type { Chatroom } from './api';

export function App() {
  const [activeChatroom, setActiveChatroom] = useState<Chatroom | null>(null);

  return (
    <div className="h-screen flex bg-gray-100 w-full font-sans">
      <Sidebar 
        activeChatroom={activeChatroom} 
        onSelectChatroom={setActiveChatroom} 
      />
      <div className="w-3/4 flex-1 flex flex-col p-0">
        {activeChatroom ? (
          <ChatWindow chatroom={activeChatroom} />
        ) : (
          <div className="flex-1 flex items-center justify-center text-gray-400">
            Select a chatroom to begin
          </div>
        )}
      </div>
    </div>
  );
}