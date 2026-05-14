import { useState, useEffect } from 'react'
import api from '../services/api'
import { BarChart3, TrendingUp, Users, RefreshCw, AlertTriangle } from 'lucide-react'

export default function Analytics() {
  const [data, setData] = useState(null)
  const [alerts, setAlerts] = useState([])
  const [loading, setLoading] = useState(true)
  const [refreshing, setRefreshing] = useState(false)

  const fetchAnalytics = async () => {
    setLoading(true)
    const res = await api.get('/analytics')
    setData(res.data)
    setLoading(false)
  }

  const fetchAlerts = async () => {
    try {
      const res = await api.get('/alerts')
      setAlerts(res.data.alerts || [])
    } catch { setAlerts([]) }
  }

  useEffect(() => { fetchAnalytics(); fetchAlerts() }, [])

  const handleRefresh = async () => {
    setRefreshing(true)
    try {
      await api.post('/analytics/refresh')
      await fetchAnalytics()
    } catch (err) {
      alert(err.response?.data?.error || 'Refresh failed')
    }
    setRefreshing(false)
  }

  const dismissAlert = async (id) => {
    await api.post(`/alerts/${id}/dismiss`)
    fetchAlerts()
  }

  if (loading) return <div className="p-8 text-gray-500">Loading analytics...</div>

  const { followers = {}, totals = {}, posts = [], by_angle = [] } = data || {}

  return (
    <div className="p-8 max-w-5xl">
      <div className="flex items-center justify-between mb-6">
        <div>
          <h2 className="text-2xl font-bold">Analytics</h2>
          <p className="text-gray-500 text-sm">LinkedIn post performance and engagement</p>
        </div>
        <button
          onClick={handleRefresh}
          disabled={refreshing}
          className="flex items-center gap-2 px-4 py-2 bg-brand-600 text-white rounded-lg text-sm font-medium hover:bg-brand-700 disabled:opacity-50"
        >
          <RefreshCw size={16} className={refreshing ? 'animate-spin' : ''} />
          {refreshing ? 'Refreshing...' : 'Refresh Data'}
        </button>
      </div>

      {alerts.length > 0 && (
        <div className="mb-6 space-y-2">
          {alerts.map((a) => (
            <div key={a.id} className="flex items-center justify-between p-3 bg-amber-50 border border-amber-200 rounded-lg">
              <div className="flex items-center gap-2">
                <AlertTriangle size={16} className="text-amber-600" />
                <div>
                  <span className="text-sm font-medium text-amber-800">{a.angle_name}</span>
                  <span className="text-xs text-amber-600 ml-2">{a.multiple}x avg engagement</span>
                </div>
              </div>
              <button onClick={() => dismissAlert(a.id)} className="text-xs text-amber-700 hover:underline">Dismiss</button>
            </div>
          ))}
        </div>
      )}

      <div className="grid grid-cols-3 gap-4 mb-6">
        <div className="bg-white rounded-xl border border-gray-200 p-4">
          <div className="flex items-center gap-2 text-gray-500 text-sm mb-1">
            <Users size={16} />Followers
          </div>
          <div className="text-2xl font-bold">{followers.total?.toLocaleString() || '—'}</div>
          {followers.growth != null && (
            <div className={`text-sm ${followers.growth >= 0 ? 'text-green-600' : 'text-red-600'}`}>
              {followers.growth >= 0 ? '+' : ''}{followers.growth} change
            </div>
          )}
        </div>
        <div className="bg-white rounded-xl border border-gray-200 p-4">
          <div className="flex items-center gap-2 text-gray-500 text-sm mb-1">
            <BarChart3 size={16} />Total Impressions
          </div>
          <div className="text-2xl font-bold">{totals.impressions?.toLocaleString() || 0}</div>
          <div className="text-sm text-gray-500">{totals.posts} posts</div>
        </div>
        <div className="bg-white rounded-xl border border-gray-200 p-4">
          <div className="flex items-center gap-2 text-gray-500 text-sm mb-1">
            <TrendingUp size={16} />Engagement
          </div>
          <div className="text-2xl font-bold">{totals.likes + totals.comments + totals.shares}</div>
          <div className="text-sm text-gray-500">{totals.likes} likes · {totals.comments} comments · {totals.shares} shares</div>
        </div>
      </div>

      {by_angle.length > 0 && (
        <div className="bg-white rounded-xl border border-gray-200 p-6 mb-6">
          <h3 className="font-semibold mb-4">Performance by Content Angle</h3>
          <div className="space-y-3">
            {by_angle.map((a) => (
              <div key={a.angle} className="flex items-center justify-between p-3 bg-gray-50 rounded-lg">
                <div>
                  <span className="font-medium text-sm">{a.angle}</span>
                  <span className="text-xs text-gray-500 ml-2">({a.posts} posts)</span>
                </div>
                <div className="text-sm text-gray-600">
                  Avg {a.avg_impressions.toLocaleString()} impressions · {a.avg_engagement} engagements
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      <div className="bg-white rounded-xl border border-gray-200 p-6">
        <h3 className="font-semibold mb-4">Post Performance</h3>
        {posts.length === 0 ? (
          <p className="text-gray-500 text-sm">No post data yet. Published posts will appear here.</p>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-gray-200 text-left text-gray-500">
                  <th className="pb-2 font-medium">Post</th>
                  <th className="pb-2 font-medium">Impressions</th>
                  <th className="pb-2 font-medium">Likes</th>
                  <th className="pb-2 font-medium">Comments</th>
                  <th className="pb-2 font-medium">Shares</th>
                  <th className="pb-2 font-medium">Eng. Rate</th>
                </tr>
              </thead>
              <tbody>
                {posts.map((p, i) => (
                  <tr key={i} className="border-b border-gray-100">
                    <td className="py-2 max-w-xs truncate">{p.content?.slice(0, 80) || p.angle_name || '—'}...</td>
                    <td className="py-2">{(p.impressions || 0).toLocaleString()}</td>
                    <td className="py-2">{p.likes || 0}</td>
                    <td className="py-2">{p.comments || 0}</td>
                    <td className="py-2">{p.shares || 0}</td>
                    <td className="py-2">{p.engagement_rate ?? '—'}%</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  )
}