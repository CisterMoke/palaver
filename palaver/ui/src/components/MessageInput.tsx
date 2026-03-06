import type { TargetedEvent } from "preact";

interface MessageInputProps {
  value: string;
  onChange: (text: string) => void;
  onSend: () => void;
}

export default function MessageInput({ value, onChange, onSend }: MessageInputProps) {
  return (
    <div className="flex gap-2">
      <input
        className="flex-1 border border-gray-300 rounded p-2 focus:outline-none focus:ring-2 focus:ring-blue-400 text-black"
        placeholder="Type a message..."
        value={value}
        onChange={(e: TargetedEvent<HTMLInputElement>) => onChange(e.currentTarget.value)}
        onKeyDown={(e) => {
          if (e.key === "Enter") onSend();
        }}
      />
      <button
        className="bg-blue-500 text-white px-4 rounded hover:bg-blue-600"
        onClick={onSend}
      >
        Send
      </button>
    </div>
  );
}