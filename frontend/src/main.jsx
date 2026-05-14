import React from 'react'
import ReactDOM from 'react-dom/client'
import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom'
import './index.css'
import App from './App'
import Login from './pages/Login'
import Dashboard from './pages/Dashboard'
import Sessions from './pages/Sessions'
import Analytics from './pages/Analytics'
import Settings from './pages/Settings'
import Admin from './pages/Admin'
import { AuthProvider, useAuth } from './services/auth'

function PrivateRoute({ children }) {
  const { user, loading } = useAuth()
  if (loading) return <div className="p-8 text-center text-gray-500">Loading...</div>
  if (!user) return <Navigate to="/login" />
  return children
}

function AdminRoute({ children }) {
  const { user, loading } = useAuth()
  if (loading) return <div className="p-8 text-center text-gray-500">Loading...</div>
  if (!user) return <Navigate to="/login" />
  if (user.role !== 'admin') return <Navigate to="/" />
  return children
}

ReactDOM.createRoot(document.getElementById('root')).render(
  <React.StrictMode>
    <BrowserRouter>
      <AuthProvider>
        <Routes>
          <Route path="/login" element={<Login />} />
          <Route path="/" element={<PrivateRoute><App /></PrivateRoute>}>
            <Route index element={<Dashboard />} />
            <Route path="sessions" element={<Sessions />} />
            <Route path="analytics" element={<Analytics />} />
            <Route path="settings" element={<Settings />} />
            <Route path="admin" element={<AdminRoute><Admin /></AdminRoute>} />
          </Route>
        </Routes>
      </AuthProvider>
    </BrowserRouter>
  </React.StrictMode>
)