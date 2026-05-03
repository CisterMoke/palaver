import { useEffect, useRef, useState } from "preact/hooks";
import type { TargetedEvent } from "preact";

interface MessageInputProps {
  value: string;
  participants: string[];
  onChange: (text: string) => void;
  onSend: (recipient?: string) => Promise<void>;
}

export default function MessageInput({ value, participants, onChange, onSend }: MessageInputProps) {
  const textareaRef = useRef<HTMLTextAreaElement>(null);
  const [recipient, setRecipient] = useState<string | undefined>(undefined);

  const autoGrow = () => {
    const el = textareaRef.current;
    if (!el) return;

    el.style.height = "auto";
    el.style.height = `${el.scrollHeight}px`;
  };

  const resizeSelectElementToCurrentValue = function (select: HTMLSelectElement) {
  // https://stackoverflow.com/a/79058181/13115502
  // remove each <option> except the current value
  const purgatory = [];
  for (const option of select.querySelectorAll('option')) {
    purgatory.push(option);
    if (!(option.value === select.value)) {
      option.remove();
    }
  }

  // allow the <select> to auto-size
  select.style.width = '';

  // copy that width to "freeze" it
  select.style.width = `${select.clientWidth+2}px`;

  // restore the <select>'s children
  select.append(...purgatory);
}

const sendMessage = async function () {
  if (recipient === "") {
    const target = participants[Math.floor(Math.random() * participants.length)];
    await onSend(target);
  }
  else { await onSend(recipient); }
} 

  useEffect(() => {
    autoGrow();
  }, [value]);

  useEffect(() => {
    if (participants.length == 0) { setRecipient(undefined); }
    else { setRecipient(participants[0]); }
  }, [participants]);

  useEffect(() => {
    const select = (document.getElementById("recipientSelection") as HTMLSelectElement);
    resizeSelectElementToCurrentValue(select);
  }, [recipient])

  return (
    <div className="relative">
      <div className="relative max-h-50 overflow-y-auto no-scrollbar">
        <textarea
          ref={textareaRef}
          rows={1}
          className="pt-3 px-4 pb-12 w-full select-text focus:outline-none whitespace-pre-wrap text-black resize-none"
          id="chat-input"
          autocomplete="off"
          placeholder="Type a message..."
          value={value}
          onChange={(e: TargetedEvent<HTMLTextAreaElement>) => onChange(e.currentTarget.value)}
          onInput={autoGrow}
          onKeyDown={(e) => {
            if (e.key === "Enter" && !e.shiftKey) {
              e.preventDefault();
              sendMessage();
            }
          }}
        />
      </div>
      <div aria-hidden="true" className="pointer-events-none absolute inset-x-0 bottom-0 h-14 bg-linear-to-t from-current from-70% to-transparent"></div>
      <div className="absolute inset-x-0 bottom-2 pointer-events-auto flex items-baseline-last">
        <select
          className="absolute left-4 p-1 max-w-40 min-w-16 truncate rounded-full text-gray-500 border border-gray-300 focus:outline-none focus:ring-2 focus:ring-blue-400"
          id="recipientSelection"
          value={recipient}
          onChange={(event) => {
            resizeSelectElementToCurrentValue(event.currentTarget);
            setRecipient(event.currentTarget.value);
          }}
        >
          <>
          {participants.map(p => (
            <option value={p} label={p} />
          ))}
          </>
          <option value={undefined} label={participants.length > 0 ? "🎲Random" : ""}/>
        </select>
        <button
          className="absolute right-4 py-1! text-black"
          onClick={sendMessage}
        >
          Send
        </button>
      </div>
    </div>
  );
}
