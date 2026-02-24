import { useState, useEffect, useRef } from 'react';
import { getCourse, deleteCourse, generateQuiz, getProgress, uploadMaterials, listMaterials, deleteMaterial, getExamsForCourse, createExam } from '../lib/api';

/* ── Types ───────────────────────────────────────────────────────────────── */

interface Subtopic {
  id: string;
  section_id: string;
  title: string;
  content: string;
  summary: string;
  order_index: number;
}

interface RelatedMaterial {
  id: string;
  filename: string;
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
  related_materials?: RelatedMaterial[];
}

interface Course {
  id: string;
  name: string;
  description: string;
  handout_raw: string;
  created_at: string;
  sections: Section[];
}

interface Material {
  id: string;
  course_id: string;
  filename: string;
  uploaded_at: string;
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
  const [quizLoading, setQuizLoading] = useState<string | null>(null);
  const [materials, setMaterials] = useState<Material[]>([]);
  const [materialsOpen, setMaterialsOpen] = useState(false);
  const [uploading, setUploading] = useState(false);
  const fileInputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    loadData();
  }, [courseId]);

  async function loadData() {
    try {
      const [courseData, progressData, materialsData] = await Promise.all([
        getCourse(courseId),
        getProgress(courseId),
        listMaterials(courseId),
      ]);
      setCourse(courseData);
      setMaterials(materialsData);

      const pMap: Record<string, string> = {};
      for (const p of progressData as ProgressEntry[]) {
        pMap[p.subtopic_id] = p.status;
      }
      setProgressMap(pMap);

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

  async function handleExamPrep() {
    setQuizLoading('exam_prep');
    try {
      const exams = await getExamsForCourse(courseId);
      if (exams.length > 0) {
        window.location.href = `/exam/${exams[0].id}`;
      } else {
        const exam = await createExam(courseId);
        window.location.href = `/exam/${exam.id}`;
      }
    } catch (e) {
      console.error('Failed to open exam prep', e);
      alert('Failed to open exam prep. Please try again.');
    } finally {
      setQuizLoading(null);
    }
  }

  async function handleUploadMaterials(fileList: FileList) {
    const files = Array.from(fileList);
    if (files.length === 0) return;
    setUploading(true);
    try {
      await uploadMaterials(courseId, files);
      // Reload everything — course structure may have changed after reprocessing
      await loadData();
    } catch (e: any) {
      alert(e.message || 'Upload failed');
    } finally {
      setUploading(false);
      if (fileInputRef.current) fileInputRef.current.value = '';
    }
  }

  async function handleDeleteMaterial(materialId: string) {
    if (!confirm('Delete this material?')) return;
    try {
      await deleteMaterial(materialId);
      setMaterials((prev) => prev.filter((m) => m.id !== materialId));
    } catch (e) {
      console.error('Failed to delete material', e);
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
    const config: Record<string, { dot: string; textColor: string; label: string }> = {
      not_started: { dot: 'bg-zinc-600', textColor: 'text-zinc-600', label: 'Not started' },
      in_progress: { dot: 'bg-amber-400', textColor: 'text-amber-400', label: 'In progress' },
      completed: { dot: 'bg-green-400', textColor: 'text-green-400', label: 'Done' },
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
        <div className="flex gap-2 flex-wrap">
          <a
            href={`/chat/course/${courseId}`}
            className="inline-flex items-center gap-2 border border-zinc-700 hover:border-indigo-500/50 hover:bg-indigo-500/10 text-zinc-300 rounded-lg px-4 py-2 text-sm font-medium transition-all bg-transparent no-underline hover:no-underline"
          >
            <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
              <path strokeLinecap="round" strokeLinejoin="round" d="M8 10h.01M12 10h.01M16 10h.01M9 16H5a2 2 0 01-2-2V6a2 2 0 012-2h14a2 2 0 012 2v8a2 2 0 01-2 2h-5l-5 5v-5z" />
            </svg>
            Course Chat
          </a>
          <button
            onClick={() => handleGenerateQuiz('course')}
            disabled={quizLoading === 'course'}
            className={`inline-flex items-center gap-2 border border-zinc-700 hover:border-indigo-500/50 hover:bg-indigo-500/10 text-zinc-300 rounded-lg px-4 py-2 text-sm font-medium transition-all bg-transparent ${
              quizLoading === 'course' ? 'opacity-70 pointer-events-none' : ''
            }`}
          >
            {quizLoading === 'course' ? 'Generating...' : 'Quick Quiz'}
          </button>
          <button
            onClick={handleExamPrep}
            disabled={quizLoading === 'exam_prep'}
            className={`inline-flex items-center gap-2 border border-amber-500/30 hover:border-amber-500/50 hover:bg-amber-500/10 text-amber-300 rounded-lg px-4 py-2 text-sm font-medium transition-all bg-transparent ${
              quizLoading === 'exam_prep' ? 'opacity-70 pointer-events-none' : ''
            }`}
          >
            <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
              <path strokeLinecap="round" strokeLinejoin="round" d="M9 5H7a2 2 0 00-2 2v12a2 2 0 002 2h10a2 2 0 002-2V7a2 2 0 00-2-2h-2M9 5a2 2 0 002 2h2a2 2 0 002-2M9 5a2 2 0 012-2h2a2 2 0 012 2" />
            </svg>
            {quizLoading === 'exam_prep' ? 'Opening...' : 'Exam Prep'}
          </button>
        </div>
      </div>

      {/* Course Materials — shown before sections */}
      <div className="mb-6 bg-zinc-900 rounded-xl overflow-hidden">
        <div
          onClick={() => setMaterialsOpen(!materialsOpen)}
          className="px-5 py-4 flex items-center justify-between cursor-pointer hover:bg-zinc-800/50 transition-colors"
        >
          <div className="flex items-center gap-3">
            <svg
              className={`w-4 h-4 text-zinc-500 transition-transform duration-200 ${materialsOpen ? 'rotate-180' : ''}`}
              fill="none"
              viewBox="0 0 24 24"
              stroke="currentColor"
              strokeWidth={2}
            >
              <path strokeLinecap="round" strokeLinejoin="round" d="M19 9l-7 7-7-7" />
            </svg>
            <svg className="w-4 h-4 text-zinc-400" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
              <path strokeLinecap="round" strokeLinejoin="round" d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
            </svg>
            <h3 className="text-base font-medium text-zinc-100">Course Materials</h3>
            <span className="text-xs text-zinc-500">
              ({materials.length} file{materials.length !== 1 ? 's' : ''})
            </span>
          </div>
        </div>

        {materialsOpen && (
          <div className="border-t border-zinc-800/50 px-5 py-4 space-y-4">
            {/* Upload */}
            <div className="flex items-center gap-3">
              <input
                ref={fileInputRef}
                type="file"
                accept=".pdf,.txt,.md,.pptx,.vtt"
                multiple
                className="hidden"
                onChange={(e) => {
                  if (e.target.files && e.target.files.length > 0) {
                    handleUploadMaterials(e.target.files);
                  }
                }}
              />
              <button
                onClick={() => fileInputRef.current?.click()}
                disabled={uploading}
                className={`inline-flex items-center gap-2 border border-zinc-700 hover:border-indigo-500/50 hover:bg-indigo-500/10 text-zinc-300 rounded-lg px-4 py-2 text-sm font-medium transition-all bg-transparent ${
                  uploading ? 'opacity-70 pointer-events-none' : ''
                }`}
              >
                {uploading ? (
                  <>
                    <svg className="animate-spin w-4 h-4" viewBox="0 0 24 24" fill="none">
                      <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                      <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
                    </svg>
                    Processing & restructuring...
                  </>
                ) : (
                  <>
                    <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                      <path strokeLinecap="round" strokeLinejoin="round" d="M12 4v16m8-8H4" />
                    </svg>
                    Upload Files
                  </>
                )}
              </button>
              <span className="text-xs text-zinc-500">PDF, PPTX, VTT, TXT, MD</span>
            </div>

            {/* File list */}
            {materials.length === 0 ? (
              <p className="text-sm text-zinc-500">No materials uploaded yet. Upload lecture slides, transcripts, or notes to enrich the course.</p>
            ) : (
              <div className="space-y-1">
                {materials.map((m) => (
                  <div
                    key={m.id}
                    className="group flex items-center justify-between py-2 px-3 rounded-lg hover:bg-zinc-800/50 transition-colors"
                  >
                    <div className="flex items-center gap-3 min-w-0">
                      <FileIcon filename={m.filename} />
                      <span className="text-sm text-zinc-300 truncate">{m.filename}</span>
                      <span className="text-xs text-zinc-600 shrink-0">
                        {new Date(m.uploaded_at + 'Z').toLocaleDateString()}
                      </span>
                    </div>
                    <button
                      onClick={() => handleDeleteMaterial(m.id)}
                      className="text-zinc-600 hover:text-red-400 opacity-0 group-hover:opacity-100 transition-all bg-transparent border-none p-1"
                    >
                      <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                        <path strokeLinecap="round" strokeLinejoin="round" d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" />
                      </svg>
                    </button>
                  </div>
                ))}
              </div>
            )}
          </div>
        )}
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

/* ── File Icon ──────────────────────────────────────────────────────────── */

function FileIcon({ filename }: { filename: string }) {
  const ext = filename.split('.').pop()?.toLowerCase() || '';
  const colors: Record<string, string> = {
    pdf: 'text-red-400',
    pptx: 'text-orange-400',
    vtt: 'text-blue-400',
    md: 'text-green-400',
    txt: 'text-zinc-400',
  };
  const color = colors[ext] || 'text-zinc-500';

  return (
    <svg className={`w-4 h-4 ${color} shrink-0`} fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
      <path strokeLinecap="round" strokeLinejoin="round" d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
    </svg>
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
  const materials = section.related_materials || [];

  if (objectives.length === 0 && concepts.length === 0 && materials.length === 0) return null;

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
      {materials.length > 0 && (
        <div>
          <p className="text-xs text-zinc-500 uppercase tracking-wide font-medium">
            Reference Materials
          </p>
          <div className="flex flex-wrap gap-2 mt-2">
            {materials.map((m) => (
              <span key={m.id} className="inline-flex items-center gap-1.5 bg-zinc-800 text-zinc-400 rounded-full px-3 py-1 text-xs">
                <FileIcon filename={m.filename} />
                {m.filename}
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
