import { useState, useEffect } from 'react'
import api from '../services/api'
import { UserPlus, Trash2, Shield } from 'lucide-react'

export default function Admin() {
  const [users, setUsers] = useState([])
  const [loading, setLoading] = useState(true)
  const [showCreate, setShowCreate] = useState(false)
  const [newEmail, setNewEmail] = useState('')
  const [newPassword, setNewPassword] = useState('')
  const [newRole, setNewRole] = useState('user')

  const fetchUsers = async () => {
    setLoading(true)
    const res = await api.get('/admin/users')
    setUsers(res.data.users || [])
    setLoading(false)
  }

  useEffect(() => { fetchUsers() }, [])

  const handleCreate = async (e) => {
    e.preventDefault()
    try {
      await api.post('/admin/users', { email: newEmail, password: newPassword, role: newRole })
      setShowCreate(false)
      setNewEmail('')
      setNewPassword('')
      setNewRole('user')
      fetchUsers()
    } catch (err) {
      alert(err.response?.data?.detail || 'Create failed')
    }
  }

  const handleDelete = async (userId) => {
    if (!confirm('Are you sure you want to delete this user?')) return
    try {
      await api.delete(`/admin/users/${userId}`)
      fetchUsers()
    } catch (err) {
      alert(err.response?.data?.detail || 'Delete failed')
    }
  }

  const handleToggleActive = async (userId, currentActive) => {
    try {
      await api.patch(`/admin/users/${userId}`, { active: currentActive ? 0 : 1 })
      fetchUsers()
    } catch (err) {
      alert(err.response?.data?.detail || 'Update failed')
    }
  }

  const handleRoleChange = async (userId, role) => {
    try {
      await api.patch(`/admin/users/${userId}`, { role })
      fetchUsers()
    } catch (err) {
      alert(err.response?.data?.detail || 'Update failed')
    }
  }

  if (loading) return <div className="p-8 text-gray-500">Loading...</div>

  return (
    <div className="p-8 max-w-4xl">
      <div className="flex items-center justify-between mb-6">
        <div>
          <h2 className="text-2xl font-bold">User Management</h2>
          <p className="text-gray-500 text-sm">Create, edit, and deactivate user accounts</p>
        </div>
        <button
          onClick={() => setShowCreate(!showCreate)}
          className="flex items-center gap-2 px-4 py-2 bg-brand-600 text-white rounded-lg text-sm font-medium hover:bg-brand-700"
        >
          <UserPlus size={16} />
          Add User
        </button>
      </div>

      {showCreate && (
        <div className="bg-white rounded-xl border border-gray-200 p-6 mb-6">
          <h3 className="font-semibold mb-4">Create New User</h3>
          <form onSubmit={handleCreate} className="flex flex-wrap gap-3 items-end">
            <div className="flex-1 min-w-[200px]">
              <label className="block text-sm font-medium text-gray-700 mb-1">Email</label>
              <input
                type="email"
                value={newEmail}
                onChange={(e) => setNewEmail(e.target.value)}
                required
                className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm focus:ring-2 focus:ring-brand-500 outline-none"
              />
            </div>
            <div className="flex-1 min-w-[150px]">
              <label className="block text-sm font-medium text-gray-700 mb-1">Password</label>
              <input
                type="password"
                value={newPassword}
                onChange={(e) => setNewPassword(e.target.value)}
                required
                minLength={6}
                className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm focus:ring-2 focus:ring-brand-500 outline-none"
              />
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">Role</label>
              <select
                value={newRole}
                onChange={(e) => setNewRole(e.target.value)}
                className="border border-gray-300 rounded-lg px-3 py-2 text-sm focus:ring-2 focus:ring-brand-500 outline-none"
              >
                <option value="user">User</option>
                <option value="admin">Admin</option>
              </select>
            </div>
            <button type="submit" className="px-4 py-2 bg-brand-600 text-white rounded-lg text-sm hover:bg-brand-700">
              Create
            </button>
          </form>
        </div>
      )}

      <div className="bg-white rounded-xl border border-gray-200 overflow-hidden">
        <table className="w-full text-sm">
          <thead className="bg-gray-50 border-b border-gray-200">
            <tr className="text-left text-gray-500">
              <th className="px-4 py-3 font-medium">Email</th>
              <th className="px-4 py-3 font-medium">Role</th>
              <th className="px-4 py-3 font-medium">Status</th>
              <th className="px-4 py-3 font-medium">Created</th>
              <th className="px-4 py-3 font-medium">Actions</th>
            </tr>
          </thead>
          <tbody>
            {users.map((u) => (
              <tr key={u.id} className="border-b border-gray-100 hover:bg-gray-50">
                <td className="px-4 py-3">{u.email}</td>
                <td className="px-4 py-3">
                  <select
                    value={u.role}
                    onChange={(e) => handleRoleChange(u.id, e.target.value)}
                    className="text-sm border border-gray-300 rounded px-2 py-1"
                  >
                    <option value="admin">Admin</option>
                    <option value="user">User</option>
                  </select>
                </td>
                <td className="px-4 py-3">
                  <button
                    onClick={() => handleToggleActive(u.id, u.active)}
                    className={`text-xs px-2 py-1 rounded-full font-medium ${
                      u.active ? 'bg-green-100 text-green-800' : 'bg-red-100 text-red-800'
                    }`}
                  >
                    {u.active ? 'Active' : 'Inactive'}
                  </button>
                </td>
                <td className="px-4 py-3 text-gray-500">{new Date(u.created_at).toLocaleDateString()}</td>
                <td className="px-4 py-3">
                  <button
                    onClick={() => handleDelete(u.id)}
                    className="text-red-600 hover:text-red-800"
                    title="Delete user"
                  >
                    <Trash2 size={16} />
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  )
}