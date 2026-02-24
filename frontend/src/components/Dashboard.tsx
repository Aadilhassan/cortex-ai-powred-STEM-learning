import { useState, useEffect } from 'react';
import { listCourses, deleteCourse } from '../lib/api';

/* ── Types ───────────────────────────────────────────────────────────────── */

interface Course {
  id: string;
  name: string;
  description: string;
  handout_raw: string;
  created_at: string;
  sections?: { id: string; subtopics?: unknown[] }[];
}

/* ── Component ───────────────────────────────────────────────────────────── */

export default function Dashboard() {
  const [courses, setCourses] = useState<Course[]>([]);
  const [loading, setLoading] = useState(true);

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
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight text-zinc-50">Your Courses</h1>
          <p className="text-sm text-zinc-500 mt-1">Continue learning or start something new</p>
        </div>
        <button
          onClick={() => (window.location.href = '/new')}
          className="inline-flex items-center gap-2 bg-indigo-500 hover:bg-indigo-400 text-white rounded-lg px-4 py-2 text-sm font-medium transition-colors"
        >
          + New Course
        </button>
      </div>

      {/* Loading */}
      {loading && <p className="text-zinc-500 text-center py-20">Loading courses...</p>}

      {/* Empty state */}
      {!loading && courses.length === 0 && (
        <div className="flex flex-col items-center justify-center py-20 text-center">
          <svg
            className="text-zinc-600"
            width="48"
            height="48"
            fill="none"
            viewBox="0 0 24 24"
            stroke="currentColor"
            strokeWidth={1.5}
          >
            <path
              strokeLinecap="round"
              strokeLinejoin="round"
              d="M12 6.042A8.967 8.967 0 006 3.75c-1.052 0-2.062.18-3 .512v14.25A8.987 8.987 0 016 18c2.305 0 4.408.867 6 2.292m0-14.25a8.966 8.966 0 016-2.292c1.052 0 2.062.18 3 .512v14.25A8.987 8.987 0 0018 18a8.967 8.967 0 00-6 2.292m0-14.25v14.25"
            />
          </svg>
          <p className="text-zinc-500 mt-4 mb-6 text-lg">
            No courses yet. Create your first course!
          </p>
          <button
            onClick={() => (window.location.href = '/new')}
            className="inline-flex items-center gap-2 bg-indigo-500 hover:bg-indigo-400 text-white rounded-lg px-4 py-2 text-sm font-medium transition-colors"
          >
            + Create Course
          </button>
        </div>
      )}

      {/* Course grid */}
      {!loading && courses.length > 0 && (
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
          {courses.map((course) => (
            <CourseCard key={course.id} course={course} onDelete={handleDelete} />
          ))}
        </div>
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
  const sectionCount = course.sections?.length ?? 0;
  const date = new Date(course.created_at).toLocaleDateString('en-US', {
    month: 'short',
    day: 'numeric',
    year: 'numeric',
  });

  return (
    <div
      className="group bg-zinc-900 rounded-xl p-5 hover:bg-zinc-800/80 hover:ring-1 hover:ring-indigo-500/30 transition-all duration-200 cursor-pointer relative"
      onClick={() => (window.location.href = `/course/${course.id}`)}
    >
      {/* Delete button */}
      <button
        onClick={(e) => {
          e.stopPropagation();
          onDelete(course.id, course.name);
        }}
        title="Delete course"
        className="absolute top-3 right-3 opacity-0 group-hover:opacity-100 p-1.5 rounded-lg text-zinc-600 hover:text-red-400 hover:bg-red-500/10 transition-all"
      >
        <svg
          width="14"
          height="14"
          viewBox="0 0 24 24"
          fill="none"
          stroke="currentColor"
          strokeWidth={2}
          strokeLinecap="round"
          strokeLinejoin="round"
        >
          <line x1="18" y1="6" x2="6" y2="18" />
          <line x1="6" y1="6" x2="18" y2="18" />
        </svg>
      </button>

      <h3 className="text-lg font-medium text-zinc-50">
        {course.name}
      </h3>

      {course.description && (
        <p className="text-sm text-zinc-400 mt-2 line-clamp-2">
          {course.description}
        </p>
      )}

      <div className="flex items-center gap-3 mt-4 text-xs text-zinc-500">
        <span>{date}</span>
        {sectionCount > 0 && (
          <span className="bg-zinc-800 text-zinc-400 rounded-full px-2.5 py-0.5">
            {sectionCount} section{sectionCount !== 1 ? 's' : ''}
          </span>
        )}
      </div>
    </div>
  );
}
