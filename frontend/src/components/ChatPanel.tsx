import { useState, useEffect, useRef, useCallback } from 'react';
import { marked } from 'marked';
import markedKatex from 'marked-katex-extension';
import 'katex/dist/katex.min.css';
import { getMaterialContent, getExamResourceContent } from '../lib/api';

marked.use(markedKatex({ throwOnError: false }));

export interface Source {
  name: string;
  type: 'subtopic' | 'material' | 'exam_resource';
  id?: string;
}

export interface Message {
  role: 'user' | 'assistant';
  content: string;
  sources?: Source[];
}

interface ChatPanelProps {
  messages: Message[];
  streamingText: string;
  streamingSources: Source[];
  isThinking: boolean;
}

export default function ChatPanel({ messages, streamingText, streamingSources, isThinking }: ChatPanelProps) {
  const scrollRef = useRef<HTMLDivElement>(null);
  const [viewerMaterial, setViewerMaterial] = useState<{ filename: string; content: string } | null>(null);
  const [viewerLoading, setViewerLoading] = useState(false);

  useEffect(() => {
    const el = scrollRef.current;
    if (el) el.scrollTop = el.scrollHeight;
  }, [messages, streamingText, isThinking]);

  function renderMarkdown(text: string): string {
    // Strip mermaid code blocks (they go to diagram panel) and [DIAGRAM: ...] signals
    let stripped = text.replace(/```mermaid\s*\n[\s\S]*?```/g, '');
    stripped = stripped.replace(/\[DIAGRAM:\s*[^\]]+\]/g, '');
    // Convert LaTeX delimiters to dollar-sign form for KaTeX
    stripped = stripped.replace(/\\\[([\s\S]*?)\\\]/g, '$$$$$1$$$$'); // \[...\] → $$...$$
    stripped = stripped.replace(/\\\((.*?)\\\)/g, '$$$1$$'); // \(...\) → $...$
    return marked.parse(stripped.trim(), { async: false }) as string;
  }

  const handleSourceClick = useCallback(async (source: Source) => {
    if (!source.id || (source.type !== 'material' && source.type !== 'exam_resource')) return;
    setViewerLoading(true);
    setViewerMaterial({ filename: source.name, content: '' });
    try {
      const data = source.type === 'exam_resource'
        ? await getExamResourceContent(source.id)
        : await getMaterialContent(source.id);
      setViewerMaterial({ filename: data.filename, content: data.content_text });
    } catch {
      setViewerMaterial({ filename: source.name, content: 'Failed to load content.' });
    } finally {
      setViewerLoading(false);
    }
  }, []);

  return (
    <div className="absolute inset-0 flex flex-col overflow-hidden">
      <div ref={scrollRef} className="flex-1 overflow-y-auto px-4 py-4">
        <div className="space-y-3">
          {messages.map((msg, i) => (
            <div key={i}>
              <div
                className={
                  msg.role === 'user'
                    ? 'self-end max-w-[75%] bg-indigo-600 text-white rounded-2xl rounded-br-md px-4 py-2.5 text-sm leading-relaxed break-words ml-auto'
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
              {/* Source references for assistant messages */}
              {msg.role === 'assistant' && msg.sources && msg.sources.length > 0 && (
                <SourceBadges sources={msg.sources} onSourceClick={handleSourceClick} />
              )}
            </div>
          ))}

          {streamingText && (
            <div>
              <div className="self-start max-w-[75%] bg-zinc-900 text-zinc-200 border border-zinc-800 rounded-2xl rounded-bl-md px-4 py-2.5 text-sm leading-relaxed break-words">
                <div
                  className="markdown-content"
                  dangerouslySetInnerHTML={{ __html: renderMarkdown(streamingText) }}
                />
                <span className="text-indigo-400 font-bold ml-0.5 animate-blink">|</span>
              </div>
              {streamingSources.length > 0 && (
                <SourceBadges sources={streamingSources} onSourceClick={handleSourceClick} />
              )}
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

          <div />
        </div>
      </div>

      {/* Material viewer slide-out panel */}
      {viewerMaterial && (
        <MaterialViewer
          filename={viewerMaterial.filename}
          content={viewerMaterial.content}
          loading={viewerLoading}
          onClose={() => setViewerMaterial(null)}
        />
      )}
    </div>
  );
}

function SourceBadges({ sources, onSourceClick }: { sources: Source[]; onSourceClick: (s: Source) => void }) {
  return (
    <div className="flex flex-wrap gap-1.5 mt-1.5 ml-1">
      <span className="text-[10px] text-zinc-600 leading-5">Sources:</span>
      {sources.map((s, i) => (
        <button
          key={i}
          onClick={() => onSourceClick(s)}
          disabled={s.type === 'subtopic' || !s.id}
          className={`inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-[10px] leading-4 border transition-colors ${
            s.type === 'material'
              ? 'bg-indigo-500/10 text-indigo-400 border-indigo-500/20 hover:bg-indigo-500/20 hover:border-indigo-500/40 cursor-pointer'
              : s.type === 'exam_resource'
              ? 'bg-amber-500/10 text-amber-400 border-amber-500/20 hover:bg-amber-500/20 hover:border-amber-500/40 cursor-pointer'
              : 'bg-zinc-800 text-zinc-500 border-zinc-700/50 cursor-default'
          }`}
        >
          {s.type === 'material' || s.type === 'exam_resource' ? (
            <svg className="w-2.5 h-2.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
              <path strokeLinecap="round" strokeLinejoin="round" d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
            </svg>
          ) : (
            <svg className="w-2.5 h-2.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
              <path strokeLinecap="round" strokeLinejoin="round" d="M12 6.253v13m0-13C10.832 5.477 9.246 5 7.5 5S4.168 5.477 3 6.253v13C4.168 18.477 5.754 18 7.5 18s3.332.477 4.5 1.253m0-13C13.168 5.477 14.754 5 16.5 5c1.747 0 3.332.477 4.5 1.253v13C19.832 18.477 18.247 18 16.5 18c-1.746 0-3.332.477-4.5 1.253" />
            </svg>
          )}
          {s.name}
        </button>
      ))}
    </div>
  );
}

function MaterialViewer({ filename, content, loading, onClose }: {
  filename: string;
  content: string;
  loading: boolean;
  onClose: () => void;
}) {
  return (
    <div className="absolute inset-0 z-20 flex">
      {/* Backdrop */}
      <div className="absolute inset-0 bg-black/40" onClick={onClose} />

      {/* Panel */}
      <div className="absolute right-0 top-0 bottom-0 w-[70%] max-w-2xl bg-zinc-950 border-l border-zinc-800 flex flex-col shadow-2xl animate-slide-in-right">
        {/* Header */}
        <div className="flex items-center justify-between px-4 py-3 border-b border-zinc-800 shrink-0">
          <div className="flex items-center gap-2 min-w-0">
            <svg className="w-4 h-4 text-indigo-400 shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
              <path strokeLinecap="round" strokeLinejoin="round" d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
            </svg>
            <span className="text-sm font-medium text-zinc-200 truncate">{filename}</span>
          </div>
          <button
            onClick={onClose}
            className="p-1.5 rounded-lg hover:bg-zinc-800 text-zinc-500 hover:text-zinc-300 transition-colors bg-transparent border-none"
          >
            <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
              <path strokeLinecap="round" strokeLinejoin="round" d="M6 18L18 6M6 6l12 12" />
            </svg>
          </button>
        </div>

        {/* Content */}
        <div className="flex-1 overflow-y-auto px-5 py-4">
          {loading ? (
            <div className="flex items-center gap-2 text-zinc-500 text-sm">
              <svg className="animate-spin w-4 h-4" viewBox="0 0 24 24" fill="none">
                <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
              </svg>
              Loading content...
            </div>
          ) : (
            <pre className="text-sm text-zinc-300 whitespace-pre-wrap font-sans leading-relaxed">{content}</pre>
          )}
        </div>
      </div>
    </div>
  );
}
