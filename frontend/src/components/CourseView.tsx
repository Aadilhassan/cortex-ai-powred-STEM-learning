import { useState, useEffect } from 'react';
import { getCourse, deleteCourse, generateQuiz, getProgress } from '../lib/api';

/* ── Types ───────────────────────────────────────────────────────────────── */

interface Subtopic {
  id: string;
  section_id: string;
  title: string;
  content: string;
  summary: string;
  order_index: number;
}

interface Section {
  id: string;
  course_id: string;
  title: string;
  summary: string;
  learning_objectives: string;
  key_concepts: string;
  prerequisites: string;
  order_index: number;
  subtopics: Subtopic[];
}

interface Course {
  id: string;
  name: string;
  description: string;
  handout_raw: string;
  created_at: string;
  sections: Section[];
}

interface ProgressEntry {
  subtopic_id: string;
  status: string;
}

/* ── Component ───────────────────────────────────────────────────────────── */

export default function CourseView({ courseId }: { courseId: string }) {
  const [course, setCourse] = useState<Course | null>(null);
  const [progressMap, setProgressMap] = useState<Record<string, string>>({});
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [expandedSections, setExpandedSections] = useState<Set<string>>(new Set());
  const [quizLoading, setQuizLoading] = useState<string | null>(null); // null | 'course' | sectionId

  useEffect(() => {
    loadData();
  }, [courseId]);

  async function loadData() {
    try {
      const [courseData, progressData] = await Promise.all([
        getCourse(courseId),
        getProgress(courseId),
      ]);
      setCourse(courseData);

      // Build progress lookup: subtopicId -> status
      const pMap: Record<string, string> = {};
      for (const p of progressData as ProgressEntry[]) {
        pMap[p.subtopic_id] = p.status;
      }
      setProgressMap(pMap);

      // Default all sections to expanded
      const allIds = new Set<string>((courseData.sections || []).map((s: Section) => s.id));
      setExpandedSections(allIds);
    } catch (e) {
      console.error('Failed to load course', e);
      setError('Failed to load course.');
    } finally {
      setLoading(false);
    }
  }

  function toggleSection(sectionId: string) {
    setExpandedSections((prev) => {
      const next = new Set(prev);
      if (next.has(sectionId)) {
        next.delete(sectionId);
      } else {
        next.add(sectionId);
      }
      return next;
    });
  }

  async function handleGenerateQuiz(scope: string, sectionId?: string) {
    const key = sectionId || 'course';
    setQuizLoading(key);
    try {
      const quiz = await generateQuiz(courseId, scope, { sectionId });
      window.location.href = `/quiz/${quiz.id}`;
    } catch (e) {
      console.error('Failed to generate quiz', e);
      alert('Failed to generate quiz. Please try again.');
    } finally {
      setQuizLoading(null);
    }
  }

  async function handleDeleteCourse() {
    if (!confirm(`Delete "${course?.name}"? This cannot be undone.`)) return;
    try {
      await deleteCourse(courseId);
      window.location.href = '/';
    } catch (e) {
      console.error('Failed to delete course', e);
    }
  }

  function getStatusBadge(subtopicId: string) {
    const status = progressMap[subtopicId] || 'not_started';
    const config: Record<string, { dot: string; text: string; textColor: string; label: string }> = {
      not_started: { dot: 'bg-zinc-600', text: 'text-zinc-600', textColor: 'text-zinc-600', label: 'Not started' },
      in_progress: { dot: 'bg-amber-400', text: 'text-amber-400', textColor: 'text-amber-400', label: 'In progress' },
      completed: { dot: 'bg-green-400', text: 'text-green-400', textColor: 'text-green-400', label: 'Done' },
    };
    const s = config[status] || config.not_started;
    return (
      <span className="flex items-center gap-2">
        <span className={`w-2 h-2 rounded-full ${s.dot}`} />
        <span className={`text-xs ${s.textColor}`}>
          {status === 'completed' && (
            <svg className="inline w-3 h-3 mr-0.5 -mt-px" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2.5}>
              <path strokeLinecap="round" strokeLinejoin="round" d="M5 13l4 4L19 7" />
            </svg>
          )}
          {s.label}
        </span>
      </span>
    );
  }

  /* ── Render ──────────────────────────────────────────────────────────── */

  if (loading) {
    return <p className="text-zinc-500 text-center py-20">Loading course...</p>;
  }

  if (error || !course) {
    return (
      <div>
        <a href="/" className="text-indigo-400 text-sm">
          &larr; Back to Dashboard
        </a>
        <p className="text-red-400 mt-4">{error || 'Course not found.'}</p>
      </div>
    );
  }

  return (
    <div>
      {/* Back link */}
      <a
        href="/"
        className="text-indigo-400 text-sm inline-block mb-6"
      >
        &larr; Back to Dashboard
      </a>

      {/* Course header */}
      <div className="flex items-start justify-between gap-4 flex-wrap mb-8">
        <div className="space-y-1">
          <h1 className="text-2xl font-semibold tracking-tight text-zinc-50">{course.name}</h1>
          {course.description && (
            <p className="text-sm text-zinc-400 max-w-2xl">
              {course.description}
            </p>
          )}
        </div>
        <button
          onClick={() => handleGenerateQuiz('course')}
          disabled={quizLoading === 'course'}
          className={`inline-flex items-center gap-2 border border-zinc-700 hover:border-indigo-500/50 hover:bg-indigo-500/10 text-zinc-300 rounded-lg px-4 py-2 text-sm font-medium transition-all bg-transparent ${
            quizLoading === 'course' ? 'opacity-70 pointer-events-none' : ''
          }`}
        >
          {quizLoading === 'course' ? 'Generating...' : 'Generate Course Quiz'}
        </button>
      </div>

      {/* Sections tree */}
      {course.sections.length === 0 ? (
        <div className="flex flex-col items-center justify-center py-16 text-center">
          <p className="text-zinc-500 text-lg">
            No sections yet. Upload a handout to generate course structure.
          </p>
        </div>
      ) : (
        <div className="space-y-4">
          {course.sections.map((section) => (
            <SectionGroup
              key={section.id}
              section={section}
              expanded={expandedSections.has(section.id)}
              onToggle={() => toggleSection(section.id)}
              getStatusBadge={getStatusBadge}
              quizLoading={quizLoading}
              onQuizSection={() => handleGenerateQuiz('topic', section.id)}
            />
          ))}
        </div>
      )}

      {/* Delete course */}
      <div className="mt-8">
        <button
          onClick={handleDeleteCourse}
          className="mt-8 border border-red-500/30 text-red-400 hover:bg-red-500/10 hover:border-red-500/50 rounded-lg px-4 py-2 text-sm transition-all bg-transparent"
        >
          Delete Course
        </button>
      </div>
    </div>
  );
}

