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
            darkMode: true,
            background: '#18181b',
            primaryColor: '#818cf8',
            primaryTextColor: '#d4d4d8',
            primaryBorderColor: '#3f3f46',
            lineColor: '#71717a',
            secondaryColor: '#27272a',
            tertiaryColor: '#09090b',
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
      <pre className="bg-zinc-950 border border-zinc-800 rounded-lg p-4 overflow-auto text-sm text-zinc-500">
        {code}
      </pre>
    );
  }

  return (
    <div
      ref={containerRef}
      className="bg-zinc-950 border border-zinc-800 rounded-lg p-4 overflow-auto flex justify-center"
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
      <div className="text-center py-16 text-zinc-500">
        Loading quiz...
      </div>
    );
  }

  if (error && !quiz) {
    return (
      <div className="text-center py-16 text-red-400">
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
    const scoreColor = pct >= 70 ? 'text-green-400' : pct >= 50 ? 'text-amber-400' : 'text-red-400';

    return (
      <div className="max-w-3xl mx-auto space-y-6">
        {/* Score banner */}
        <div className="bg-zinc-900 rounded-xl p-8 text-center mb-8">
          <div className={`text-4xl font-bold ${scoreColor}`}>
            {correctCount}/{total} &mdash; {pct}%
          </div>
          <div className="text-zinc-500 mt-2">
            Quiz complete
          </div>
        </div>

        {/* Feedback per question */}
        {result.feedback.map((fb, i) => {
          const question = quiz.questions[i];
          return (
            <div key={i} className={`${fb.correct ? 'bg-green-500/5 border-l-2 border-green-500' : 'bg-red-500/5 border-l-2 border-red-500'} rounded-lg p-5 mb-3`}>
              <div className="flex items-start gap-3 mb-4">
                <span className={`text-lg font-bold shrink-0 ${fb.correct ? 'text-green-400' : 'text-red-400'}`}>
                  {fb.correct ? '\u2713' : '\u2717'}
                </span>
                <div className="font-semibold leading-relaxed">
                  Q{i + 1}. {fb.question}
                </div>
              </div>

              {/* Show diagram if diagram question */}
              {question?.type === 'diagram' && question.diagram && (
                <div className="mb-4">
                  <MermaidDiagram code={question.diagram} id={`result-${i}`} />
                </div>
              )}

              <div className={`grid grid-cols-2 gap-3 text-sm ${fb.explanation ? 'mb-3' : ''}`}>
                <div>
                  <span className="text-xs text-zinc-500 uppercase tracking-wide">Your answer: </span>
                  <span className={fb.correct ? 'text-green-400' : 'text-red-400'}>
                    {fb.your_answer || '(empty)'}
                  </span>
                </div>
                <div>
                  <span className="text-xs text-zinc-500 uppercase tracking-wide">Correct answer: </span>
                  <span className="text-green-400">
                    {fb.correct_answer}
                  </span>
                </div>
              </div>

              {fb.explanation && (
                <div className="bg-zinc-950 rounded-lg p-3 mt-3 text-sm text-zinc-400 leading-relaxed">
                  {fb.explanation}
                </div>
              )}
            </div>
          );
        })}

        {/* Back to course link */}
        <div className="text-center mt-8">
          <a
            href={`/course/${quiz.course_id}`}
            className="inline-flex items-center gap-2 bg-indigo-500 hover:bg-indigo-400 text-white rounded-lg px-6 py-2.5 font-medium no-underline hover:no-underline transition-colors"
          >
            Back to Course
          </a>
        </div>
      </div>
    );
  }

  /* ── Quiz state ────────────────────────────────────────────────────── */

  return (
    <div className="max-w-3xl mx-auto space-y-6">
      <h1 className="text-2xl font-semibold tracking-tight text-zinc-50">
        Quiz
      </h1>

      {quiz.questions.map((q, i) => (
        <div key={i} className="bg-zinc-900 rounded-xl p-6 space-y-4">
          <div className="text-xs text-zinc-500 uppercase tracking-wide font-medium">
            Question {i + 1}
          </div>
          <div className="text-lg font-medium text-zinc-100">
            {q.question}
          </div>

          {/* Diagram rendering */}
          {q.type === 'diagram' && q.diagram && (
            <div>
              <MermaidDiagram code={q.diagram} id={`q-${i}`} />
            </div>
          )}

          {/* MCQ options */}
          {q.type === 'mcq' && (
            <div className="flex flex-col gap-2">
              {q.options.map((opt, j) => {
                const selected = answers[i] === opt;
                return (
                  <label
                    key={j}
                    className={`flex items-center gap-3 border rounded-lg px-4 py-3 cursor-pointer transition-colors ${
                      selected
                        ? 'border-indigo-500 bg-indigo-500/10'
                        : 'border-zinc-800 hover:border-zinc-600'
                    }`}
                  >
                    <input
                      type="radio"
                      name={`question-${i}`}
                      value={opt}
                      checked={selected}
                      onChange={() => setAnswer(i, opt)}
                      className="hidden"
                    />
                    <span className={
                      selected
                        ? 'w-5 h-5 rounded-full border-2 border-indigo-500 bg-indigo-500 shrink-0 flex items-center justify-center'
                        : 'w-5 h-5 rounded-full border-2 border-zinc-600 shrink-0'
                    }>
                      {selected && (
                        <span className="w-2 h-2 rounded-full bg-white" />
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
              className="w-full bg-zinc-950 border border-zinc-800 rounded-lg px-4 py-3 text-zinc-200 text-sm focus:border-indigo-500/50 focus:ring-1 focus:ring-indigo-500/20 focus:outline-none transition-colors placeholder-zinc-600"
            />
          )}
        </div>
      ))}

      {/* Submit button */}
      <div className="text-center mt-8 mb-8">
        <button
          onClick={handleSubmit}
          disabled={!allAnswered || submitting}
          className="block mx-auto bg-indigo-500 hover:bg-indigo-400 disabled:bg-zinc-800 disabled:text-zinc-600 disabled:cursor-not-allowed text-white rounded-lg px-8 py-3 text-sm font-medium transition-colors border-none"
        >
          {submitting ? 'Submitting...' : 'Submit Quiz'}
        </button>
      </div>

      {error && (
        <div className="text-center text-red-400 mt-4">
          {error}
        </div>
      )}
    </div>
  );
}
