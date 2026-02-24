interface AudioControllerProps {
  enabled: boolean;
  onToggle: () => void;
}

export default function AudioController({ enabled, onToggle }: AudioControllerProps) {
  return (
    <button
      onClick={onToggle}
      style={{
        ...styles.button,
        ...(enabled ? styles.enabled : styles.disabled),
      }}
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

const styles: Record<string, React.CSSProperties> = {
  button: {
    border: '2px solid #2a2a3d',
    borderRadius: '50%',
    width: '42px',
    height: '42px',
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'center',
    transition: 'all 0.2s',
    flexShrink: 0,
  },
  enabled: {
    background: 'rgba(124, 138, 255, 0.1)',
    borderColor: '#7c8aff',
    color: '#7c8aff',
  },
  disabled: {
    background: 'none',
    color: '#8888a0',
  },
};