/* ── Section Group ───────────────────────────────────────────────────────── */

function SectionGroup({
  section,
  expanded,
  onToggle,
  getStatusBadge,
  quizLoading,
  onQuizSection,
}: {
  section: Section;
  expanded: boolean;
  onToggle: () => void;
  getStatusBadge: (subtopicId: string) => React.ReactNode;
  quizLoading: string | null;
  onQuizSection: () => void;
}) {
  const isQuizzing = quizLoading === section.id;

  return (
    <div className="bg-zinc-900 rounded-xl overflow-hidden">
      {/* Section header */}
      <div
        onClick={onToggle}
        className="px-5 py-4 flex items-center justify-between cursor-pointer hover:bg-zinc-800/50 transition-colors"
      >
        <div className="flex items-center gap-3">
          <svg
            className={`w-4 h-4 text-zinc-500 transition-transform duration-200 ${expanded ? 'rotate-180' : ''}`}
            fill="none"
            viewBox="0 0 24 24"
            stroke="currentColor"
            strokeWidth={2}
          >
            <path strokeLinecap="round" strokeLinejoin="round" d="M19 9l-7 7-7-7" />
          </svg>
          <h3 className="text-base font-medium text-zinc-100">{section.title}</h3>
          <span className="text-xs text-zinc-500">
            ({section.subtopics.length} subtopic{section.subtopics.length !== 1 ? 's' : ''})
          </span>
        </div>
        <button
          onClick={(e) => {
            e.stopPropagation();
            onQuizSection();
          }}
          disabled={isQuizzing}
          className={`text-xs text-indigo-400 hover:text-indigo-300 bg-transparent border-none transition-colors ${
            isQuizzing ? 'opacity-70 pointer-events-none' : ''
          }`}
        >
          {isQuizzing ? 'Generating...' : 'Quiz this section'}
        </button>
      </div>

      {/* Section metadata + subtopics */}
      {expanded && (
        <div className="border-t border-zinc-800/50">
          <SectionMeta section={section} />
          {section.subtopics.map((subtopic, i) => (
            <SubtopicRow
              key={subtopic.id}
              subtopic={subtopic}
              statusBadge={getStatusBadge(subtopic.id)}
              isFirst={i === 0}
            />
          ))}
        </div>
      )}
    </div>
  );
}

