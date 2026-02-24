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
    // Strip mermaid code blocks from chat display (they go to diagram panel)
    const stripped = text.replace(/```mermaid\s*\n[\s\S]*?```/g, '').trim();
    return marked.parse(stripped, { async: false }) as string;
  }

  return (
    <div style={styles.container}>
      <div style={styles.messageList}>
        {messages.map((msg, i) => (
          <div
            key={i}
            style={{
              ...styles.messageBubble,
              ...(msg.role === 'user' ? styles.userBubble : styles.assistantBubble),
            }}
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
          <div style={{ ...styles.messageBubble, ...styles.assistantBubble }}>
            <div
              className="markdown-content"
              dangerouslySetInnerHTML={{ __html: renderMarkdown(streamingText) }}
            />
            <span style={styles.cursor}>|</span>
          </div>
        )}

        {isThinking && (
          <div style={{ ...styles.messageBubble, ...styles.assistantBubble }}>
            <div style={styles.thinkingDots}>
              <span style={{ ...styles.dot, animationDelay: '0s' }} />
              <span style={{ ...styles.dot, animationDelay: '0.2s' }} />
              <span style={{ ...styles.dot, animationDelay: '0.4s' }} />
            </div>
          </div>
        )}

        <div ref={bottomRef} />
      </div>

      <style>{`
        .markdown-content h1, .markdown-content h2, .markdown-content h3 {
          margin: 0.5em 0 0.25em;
          color: #fff;
        }
        .markdown-content p { margin: 0.4em 0; line-height: 1.6; }
        .markdown-content ul, .markdown-content ol { margin: 0.4em 0; padding-left: 1.5em; }
        .markdown-content li { margin: 0.2em 0; }
        .markdown-content code {
          background: #2a2a3d;
          padding: 0.15em 0.4em;
          border-radius: 4px;
          font-size: 0.9em;
          font-family: 'Fira Code', monospace;
        }
        .markdown-content pre {
          background: #12121a;
          padding: 1em;
          border-radius: 8px;
          overflow-x: auto;
          margin: 0.5em 0;
        }
        .markdown-content pre code {
          background: none;
          padding: 0;
        }
        .markdown-content blockquote {
          border-left: 3px solid #7c8aff;
          padding-left: 1em;
          margin: 0.5em 0;
          color: #8888a0;
        }
        .markdown-content a { color: #7c8aff; }
        .markdown-content table {
          border-collapse: collapse;
          margin: 0.5em 0;
          width: 100%;
        }
        .markdown-content th, .markdown-content td {
          border: 1px solid #2a2a3d;
          padding: 0.5em;
          text-align: left;
        }
        .markdown-content th { background: #1a1a24; }
        @keyframes blink {
          0%, 100% { opacity: 1; }
          50% { opacity: 0; }
        }
        @keyframes pulse-dot {
          0%, 100% { opacity: 0.3; transform: scale(0.8); }
          50% { opacity: 1; transform: scale(1); }
        }
      `}</style>
    </div>
  );
}

const styles: Record<string, React.CSSProperties> = {
  container: {
    display: 'flex',
    flexDirection: 'column',
    height: '100%',
    overflow: 'hidden',
  },
  messageList: {
    flex: 1,
    overflowY: 'auto',
    padding: '1rem',
    display: 'flex',
    flexDirection: 'column',
    gap: '0.75rem',
  },
  messageBubble: {
    maxWidth: '85%',
    padding: '0.75rem 1rem',
    borderRadius: '12px',
    fontSize: '0.95rem',
    lineHeight: 1.5,
    wordBreak: 'break-word' as const,
  },
  userBubble: {
    alignSelf: 'flex-end',
    background: '#7c8aff',
    color: '#fff',
    borderBottomRightRadius: '4px',
  },
  assistantBubble: {
    alignSelf: 'flex-start',
    background: '#1a1a24',
    color: '#e0e0e0',
    borderBottomLeftRadius: '4px',
    border: '1px solid #2a2a3d',
  },
  cursor: {
    animation: 'blink 0.8s infinite',
    color: '#7c8aff',
    fontWeight: 'bold',
    marginLeft: '2px',
  },
  thinkingDots: {
    display: 'flex',
    gap: '6px',
    padding: '4px 0',
    alignItems: 'center',
  },
  dot: {
    width: '8px',
    height: '8px',
    borderRadius: '50%',
    background: '#7c8aff',
    display: 'inline-block',
    animation: 'pulse-dot 1.2s infinite ease-in-out',
  },
};
