import { useState, useEffect, useRef, useCallback } from 'react';
import { StudySocket } from '../lib/websocket';
import { generateDiagram } from '../lib/api';
import { AudioPlayer } from './AudioPlayer';
import ChatPanel, { type Message } from './ChatPanel';
import DiagramPanel from './DiagramPanel';
import VoiceInput from './VoiceInput';
import AudioController from './AudioController';

interface StudyViewProps {
  subtopicId: string;
}

export default function StudyView({ subtopicId }: StudyViewProps) {
  const [messages, setMessages] = useState<Message[]>([]);
  const [streamingText, setStreamingText] = useState('');
  const [diagrams, setDiagrams] = useState<string[]>([]);
  const [isConnected, setIsConnected] = useState(false);
  const [isThinking, setIsThinking] = useState(false);
  const [isTTSEnabled, setIsTTSEnabled] = useState(false);
  const [isDiagramOpen, setIsDiagramOpen] = useState(true);
  const [isListening, setIsListening] = useState(false);
  const [inputText, setInputText] = useState('');

  const socketRef = useRef<StudySocket | null>(null);
  const audioPlayerRef = useRef<AudioPlayer | null>(null);
  const streamingTextRef = useRef('');

  // Extract mermaid blocks from text and return [cleanedText, mermaidCodes[]]
  const extractMermaid = useCallback((text: string): [string, string[]] => {
    const mermaidBlocks: string[] = [];
    const cleaned = text.replace(/```mermaid\s*\n([\s\S]*?)```/g, (_match, code: string) => {
      mermaidBlocks.push(code.trim());
      return '';
    });
    return [cleaned.trim(), mermaidBlocks];
  }, []);

  // Handle WebSocket messages
  const handleMessage = useCallback((msg: { type: string; content?: string; data?: string; mermaid?: string }) => {
    switch (msg.type) {
      case 'text_delta': {
        setIsThinking(false);
        const content = msg.content ?? '';
        streamingTextRef.current += content;
        setStreamingText(streamingTextRef.current);
        break;
      }
      case 'audio_chunk': {
        const data = msg.data ?? '';
        if (audioPlayerRef.current) {
          audioPlayerRef.current.addChunk(data);
        }
        break;
      }
      case 'diagram': {
        const code = msg.mermaid ?? '';
        if (code) {
          setDiagrams(prev => [...prev, code]);
          setIsDiagramOpen(true);
        }
        break;
      }
      case 'transcript': {
        // STT result from backend — show as user message
        const text = msg.content ?? '';
        if (text) {
          // Interrupt any playing audio
          audioPlayerRef.current?.interrupt();
          setMessages(prev => [...prev, { role: 'user', content: text }]);
          setIsThinking(true);
          streamingTextRef.current = '';
          setStreamingText('');
        }
        break;
      }
      case 'done': {
        setIsThinking(false);
        const fullText = streamingTextRef.current;
        if (fullText) {
          const [, mermaidBlocks] = extractMermaid(fullText);
          if (mermaidBlocks.length > 0) {
            setDiagrams(prev => [...prev, ...mermaidBlocks]);
            setIsDiagramOpen(true);
          }
          setMessages(prev => [...prev, { role: 'assistant', content: fullText }]);
        }
        streamingTextRef.current = '';
        setStreamingText('');
        break;
      }
    }
  }, [extractMermaid]);

  // Load chat history from DB on mount
  useEffect(() => {
    fetch(`/api/chat/${subtopicId}/messages`)
      .then(r => r.ok ? r.json() : [])
      .then((msgs: Message[]) => {
        if (msgs.length > 0) setMessages(msgs);
      })
      .catch(() => {});
  }, [subtopicId]);

  // Initialize WebSocket and AudioPlayer
  useEffect(() => {
    const socket = new StudySocket(
      subtopicId,
      handleMessage,
      () => setIsConnected(true),
      () => setIsConnected(false),
    );
    socket.connect();
    socketRef.current = socket;

    const player = new AudioPlayer();
    audioPlayerRef.current = player;

    return () => {
      socket.disconnect();
      player.dispose();
      socketRef.current = null;
      audioPlayerRef.current = null;
    };
  }, [subtopicId, handleMessage]);

  // Sync TTS enabled state with AudioPlayer
  useEffect(() => {
    if (audioPlayerRef.current) {
      audioPlayerRef.current.enabled = isTTSEnabled;
    }
  }, [isTTSEnabled]);

  // Send a message — interrupts any playing audio
  const sendMessage = useCallback((text: string) => {
    const trimmed = text.trim();
    if (!trimmed || !socketRef.current) return;

    // Interrupt current audio playback (speak-to-interrupt)
    audioPlayerRef.current?.interrupt();

    setMessages(prev => [...prev, { role: 'user', content: trimmed }]);
    setIsThinking(true);
    streamingTextRef.current = '';
    setStreamingText('');
    socketRef.current.send(trimmed);
    setInputText('');
  }, []);

  const handleSubmit = (e: React.SyntheticEvent<HTMLFormElement>) => {
    e.preventDefault();
    sendMessage(inputText);
  };

  // Send audio data to backend for local STT
  const handleAudioData = useCallback((base64: string) => {
    if (!socketRef.current) return;
    // Interrupt AI audio when user speaks
    audioPlayerRef.current?.interrupt();
    socketRef.current.sendRaw({ type: 'audio', data: base64 });
  }, []);

  const handleVoiceToggle = useCallback(() => {
    const newListening = !isListening;
    if (newListening) {
      audioPlayerRef.current?.interrupt();
    }
    setIsListening(newListening);
  }, [isListening]);

  const handleClearChat = useCallback(async () => {
    try {
      await fetch(`/api/chat/${subtopicId}/messages`, { method: 'DELETE' });
      setMessages([]);
      setDiagrams([]);
      setStreamingText('');
      streamingTextRef.current = '';
    } catch { /* ignore */ }
  }, [subtopicId]);

  const handleGenerateDiagram = useCallback(async () => {
    const topic = prompt('Diagram topic:');
    if (!topic?.trim()) return;
    try {
      const result = await generateDiagram(topic.trim());
      if (result.mermaid) {
        setDiagrams(prev => [...prev, result.mermaid]);
        setIsDiagramOpen(true);
      }
    } catch (e) {
      console.error('Diagram generation failed:', e);
    }
  }, []);

  const handleKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      sendMessage(inputText);
    }
  };

  return (
    <div style={styles.root}>
      {/* Header */}
      <div style={styles.header}>
        <div style={styles.headerLeft}>
          <a href="/" style={styles.backLink}>
            <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
              <polyline points="15 18 9 12 15 6" />
            </svg>
            Back
          </a>
          <span style={styles.headerDivider}>|</span>
          <span style={styles.subtopicLabel}>
            Subtopic: <strong>{subtopicId}</strong>
          </span>
          <span style={{
            ...styles.connectionDot,
            background: isConnected ? '#4ade80' : '#f87171',
          }} title={isConnected ? 'Connected' : 'Disconnected'} />
        </div>
        <div style={{ display: 'flex', gap: '0.5rem', alignItems: 'center' }}>
          <button
            onClick={handleClearChat}
            style={styles.clearChatBtn}
            title="Clear chat history"
          >
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
              <polyline points="3 6 5 6 21 6" />
              <path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2" />
            </svg>
            Clear
          </button>
          <button
            onClick={handleGenerateDiagram}
            style={styles.clearChatBtn}
            title="Generate a diagram on any topic"
          >
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
              <rect x="3" y="3" width="18" height="18" rx="2" />
              <path d="M12 8v8" />
              <path d="M8 12h8" />
            </svg>
            Diagram
          </button>
          <button
            onClick={() => setIsDiagramOpen(!isDiagramOpen)}
            style={styles.diagramToggleBtn}
          >
            Diagrams {isDiagramOpen ? '\u25B6' : '\u25C0'}
          </button>
        </div>
      </div>

      {/* Main content area */}
      <div style={styles.mainContent}>
        {/* Chat panel */}
        <div style={{
          ...styles.chatArea,
          width: isDiagramOpen ? '60%' : '100%',
        }}>
          <ChatPanel
            messages={messages}
            streamingText={streamingText}
            isThinking={isThinking}
          />
        </div>

        {/* Diagram panel */}
        <div style={{
          ...styles.diagramArea,
          width: isDiagramOpen ? '40%' : '0',
          display: isDiagramOpen ? 'block' : 'none',
          position: 'relative' as const,
        }}>
          <DiagramPanel
            diagrams={diagrams}
            isOpen={isDiagramOpen}
            onToggle={() => setIsDiagramOpen(!isDiagramOpen)}
          />
        </div>

        {/* Collapsed diagram toggle (show when panel is closed) */}
        {!isDiagramOpen && diagrams.length > 0 && (
          <button
            onClick={() => setIsDiagramOpen(true)}
            style={styles.collapsedPanelHint}
            title="Open diagram panel"
          >
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
              <polyline points="15 18 9 12 15 6" />
            </svg>
            <span style={{ fontSize: '0.75rem' }}>{diagrams.length}</span>
          </button>
        )}
      </div>

      {/* Input bar */}
      <form onSubmit={handleSubmit} style={styles.inputBar}>
        <VoiceInput
          onAudioData={handleAudioData}
          isListening={isListening}
          onToggle={handleVoiceToggle}
        />

        <textarea
          value={inputText}
          onChange={e => setInputText(e.target.value)}
          onKeyDown={handleKeyDown}
          placeholder="Type a message..."
          style={styles.textInput}
          rows={1}
          disabled={!isConnected}
        />

        <button
          type="submit"
          disabled={!inputText.trim() || !isConnected}
          style={{
            ...styles.sendButton,
            opacity: (!inputText.trim() || !isConnected) ? 0.4 : 1,
          }}
        >
          <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
            <line x1="22" y1="2" x2="11" y2="13" />
            <polygon points="22 2 15 22 11 13 2 9 22 2" />
          </svg>
        </button>

        <AudioController
          enabled={isTTSEnabled}
          onToggle={() => setIsTTSEnabled(!isTTSEnabled)}
        />
      </form>
    </div>
  );
}

