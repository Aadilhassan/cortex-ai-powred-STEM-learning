import { useState, useEffect, useRef } from 'react';
import { listCourses, createCourse, uploadCourse, deleteCourse } from '../lib/api';

/* ── Types ───────────────────────────────────────────────────────────────── */

interface Course {
  id: string;
  name: string;
  description: string;
  handout_raw: string;
  created_at: string;
  sections?: { id: string; subtopics?: unknown[] }[];
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

export default function Dashboard() {
  const [courses, setCourses] = useState<Course[]>([]);
  const [loading, setLoading] = useState(true);
  const [showModal, setShowModal] = useState(false);

  useEffect(() => {
    loadCourses();
  }, []);

  async function loadCourses() {
    try {
      const data = await listCourses();
      setCourses(data);
    } catch (e) {
      console.error('Failed to load courses', e);
    } finally {
      setLoading(false);
    }
  }

  async function handleDelete(id: string, name: string) {
    if (!confirm(`Delete "${name}"? This cannot be undone.`)) return;
    try {
      await deleteCourse(id);
      setCourses((prev) => prev.filter((c) => c.id !== id));
    } catch (e) {
      console.error('Failed to delete course', e);
    }
  }

  return (
    <div>
      {/* Header */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '2rem' }}>
        <h1 style={{ fontSize: '1.75rem', fontWeight: 700 }}>Your Courses</h1>
        <button
          onClick={() => setShowModal(true)}
          style={{
            background: C.accent,
            color: '#fff',
            border: 'none',
            borderRadius: '8px',
            padding: '0.625rem 1.25rem',
            fontSize: '0.9rem',
            fontWeight: 600,
            transition: 'background 0.15s',
          }}
          onMouseEnter={(e) => (e.currentTarget.style.background = C.accentHover)}
          onMouseLeave={(e) => (e.currentTarget.style.background = C.accent)}
        >
          + New Course
        </button>
      </div>

      {/* Loading */}
      {loading && <p style={{ color: C.textSecondary }}>Loading courses...</p>}

      {/* Empty state */}
      {!loading && courses.length === 0 && (
        <div style={{ textAlign: 'center', padding: '4rem 1rem' }}>
          <p style={{ color: C.textSecondary, fontSize: '1.1rem', marginBottom: '1rem' }}>
            No courses yet. Create your first course!
          </p>
          <button
            onClick={() => setShowModal(true)}
            style={{
              background: C.accent,
              color: '#fff',
              border: 'none',
              borderRadius: '8px',
              padding: '0.75rem 1.5rem',
              fontSize: '1rem',
              fontWeight: 600,
            }}
          >
            + Create Course
          </button>
        </div>
      )}

      {/* Course grid */}
      {!loading && courses.length > 0 && (
        <div
          style={{
            display: 'grid',
            gridTemplateColumns: 'repeat(auto-fill, minmax(320px, 1fr))',
            gap: '1.25rem',
          }}
        >
          {courses.map((course) => (
            <CourseCard key={course.id} course={course} onDelete={handleDelete} />
          ))}
        </div>
      )}

      {/* Create modal */}
      {showModal && (
        <CreateCourseModal
          onClose={() => setShowModal(false)}
          onCreated={(newCourse) => {
            setShowModal(false);
            window.location.href = `/course/${newCourse.id}`;
          }}
        />
      )}
    </div>
  );
}

/* ── Course Card ─────────────────────────────────────────────────────────── */

