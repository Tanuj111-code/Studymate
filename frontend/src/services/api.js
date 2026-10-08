const API = import.meta.env.VITE_API_URL || 'http://127.0.0.1:5000'
async function request(path, options) {
  let response
  try { response = await fetch(`${API}${path}`, options) } catch { throw new Error('Could not reach the StudyMate server. Check that the backend is running.') }
  const data = await response.json().catch(() => ({}))
  if (!response.ok) throw new Error(data.error || 'Something went wrong. Please try again.')
  return data
}
export const analyzeFile = file => { const form = new FormData(); form.append('file', file); return request('/api/analyze', { method: 'POST', body: form }) }
export const evaluateQuiz = (analysis, answers) => request('/api/evaluate', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ analysis, answers }) })
