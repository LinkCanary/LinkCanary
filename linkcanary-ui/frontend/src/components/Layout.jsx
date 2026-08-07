import { useState, useRef, useEffect } from 'react';
import { Link, useLocation } from 'react-router-dom';
import { useTheme } from '../context/ThemeContext';
import { useAuth } from '../context/AuthContext';

const navItems = [
  { path: '/', label: 'Dashboard' },
  { path: '/crawl/new', label: 'New Crawl' },
  { path: '/backlinks', label: 'Backlink Checker' },
  { path: '/url-resolution', label: 'URL Resolution' },
  { path: '/reports', label: 'Reports' },
  { path: '/integrations', label: 'Integrations' },
  { path: '/ci-setup', label: 'CI Setup' },
  { path: '/settings', label: 'Settings' },
];

function ThemeToggle() {
  const { darkMode, toggleDarkMode } = useTheme();
  
  return (
    <button
      onClick={toggleDarkMode}
      className="p-2 rounded-lg text-secondary hover:bg-primary/20 hover:text-primary transition-colors"
      title={darkMode ? 'Switch to light mode' : 'Switch to dark mode'}
    >
      {darkMode ? (
        <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 3v1m0 16v1m9-9h-1M4 12H3m15.364 6.364l-.707-.707M6.343 6.343l-.707-.707m12.728 0l-.707.707M6.343 17.657l-.707.707M16 12a4 4 0 11-8 0 4 4 0 018 0z" />
        </svg>
      ) : (
        <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M20.354 15.354A9 9 0 018.646 3.646 9.003 9.003 0 0012 21a9.003 9.003 0 008.354-5.646z" />
        </svg>
      )}
    </button>
  );
}

export default function Layout({ children }) {
  const location = useLocation();
  
  return (
    <div className="min-h-screen bg-secondary dark:bg-dark transition-colors">
      <header className="bg-dark dark:bg-dark/95 text-primary shadow-lg">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="flex items-center justify-between h-16">
            <Link to="/" className="flex items-center gap-2">
              <svg className="w-8 h-8" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13.828 10.172a4 4 0 00-5.656 0l-4 4a4 4 0 105.656 5.656l1.102-1.101m-.758-4.899a4 4 0 005.656 0l4-4a4 4 0 00-5.656-5.656l-1.1 1.1" />
              </svg>
              <span className="text-xl font-bold">LinkCanary</span>
              <span className="text-xs font-mono font-medium px-1.5 py-0.5 rounded bg-primary/20 text-primary border border-primary/30 leading-none">
                v1.1
              </span>
            </Link>
            
            <div className="flex items-center gap-2">
              <nav className="flex gap-1">
                {navItems.map((item) => (
                  <Link
                    key={item.path}
                    to={item.path}
                    className={`px-4 py-2 rounded-lg text-sm font-medium transition-colors ${
                      location.pathname === item.path
                        ? 'bg-primary text-dark'
                        : 'text-secondary hover:bg-primary/20 hover:text-primary'
                    }`}
                  >
                    {item.label}
                  </Link>
                ))}
              </nav>
              <ThemeToggle />
              <UserMenu />
            </div>
          </div>
        </div>
      </header>
      
      <main className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
        {children}
      </main>
    </div>
  );
}

function UserMenu() {
  const { logout } = useAuth();
  const [open, setOpen] = useState(false);
  const ref = useRef(null);

  useEffect(() => {
    const handler = (e) => { if (ref.current && !ref.current.contains(e.target)) setOpen(false); };
    document.addEventListener('mousedown', handler);
    return () => document.removeEventListener('mousedown', handler);
  }, []);

  return (
    <div className="relative" ref={ref}>
      <button
        onClick={() => setOpen(!open)}
        className="w-8 h-8 rounded-full bg-primary text-dark flex items-center justify-center text-sm font-bold hover:opacity-90 transition-opacity"
      >
        <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M16 7a4 4 0 11-8 0 4 4 0 018 0zM12 14a7 7 0 00-7 7h14a7 7 0 00-7-7z" />
        </svg>
      </button>
      {open && (
        <div className="absolute right-0 mt-2 w-48 bg-white dark:bg-[#232a3b] rounded-xl shadow-lg border border-gray-100 dark:border-gray-700 py-1 z-50">
          <Link to="/account" onClick={() => setOpen(false)} className="block px-4 py-2 text-sm text-[#2B3A4A] dark:text-gray-300 hover:bg-gray-50 dark:hover:bg-[#2a3348]">
            Account
          </Link>
          <Link to="/account/billing" onClick={() => setOpen(false)} className="block px-4 py-2 text-sm text-[#2B3A4A] dark:text-gray-300 hover:bg-gray-50 dark:hover:bg-[#2a3348]">
            Billing
          </Link>
          <hr className="my-1 border-gray-100 dark:border-gray-700" />
          <button onClick={logout} className="w-full text-left px-4 py-2 text-sm text-red-600 dark:text-red-400 hover:bg-gray-50 dark:hover:bg-[#2a3348]">
            Log out
          </button>
        </div>
      )}
    </div>
  );
}
