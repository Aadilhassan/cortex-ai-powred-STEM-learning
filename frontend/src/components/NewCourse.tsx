import { useState, useRef } from 'react';
import { createCourse, uploadCourse } from '../lib/api';

/* ── Processing Steps ────────────────────────────────────────────────────── */

const STEPS = [
  { label: 'Uploading content', icon: '1' },
  { label: 'Analyzing handout with AI', icon: '2' },
  { label: 'Building course structure', icon: '3' },
];

/* ── Component ───────────────────────────────────────────────────────────── */

export default function NewCourse() {
  const [tab, setTab] = useState<'upload' | 'paste'>('upload');
  const [handoutText, setHandoutText] = useState('');
  const [file, setFile] = useState<File | null>(null);
  const [dragOver, setDragOver] = useState(false);
  const [processing, setProcessing] = useState(false);
  const [currentStep, setCurrentStep] = useState(0);
  const [error, setError] = useState('');
  const fileInputRef = useRef<HTMLInputElement>(null);

  async function handleSubmit() {
    if (tab === 'paste' && !handoutText.trim()) {
      setError('Please paste your handout text.');
      return;
    }
    if (tab === 'upload' && !file) {
      setError('Please select a file to upload.');
      return;
    }

    setProcessing(true);
    setError('');
    setCurrentStep(0);

    try {
      // Step 1: Uploading
      setCurrentStep(0);
      await new Promise(r => setTimeout(r, 300));

      // Step 2: Analyzing
      setCurrentStep(1);

      let course;
      if (tab === 'upload' && file) {
        course = await uploadCourse(file);
      } else {
        course = await createCourse(handoutText);
      }

      // Step 3: Done
      setCurrentStep(2);
      await new Promise(r => setTimeout(r, 500));

      window.location.href = `/course/${course.id}`;
    } catch (e) {
      console.error('Failed to create course', e);
      setError('Failed to create course. Please try again.');
      setProcessing(false);
    }
  }

  function handleDrop(e: React.DragEvent) {
    e.preventDefault();
    setDragOver(false);
    const dropped = e.dataTransfer.files[0];
    if (dropped) {
      setFile(dropped);
      setError('');
    }
  }

  function removeFile() {
    setFile(null);
    if (fileInputRef.current) fileInputRef.current.value = '';
  }

  /* ── Processing overlay ─────────────────────────────────────────────── */

  if (processing) {
    return (
      <div className="flex flex-col items-center justify-center py-16 max-w-md mx-auto text-center">
        <div className="mb-8">
          <svg
            className="animate-spin text-indigo-400 w-12 h-12"
            viewBox="0 0 24 24"
            fill="none"
            stroke="currentColor"
            strokeWidth="1.5"
          >
            <path
              d="M12 2v4M12 18v4M4.93 4.93l2.83 2.83M16.24 16.24l2.83 2.83M2 12h4M18 12h4M4.93 19.07l2.83-2.83M16.24 7.76l2.83-2.83"
              strokeLinecap="round"
            />
          </svg>
        </div>
        <h2 className="text-xl font-bold text-zinc-50 mb-8">
          Creating your course...
        </h2>
        <div className="space-y-3 mt-8 w-full">
          {STEPS.map((step, i) => {
            const done = i < currentStep;
            const active = i === currentStep;
            return (
              <div
                key={i}
                className={`flex items-center gap-3 text-sm px-4 py-3 rounded-lg transition-all ${
                  active ? 'bg-indigo-500/10' : ''
                }`}
              >
                <div
                  className={`w-6 h-6 rounded-full flex items-center justify-center text-xs shrink-0 ${
                    done
                      ? 'bg-green-500/20 text-green-400'
                      : active
                        ? 'border border-indigo-500 bg-indigo-500/20 text-indigo-400'
                        : 'border border-zinc-700 text-zinc-600'
                  }`}
                >
                  {done ? '\u2713' : step.icon}
                </div>
                <span
                  className={`${
                    done
                      ? 'text-zinc-400'
                      : active
                        ? 'text-zinc-200 font-medium'
                        : 'text-zinc-500'
                  } transition-colors`}
                >
                  {step.label}
                  {active && <span className="text-zinc-500"> ...</span>}
                </span>
              </div>
            );
          })}
        </div>
      </div>
    );
  }

  /* ── Main form ──────────────────────────────────────────────────────── */

  return (
    <div className="max-w-2xl mx-auto space-y-6">
      {/* Back link */}
      <a
        href="/"
        className="inline-flex items-center gap-1 text-indigo-400 hover:text-indigo-300 text-sm no-underline transition-colors"
      >
        <svg
          width="16"
          height="16"
          viewBox="0 0 24 24"
          fill="none"
          stroke="currentColor"
          strokeWidth="2"
          strokeLinecap="round"
          strokeLinejoin="round"
        >
          <polyline points="15 18 9 12 15 6" />
        </svg>
        Back to Dashboard
      </a>

      {/* Header */}
      <div>
        <h1 className="text-2xl font-semibold tracking-tight text-zinc-50 mb-2">
          New Course
        </h1>
        <p className="text-zinc-400 text-sm leading-relaxed">
          Upload a handout or paste your notes. The AI will automatically extract the course name,
          description, sections, and subtopics.
        </p>
      </div>

      {/* Tab toggle */}
      <div className="inline-flex bg-zinc-950 rounded-lg p-1">
        {(['upload', 'paste'] as const).map((t) => (
          <button
            key={t}
            onClick={() => { setTab(t); setError(''); }}
            className={`px-4 py-2 rounded-md text-sm font-medium transition-all ${
              tab === t
                ? 'bg-zinc-800 text-zinc-50 shadow-sm'
                : 'text-zinc-500 hover:text-zinc-300 transition-colors bg-transparent border-none'
            }`}
          >
            {t === 'upload' ? 'Upload File' : 'Paste Text'}
          </button>
        ))}
      </div>

      {/* Upload tab */}
      {tab === 'upload' && (
        <div>
          <div
            onDragOver={(e) => { e.preventDefault(); setDragOver(true); }}
            onDragLeave={() => setDragOver(false)}
            onDrop={handleDrop}
            onClick={() => !file && fileInputRef.current?.click()}
            className={`border-2 border-dashed rounded-xl text-center transition-colors ${
              dragOver
                ? 'border-indigo-500 bg-indigo-500/5'
                : file
                  ? 'border-green-500/50 bg-green-500/5'
                  : 'border-zinc-700'
            } ${file ? 'p-6 cursor-default' : 'p-8 cursor-pointer'}`}
          >
            <input
              ref={fileInputRef}
              type="file"
              accept=".pdf,.txt,.md"
              className="hidden"
              onChange={(e) => {
                const f = e.target.files?.[0];
                if (f) { setFile(f); setError(''); }
              }}
            />
            {file ? (
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-3">
                  <div className="w-10 h-10 rounded-lg bg-indigo-500/10 flex items-center justify-center">
                    <svg
                      width="20"
                      height="20"
                      viewBox="0 0 24 24"
                      fill="none"
                      stroke="currentColor"
                      strokeWidth="2"
                      strokeLinecap="round"
                      strokeLinejoin="round"
                      className="text-indigo-400"
                    >
                      <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z" />
                      <polyline points="14 2 14 8 20 8" />
                    </svg>
                  </div>
                  <div className="text-left">
                    <p className="text-zinc-200 text-sm font-medium">{file.name}</p>
                    <p className="text-zinc-500 text-xs">
                      {(file.size / 1024).toFixed(1)} KB
                    </p>
                  </div>
                </div>
                <button
                  onClick={(e) => { e.stopPropagation(); removeFile(); }}
                  className="text-sm text-red-400 hover:text-red-300 bg-transparent border-none cursor-pointer"
                >
                  Remove
                </button>
              </div>
            ) : (
              <>
                <div className="mb-4">
                  <svg
                    width="40"
                    height="40"
                    viewBox="0 0 24 24"
                    fill="none"
                    stroke="currentColor"
                    strokeWidth="1.5"
                    strokeLinecap="round"
                    strokeLinejoin="round"
                    className={dragOver ? 'text-indigo-400' : 'text-zinc-500'}
                  >
                    <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4" />
                    <polyline points="17 8 12 3 7 8" />
                    <line x1="12" y1="3" x2="12" y2="15" />
                  </svg>
                </div>
                <p className="text-zinc-200 text-base font-medium mb-2">
                  Drop your file here, or click to browse
                </p>
                <p className="text-sm text-zinc-500 mt-2">
                  Supports PDF, TXT, and Markdown files
                </p>
              </>
            )}
          </div>
        </div>
      )}

      {/* Paste tab */}
      {tab === 'paste' && (
        <div>
          <textarea
            value={handoutText}
            onChange={(e) => { setHandoutText(e.target.value); setError(''); }}
            placeholder="Paste your handout, lecture notes, or study material here..."
            rows={14}
            className="w-full bg-zinc-950 border border-zinc-800 rounded-xl px-4 py-3 text-zinc-200 text-sm leading-relaxed resize-y focus:border-indigo-500/50 focus:ring-1 focus:ring-indigo-500/20 focus:outline-none transition-colors min-h-[200px] placeholder-zinc-600 font-[inherit]"
          />
          {handoutText.length > 0 && (
            <p className="text-right text-xs text-zinc-600 mt-1">
              {handoutText.split(/\s+/).filter(Boolean).length} words
            </p>
          )}
        </div>
      )}

      {/* Error */}
      {error && (
        <div className="bg-red-500/10 border border-red-500/20 rounded-lg p-4 text-red-400 text-sm">
          {error}
        </div>
      )}

      {/* Submit */}
      <button
        onClick={handleSubmit}
        disabled={processing}
        className="w-full bg-indigo-500 hover:bg-indigo-400 disabled:bg-zinc-800 disabled:text-zinc-600 disabled:cursor-not-allowed text-white rounded-lg py-3 text-sm font-medium transition-colors border-none cursor-pointer"
      >
        Create Course
      </button>

      {/* Info */}
      <div className="bg-zinc-900 border border-zinc-800 rounded-xl p-4 text-sm text-zinc-400">
        <p className="leading-relaxed">
          <strong className="text-zinc-200">What happens next?</strong>
          <br />
          The AI will analyze your content and automatically create a structured course with
          sections, subtopics, learning objectives, and key concepts. You can then study each
          subtopic with an AI tutor, generate quizzes, and track your progress.
        </p>
      </div>
    </div>
  );
}
