import Markdown from 'preact-markdown';
import { getBotAvatarUrl } from "../utils/avatar";

interface MessageProps {
  text: string;
  sender: string;
  recipient?: string;
  role: "user" | "assistant" | "system";
  status?: "sending" | "error" | "sent";
}

export default function Message({ text, sender, recipient, role, status }: MessageProps) {
  const isUser = role === "user";
  const title = recipient ? `${sender} -> ${recipient}` : sender;
  
  let bgClass = isUser ? "bg-blue-500 text-white" : "bg-gray-100 text-gray-800 border border-gray-200";
  if (status === "error") bgClass = "bg-red-500 text-white";
  const alignClass = isUser ? "text-right self-end" : "text-left self-start"

  return (
    <div className={`max-w-4/5 ${alignClass}`}>
      {!isUser && (
        <div className="flex items-center gap-2 mb-1 text-left">
          <img
            src={getBotAvatarUrl(sender, 20)}
            alt={`${sender} avatar`}
            className="w-5 h-5 rounded-full border border-gray-200 bg-gray-100"
            loading="lazy"
          />
          <div className="text-xs text-gray-400 font-semibold tracking-wide">{title}</div>
        </div>
      )}
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
