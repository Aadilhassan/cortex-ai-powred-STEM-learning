import { useRef, useState, useEffect, useCallback } from 'react';

interface VoiceInputProps {
  onAudioData: (base64: string) => void;
  isListening: boolean;
  onToggle: () => void;
}

export default function VoiceInput({ onAudioData, isListening, onToggle }: VoiceInputProps) {
  const [status, setStatus] = useState<'idle' | 'listening' | 'speaking' | 'processing' | 'error'>('idle');
  const [errorMsg, setErrorMsg] = useState('');

  const streamRef = useRef<MediaStream | null>(null);
  const recorderRef = useRef<MediaRecorder | null>(null);
  const chunksRef = useRef<Blob[]>([]);
  const analyserRef = useRef<AnalyserNode | null>(null);
  const audioCtxRef = useRef<AudioContext | null>(null);
  const rafRef = useRef<number>(0);
  const silenceStartRef = useRef<number>(0);
  const isSpeakingRef = useRef(false);
  const activeRef = useRef(false); // master flag

  const SILENCE_THRESHOLD = 12;
  const SILENCE_DURATION = 1200;
  const onAudioDataRef = useRef(onAudioData);
  onAudioDataRef.current = onAudioData;

  // Volume monitoring — runs continuously via requestAnimationFrame
  const monitorVolume = useCallback(() => {
    if (!activeRef.current) return;
    const analyser = analyserRef.current;
    if (!analyser) { rafRef.current = requestAnimationFrame(monitorVolume); return; }

    const data = new Uint8Array(analyser.fftSize);
    analyser.getByteTimeDomainData(data);

    let sum = 0;
    for (let i = 0; i < data.length; i++) {
      const val = (data[i] - 128) / 128;
      sum += val * val;
    }
    const rms = Math.sqrt(sum / data.length) * 100;
    const now = Date.now();

    if (rms > SILENCE_THRESHOLD) {
      if (!isSpeakingRef.current) {
        isSpeakingRef.current = true;
        setStatus('speaking');
      }
      silenceStartRef.current = 0;
    } else if (isSpeakingRef.current) {
      if (silenceStartRef.current === 0) {
        silenceStartRef.current = now;
      } else if (now - silenceStartRef.current > SILENCE_DURATION) {
        // Utterance complete — stop recorder, which triggers send + restart
        isSpeakingRef.current = false;
        silenceStartRef.current = 0;
        const rec = recorderRef.current;
        if (rec && rec.state === 'recording') {
          rec.stop();
        }
      }
    }

    // Always keep the loop running while active
    rafRef.current = requestAnimationFrame(monitorVolume);
  }, []);

  // Start a new MediaRecorder on the existing stream
  const startRecorder = useCallback(() => {
    const stream = streamRef.current;
    if (!stream || !activeRef.current) return;

    const mimeType = MediaRecorder.isTypeSupported('audio/webm;codecs=opus')
      ? 'audio/webm;codecs=opus' : 'audio/webm';

    const recorder = new MediaRecorder(stream, { mimeType });
    chunksRef.current = [];

    recorder.ondataavailable = (e) => {
      if (e.data.size > 0) chunksRef.current.push(e.data);
    };

    recorder.onstop = () => {
      const chunks = chunksRef.current;
      chunksRef.current = [];
      if (chunks.length === 0) { startRecorder(); return; }

      const blob = new Blob(chunks, { type: mimeType });
      if (blob.size < 2000) {
        // Too short, restart immediately
        if (activeRef.current) startRecorder();
        return;
      }

      setStatus('processing');

      const reader = new FileReader();
      reader.onload = () => {
        const b64 = (reader.result as string).split(',')[1];
        if (b64) onAudioDataRef.current(b64);
        // Restart recording for next utterance
        if (activeRef.current) {
          startRecorder();
          setStatus('listening');
        }
      };
      reader.onerror = () => {
        if (activeRef.current) {
          startRecorder();
          setStatus('listening');
        }
      };
      reader.readAsDataURL(blob);
    };

    recorderRef.current = recorder;
    recorder.start();
    isSpeakingRef.current = false;
    silenceStartRef.current = 0;
    setStatus('listening');
  }, []);

  useEffect(() => {
    if (!isListening) {
      activeRef.current = false;
      cancelAnimationFrame(rafRef.current);
      if (recorderRef.current?.state === 'recording') {
        try { recorderRef.current.stop(); } catch { /* */ }
      }
      recorderRef.current = null;
      if (streamRef.current) {
        streamRef.current.getTracks().forEach(t => t.stop());
        streamRef.current = null;
      }
      if (audioCtxRef.current) {
        audioCtxRef.current.close().catch(() => {});
        audioCtxRef.current = null;
      }
      analyserRef.current = null;
      setStatus('idle');
      return;
    }

    activeRef.current = true;
    let cancelled = false;

    (async () => {
      try {
        const stream = await navigator.mediaDevices.getUserMedia({
          audio: { echoCancellation: true, noiseSuppression: true },
        });
        if (cancelled || !activeRef.current) {
          stream.getTracks().forEach(t => t.stop());
          return;
        }
        streamRef.current = stream;

        const ctx = new AudioContext();
        audioCtxRef.current = ctx;
        const source = ctx.createMediaStreamSource(stream);
        const analyser = ctx.createAnalyser();
        analyser.fftSize = 512;
        source.connect(analyser);
        analyserRef.current = analyser;

        startRecorder();
        rafRef.current = requestAnimationFrame(monitorVolume);
      } catch {
        if (!cancelled) {
          setStatus('error');
          setErrorMsg('Mic permission denied');
        }
      }
    })();

    return () => {
      cancelled = true;
      activeRef.current = false;
      cancelAnimationFrame(rafRef.current);
    };
  }, [isListening, startRecorder, monitorVolume]);

  const label =
    status === 'speaking' ? 'Speaking...' :
    status === 'listening' ? 'Listening...' :
    status === 'processing' ? 'Transcribing...' :
    status === 'error' ? errorMsg : '';

  const isActive = status === 'listening' || status === 'speaking' || status === 'processing';

  const micClasses = `w-10 h-10 rounded-full border-2 flex items-center justify-center relative transition-all shrink-0 cursor-pointer bg-transparent ${
    status === 'speaking'
      ? 'border-green-500 text-green-400 bg-green-500/10'
      : isActive
        ? 'border-red-500 text-red-400 bg-red-500/10'
        : status === 'error'
          ? 'border-amber-500 text-amber-400 bg-amber-500/10'
          : 'border-zinc-700 text-zinc-500 hover:border-zinc-500 hover:text-zinc-300'
  }`;

  const tooltipTextColor =
    status === 'speaking' ? 'text-green-400'
    : status === 'processing' ? 'text-indigo-400'
    : status === 'error' ? 'text-amber-400'
    : 'text-red-400';

  return (
    <div className="relative flex items-center">
      <button
        onClick={onToggle}
        className={micClasses}
        title={isActive ? 'Stop listening' : 'Start voice input'}
      >
        <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
          <path d="M12 1a3 3 0 0 0-3 3v8a3 3 0 0 0 6 0V4a3 3 0 0 0-3-3z" />
          <path d="M19 10v2a7 7 0 0 1-14 0v-2" />
          <line x1="12" y1="19" x2="12" y2="23" />
          <line x1="8" y1="23" x2="16" y2="23" />
        </svg>
        {status === 'speaking' && <span className="absolute inset-[-2px] rounded-full border-2 border-green-500 animate-pulse-ring pointer-events-none" />}
        {(status === 'listening' || status === 'processing') && <span className="absolute inset-[-2px] rounded-full border-2 border-red-500 animate-pulse-ring pointer-events-none" />}
      </button>

      {label && (
        <div className={`absolute bottom-full left-1/2 -translate-x-1/2 mb-2 bg-zinc-900 border border-zinc-800 rounded-lg px-2.5 py-1.5 text-xs whitespace-nowrap ${tooltipTextColor}`}>
          {label}
        </div>
      )}
    </div>
  );
}
