interface AudioControllerProps {
  enabled: boolean;
  onToggle: () => void;
}

export default function AudioController({ enabled, onToggle }: AudioControllerProps) {
  return (
    <button
      onClick={onToggle}
      className={`w-10 h-10 rounded-full border-2 flex items-center justify-center transition-all shrink-0 cursor-pointer ${
        enabled
          ? 'border-indigo-500 text-indigo-400 bg-indigo-500/10'
          : 'border-zinc-700 text-zinc-500 bg-transparent hover:border-zinc-500 hover:text-zinc-300'
      }`}
      title={enabled ? 'Disable text-to-speech' : 'Enable text-to-speech'}
    >
      {enabled ? (
        <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
          <polygon points="11 5 6 9 2 9 2 15 6 15 11 19 11 5" />
          <path d="M19.07 4.93a10 10 0 0 1 0 14.14" />
          <path d="M15.54 8.46a5 5 0 0 1 0 7.07" />
        </svg>
      ) : (
        <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
          <polygon points="11 5 6 9 2 9 2 15 6 15 11 19 11 5" />
          <line x1="23" y1="9" x2="17" y2="15" />
          <line x1="17" y1="9" x2="23" y2="15" />
        </svg>
      )}
    </button>
  );
}
