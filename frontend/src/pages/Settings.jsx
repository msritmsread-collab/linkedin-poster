import { useState, useEffect } from 'react'
import api from '../services/api'
import { Save, CheckCircle, XCircle, Loader } from 'lucide-react'

const DAYS = ['mon', 'tue', 'wed', 'thu', 'fri', 'sat', 'sun']

export default function Settings() {
  const [settings, setSettings] = useState(null)
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)
  const [testing, setTesting] = useState(false)
  const [testResult, setTestResult] = useState(null)
  const [saved, setSaved] = useState(false)

  const [token, setToken] = useState('')
  const [orgId, setOrgId] = useState('')
  const [memberId, setMemberId] = useState('')
  const [postMode, setPostMode] = useState('org')
  const [scheduleDays, setScheduleDays] = useState(['mon', 'wed', 'fri'])
  const [scheduleTime, setScheduleTime] = useState('09:00')
  const [topics, setTopics] = useState([])
  const [newTopic, setNewTopic] = useState('')
  const [referencePosts, setReferencePosts] = useState([])

  useEffect(() => {
    api.get('/settings').then((res) => {
      const d = res.data
      setSettings(d)
      setOrgId(d.linkedin_org_id)
      setMemberId(d.linkedin_member_id || '')
      setPostMode(d.post_mode)
      setScheduleDays(d.schedule_days)
      setScheduleTime(d.schedule_time)
      setTopics(d.default_topics)
      setReferencePosts(d.reference_posts || [])
      setLoading(false)
    })
  }, [])

  const handleSave = async () => {
    setSaving(true)
    setSaved(false)
    try {
      await api.put('/settings', {
        linkedin_token: token || undefined,
        linkedin_org_id: orgId,
        linkedin_member_id: memberId,
        post_mode: postMode,
        schedule_days: scheduleDays,
        schedule_time: scheduleTime,
        default_topics: topics,
        reference_posts: referencePosts,
      })
      setSaved(true)
      setToken('')
      setTimeout(() => setSaved(false), 3000)
    } catch (err) {
      alert('Save failed: ' + (err.response?.data?.detail || err.message))
    }
    setSaving(false)
  }

  const handleTest = async () => {
    setTesting(true)
    setTestResult(null)
    try {
      const res = await api.post('/settings/test')
      setTestResult(res.data)
    } catch (err) {
      setTestResult({ ok: false, error: err.response?.data?.detail || 'Connection test failed' })
    }
    setTesting(false)
  }

  const toggleDay = (day) => {
    setScheduleDays((prev) =>
      prev.includes(day) ? prev.filter((d) => d !== day) : [...prev, day]
    )
  }

  const addTopic = () => {
    if (newTopic.trim()) {
      setTopics([...topics, newTopic.trim()])
      setNewTopic('')
    }
  }

  const removeTopic = (i) => {
    setTopics(topics.filter((_, idx) => idx !== i))
  }

  const addRefPost = () => {
    setReferencePosts([...referencePosts, { label: '', text: '' }])
  }

  const removeRefPost = (i) => {
    setReferencePosts(referencePosts.filter((_, idx) => idx !== i))
  }

  const updateRefPost = (i, field, value) => {
    const updated = [...referencePosts]
    updated[i][field] = value
    setReferencePosts(updated)
  }

  if (loading) return <div className="p-8 text-gray-500">Loading settings...</div>

  return (
    <div className="p-8 max-w-3xl">
      <h2 className="text-2xl font-bold mb-1">Settings</h2>
      <p className="text-gray-500 text-sm mb-6">Configure LinkedIn credentials, schedule, and preferences</p>

      <div className="space-y-6">
        {/* LinkedIn Connection */}
        <div className="bg-white rounded-xl border border-gray-200 p-6">
          <h3 className="font-semibold mb-4">LinkedIn Connection</h3>
          <div className="space-y-4">
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">Access Token</label>
              <input
                type="password"
                value={token}
                onChange={(e) => setToken(e.target.value)}
                placeholder={settings?.linkedin_token_set ? 'Token saved (leave blank to keep)' : 'Enter LinkedIn access token'}
                className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm focus:ring-2 focus:ring-brand-500 outline-none"
              />
              {settings?.linkedin_token_masked && (
                <p className="text-xs text-gray-500 mt-1">Current: {settings.linkedin_token_masked}</p>
              )}
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">Post Mode</label>
              <select
                value={postMode}
                onChange={(e) => setPostMode(e.target.value)}
                className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm focus:ring-2 focus:ring-brand-500 outline-none"
              >
                <option value="org">Company Page (Organization)</option>
                <option value="personal">Personal Profile</option>
              </select>
            </div>
            {postMode === 'org' ? (
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">Organization ID</label>
                <input
                  type="text"
                  value={orgId}
                  onChange={(e) => setOrgId(e.target.value)}
                  className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm focus:ring-2 focus:ring-brand-500 outline-none"
                />
              </div>
            ) : (
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">Member ID</label>
                <input
                  type="text"
                  value={memberId}
                  onChange={(e) => setMemberId(e.target.value)}
                  placeholder="LinkedIn member ID (numeric)"
                  className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm focus:ring-2 focus:ring-brand-500 outline-none"
                />
              </div>
            )}
            <button
              onClick={handleTest}
              disabled={testing}
              className="flex items-center gap-2 px-4 py-2 border border-gray-300 rounded-lg text-sm hover:bg-gray-50 disabled:opacity-50"
            >
              {testing ? <Loader size={16} className="animate-spin" /> : <CheckCircle size={16} />}
              Test Connection
            </button>
            {testResult && (
              <div className={`p-3 rounded-lg text-sm ${testResult.ok ? 'bg-green-50 text-green-800' : 'bg-red-50 text-red-800'}`}>
                {testResult.ok
                  ? `Connected as: ${testResult.org_name || testResult.name} (Mode: ${testResult.mode})`
                  : `Failed: ${testResult.error}`}
              </div>
            )}
          </div>
        </div>

        {/* Schedule */}
        <div className="bg-white rounded-xl border border-gray-200 p-6">
          <h3 className="font-semibold mb-4">Posting Schedule</h3>
          <div className="space-y-4">
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-2">Days</label>
              <div className="flex flex-wrap gap-2">
                {DAYS.map((d) => (
                  <button
                    key={d}
                    onClick={() => toggleDay(d)}
                    className={`px-3 py-1.5 rounded-lg text-sm font-medium transition-colors ${
                      scheduleDays.includes(d)
                        ? 'bg-brand-600 text-white'
                        : 'bg-gray-100 text-gray-600 hover:bg-gray-200'
                    }`}
                  >
                    {d.charAt(0).toUpperCase() + d.slice(1)}
                  </button>
                ))}
              </div>
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">Time (Malaysia)</label>
              <input
                type="time"
                value={scheduleTime}
                onChange={(e) => setScheduleTime(e.target.value)}
                className="border border-gray-300 rounded-lg px-3 py-2 text-sm focus:ring-2 focus:ring-brand-500 outline-none"
              />
            </div>
          </div>
        </div>

        {/* Default Topics */}
        <div className="bg-white rounded-xl border border-gray-200 p-6">
          <h3 className="font-semibold mb-4">Default Topics</h3>
          <div className="flex flex-wrap gap-2 mb-3">
            {topics.map((t, i) => (
              <span key={i} className="flex items-center gap-1 bg-brand-50 text-brand-700 px-3 py-1 rounded-full text-sm">
                {t}
                <button onClick={() => removeTopic(i)} className="hover:text-red-500"><XCircle size={14} /></button>
              </span>
            ))}
          </div>
          <div className="flex gap-2">
            <input
              type="text"
              value={newTopic}
              onChange={(e) => setNewTopic(e.target.value)}
              onKeyDown={(e) => e.key === 'Enter' && addTopic()}
              placeholder="Add a topic..."
              className="flex-1 border border-gray-300 rounded-lg px-3 py-2 text-sm focus:ring-2 focus:ring-brand-500 outline-none"
            />
            <button onClick={addTopic} className="px-4 py-2 bg-brand-600 text-white rounded-lg text-sm hover:bg-brand-700">Add</button>
          </div>
        </div>

        {/* Reference Posts */}
        <div className="bg-white rounded-xl border border-gray-200 p-6">
          <h3 className="font-semibold mb-4">Reference Posts</h3>
          <p className="text-sm text-gray-500 mb-3">Add example LinkedIn posts for the AI to learn tone and style from.</p>
          {referencePosts.map((ref, i) => (
            <div key={i} className="mb-4 p-3 bg-gray-50 rounded-lg">
              <input
                type="text"
                value={ref.label}
                onChange={(e) => updateRefPost(i, 'label', e.target.value)}
                placeholder="Label (e.g. Brand Story Example 1)"
                className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm mb-2 focus:ring-2 focus:ring-brand-500 outline-none"
              />
              <textarea
                value={ref.text}
                onChange={(e) => updateRefPost(i, 'text', e.target.value)}
                placeholder="Paste the full post text here..."
                rows={3}
                className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm focus:ring-2 focus:ring-brand-500 outline-none"
              />
              <button onClick={() => removeRefPost(i)} className="text-sm text-red-600 hover:underline mt-1">Remove</button>
            </div>
          ))}
          <button onClick={addRefPost} className="text-sm text-brand-600 hover:underline">+ Add reference post</button>
        </div>

        {/* Save */}
        <div className="flex items-center gap-3">
          <button
            onClick={handleSave}
            disabled={saving}
            className="flex items-center gap-2 px-6 py-2.5 bg-brand-600 text-white rounded-lg text-sm font-medium hover:bg-brand-700 disabled:opacity-50"
          >
            <Save size={16} />
            {saving ? 'Saving...' : 'Save Settings'}
          </button>
          {saved && <span className="text-green-600 text-sm font-medium">Settings saved!</span>}
        </div>
      </div>
    </div>
  )
}