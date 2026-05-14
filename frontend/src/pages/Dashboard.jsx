import { useState, useEffect } from 'react'
import api from '../services/api'
import { Sparkles, AlertTriangle } from 'lucide-react'

export default function Dashboard() {
  const [sessions, setSessions] = useState([])
  const [alerts, setAlerts] = useState([])
  const [loading, setLoading] = useState(true)
  const [triggering, setTriggering] = useState(false)
  const [topic, setTopic] = useState('')
  const [image, setImage] = useState(null)

  useEffect(() => {
    Promise.all([
      api.get('/sessions?status=pending').then(r => r.data),
      api.get('/alerts').then(r => r.data).catch(() => ({ alerts: [] })),
    ]).then(([sessData, alertData]) => {
      setSessions(sessData.sessions || [])
      setAlerts(alertData.alerts || [])
      setLoading(false)
    })
  }, [])

  const handleTrigger = async () => {
    setTriggering(true)
    try {
      const form = new FormData()
      if (topic) form.append('topic', topic)
      if (image) form.append('image', image)
      await api.post('/trigger', form)
      window.location.href = '/sessions'
    } catch (err) {
      alert(err.response?.data?.detail || 'Generation failed')
    }
    setTriggering(false)
  }

  if (loading) return <div className="p-8 text-gray-500">Loading...</div>

  return (
    <div className="p-8 max-w-4xl">
      <h2 className="text-2xl font-bold mb-1 text-gray-900">Dashboard</h2>
      <p className="text-gray-500 text-sm mb-6">Generate and manage LinkedIn posts for MS. READ</p>

      {alerts.length > 0 && (
        <div className="mb-6 p-4 rounded-xl flex items-start gap-3" style={{ background: '#FFF5F2', border: '1px solid #FFAC9C' }}>
          <AlertTriangle className="mt-0.5" size={20} style={{ color: '#E8613F' }} />
          <div>
            <p className="font-medium" style={{ color: '#9E1A00' }}>{alerts.length} engagement alert{alerts.length > 1 ? 's' : ''}</p>
            <p className="text-sm" style={{ color: '#E8613F' }}>Some posts are performing above average. Check Analytics for details.</p>
          </div>
        </div>
      )}

      <div className="bg-white rounded-xl border border-gray-200 p-6 mb-6">
        <h3 className="font-semibold mb-4 flex items-center gap-2" style={{ color: '#9E1A00' }}>
          <Sparkles size={18} style={{ color: '#E8613F' }} />
          Generate New Content
        </h3>
        <div className="space-y-4">
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">Topic (optional)</label>
            <input
              type="text"
              value={topic}
              onChange={(e) => setTopic(e.target.value)}
              placeholder="e.g. Workplace culture, hiring tips..."
              className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm focus:ring-2 outline-none"
              style={{ '--tw-ring-color': '#E8613F' }}
              onFocus={(e) => e.target.style.borderColor = '#E8613F'}
              onBlur={(e) => e.target.style.borderColor = ''}
            />
          </div>
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">Attach image (optional)</label>
            <input
              type="file"
              accept="image/*"
              onChange={(e) => setImage(e.target.files[0])}
              className="block w-full text-sm text-gray-500 file:mr-4 file:py-2 file:px-4 file:rounded-lg file:border-0 file:text-sm file:font-medium file:text-white"
              style={{ '--tw-file-bg': '#E8613F' }}
            />
          </div>
          <button
            onClick={handleTrigger}
            disabled={triggering}
            className="text-white px-6 py-2.5 rounded-lg text-sm font-medium transition-colors disabled:opacity-50"
            style={{ background: triggering ? '#D05234' : '#E8613F' }}
            onMouseEnter={(e) => e.target.style.background = '#D05234'}
            onMouseLeave={(e) => e.target.style.background = triggering ? '#D05234' : '#E8613F'}
          >
            {triggering ? 'Generating...' : 'Generate 3 Options'}
          </button>
        </div>
      </div>

      <div className="bg-white rounded-xl border border-gray-200 p-6">
        <h3 className="font-semibold mb-4 text-gray-900">Recent Pending Sessions</h3>
        {sessions.length === 0 ? (
          <p className="text-gray-500 text-sm">No pending sessions. Generate content above to get started.</p>
        ) : (
          <div className="space-y-3">
            {sessions.slice(0, 5).map((s) => (
              <div key={s.id} className="flex items-center justify-between p-3 rounded-lg" style={{ background: '#FFF5F2' }}>
                <div>
                  <span className="text-sm font-medium">Session #{s.id}</span>
                  {s.topic && <span className="text-sm text-gray-500 ml-2">— {s.topic}</span>}
                </div>
                <a href="/sessions" className="text-sm font-medium hover:underline" style={{ color: '#E8613F' }}>View</a>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  )
}