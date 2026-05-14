import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { useAuth } from '../services/auth'

export default function Login() {
  const { login } = useAuth()
  const navigate = useNavigate()
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)

  const handleSubmit = async (e) => {
    e.preventDefault()
    setError('')
    setLoading(true)
    try {
      await login(email, password)
      navigate('/', { replace: true })
    } catch (err) {
      setError(err.response?.data?.detail || 'Login failed')
    }
    setLoading(false)
  }

  return (
    <div className="min-h-screen flex items-center justify-center" style={{ background: '#FFF5F2' }}>
      <div className="w-full max-w-sm bg-white rounded-2xl shadow-lg p-8">
        <div className="text-center mb-8">
          <div className="inline-flex items-center justify-center w-14 h-14 rounded-xl mb-3" style={{ background: 'linear-gradient(135deg, #9E1A00 0%, #E8613F 100%)' }}>
            <span className="text-white text-xl font-bold">MR</span>
          </div>
          <h1 className="text-xl font-bold" style={{ color: '#9E1A00' }}>MS. READ</h1>
          <p className="text-sm text-gray-500 mt-1">LinkedIn Auto-Poster</p>
        </div>
        <form onSubmit={handleSubmit} className="space-y-4">
          {error && (
            <div className="p-3 rounded-lg text-sm" style={{ background: '#FFF5F2', color: '#9E1A00', border: '1px solid #FFAC9C' }}>
              {error}
            </div>
          )}
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">Email</label>
            <input
              type="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              className="w-full border border-gray-300 rounded-lg px-3 py-2.5 text-sm focus:ring-2 outline-none transition-colors"
              style={{ '--tw-ring-color': '#E8613F' }}
              onFocus={(e) => e.target.style.borderColor = '#E8613F'}
              onBlur={(e) => e.target.style.borderColor = ''}
              required
            />
          </div>
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">Password</label>
            <input
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              className="w-full border border-gray-300 rounded-lg px-3 py-2.5 text-sm focus:ring-2 outline-none transition-colors"
              style={{ '--tw-ring-color': '#E8613F' }}
              onFocus={(e) => e.target.style.borderColor = '#E8613F'}
              onBlur={(e) => e.target.style.borderColor = ''}
              required
            />
          </div>
          <button
            type="submit"
            disabled={loading}
            className="w-full text-white py-2.5 rounded-lg text-sm font-medium transition-colors disabled:opacity-50"
            style={{ background: loading ? '#D05234' : '#E8613F' }}
            onMouseEnter={(e) => !loading && (e.target.style.background = '#9E1A00')}
            onMouseLeave={(e) => (e.target.style.background = loading ? '#D05234' : '#E8613F')}
          >
            {loading ? 'Signing in...' : 'Sign in'}
          </button>
        </form>
      </div>
    </div>
  )
}