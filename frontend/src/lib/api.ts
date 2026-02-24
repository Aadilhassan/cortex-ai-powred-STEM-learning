const BASE = '/api';

export async function listCourses() {
  const r = await fetch(`${BASE}/courses`);
  return r.json();
}

export async function getCourse(id: string) {
  const r = await fetch(`${BASE}/courses/${id}`);
  return r.json();
}

export async function createCourse(handoutText: string) {
  const r = await fetch(`${BASE}/courses`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ handout_text: handoutText }),
  });
  return r.json();
}

export async function uploadCourse(file: File) {
  const form = new FormData();
  form.append('file', file);
  const r = await fetch(`${BASE}/courses/upload`, { method: 'POST', body: form });
  return r.json();
}

export async function generateDiagram(topic: string, context?: string, diagramType?: string) {
  const r = await fetch(`${BASE}/diagrams`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ topic, context, diagram_type: diagramType }),
  });
  return r.json();
}

export async function deleteCourse(id: string) {
  await fetch(`${BASE}/courses/${id}`, { method: 'DELETE' });
}

export async function generateQuiz(courseId: string, scope: string, opts?: { sectionId?: string; subtopicId?: string; numQuestions?: number }) {
  const r = await fetch(`${BASE}/quiz/generate`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ course_id: courseId, scope, section_id: opts?.sectionId, subtopic_id: opts?.subtopicId, num_questions: opts?.numQuestions ?? 5 }),
  });
  return r.json();
}

export async function getQuiz(id: string) {
  const r = await fetch(`${BASE}/quiz/${id}`);
  return r.json();
}

export async function submitQuiz(quizId: string, answers: string[]) {
  const r = await fetch(`${BASE}/quiz/${quizId}/submit`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ answers }),
  });
  return r.json();
}

export async function getProgress(courseId: string) {
  const r = await fetch(`${BASE}/progress/${courseId}`);
  return r.json();
}