function CourseCard({
  course,
  onDelete,
}: {
  course: Course;
  onDelete: (id: string, name: string) => void;
}) {
  const [hovered, setHovered] = useState(false);

  const sectionCount = course.sections?.length ?? 0;
  const desc =
    course.description.length > 120
      ? course.description.slice(0, 120) + '...'
      : course.description;
  const date = new Date(course.created_at).toLocaleDateString('en-US', {
    month: 'short',
    day: 'numeric',
    year: 'numeric',
  });

  return (
    <div
      style={{
        background: C.surface,
        border: `1px solid ${hovered ? C.accent : C.border}`,
        borderRadius: '12px',
        padding: '1.25rem',
        position: 'relative',
        transition: 'border-color 0.15s, background 0.15s',
        cursor: 'pointer',
        ...(hovered ? { background: C.surfaceHover } : {}),
      }}
      onMouseEnter={() => setHovered(true)}
      onMouseLeave={() => setHovered(false)}
      onClick={() => (window.location.href = `/course/${course.id}`)}
    >
      {/* Delete button */}
      <button
        onClick={(e) => {
          e.stopPropagation();
          onDelete(course.id, course.name);
        }}
        title="Delete course"
        style={{
          position: 'absolute',
          top: '0.75rem',
          right: '0.75rem',
          background: 'transparent',
          border: 'none',
          color: C.textSecondary,
          fontSize: '1.1rem',
          lineHeight: 1,
          padding: '0.25rem 0.4rem',
          borderRadius: '4px',
          transition: 'color 0.15s, background 0.15s',
        }}
        onMouseEnter={(e) => {
          e.currentTarget.style.color = '#f87171';
          e.currentTarget.style.background = 'rgba(248,113,113,0.1)';
        }}
        onMouseLeave={(e) => {
          e.currentTarget.style.color = C.textSecondary;
          e.currentTarget.style.background = 'transparent';
        }}
      >
        x
      </button>

      <h3 style={{ fontSize: '1.1rem', fontWeight: 600, marginBottom: '0.5rem', paddingRight: '1.5rem' }}>
        {course.name}
      </h3>

      {desc && (
        <p style={{ color: C.textSecondary, fontSize: '0.875rem', lineHeight: 1.5, marginBottom: '0.75rem' }}>
          {desc}
        </p>
      )}

      <div
        style={{
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'center',
          fontSize: '0.8rem',
          color: C.textSecondary,
        }}
      >
        <span>{date}</span>
        {sectionCount > 0 && (
          <span style={{ background: C.bg, padding: '0.2rem 0.5rem', borderRadius: '4px' }}>
            {sectionCount} section{sectionCount !== 1 ? 's' : ''}
          </span>
        )}
      </div>
    </div>
  );
}

/* ── Create Course Modal ─────────────────────────────────────────────────── */

