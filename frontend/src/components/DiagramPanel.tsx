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
        background: '#1a1a24',
        primaryColor: '#7c8aff',
        primaryTextColor: '#e0e0e0',
        primaryBorderColor: '#2a2a3d',
        lineColor: '#8888a0',
        secondaryColor: '#2a2a3d',
        tertiaryColor: '#0f0f13',
      },
    });
    mermaidInitialized = true;
  }
}

function DiagramRenderer({ code, index }: { code: string; index: number }) {
  const containerRef = useRef<HTMLDivElement>(null);

  const renderDiagram = useCallback(async () => {
    if (!containerRef.current) return;
    try {
      initMermaid();
      const id = `mermaid-diagram-${index}-${Date.now()}`;
      const { svg } = await mermaid.render(id, code);
      if (containerRef.current) {
        containerRef.current.innerHTML = svg;
      }
    } catch (err) {
      console.error('Mermaid render error:', err);
      if (containerRef.current) {
        containerRef.current.innerHTML = `<pre style="color: #ff6b6b; padding: 1em; font-size: 0.85em; white-space: pre-wrap;">Diagram render error:\n${code}</pre>`;
      }
    }
  }, [code, index]);

  useEffect(() => {
    renderDiagram();
  }, [renderDiagram]);

  return (
    <div
      ref={containerRef}
      style={{
        background: '#12121a',
        borderRadius: '8px',
        padding: '1rem',
        border: '1px solid #2a2a3d',
        overflow: 'auto',
        textAlign: 'center',
      }}
    />
  );
}

export default function DiagramPanel({ diagrams, isOpen, onToggle }: DiagramPanelProps) {
  if (!isOpen) {
    return (
      <button onClick={onToggle} style={styles.collapsedToggle} title="Open diagram panel">
        <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
          <polyline points="15 18 9 12 15 6" />
        </svg>
      </button>
    );
  }

  const latestDiagram = diagrams.length > 0 ? diagrams[diagrams.length - 1] : null;
  const previousDiagrams = diagrams.length > 1 ? diagrams.slice(0, -1).reverse() : [];

  return (
    <div style={styles.panel}>
      <div style={styles.header}>
        <span style={styles.headerTitle}>Diagrams</span>
        <button onClick={onToggle} style={styles.toggleButton} title="Close diagram panel">
          <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
            <polyline points="9 18 15 12 9 6" />
          </svg>
        </button>
      </div>

      <div style={styles.content}>
        {diagrams.length === 0 ? (
          <div style={styles.emptyState}>
            <svg width="48" height="48" viewBox="0 0 24 24" fill="none" stroke="#8888a0" strokeWidth="1.5">
              <rect x="3" y="3" width="18" height="18" rx="2" />
              <path d="M3 9h18M9 21V9" />
            </svg>
            <p style={{ color: '#8888a0', marginTop: '0.75rem', fontSize: '0.9rem' }}>
              Diagrams will appear here as the AI generates them during your conversation.
            </p>
          </div>
        ) : (
          <>
            {latestDiagram && (
              <div style={styles.latestSection}>
                <span style={styles.sectionLabel}>Latest</span>
                <DiagramRenderer code={latestDiagram} index={diagrams.length - 1} />
              </div>
            )}

            {previousDiagrams.length > 0 && (
              <div style={styles.previousSection}>
                <span style={styles.sectionLabel}>Previous</span>
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

const styles: Record<string, React.CSSProperties> = {
  panel: {
    display: 'flex',
    flexDirection: 'column',
    height: '100%',
    borderLeft: '1px solid #2a2a3d',
    background: '#0f0f13',
  },
  header: {
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'space-between',
    padding: '0.75rem 1rem',
    borderBottom: '1px solid #2a2a3d',
    background: '#1a1a24',
  },
  headerTitle: {
    fontWeight: 600,
    fontSize: '0.9rem',
    color: '#e0e0e0',
  },
  toggleButton: {
    background: 'none',
    border: 'none',
    color: '#8888a0',
    padding: '4px',
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'center',
    borderRadius: '4px',
    transition: 'color 0.2s',
  },
  collapsedToggle: {
    position: 'absolute',
    right: 0,
    top: '50%',
    transform: 'translateY(-50%)',
    background: '#1a1a24',
    border: '1px solid #2a2a3d',
    borderRight: 'none',
    color: '#8888a0',
    padding: '12px 4px',
    borderRadius: '8px 0 0 8px',
    display: 'flex',
    alignItems: 'center',
    cursor: 'pointer',
    zIndex: 10,
  },
  content: {
    flex: 1,
    overflowY: 'auto',
    padding: '1rem',
    display: 'flex',
    flexDirection: 'column',
    gap: '1rem',
  },
  emptyState: {
    display: 'flex',
    flexDirection: 'column',
    alignItems: 'center',
    justifyContent: 'center',
    height: '100%',
    textAlign: 'center',
    padding: '2rem',
  },
  latestSection: {
    display: 'flex',
    flexDirection: 'column',
    gap: '0.5rem',
  },
  previousSection: {
    display: 'flex',
    flexDirection: 'column',
    gap: '0.75rem',
    marginTop: '0.5rem',
  },
  sectionLabel: {
    fontSize: '0.75rem',
    fontWeight: 600,
    textTransform: 'uppercase' as const,
    letterSpacing: '0.05em',
    color: '#8888a0',
  },
};
