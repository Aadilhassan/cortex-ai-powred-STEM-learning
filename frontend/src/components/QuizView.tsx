import { useState, useEffect, useRef, useCallback } from 'react';
import { getQuiz, submitQuiz } from '../lib/api';

/* ── Types ────────────────────────────────────────────────────────────── */

interface MCQQuestion {
  type: 'mcq';
  question: string;
  options: string[];
  correct_answer: string;
  explanation: string;
}

interface ShortAnswerQuestion {
  type: 'short_answer';
  question: string;
  correct_answer: string;
  explanation: string;
}

interface DiagramQuestion {
  type: 'diagram';
  question: string;
  diagram: string;
  correct_answer: string;
  explanation: string;
}

type Question = MCQQuestion | ShortAnswerQuestion | DiagramQuestion;

interface Quiz {
  id: string;
  course_id: string;
  questions: Question[];
}

interface FeedbackItem {
  question: string;
  your_answer: string;
  correct_answer: string;
  correct: boolean;
  explanation: string;
}

interface SubmitResult {
  score: number;
  feedback: FeedbackItem[];
}

/* ── Theme tokens ─────────────────────────────────────────────────────── */

const colors = {
  bg: '#0f0f13',
  surface: '#1a1a24',
  border: '#2a2a3d',
  text: '#e0e0e0',
  textMuted: '#8888a0',
  accent: '#7c8aff',
  success: '#4ade80',
  error: '#f87171',
  warning: '#facc15',
} as const;

/* ── Mermaid diagram component ────────────────────────────────────────── */

function MermaidDiagram({ code, id }: { code: string; id: string }) {
  const containerRef = useRef<HTMLDivElement>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;

    async function render() {
      try {
        const mermaid = (await import('mermaid')).default;
        mermaid.initialize({
          startOnLoad: false,
          theme: 'dark',
          themeVariables: {
            primaryColor: colors.accent,
            primaryTextColor: colors.text,
            lineColor: colors.border,
            background: colors.surface,
          },
        });

        const uniqueId = `mermaid-${id}-${Date.now()}`;
        const { svg } = await mermaid.render(uniqueId, code);
        if (!cancelled && containerRef.current) {
          containerRef.current.innerHTML = svg;
        }
      } catch (err) {
        if (!cancelled) {
          setError(err instanceof Error ? err.message : 'Failed to render diagram');
        }
      }
    }

    render();
    return () => { cancelled = true; };
  }, [code, id]);

  if (error) {
    return (
      <pre style={{
        background: colors.bg,
        border: `1px solid ${colors.border}`,
        borderRadius: '8px',
        padding: '1rem',
        overflow: 'auto',
        fontSize: '0.85rem',
        color: colors.textMuted,
      }}>
        {code}
      </pre>
    );
  }

  return (
    <div
      ref={containerRef}
      style={{
        background: colors.bg,
        border: `1px solid ${colors.border}`,
        borderRadius: '8px',
        padding: '1rem',
        overflow: 'auto',
        display: 'flex',
        justifyContent: 'center',
      }}
    />
  );
}

/* ── Main component ───────────────────────────────────────────────────── */

