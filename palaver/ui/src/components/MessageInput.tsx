import { useEffect, useRef } from "preact/hooks";
import type { TargetedEvent } from "preact";

interface MessageInputProps {
  value: string;
  onChange: (text: string) => void;
  onSend: () => void;
}

export default function MessageInput({ value, onChange, onSend }: MessageInputProps) {
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  const autoGrow = () => {
    const el = textareaRef.current;
    if (!el) return;

    const maxHeight = 180;
    el.style.height = "auto";
    el.style.height = `${Math.min(el.scrollHeight, maxHeight)}px`;
    el.style.overflowY = el.scrollHeight > maxHeight ? "auto" : "hidden";
  };

  useEffect(() => {
    autoGrow();
  }, [value]);

  return (
    <div className="flex gap-2">
      <textarea
        ref={textareaRef}
        rows={1}
        className="flex-1 border border-gray-300 rounded p-2 focus:outline-none focus:ring-2 focus:ring-blue-400 text-black min-h-10 max-h-45"
        placeholder="Type a message..."
        value={value}
        onChange={(e: TargetedEvent<HTMLTextAreaElement>) => onChange(e.currentTarget.value)}
        onInput={autoGrow}
        onKeyDown={(e) => {
          if (e.key === "Enter" && (e.ctrlKey || e.metaKey)) {
            e.preventDefault();
            onSend();
          }
        }}
      />
      <button
        className="px-4 rounded text-black"
        onClick={onSend}
      >
        Send
      </button>
    </div>
  );
}