/* ── Section Metadata ────────────────────────────────────────────────────── */

function SectionMeta({ section }: { section: Section }) {
  const objectives: string[] = safeParse(section.learning_objectives);
  const concepts: string[] = safeParse(section.key_concepts);

  if (objectives.length === 0 && concepts.length === 0) return null;

  return (
    <div className="px-5 py-4 space-y-4 bg-zinc-950/50">
      {objectives.length > 0 && (
        <div>
          <p className="text-xs text-zinc-500 uppercase tracking-wide font-medium">
            Learning Objectives
          </p>
          <div className="space-y-1 mt-2">
            {objectives.map((obj, i) => (
              <p key={i} className="text-sm text-zinc-400 pl-4 border-l-2 border-zinc-800">
                {obj}
              </p>
            ))}
          </div>
        </div>
      )}
      {concepts.length > 0 && (
        <div>
          <p className="text-xs text-zinc-500 uppercase tracking-wide font-medium">
            Key Concepts
          </p>
          <div className="flex flex-wrap gap-2 mt-2">
            {concepts.map((concept, i) => (
              <span key={i} className="bg-zinc-800 text-zinc-300 rounded-full px-3 py-1 text-xs">
                {concept}
              </span>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}

function safeParse(val: string | string[]): string[] {
  if (Array.isArray(val)) return val;
  if (!val || val === '[]') return [];
  try { return JSON.parse(val); } catch { return []; }
}

/* ── Subtopic Row ────────────────────────────────────────────────────────── */

function SubtopicRow({
  subtopic,
  statusBadge,
  isFirst,
}: {
  subtopic: Subtopic;
  statusBadge: React.ReactNode;
  isFirst: boolean;
}) {
  return (
    <div
      className={`group px-5 py-3 flex items-center justify-between hover:bg-zinc-800/50 transition-colors ${
        isFirst ? '' : 'border-t border-zinc-800/50'
      }`}
    >
      <div className="flex items-center gap-3 flex-1 min-w-0">
        <span className="text-sm text-zinc-200 truncate">
          {subtopic.title}
        </span>
        {statusBadge}
      </div>
      <a
        href={`/study/${subtopic.id}`}
        className="text-sm text-indigo-400 hover:text-indigo-300 opacity-0 group-hover:opacity-100 transition-all flex items-center gap-1 no-underline hover:no-underline"
        onClick={(e) => e.stopPropagation()}
      >
        Study
        <svg className="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
          <path strokeLinecap="round" strokeLinejoin="round" d="M9 5l7 7-7 7" />
        </svg>
      </a>
    </div>
  );
}
