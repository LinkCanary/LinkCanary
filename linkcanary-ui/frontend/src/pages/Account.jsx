import { useState, useEffect } from 'react';
import { Link } from 'react-router-dom';

export default function Account() {
  const [account, setAccount] = useState(null);
  const [members, setMembers] = useState([]);
  const [loading, setLoading] = useState(true);
  const [orgName, setOrgName] = useState('');
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    Promise.all([
      fetch('/api/account/me', { credentials: 'include' }).then(r => r.json()),
      fetch('/api/account/members', { credentials: 'include' }).then(r => r.json()),
    ]).then(([me, mems]) => {
      setAccount(me);
      setMembers(mems);
      setOrgName(me.org_name);
      setLoading(false);
    });
  }, []);

  const handleSaveOrg = async () => {
    setSaving(true);
    await fetch('/api/account/org', {
      method: 'PUT',
      credentials: 'include',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ name: orgName }),
    });
    setSaving(false);
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center min-h-[50vh]">
        <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-[#F5B800]" />
      </div>
    );
  }

  return (
    <div className="max-w-3xl mx-auto px-4 py-8">
      <h1 className="text-2xl font-bold text-[#2B3A4A] dark:text-white mb-8">Account</h1>

      {/* Org settings */}
      <section className="bg-white dark:bg-[#232a3b] rounded-2xl shadow-sm border border-gray-100 dark:border-gray-700 p-6 mb-6">
        <h2 className="font-semibold text-[#2B3A4A] dark:text-white mb-4">Organization</h2>
        <div className="space-y-4">
          <div>
            <label className="block text-sm font-medium text-[#2B3A4A] dark:text-gray-300 mb-1">Name</label>
            <div className="flex gap-3">
              <input
                type="text"
                value={orgName}
                onChange={(e) => setOrgName(e.target.value)}
                className="flex-1 px-4 py-2 border border-gray-200 dark:border-gray-600 rounded-xl bg-white dark:bg-[#1a1f2e] text-[#2B3A4A] dark:text-white focus:ring-2 focus:ring-[#F5B800] focus:border-transparent outline-none"
              />
              <button
                onClick={handleSaveOrg}
                disabled={saving}
                className="px-4 py-2 bg-[#F5B800] hover:bg-[#e0a800] disabled:opacity-50 text-[#2B3A4A] font-medium rounded-xl transition-colors"
              >
                {saving ? 'Saving...' : 'Save'}
              </button>
            </div>
          </div>
          <div>
            <label className="block text-sm font-medium text-[#2B3A4A] dark:text-gray-300 mb-1">Slug</label>
            <p className="text-gray-500 dark:text-gray-400 text-sm">{account?.org_slug}</p>
          </div>
          <div>
            <label className="block text-sm font-medium text-[#2B3A4A] dark:text-gray-300 mb-1">Plan</label>
            <div className="flex items-center gap-3">
              <span className="px-3 py-1 bg-[#F5B800]/10 text-[#F5B800] rounded-lg text-sm font-medium capitalize">
                {account?.plan}
              </span>
              <Link to="/account/billing" className="text-sm text-[#F5B800] hover:underline">Manage plan →</Link>
            </div>
          </div>
        </div>
      </section>

      {/* Team members */}
      <section className="bg-white dark:bg-[#232a3b] rounded-2xl shadow-sm border border-gray-100 dark:border-gray-700 p-6 mb-6">
        <div className="flex items-center justify-between mb-4">
          <h2 className="font-semibold text-[#2B3A4A] dark:text-white">Team members</h2>
          {account?.role === 'owner' || account?.role === 'admin' ? (
            <button className="text-sm text-[#F5B800] hover:underline font-medium">Invite member</button>
          ) : null}
        </div>
        <div className="space-y-3">
          {members.map((m) => (
            <div key={m.id} className="flex items-center justify-between py-2 border-b border-gray-50 dark:border-gray-700 last:border-0">
              <div>
                <p className="text-sm font-medium text-[#2B3A4A] dark:text-white">{m.user_id}</p>
                <p className="text-xs text-gray-400">Joined {new Date(m.created_at).toLocaleDateString()}</p>
              </div>
              <span className="px-2 py-1 text-xs font-medium rounded-lg bg-gray-100 dark:bg-gray-700 text-gray-500 dark:text-gray-400 capitalize">
                {m.role}
              </span>
            </div>
          ))}
          {members.length === 0 && (
            <p className="text-sm text-gray-400">No members found</p>
          )}
        </div>
      </section>

      {/* Quick links */}
      <section className="bg-white dark:bg-[#232a3b] rounded-2xl shadow-sm border border-gray-100 dark:border-gray-700 p-6">
        <h2 className="font-semibold text-[#2B3A4A] dark:text-white mb-4">Quick links</h2>
        <div className="space-y-2">
          <Link to="/account/billing" className="block text-sm text-[#2B3A4A] dark:text-gray-300 hover:text-[#F5B800] transition-colors">
            Billing & usage →
          </Link>
          <Link to="/settings" className="block text-sm text-[#2B3A4A] dark:text-gray-300 hover:text-[#F5B800] transition-colors">
            Webhook settings →
          </Link>
          <Link to="/integrations" className="block text-sm text-[#2B3A4A] dark:text-gray-300 hover:text-[#F5B800] transition-colors">
            Integrations →
          </Link>
        </div>
      </section>
    </div>
  );
}