function CreateCourseModal({
  onClose,
  onCreated,
}: {
  onClose: () => void;
  onCreated: (course: Course) => void;
}) {
  const [tab, setTab] = useState<'paste' | 'upload'>('paste');
  const [handoutText, setHandoutText] = useState('');
  const [file, setFile] = useState<File | null>(null);
  const [creating, setCreating] = useState(false);
  const [error, setError] = useState('');
  const [dragOver, setDragOver] = useState(false);
  const fileInputRef = useRef<HTMLInputElement>(null);

  async function handleCreate() {
    if (tab === 'paste' && !handoutText.trim()) {
      setError('Please paste your handout text.');
      return;
    }
    if (tab === 'upload' && !file) {
      setError('Please select a file to upload.');
      return;
    }

    setCreating(true);
    setError('');

    try {
      let course: Course;
      if (tab === 'upload' && file) {
        course = await uploadCourse(file);
      } else {
        course = await createCourse(handoutText);
      }
      onCreated(course);
    } catch (e) {
      console.error('Failed to create course', e);
      setError('Failed to create course. Please try again.');
    } finally {
      setCreating(false);
    }
  }

  function handleDrop(e: React.DragEvent) {
    e.preventDefault();
    setDragOver(false);
    const dropped = e.dataTransfer.files[0];
    if (dropped) setFile(dropped);
  }

  const inputStyle: React.CSSProperties = {
    width: '100%',
    background: C.bg,
    border: `1px solid ${C.border}`,
    borderRadius: '8px',
    padding: '0.75rem',
    color: C.text,
    fontSize: '0.9rem',
    outline: 'none',
    fontFamily: 'inherit',
  };

  return (
    <div
      style={{
        position: 'fixed',
        inset: 0,
        background: 'rgba(0,0,0,0.7)',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        zIndex: 100,
      }}
      onClick={onClose}
    >
      <div
        style={{
          background: C.surface,
          border: `1px solid ${C.border}`,
          borderRadius: '16px',
          padding: '2rem',
          width: '100%',
          maxWidth: '560px',
          maxHeight: '90vh',
          overflowY: 'auto',
        }}
        onClick={(e) => e.stopPropagation()}
      >
        <h2 style={{ fontSize: '1.25rem', fontWeight: 700, marginBottom: '0.5rem' }}>Create Course from Handout</h2>
        <p style={{ color: C.textSecondary, fontSize: '0.85rem', marginBottom: '1.5rem' }}>
          Upload or paste your handout — the AI will extract the course name, description, and structure automatically.
        </p>

        {/* Tab toggle */}
        <div style={{ display: 'flex', gap: '0.5rem', marginBottom: '1rem' }}>
          {(['paste', 'upload'] as const).map((t) => (
            <button
              key={t}
              onClick={() => setTab(t)}
              style={{
                flex: 1,
                padding: '0.5rem',
                borderRadius: '8px',
                border: `1px solid ${tab === t ? C.accent : C.border}`,
                background: tab === t ? C.accent + '22' : 'transparent',
                color: tab === t ? C.accent : C.textSecondary,
                fontSize: '0.85rem',
                fontWeight: 500,
                transition: 'all 0.15s',
              }}
            >
              {t === 'paste' ? 'Paste Text' : 'Upload File'}
            </button>
          ))}
        </div>

        {/* Paste tab */}
        {tab === 'paste' && (
          <textarea
            value={handoutText}
            onChange={(e) => setHandoutText(e.target.value)}
            placeholder="Paste your handout or lecture notes here..."
            rows={8}
            style={{ ...inputStyle, marginBottom: '1rem', resize: 'vertical' }}
          />
        )}

        {/* Upload tab */}
        {tab === 'upload' && (
          <div
            onDragOver={(e) => {
              e.preventDefault();
              setDragOver(true);
            }}
            onDragLeave={() => setDragOver(false)}
            onDrop={handleDrop}
            onClick={() => fileInputRef.current?.click()}
            style={{
              border: `2px dashed ${dragOver ? C.accent : C.border}`,
              borderRadius: '12px',
              padding: '2rem',
              textAlign: 'center',
              cursor: 'pointer',
              marginBottom: '1rem',
              transition: 'border-color 0.15s',
              background: dragOver ? C.accent + '08' : 'transparent',
            }}
          >
            <input
              ref={fileInputRef}
              type="file"
              accept=".pdf,.txt,.md"
              style={{ display: 'none' }}
              onChange={(e) => {
                const f = e.target.files?.[0];
                if (f) setFile(f);
              }}
            />
            {file ? (
              <p style={{ color: C.text, fontSize: '0.9rem' }}>{file.name}</p>
            ) : (
              <>
                <p style={{ color: C.textSecondary, marginBottom: '0.5rem' }}>
                  Drop a file here, or click to browse
                </p>
                <p style={{ color: C.textSecondary, fontSize: '0.8rem' }}>
                  Accepts .pdf, .txt, .md
                </p>
              </>
            )}
          </div>
        )}

        {/* Error */}
        {error && (
          <p style={{ color: '#f87171', fontSize: '0.85rem', marginBottom: '1rem' }}>{error}</p>
        )}

        {/* Actions */}
        <div style={{ display: 'flex', justifyContent: 'flex-end', gap: '0.75rem' }}>
          <button
            onClick={onClose}
            style={{
              background: 'transparent',
              border: `1px solid ${C.border}`,
              borderRadius: '8px',
              padding: '0.625rem 1.25rem',
              color: C.textSecondary,
              fontSize: '0.9rem',
            }}
          >
            Cancel
          </button>
          <button
            onClick={handleCreate}
            disabled={creating}
            style={{
              background: creating ? C.textSecondary : C.accent,
              color: '#fff',
              border: 'none',
              borderRadius: '8px',
              padding: '0.625rem 1.25rem',
              fontSize: '0.9rem',
              fontWeight: 600,
              opacity: creating ? 0.7 : 1,
            }}
          >
            {creating ? 'Analyzing handout...' : 'Create Course'}
          </button>
        </div>
      </div>
    </div>
  );
}
