import { useEffect, useRef, useCallback } from 'react';
import mermaid from 'mermaid';

interface DiagramPanelProps {
  diagrams: string[];
  isOpen: boolean;
  onToggle: () => void;
}

let mermaidInitialized = false;

function initMermaid() {
  if (!mermaidInitialized) {
    mermaid.initialize({
      startOnLoad: false,
      theme: 'dark',
      themeVariables: {
        darkMode: true,
        background: '#18181b',      // zinc-900
        primaryColor: '#818cf8',     // indigo-400
        primaryTextColor: '#d4d4d8', // zinc-300
        primaryBorderColor: '#3f3f46', // zinc-700
        lineColor: '#71717a',        // zinc-500
        secondaryColor: '#27272a',   // zinc-800
        tertiaryColor: '#09090b',    // zinc-950
      },
    });
    mermaidInitialized = true;
  }
}

function sanitizeMermaidCode(code: string): string {
  // Trim and normalize whitespace
  let cleaned = code.trim();

  // Remove style/classDef lines that mermaid chokes on from LLM output
  cleaned = cleaned.replace(/^\s*style\s+\w+\s+.*$/gm, '');
  cleaned = cleaned.replace(/^\s*classDef\s+\w+\s+.*$/gm, '');
  cleaned = cleaned.replace(/^\s*class\s+\w[\w,]*\s+\w+\s*$/gm, '');

  // Fix invalid -->|label|> syntax: should be -->|label| (no trailing >)
  // Matches any arrow with pipe-delimited label followed by extra >
  cleaned = cleaned.replace(/(--[->])\|([^|]*)\|>/g, '$1|$2|');

  // Fix node labels: parentheses inside [] brackets break mermaid
  // e.g. A[Address Pins (A0-A19)] -> A["Address Pins (A0-A19)"]
  cleaned = cleaned.replace(/\[([^\]]*\([^\]]*\)[^\]]*)\]/g, '["$1"]');

  // Fix multiline node labels: newlines inside bracket labels break Mermaid
  // Handle both quoted ["..."] and unquoted [...] labels that span multiple lines
  cleaned = cleaned.replace(/\["([\s\S]*?)"\]/g, (_match, inner: string) => {
    const fixed = inner.replace(/\n/g, '<br/>');
    return `["${fixed}"]`;
  });
  // Also catch unquoted multiline labels like [Foo\nBar] and quote+fix them
  cleaned = cleaned.replace(/\[([^\]"]*\n[^\]]*)\]/g, (_match, inner: string) => {
    const fixed = inner.replace(/\n/g, '<br/>');
    return `["${fixed}"]`;
  });

  // Remove empty lines left from stripping style lines
  cleaned = cleaned.replace(/\n{3,}/g, '\n\n');

  return cleaned;
}

function DiagramRenderer({ code, index }: { code: string; index: number }) {
  const containerRef = useRef<HTMLDivElement>(null);

  const renderDiagram = useCallback(async () => {
    if (!containerRef.current) return;
    const sanitized = sanitizeMermaidCode(code);
    try {
      initMermaid();
      const id = `mermaid-diagram-${index}-${Date.now()}`;
      const { svg } = await mermaid.render(id, sanitized);
      if (containerRef.current) {
        containerRef.current.innerHTML = svg;
      }
    } catch (err) {
      console.error('Mermaid render error:', err, '\nSanitized code:', sanitized);
      // Second attempt: quote all unquoted labels
      try {
        const quoted = sanitized.replace(/\[([^\]"]+)\]/g, '["$1"]');
        const retryId = `mermaid-retry-${index}-${Date.now()}`;
        const { svg } = await mermaid.render(retryId, quoted);
        if (containerRef.current) {
          containerRef.current.innerHTML = svg;
        }
      } catch (retryErr) {
        console.error('Mermaid retry also failed:', retryErr);
        if (containerRef.current) {
          const errMsg = retryErr instanceof Error ? retryErr.message : String(retryErr);
          containerRef.current.innerHTML = `<pre style="color: #f87171; padding: 1em; font-size: 0.85em; white-space: pre-wrap;">Diagram render failed: ${errMsg}\n\nCode:\n${sanitized}</pre>`;
        }
      }
    }
  }, [code, index]);

  useEffect(() => {
    renderDiagram();
  }, [renderDiagram]);

  return (
    <div
      ref={containerRef}
      className="bg-zinc-950 rounded-lg border border-zinc-800 p-4 overflow-auto text-center"
    />
  );
}

export default function DiagramPanel({ diagrams, isOpen, onToggle }: DiagramPanelProps) {
  if (!isOpen) {
    return (
      <button
        onClick={onToggle}
        className="absolute right-0 top-1/2 -translate-y-1/2 bg-zinc-900 border border-zinc-800 border-r-0 text-zinc-500 hover:text-indigo-400 px-1.5 py-3 rounded-l-lg flex items-center cursor-pointer z-10 transition-colors bg-transparent"
        title="Open diagram panel"
      >
        <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
          <polyline points="15 18 9 12 15 6" />
        </svg>
      </button>
    );
  }

  const latestDiagram = diagrams.length > 0 ? diagrams[diagrams.length - 1] : null;
  const previousDiagrams = diagrams.length > 1 ? diagrams.slice(0, -1).reverse() : [];

  return (
    <div className="flex flex-col h-full border-l border-zinc-800 bg-sp-base">
      <div className="flex items-center justify-between px-4 py-3 border-b border-zinc-800/50 bg-zinc-900 shrink-0">
        <span className="text-sm font-semibold text-zinc-200">Diagrams</span>
        <button
          onClick={onToggle}
          className="p-1 rounded-md text-zinc-500 hover:text-zinc-300 transition-colors bg-transparent border-none cursor-pointer flex items-center justify-center"
          title="Close diagram panel"
        >
          <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
            <polyline points="9 18 15 12 9 6" />
          </svg>
        </button>
      </div>

      <div className="flex-1 overflow-y-auto p-4 flex flex-col gap-4">
        {diagrams.length === 0 ? (
          <div className="flex flex-col items-center justify-center h-full text-center px-8">
            <svg className="text-zinc-500" width="48" height="48" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5">
              <rect x="3" y="3" width="18" height="18" rx="2" />
              <path d="M3 9h18M9 21V9" />
            </svg>
            <p className="text-zinc-500 mt-3 text-sm">
              Diagrams will appear here as the AI generates them during your conversation.
            </p>
          </div>
        ) : (
          <>
            {latestDiagram && (
              <div className="flex flex-col gap-2">
                <span className="text-xs font-semibold uppercase tracking-wider text-zinc-500">Latest</span>
                <DiagramRenderer code={latestDiagram} index={diagrams.length - 1} />
              </div>
            )}

            {previousDiagrams.length > 0 && (
              <div className="flex flex-col gap-3 mt-2">
                <span className="text-xs font-semibold uppercase tracking-wider text-zinc-500">Previous</span>
                {previousDiagrams.map((code, i) => (
                  <DiagramRenderer
                    key={`prev-${diagrams.length - 2 - i}`}
                    code={code}
                    index={diagrams.length - 2 - i}
                  />
                ))}
              </div>
            )}
          </>
        )}
      </div>
    </div>
  );
}