const styles: Record<string, React.CSSProperties> = {
  root: {
    display: 'flex',
    flexDirection: 'column',
    height: 'calc(100vh - 60px)',
    margin: '-2rem',
    background: '#0f0f13',
  },
  header: {
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'space-between',
    padding: '0.75rem 1.25rem',
    borderBottom: '1px solid #2a2a3d',
    background: '#1a1a24',
    flexShrink: 0,
  },
  headerLeft: {
    display: 'flex',
    alignItems: 'center',
    gap: '0.75rem',
  },
  backLink: {
    display: 'flex',
    alignItems: 'center',
    gap: '4px',
    color: '#7c8aff',
    textDecoration: 'none',
    fontSize: '0.9rem',
    fontWeight: 500,
  },
  headerDivider: {
    color: '#2a2a3d',
  },
  subtopicLabel: {
    fontSize: '0.9rem',
    color: '#8888a0',
  },
  connectionDot: {
    width: '8px',
    height: '8px',
    borderRadius: '50%',
    flexShrink: 0,
  },
  clearChatBtn: {
    background: 'none',
    border: '1px solid #2a2a3d',
    color: '#8888a0',
    padding: '0.4rem 0.75rem',
    borderRadius: '6px',
    fontSize: '0.85rem',
    cursor: 'pointer',
    transition: 'all 0.2s',
    display: 'flex',
    alignItems: 'center',
    gap: '4px',
  },
  diagramToggleBtn: {
    background: 'none',
    border: '1px solid #2a2a3d',
    color: '#8888a0',
    padding: '0.4rem 0.75rem',
    borderRadius: '6px',
    fontSize: '0.85rem',
    cursor: 'pointer',
    transition: 'all 0.2s',
  },
  mainContent: {
    flex: 1,
    display: 'flex',
    overflow: 'hidden',
    position: 'relative' as const,
  },
  chatArea: {
    transition: 'width 0.3s ease',
    overflow: 'hidden',
    display: 'flex',
    flexDirection: 'column',
  },
  diagramArea: {
    transition: 'width 0.3s ease',
    overflow: 'hidden',
    flexShrink: 0,
  },
  collapsedPanelHint: {
    position: 'absolute',
    right: 0,
    top: '50%',
    transform: 'translateY(-50%)',
    background: '#1a1a24',
    border: '1px solid #2a2a3d',
    borderRight: 'none',
    color: '#7c8aff',
    padding: '8px 6px',
    borderRadius: '8px 0 0 8px',
    display: 'flex',
    flexDirection: 'column',
    alignItems: 'center',
    gap: '4px',
    cursor: 'pointer',
    zIndex: 10,
  },
  inputBar: {
    display: 'flex',
    alignItems: 'center',
    gap: '0.75rem',
    padding: '0.75rem 1.25rem',
    borderTop: '1px solid #2a2a3d',
    background: '#1a1a24',
    flexShrink: 0,
  },
  textInput: {
    flex: 1,
    background: '#0f0f13',
    border: '1px solid #2a2a3d',
    borderRadius: '8px',
    color: '#e0e0e0',
    padding: '0.65rem 1rem',
    fontSize: '0.95rem',
    resize: 'none',
    outline: 'none',
    fontFamily: 'inherit',
    lineHeight: 1.5,
    minHeight: '42px',
    maxHeight: '120px',
  },
  sendButton: {
    background: '#7c8aff',
    border: 'none',
    color: '#fff',
    borderRadius: '50%',
    width: '42px',
    height: '42px',
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'center',
    transition: 'opacity 0.2s',
    flexShrink: 0,
  },
};
