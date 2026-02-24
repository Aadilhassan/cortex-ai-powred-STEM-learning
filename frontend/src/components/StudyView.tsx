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
    <div className="flex flex-col h-[calc(100vh-56px)]">
      {/* Header */}
      <div className="flex items-center justify-between px-4 py-3 bg-zinc-900/80 backdrop-blur-sm border-b border-zinc-800/50 shrink-0">
        <div className="flex items-center gap-3">
          <a href="/" className="flex items-center gap-1 text-sm text-indigo-400 hover:text-indigo-300 no-underline hover:no-underline transition-colors">
            <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
              <polyline points="15 18 9 12 15 6" />
            </svg>
            Back
          </a>
          <span className="text-sm text-zinc-500">
            Subtopic: <strong>{subtopicId}</strong>
          </span>
          <span
            className={`w-2 h-2 rounded-full shrink-0 ${isConnected ? 'bg-green-400 animate-pulse' : 'bg-red-400'}`}
            title={isConnected ? 'Connected' : 'Disconnected'}
          />
        </div>
        <div className="flex gap-2 items-center">
          <button
            onClick={handleClearChat}
            className="p-2 rounded-lg hover:bg-zinc-800 text-zinc-500 hover:text-zinc-300 transition-colors flex items-center gap-1.5 text-sm border border-zinc-800"
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
            className="p-2 rounded-lg hover:bg-zinc-800 text-zinc-500 hover:text-zinc-300 transition-colors flex items-center gap-1.5 text-sm border border-zinc-800"
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
            className="p-2 rounded-lg hover:bg-zinc-800 text-zinc-500 hover:text-zinc-300 transition-colors flex items-center gap-1.5 text-sm border border-zinc-800"
          >
            Diagrams {isDiagramOpen ? '\u25B6' : '\u25C0'}
          </button>
        </div>
      </div>

      {/* Main content area */}
      <div className="flex flex-1 overflow-hidden relative">
        {/* Chat panel */}
        <div className={`${isDiagramOpen ? 'w-[60%]' : 'w-full'} flex flex-col overflow-hidden transition-all duration-300`}>
          <ChatPanel
            messages={messages}
            streamingText={streamingText}
            isThinking={isThinking}
          />
        </div>

        {/* Diagram panel */}
        <div className={isDiagramOpen
          ? 'w-[40%] shrink-0 transition-all duration-300 relative'
          : 'w-0 shrink-0 overflow-hidden transition-all duration-300'
        }>
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
            className="absolute right-0 top-1/2 -translate-y-1/2 bg-zinc-900 border border-zinc-800 border-r-0 text-indigo-400 px-1.5 py-3 rounded-l-lg flex flex-col items-center gap-1 cursor-pointer transition-colors z-10 hover:text-indigo-300"
            title="Open diagram panel"
          >
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
              <polyline points="15 18 9 12 15 6" />
            </svg>
            <span className="text-xs">{diagrams.length}</span>
          </button>
        )}
      </div>

      {/* Input bar */}
      <form onSubmit={handleSubmit} className="flex items-center gap-3 px-4 py-3 bg-zinc-900 border-t border-zinc-800/50 shrink-0">
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
          className="flex-1 bg-zinc-950 border border-zinc-800 rounded-xl px-4 py-2.5 text-zinc-200 text-sm resize-none focus:border-indigo-500/50 focus:ring-1 focus:ring-indigo-500/20 focus:outline-none transition-colors font-sans leading-normal min-h-[42px] max-h-[120px]"
          rows={1}
          disabled={!isConnected}
        />

        <button
          type="submit"
          disabled={!inputText.trim() || !isConnected}
          className="bg-indigo-500 hover:bg-indigo-400 disabled:opacity-30 text-white rounded-full w-10 h-10 flex items-center justify-center shrink-0 transition-all border-none"
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
