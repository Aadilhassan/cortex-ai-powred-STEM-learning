import { useEffect, useRef } from 'react';
import { marked } from 'marked';

export interface Message {
  role: 'user' | 'assistant';
  content: string;
}

interface ChatPanelProps {
  messages: Message[];
  streamingText: string;
  isThinking: boolean;
}

export default function ChatPanel({ messages, streamingText, isThinking }: ChatPanelProps) {
  const bottomRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages, streamingText, isThinking]);

  function renderMarkdown(text: string): string {
    // Strip mermaid code blocks (they go to diagram panel) and [DIAGRAM: ...] signals
    let stripped = text.replace(/```mermaid\s*\n[\s\S]*?```/g, '');
    stripped = stripped.replace(/\[DIAGRAM:\s*[^\]]+\]/g, '');
    return marked.parse(stripped.trim(), { async: false }) as string;
  }

  return (
    <div className="flex flex-col h-full overflow-hidden">
      <div className="flex-1 overflow-y-auto px-4 py-4 flex flex-col gap-3">
        {messages.map((msg, i) => (
          <div
            key={i}
            className={
              msg.role === 'user'
                ? 'self-end max-w-[75%] bg-indigo-600 text-white rounded-2xl rounded-br-md px-4 py-2.5 text-sm leading-relaxed break-words'
                : 'self-start max-w-[75%] bg-zinc-900 text-zinc-200 border border-zinc-800 rounded-2xl rounded-bl-md px-4 py-2.5 text-sm leading-relaxed break-words'
            }
          >
            {msg.role === 'user' ? (
              <span>{msg.content}</span>
            ) : (
              <div
                className="markdown-content"
                dangerouslySetInnerHTML={{ __html: renderMarkdown(msg.content) }}
              />
            )}
          </div>
        ))}

        {streamingText && (
          <div className="self-start max-w-[75%] bg-zinc-900 text-zinc-200 border border-zinc-800 rounded-2xl rounded-bl-md px-4 py-2.5 text-sm leading-relaxed break-words">
            <div
              className="markdown-content"
              dangerouslySetInnerHTML={{ __html: renderMarkdown(streamingText) }}
            />
            <span className="text-indigo-400 font-bold ml-0.5 animate-blink">|</span>
          </div>
        )}

        {isThinking && (
          <div className="self-start max-w-[75%] bg-zinc-900 text-zinc-200 border border-zinc-800 rounded-2xl rounded-bl-md px-4 py-2.5 text-sm leading-relaxed break-words">
            <div className="flex gap-1.5 py-1 items-center">
              <span className="w-2 h-2 rounded-full bg-indigo-400 animate-bounce-dot" style={{ animationDelay: '0s' }} />
              <span className="w-2 h-2 rounded-full bg-indigo-400 animate-bounce-dot" style={{ animationDelay: '0.15s' }} />
              <span className="w-2 h-2 rounded-full bg-indigo-400 animate-bounce-dot" style={{ animationDelay: '0.3s' }} />
            </div>
          </div>
        )}

        <div ref={bottomRef} />
      </div>
    </div>
  );
}
