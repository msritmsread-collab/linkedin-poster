import { useState, useEffect } from 'react'
import api from '../services/api'
import { Check, X, RefreshCw, Clock, Image as ImageIcon } from 'lucide-react'

const STATUS_BADGE = {
  pending: 'bg-yellow-100 text-yellow-800',
  approved: 'bg-green-100 text-green-800',
  rejected: 'bg-red-100 text-red-800',
  posted: 'bg-blue-100 text-blue-800',
}

export default function Sessions() {
  const [sessions, setSessions] = useState([])
  const [filter, setFilter] = useState('')
  const [loading, setLoading] = useState(true)
  const [approving, setApproving] = useState(null)
  const [expanded, setExpanded] = useState(null)

  const fetchSessions = async (status = '') => {
    setLoading(true)
    const params = status ? `?status=${status}` : ''
    const res = await api.get(`/sessions${params}`)
    setSessions(res.data.sessions || [])
    setLoading(false)
  }

  useEffect(() => { fetchSessions() }, [])

  const handleApprove = async (sessionId, label) => {
    setApproving(`${sessionId}-${label}`)
    try {
      await api.post(`/sessions/${sessionId}/approve/${label}`)
      fetchSessions(filter)
    } catch (err) {
      alert(err.response?.data?.detail || 'Post failed')
    }
    setApproving(null)
  }

  const handleReject = async (sessionId) => {
    const keywords = prompt('Enter topic keywords to block (6 months):')
    if (!keywords) return
    try {
      await api.post(`/sessions/${sessionId}/reject`, { keywords })
      fetchSessions(filter)
    } catch (err) {
      alert(err.response?.data?.detail || 'Reject failed')
    }
  }

  const filteredSessions = filter
    ? sessions.filter((s) => s.status === filter)
    : sessions

  return (
    <div className="p-8 max-w-5xl">
      <div className="flex items-center justify-between mb-6">
        <div>
          <h2 className="text-2xl font-bold">Sessions</h2>
          <p className="text-gray-500 text-sm">Review, approve, or reject generated content</p>
        </div>
        <button onClick={() => fetchSessions(filter)} className="flex items-center gap-1 text-sm text-brand-600 hover:text-brand-700">
          <RefreshCw size={14} />
          Refresh
        </button>
      </div>

      <div className="flex gap-2 mb-4">
        {['', 'pending', 'approved', 'rejected', 'posted'].map((s) => (
          <button
            key={s}
            onClick={() => { setFilter(s); fetchSessions(s) }}
            className={`px-3 py-1.5 rounded-lg text-sm font-medium transition-colors ${
              filter === s ? 'bg-brand-600 text-white' : 'bg-gray-100 text-gray-600 hover:bg-gray-200'
            }`}
          >
            {s || 'All'}
          </button>
        ))}
      </div>

      {loading ? (
        <div className="text-gray-500">Loading...</div>
      ) : filteredSessions.length === 0 ? (
        <div className="text-gray-500 text-sm">No sessions found.</div>
      ) : (
        <div className="space-y-4">
          {filteredSessions.map((s) => (
            <div key={s.id} className="bg-white rounded-xl border border-gray-200">
              <div
                className="p-4 cursor-pointer hover:bg-gray-50 flex items-center justify-between"
                onClick={() => setExpanded(expanded === s.id ? null : s.id)}
              >
                <div className="flex items-center gap-3">
                  <span className="font-medium">Session #{s.id}</span>
                  {s.topic && <span className="text-sm text-gray-500">— {s.topic}</span>}
                  <span className={`text-xs px-2 py-0.5 rounded-full ${STATUS_BADGE[s.status] || 'bg-gray-100 text-gray-600'}`}>
                    {s.status}
                  </span>
                </div>
                <div className="flex items-center gap-2 text-xs text-gray-400">
                  <Clock size={12} />
                  {new Date(s.created_at).toLocaleString()}
                </div>
              </div>

              {expanded === s.id && s.options && (
                <div className="border-t border-gray-100 p-4 space-y-3">
                  {s.image_path && (
                    <div className="flex items-center gap-2 text-sm text-gray-500 mb-2">
                      <ImageIcon size={14} />
                      Image attached
                    </div>
                  )}
                  {s.options.map((opt) => (
                    <div key={opt.id} className="p-3 bg-gray-50 rounded-lg">
                      <div className="flex items-center justify-between mb-2">
                        <span className="font-medium text-sm">
                          Option {opt.label} — {opt.angle_name}
                        </span>
                        <span className={`text-xs px-2 py-0.5 rounded-full ${STATUS_BADGE[opt.status] || 'bg-gray-100 text-gray-600'}`}>
                          {opt.status}
                        </span>
                      </div>
                      <p className="text-sm text-gray-700 whitespace-pre-wrap">{opt.content}</p>

                      {s.status === 'pending' && (
                        <div className="flex gap-2 mt-3">
                          <button
                            onClick={(e) => { e.stopPropagation(); handleApprove(s.id, opt.label) }}
                            disabled={!!approving}
                            className="flex items-center gap-1 px-3 py-1.5 bg-green-600 text-white rounded-lg text-sm hover:bg-green-700 disabled:opacity-50"
                          >
                            <Check size={14} />
                            {approving === `${s.id}-${opt.label}` ? 'Posting...' : 'Approve & Post'}
                          </button>
                        </div>
                      )}
                    </div>
                  ))}
                  {s.status === 'pending' && (
                    <button
                      onClick={(e) => { e.stopPropagation(); handleReject(s.id) }}
                      className="flex items-center gap-1 px-3 py-1.5 text-red-600 border border-red-200 rounded-lg text-sm hover:bg-red-50"
                    >
                      <X size={14} />
                      Reject All
                    </button>
                  )}
                </div>
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  )
}