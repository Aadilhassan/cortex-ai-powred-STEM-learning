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

/* ── Palette ─────────────────────────────────────────────────────────────── */

const C = {
  bg: '#0f0f13',
  surface: '#1a1a24',
  surfaceHover: '#252536',
  border: '#2a2a3d',
  text: '#e0e0e0',
  textSecondary: '#8888a0',
  accent: '#7c8aff',
  accentHover: '#9ba6ff',
  success: '#4ade80',
  warning: '#fbbf24',
} as const;

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
    const styles: Record<string, { bg: string; text: string; label: string }> = {
      not_started: { bg: C.border, text: C.textSecondary, label: 'Not started' },
      in_progress: { bg: C.warning + '22', text: C.warning, label: 'In progress' },
      completed: { bg: C.success + '22', text: C.success, label: 'Completed' },
    };
    const s = styles[status] || styles.not_started;
    return (
      <span
        style={{
          background: s.bg,
          color: s.text,
          padding: '0.2rem 0.6rem',
          borderRadius: '9999px',
          fontSize: '0.75rem',
          fontWeight: 500,
          whiteSpace: 'nowrap',
        }}
      >
        {s.label}
      </span>
    );
  }

  /* ── Render ──────────────────────────────────────────────────────────── */

  if (loading) {
    return <p style={{ color: C.textSecondary }}>Loading course...</p>;
  }

  if (error || !course) {
    return (
      <div>
        <a href="/" style={{ color: C.accent, fontSize: '0.9rem' }}>
          &larr; Back to Dashboard
        </a>
        <p style={{ color: '#f87171', marginTop: '1rem' }}>{error || 'Course not found.'}</p>
      </div>
    );
  }

  return (
    <div>
      {/* Back link */}
      <a
        href="/"
        style={{
          color: C.accent,
          fontSize: '0.9rem',
          display: 'inline-block',
          marginBottom: '1.5rem',
        }}
      >
        &larr; Back to Dashboard
      </a>

      {/* Course header */}
      <div style={{ marginBottom: '2rem' }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', gap: '1rem', flexWrap: 'wrap' }}>
          <div>
            <h1 style={{ fontSize: '1.75rem', fontWeight: 700, marginBottom: '0.5rem' }}>{course.name}</h1>
            {course.description && (
              <p style={{ color: C.textSecondary, fontSize: '0.95rem', lineHeight: 1.6, maxWidth: '700px' }}>
                {course.description}
              </p>
            )}
          </div>
          <button
            onClick={() => handleGenerateQuiz('course')}
            disabled={quizLoading === 'course'}
            style={{
              background: C.accent,
              color: '#fff',
              border: 'none',
              borderRadius: '8px',
              padding: '0.625rem 1.25rem',
              fontSize: '0.9rem',
              fontWeight: 600,
              whiteSpace: 'nowrap',
              opacity: quizLoading === 'course' ? 0.7 : 1,
              transition: 'background 0.15s',
            }}
            onMouseEnter={(e) => {
              if (quizLoading !== 'course') e.currentTarget.style.background = C.accentHover;
            }}
            onMouseLeave={(e) => (e.currentTarget.style.background = C.accent)}
          >
            {quizLoading === 'course' ? 'Generating...' : 'Generate Course Quiz'}
          </button>
        </div>
      </div>

      {/* Sections tree */}
      {course.sections.length === 0 ? (
        <div
          style={{
            background: C.surface,
            border: `1px solid ${C.border}`,
            borderRadius: '12px',
            padding: '2rem',
            textAlign: 'center',
          }}
        >
          <p style={{ color: C.textSecondary }}>
            No sections yet. Upload a handout to generate course structure.
          </p>
        </div>
      ) : (
        <div style={{ display: 'flex', flexDirection: 'column', gap: '0.75rem' }}>
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
      <div style={{ marginTop: '3rem', paddingTop: '2rem', borderTop: `1px solid ${C.border}` }}>
        <button
          onClick={handleDeleteCourse}
          style={{
            background: 'transparent',
            border: '1px solid #f8717144',
            borderRadius: '8px',
            padding: '0.5rem 1rem',
            color: '#f87171',
            fontSize: '0.85rem',
            transition: 'background 0.15s, border-color 0.15s',
          }}
          onMouseEnter={(e) => {
            e.currentTarget.style.background = 'rgba(248,113,113,0.1)';
            e.currentTarget.style.borderColor = '#f87171';
          }}
          onMouseLeave={(e) => {
            e.currentTarget.style.background = 'transparent';
            e.currentTarget.style.borderColor = '#f8717144';
          }}
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
    <div
      style={{
        background: C.surface,
        border: `1px solid ${C.border}`,
        borderRadius: '12px',
        overflow: 'hidden',
      }}
    >
      {/* Section header */}
      <div
        onClick={onToggle}
        style={{
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          padding: '1rem 1.25rem',
          cursor: 'pointer',
          transition: 'background 0.15s',
        }}
        onMouseEnter={(e) => (e.currentTarget.style.background = C.surfaceHover)}
        onMouseLeave={(e) => (e.currentTarget.style.background = 'transparent')}
      >
        <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem' }}>
          <span
            style={{
              display: 'inline-block',
              transition: 'transform 0.15s',
              transform: expanded ? 'rotate(90deg)' : 'rotate(0deg)',
              fontSize: '0.8rem',
              color: C.textSecondary,
            }}
          >
            &#9654;
          </span>
          <h3 style={{ fontSize: '1rem', fontWeight: 600 }}>{section.title}</h3>
          <span style={{ color: C.textSecondary, fontSize: '0.8rem' }}>
            ({section.subtopics.length} subtopic{section.subtopics.length !== 1 ? 's' : ''})
          </span>
        </div>
        <button
          onClick={(e) => {
            e.stopPropagation();
            onQuizSection();
          }}
          disabled={isQuizzing}
          style={{
            background: 'transparent',
            border: `1px solid ${C.border}`,
            borderRadius: '6px',
            padding: '0.35rem 0.75rem',
            color: C.accent,
            fontSize: '0.8rem',
            fontWeight: 500,
            opacity: isQuizzing ? 0.7 : 1,
            transition: 'border-color 0.15s',
          }}
          onMouseEnter={(e) => (e.currentTarget.style.borderColor = C.accent)}
          onMouseLeave={(e) => (e.currentTarget.style.borderColor = C.border)}
        >
          {isQuizzing ? 'Generating...' : 'Quiz this section'}
        </button>
      </div>

      {/* Subtopics */}
      {expanded && section.subtopics.length > 0 && (
        <div style={{ borderTop: `1px solid ${C.border}` }}>
          {section.subtopics.map((subtopic) => (
            <SubtopicRow key={subtopic.id} subtopic={subtopic} statusBadge={getStatusBadge(subtopic.id)} />
          ))}
        </div>
      )}
    </div>
  );
}

/* ── Subtopic Row ────────────────────────────────────────────────────────── */

function SubtopicRow({
  subtopic,
  statusBadge,
}: {
  subtopic: Subtopic;
  statusBadge: React.ReactNode;
}) {
  return (
    <div
      style={{
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'space-between',
        padding: '0.75rem 1.25rem 0.75rem 3rem',
        borderBottom: `1px solid ${C.border}`,
        transition: 'background 0.15s',
      }}
      onMouseEnter={(e) => (e.currentTarget.style.background = C.surfaceHover)}
      onMouseLeave={(e) => (e.currentTarget.style.background = 'transparent')}
    >
      <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem', flex: 1, minWidth: 0 }}>
        <span
          style={{
            fontSize: '0.9rem',
            overflow: 'hidden',
            textOverflow: 'ellipsis',
            whiteSpace: 'nowrap',
          }}
        >
          {subtopic.title}
        </span>
        {statusBadge}
      </div>
      <a
        href={`/study/${subtopic.id}`}
        style={{
          background: C.accent + '18',
          color: C.accent,
          border: `1px solid ${C.accent}44`,
          borderRadius: '6px',
          padding: '0.35rem 0.85rem',
          fontSize: '0.8rem',
          fontWeight: 500,
          textDecoration: 'none',
          whiteSpace: 'nowrap',
          transition: 'background 0.15s',
        }}
        onMouseEnter={(e) => (e.currentTarget.style.background = C.accent + '30')}
        onMouseLeave={(e) => (e.currentTarget.style.background = C.accent + '18')}
        onClick={(e) => e.stopPropagation()}
      >
        Study
      </a>
    </div>
  );
}
