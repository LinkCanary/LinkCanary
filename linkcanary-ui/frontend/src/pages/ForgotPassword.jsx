import { useState } from 'react';
import { Link } from 'react-router-dom';
import { forgotPassword } from '../services/auth';

export default function ForgotPassword() {
  const [email, setEmail] = useState('');
  const [sent, setSent] = useState(false);
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError('');
    setLoading(true);
    try {
      await forgotPassword(email);
      setSent(true);
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  if (sent) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-gray-50 dark:bg-[#1a1f2e] px-4">
        <div className="w-full max-w-md text-center">
          <div className="bg-white dark:bg-[#232a3b] rounded-2xl shadow-lg p-8">
            <div className="text-4xl mb-4">✉️</div>
            <h2 className="text-2xl font-bold text-[#2B3A4A] dark:text-white mb-2">Check your email</h2>
            <p className="text-gray-500 dark:text-gray-400 mb-6">
              We sent a password reset link to <strong>{email}</strong>. It expires in 1 hour.
            </p>
            <Link to="/login" className="text-[#F5B800] hover:underline font-medium">Back to login</Link>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen flex items-center justify-center bg-gray-50 dark:bg-[#1a1f2e] px-4">
      <div className="w-full max-w-md">
        <div className="text-center mb-8">
          <h1 className="text-3xl font-bold text-[#2B3A4A] dark:text-white">Reset your password</h1>
          <p className="mt-2 text-gray-500 dark:text-gray-400">Enter your email and we'll send you a reset link</p>
        </div>

        <div className="bg-white dark:bg-[#232a3b] rounded-2xl shadow-lg p-8">
          {error && (
            <div className="mb-4 p-3 bg-red-50 dark:bg-red-900/20 border border-red-200 dark:border-red-800 rounded-lg text-red-600 dark:text-red-400 text-sm">
              {error}
            </div>
          )}

          <form onSubmit={handleSubmit} className="space-y-4">
            <div>
              <label className="block text-sm font-medium text-[#2B3A4A] dark:text-gray-300 mb-1">Email</label>
              <input
                type="email"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                placeholder="you@example.com"
                required
                className="w-full px-4 py-3 border border-gray-200 dark:border-gray-600 rounded-xl bg-white dark:bg-[#1a1f2e] text-[#2B3A4A] dark:text-white focus:ring-2 focus:ring-[#F5B800] focus:border-transparent outline-none transition-all"
              />
            </div>
            <button
              type="submit"
              disabled={loading}
              className="w-full py-3 bg-[#F5B800] hover:bg-[#e0a800] disabled:opacity-50 text-[#2B3A4A] font-bold rounded-xl transition-colors"
            >
              {loading ? 'Sending...' : 'Send reset link'}
            </button>
          </form>

          <p className="mt-6 text-center text-sm text-gray-500 dark:text-gray-400">
            Remember your password?{' '}
            <Link to="/login" className="text-[#F5B800] hover:underline font-medium">Log in</Link>
          </p>
        </div>
      </div>
    </div>
  );
}