export default function QuizView({ quizId }: { quizId: string }) {
  const [quiz, setQuiz] = useState<Quiz | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [answers, setAnswers] = useState<string[]>([]);
  const [submitting, setSubmitting] = useState(false);
  const [result, setResult] = useState<SubmitResult | null>(null);

  /* Fetch quiz on mount */
  useEffect(() => {
    let cancelled = false;
    async function load() {
      try {
        const data = await getQuiz(quizId);
        if (cancelled) return;
        setQuiz(data);
        setAnswers(new Array(data.questions.length).fill(''));
      } catch (err) {
        if (!cancelled) {
          setError(err instanceof Error ? err.message : 'Failed to load quiz');
        }
      } finally {
        if (!cancelled) setLoading(false);
      }
    }
    load();
    return () => { cancelled = true; };
  }, [quizId]);

  /* Answer setter */
  const setAnswer = useCallback((index: number, value: string) => {
    setAnswers(prev => {
      const next = [...prev];
      next[index] = value;
      return next;
    });
  }, []);

  /* Submit handler */
  const handleSubmit = async () => {
    setSubmitting(true);
    try {
      const data = await submitQuiz(quizId, answers);
      setResult(data);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to submit quiz');
    } finally {
      setSubmitting(false);
    }
  };

  const allAnswered = answers.length > 0 && answers.every(a => a.trim() !== '');

  /* ── Loading state ─────────────────────────────────────────────────── */

  if (loading) {
    return (
      <div style={{ textAlign: 'center', padding: '4rem 0', color: colors.textMuted }}>
        Loading quiz...
      </div>
    );
  }

  if (error && !quiz) {
    return (
      <div style={{ textAlign: 'center', padding: '4rem 0', color: colors.error }}>
        {error}
      </div>
    );
  }

  if (!quiz) return null;

  /* ── Results state ─────────────────────────────────────────────────── */

  if (result) {
    const total = result.feedback.length;
    const correctCount = result.feedback.filter(f => f.correct).length;
    const pct = Math.round(result.score);
    const scoreColor = pct >= 70 ? colors.success : pct >= 50 ? colors.warning : colors.error;

    return (
      <div style={{ maxWidth: 800, margin: '0 auto' }}>
        {/* Score banner */}
        <div style={{
          background: colors.surface,
          border: `1px solid ${colors.border}`,
          borderRadius: '12px',
          padding: '2rem',
          textAlign: 'center',
          marginBottom: '2rem',
        }}>
          <div style={{ fontSize: '2.5rem', fontWeight: 700, color: scoreColor }}>
            {correctCount}/{total} &mdash; {pct}%
          </div>
          <div style={{ color: colors.textMuted, marginTop: '0.5rem' }}>
            Quiz complete
          </div>
        </div>

        {/* Feedback per question */}
        {result.feedback.map((fb, i) => {
          const question = quiz.questions[i];
          return (
            <div key={i} style={{
              background: colors.surface,
              border: `1px solid ${fb.correct ? colors.success : colors.error}`,
              borderRadius: '12px',
              padding: '1.5rem',
              marginBottom: '1rem',
            }}>
              <div style={{ display: 'flex', alignItems: 'flex-start', gap: '0.75rem', marginBottom: '1rem' }}>
                <span style={{
                  fontSize: '1.25rem',
                  flexShrink: 0,
                  color: fb.correct ? colors.success : colors.error,
                }}>
                  {fb.correct ? '\u2713' : '\u2717'}
                </span>
                <div style={{ fontWeight: 600, lineHeight: 1.4 }}>
                  Q{i + 1}. {fb.question}
                </div>
              </div>

              {/* Show diagram if diagram question */}
              {question?.type === 'diagram' && question.diagram && (
                <div style={{ marginBottom: '1rem' }}>
                  <MermaidDiagram code={question.diagram} id={`result-${i}`} />
                </div>
              )}

              <div style={{
                display: 'grid',
                gridTemplateColumns: '1fr 1fr',
                gap: '0.75rem',
                fontSize: '0.9rem',
                marginBottom: fb.explanation ? '0.75rem' : 0,
              }}>
                <div>
                  <span style={{ color: colors.textMuted }}>Your answer: </span>
                  <span style={{ color: fb.correct ? colors.success : colors.error }}>
                    {fb.your_answer || '(empty)'}
                  </span>
                </div>
                <div>
                  <span style={{ color: colors.textMuted }}>Correct answer: </span>
                  <span style={{ color: colors.success }}>
                    {fb.correct_answer}
                  </span>
                </div>
              </div>

              {fb.explanation && (
                <div style={{
                  fontSize: '0.85rem',
                  color: colors.textMuted,
                  background: colors.bg,
                  borderRadius: '8px',
                  padding: '0.75rem 1rem',
                  lineHeight: 1.5,
                }}>
                  {fb.explanation}
                </div>
              )}
            </div>
          );
        })}

        {/* Back to course link */}
        <div style={{ textAlign: 'center', marginTop: '2rem' }}>
          <a
            href={`/course/${quiz.course_id}`}
            style={{
              display: 'inline-block',
              padding: '0.75rem 2rem',
              background: colors.accent,
              color: '#fff',
              borderRadius: '8px',
              fontWeight: 600,
              textDecoration: 'none',
            }}
          >
            Back to Course
          </a>
        </div>
      </div>
    );
  }

  /* ── Quiz state ────────────────────────────────────────────────────── */

  return (
    <div style={{ maxWidth: 800, margin: '0 auto' }}>
      <h1 style={{ fontSize: '1.5rem', fontWeight: 700, marginBottom: '2rem' }}>
        Quiz
      </h1>

      {quiz.questions.map((q, i) => (
        <div key={i} style={{
          background: colors.surface,
          border: `1px solid ${colors.border}`,
          borderRadius: '12px',
          padding: '1.5rem',
          marginBottom: '1.25rem',
        }}>
          <div style={{ fontWeight: 600, marginBottom: '1rem', lineHeight: 1.4 }}>
            Q{i + 1}. {q.question}
          </div>

          {/* Diagram rendering */}
          {q.type === 'diagram' && q.diagram && (
            <div style={{ marginBottom: '1rem' }}>
              <MermaidDiagram code={q.diagram} id={`q-${i}`} />
            </div>
          )}

          {/* MCQ options */}
          {q.type === 'mcq' && (
            <div style={{ display: 'flex', flexDirection: 'column', gap: '0.5rem' }}>
              {q.options.map((opt, j) => {
                const selected = answers[i] === opt;
                return (
                  <label
                    key={j}
                    style={{
                      display: 'flex',
                      alignItems: 'center',
                      gap: '0.75rem',
                      padding: '0.75rem 1rem',
                      background: colors.bg,
                      border: `2px solid ${selected ? colors.accent : colors.border}`,
                      borderRadius: '8px',
                      cursor: 'pointer',
                      transition: 'border-color 0.15s',
                    }}
                  >
                    <input
                      type="radio"
                      name={`question-${i}`}
                      value={opt}
                      checked={selected}
                      onChange={() => setAnswer(i, opt)}
                      style={{ display: 'none' }}
                    />
                    <span style={{
                      width: 20,
                      height: 20,
                      borderRadius: '50%',
                      border: `2px solid ${selected ? colors.accent : colors.border}`,
                      background: selected ? colors.accent : 'transparent',
                      flexShrink: 0,
                      display: 'flex',
                      alignItems: 'center',
                      justifyContent: 'center',
                    }}>
                      {selected && (
                        <span style={{ width: 8, height: 8, borderRadius: '50%', background: '#fff' }} />
                      )}
                    </span>
                    <span>{opt}</span>
                  </label>
                );
              })}
            </div>
          )}

          {/* Short answer and diagram answer input */}
          {(q.type === 'short_answer' || q.type === 'diagram') && (
            <input
              type="text"
              placeholder="Type your answer..."
              value={answers[i]}
              onChange={e => setAnswer(i, e.target.value)}
              style={{
                width: '100%',
                padding: '0.75rem 1rem',
                background: colors.bg,
                border: `1px solid ${colors.border}`,
                borderRadius: '8px',
                color: colors.text,
                fontSize: '0.95rem',
                outline: 'none',
              }}
              onFocus={e => e.target.style.borderColor = colors.accent}
              onBlur={e => e.target.style.borderColor = colors.border}
            />
          )}
        </div>
      ))}

      {/* Submit button */}
      <div style={{ textAlign: 'center', marginTop: '2rem', marginBottom: '2rem' }}>
        <button
          onClick={handleSubmit}
          disabled={!allAnswered || submitting}
          style={{
            padding: '0.75rem 2.5rem',
            background: allAnswered && !submitting ? colors.accent : colors.border,
            color: allAnswered && !submitting ? '#fff' : colors.textMuted,
            border: 'none',
            borderRadius: '8px',
            fontSize: '1rem',
            fontWeight: 600,
            cursor: allAnswered && !submitting ? 'pointer' : 'not-allowed',
            transition: 'background 0.15s',
          }}
        >
          {submitting ? 'Submitting...' : 'Submit Quiz'}
        </button>
      </div>

      {error && (
        <div style={{ textAlign: 'center', color: colors.error, marginTop: '1rem' }}>
          {error}
        </div>
      )}
    </div>
  );
}
