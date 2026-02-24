import { useEffect, useRef, useState } from 'react';

// Web Speech API type augmentation
interface IWindow extends Window {
  SpeechRecognition?: new () => ISpeechRecognition;
  webkitSpeechRecognition?: new () => ISpeechRecognition;
}

interface ISpeechRecognition extends EventTarget {
  continuous: boolean;
  interimResults: boolean;
  lang: string;
  onresult: ((event: ISpeechRecognitionEvent) => void) | null;
  onerror: ((event: { error: string }) => void) | null;
  onend: (() => void) | null;
  start(): void;
  stop(): void;
  abort(): void;
}

interface ISpeechRecognitionEvent {
  resultIndex: number;
  results: {
    length: number;
    [index: number]: {
      isFinal: boolean;
      0: { transcript: string };
    };
  };
}

interface VoiceInputProps {
  onTranscript: (text: string) => void;
  isListening: boolean;
  onToggle: () => void;
}

export default function VoiceInput({ onTranscript, isListening, onToggle }: VoiceInputProps) {
  const [interimText, setInterimText] = useState('');
  const recognitionRef = useRef<ISpeechRecognition | null>(null);
  const w = typeof window !== 'undefined' ? (window as unknown as IWindow) : null;
  const isSupported = !!(w && (w.SpeechRecognition || w.webkitSpeechRecognition));

  useEffect(() => {
    if (!isSupported || !w) return;

    const SpeechRecognitionCtor = w.SpeechRecognition || w.webkitSpeechRecognition;
    if (!SpeechRecognitionCtor) return;
    const recognition = new SpeechRecognitionCtor();
    recognition.continuous = false;
    recognition.interimResults = true;
    recognition.lang = 'en-US';

    recognition.onresult = (event: ISpeechRecognitionEvent) => {
      let interim = '';
      let finalResult = '';

      for (let i = event.resultIndex; i < event.results.length; i++) {
        const transcript = event.results[i][0].transcript;
        if (event.results[i].isFinal) {
          finalResult += transcript;
        } else {
          interim += transcript;
        }
      }

      if (finalResult) {
        onTranscript(finalResult);
        setInterimText('');
      } else {
        setInterimText(interim);
      }
    };

    recognition.onerror = (event: { error: string }) => {
      console.error('Speech recognition error:', event.error);
      setInterimText('');
    };

    recognition.onend = () => {
      setInterimText('');
      // If we're still supposed to be listening but recognition ended, the parent
      // controls the state via onToggle — we just notify through the effect below
    };

    recognitionRef.current = recognition;

    return () => {
      recognition.abort();
      recognitionRef.current = null;
    };
  }, [isSupported, w, onTranscript]);

  useEffect(() => {
    const recognition = recognitionRef.current;
    if (!recognition) return;

    if (isListening) {
      try {
        recognition.start();
      } catch {
        // Already started — ignore
      }
    } else {
      recognition.stop();
      setInterimText('');
    }
  }, [isListening]);

  if (!isSupported) {
    return null;
  }

  return (
    <div style={styles.wrapper}>
      <button
        onClick={onToggle}
        style={{
          ...styles.micButton,
          ...(isListening ? styles.micButtonActive : {}),
        }}
        title={isListening ? 'Stop listening' : 'Start voice input'}
      >
        <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
          <path d="M12 1a3 3 0 0 0-3 3v8a3 3 0 0 0 6 0V4a3 3 0 0 0-3-3z" />
          <path d="M19 10v2a7 7 0 0 1-14 0v-2" />
          <line x1="12" y1="19" x2="12" y2="23" />
          <line x1="8" y1="23" x2="16" y2="23" />
        </svg>
        {isListening && <span style={styles.pulseRing} />}
      </button>

      {isListening && interimText && (
        <div style={styles.interimText}>
          {interimText}
        </div>
      )}

      <style>{`
        @keyframes pulse-ring-anim {
          0% { transform: scale(1); opacity: 0.8; }
          100% { transform: scale(1.8); opacity: 0; }
        }
      `}</style>
    </div>
  );
}

const styles: Record<string, React.CSSProperties> = {
  wrapper: {
    position: 'relative',
    display: 'flex',
    alignItems: 'center',
  },
  micButton: {
    background: 'none',
    border: '2px solid #2a2a3d',
    color: '#8888a0',
    borderRadius: '50%',
    width: '42px',
    height: '42px',
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'center',
    position: 'relative',
    transition: 'all 0.2s',
    flexShrink: 0,
  },
  micButtonActive: {
    borderColor: '#ff4444',
    color: '#ff4444',
    background: 'rgba(255, 68, 68, 0.1)',
  },
  pulseRing: {
    position: 'absolute',
    top: '-2px',
    left: '-2px',
    right: '-2px',
    bottom: '-2px',
    borderRadius: '50%',
    border: '2px solid #ff4444',
    animation: 'pulse-ring-anim 1.5s infinite',
    pointerEvents: 'none' as const,
  },
  interimText: {
    position: 'absolute',
    bottom: '100%',
    left: '50%',
    transform: 'translateX(-50%)',
    background: '#1a1a24',
    border: '1px solid #2a2a3d',
    borderRadius: '8px',
    padding: '0.5rem 0.75rem',
    fontSize: '0.85rem',
    color: '#8888a0',
    whiteSpace: 'nowrap',
    marginBottom: '8px',
    maxWidth: '300px',
    overflow: 'hidden',
    textOverflow: 'ellipsis',
  },
};
