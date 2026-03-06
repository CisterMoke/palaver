import Markdown from 'preact-markdown';

interface MessageProps {
  text: string;
  sender: string;
  role: "user" | "assistant" | "system";
  status?: "sending" | "error" | "sent";
}

export default function Message({ text, sender, role, status }: MessageProps) {
  const isUser = role === "user";
  
  let bgClass = isUser ? "bg-blue-500 text-white" : "bg-gray-100 text-gray-800 border border-gray-200";
  if (status === "error") bgClass = "bg-red-500 text-white";
  const alignClass = isUser ? "text-right self-end" : "text-left self-start"

  return (
    <div className={`max-w-4/5 ${alignClass}`}>
      {!isUser && <div className="text-xs text-gray-400 font-semibold mb-1 uppercase tracking-wider text-left">{sender}</div>}
      <div
        className={`p-3 rounded-xl wrap-break-word whitespace-normal ${bgClass} ${
          isUser ? "ml-auto rounded-tr-sm" : "rounded-tl-sm text-left"
        } ${status === "sending" ? "opacity-50" : ""}`}
      >
        {text === "" ? <div className="animate-pulse h-4 w-12 bg-gray-300 rounded"/> : Markdown(text.trim())}
      </div>
    </div>
  );
}