import { createContext, useContext, useState, useEffect, useCallback, useRef } from 'react'
import api from './api'

const AuthContext = createContext(null)

export function AuthProvider({ children }) {
  const [user, setUser] = useState(null)
  const [loading, setLoading] = useState(true)
  const checked = useRef(false)

  const checkAuth = useCallback(async () => {
    const token = localStorage.getItem('token')
    if (!token) { setUser(null); setLoading(false); return }
    try {
      const res = await api.get('/auth/me')
      setUser(res.data)
    } catch {
      localStorage.removeItem('token')
      setUser(null)
    }
    setLoading(false)
  }, [])

  useEffect(() => {
    if (!checked.current) {
      checked.current = true
      checkAuth()
    }
  }, [checkAuth])

  const login = async (email, password) => {
    const res = await api.post('/auth/login', { email, password })
    localStorage.setItem('token', res.data.access_token)
    setUser(res.data.user)
    return res.data
  }

  const logout = () => {
    localStorage.removeItem('token')
    setUser(null)
  }

  return (
    <AuthContext.Provider value={{ user, loading, login, logout, checkAuth }}>
      {children}
    </AuthContext.Provider>
  )
}

export const useAuth = () => useContext(AuthContext)