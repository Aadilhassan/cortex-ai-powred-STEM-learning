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

export async function generateQuiz(courseId: string, scope: string, opts?: { sectionId?: string; subtopicId?: string; numQuestions?: number; examType?: string }) {
  const body: Record<string, unknown> = {
    course_id: courseId,
    scope,
    section_id: opts?.sectionId,
    subtopic_id: opts?.subtopicId,
    exam_type: opts?.examType,
  };
  // Only send num_questions if explicitly provided (let backend use exam defaults otherwise)
  if (opts?.numQuestions != null) {
    body.num_questions = opts.numQuestions;
  } else if (!opts?.examType) {
    body.num_questions = 5;
  }
  const r = await fetch(`${BASE}/quiz/generate`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  });
  if (!r.ok) {
    const err = await r.json().catch(() => ({ detail: 'Quiz generation failed' }));
    throw new Error(err.detail || 'Quiz generation failed');
  }
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

export async function uploadMaterials(courseId: string, files: File[]) {
  const form = new FormData();
  for (const file of files) {
    form.append('files', file);
  }
  const r = await fetch(`${BASE}/courses/${courseId}/materials`, { method: 'POST', body: form });
  if (!r.ok) {
    const err = await r.json().catch(() => ({ detail: 'Upload failed' }));
    throw new Error(err.detail || 'Upload failed');
  }
  return r.json();
}

export async function listMaterials(courseId: string) {
  const r = await fetch(`${BASE}/courses/${courseId}/materials`);
  return r.json();
}

export async function deleteMaterial(materialId: string) {
  await fetch(`${BASE}/materials/${materialId}`, { method: 'DELETE' });
}

export async function getSubtopicInfo(subtopicId: string) {
  const r = await fetch(`${BASE}/chat/${subtopicId}/info`);
  return r.json();
}

export async function getMaterialContent(materialId: string) {
  const r = await fetch(`${BASE}/materials/${materialId}/content`);
  return r.json();
}

// ── Exams ───────────────────────────────────────────────────────────────────

export async function createExam(courseId: string, title = 'Exam Prep', details = '') {
  const r = await fetch(`${BASE}/exams`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ course_id: courseId, title, details }),
  });
  return r.json();
}

export async function getExamsForCourse(courseId: string) {
  const r = await fetch(`${BASE}/exams/course/${courseId}`);
  return r.json();
}

export async function getExam(examId: string) {
  const r = await fetch(`${BASE}/exams/${examId}`);
  return r.json();
}

export async function updateExam(examId: string, fields: { title?: string; details?: string }) {
  const r = await fetch(`${BASE}/exams/${examId}`, {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(fields),
  });
  return r.json();
}

export async function deleteExam(examId: string) {
  await fetch(`${BASE}/exams/${examId}`, { method: 'DELETE' });
}

export async function uploadExamResources(examId: string, files: File[]) {
  const form = new FormData();
  for (const file of files) {
    form.append('files', file);
  }
  const r = await fetch(`${BASE}/exams/${examId}/resources`, { method: 'POST', body: form });
  if (!r.ok) {
    const err = await r.json().catch(() => ({ detail: 'Upload failed' }));
    throw new Error(err.detail || 'Upload failed');
  }
  return r.json();
}

export async function listExamResources(examId: string) {
  const r = await fetch(`${BASE}/exams/${examId}/resources`);
  return r.json();
}

export async function deleteExamResource(resourceId: string) {
  await fetch(`${BASE}/exam-resources/${resourceId}`, { method: 'DELETE' });
}

export async function getExamResourceContent(resourceId: string) {
  const r = await fetch(`${BASE}/exam-resources/${resourceId}/content`);
  return r.json();
}
