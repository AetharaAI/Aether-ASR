import { Outlet, Link, useLocation } from 'react-router-dom';
import { Mic, List, Settings, Home, LogOut } from 'lucide-react';
import { useStore } from '../store';

const navItems = [
  { path: '/', label: 'Home', icon: Home },
  { path: '/transcribe', label: 'Transcribe', icon: Mic },
  { path: '/jobs', label: 'Jobs', icon: List },
  { path: '/settings', label: 'Settings', icon: Settings },
];

export default function Layout() {
  const location = useLocation();
  const { setApiKey } = useStore();

  const handleLogout = () => {
    setApiKey(null);
  };

  return (
    <div className="min-h-screen bg-gray-50">
      {/* Sidebar */}
      <aside className="fixed left-0 top-0 h-full w-64 bg-white border-r border-gray-200">
        <div className="p-6">
          <h1 className="text-2xl font-bold text-primary-600">ASR Service</h1>
          <p className="text-sm text-gray-500 mt-1">Speech-to-Text</p>
        </div>

        <nav className="px-4 pb-4">
          {navItems.map((item) => {
            const Icon = item.icon;
            const isActive = location.pathname === item.path;

            return (
              <Link
                key={item.path}
                to={item.path}
                className={`flex items-center gap-3 px-4 py-3 rounded-lg mb-1 transition-colors ${
                  isActive
                    ? 'bg-primary-50 text-primary-700'
                    : 'text-gray-600 hover:bg-gray-50'
                }`}
              >
                <Icon className="w-5 h-5" />
                <span className="font-medium">{item.label}</span>
              </Link>
            );
          })}
        </nav>

        <div className="absolute bottom-0 left-0 right-0 p-4 border-t border-gray-200">
          <button
            onClick={handleLogout}
            className="flex items-center gap-3 px-4 py-3 w-full text-gray-600 hover:bg-gray-50 rounded-lg transition-colors"
          >
            <LogOut className="w-5 h-5" />
            <span className="font-medium">Logout</span>
          </button>
        </div>
      </aside>

      {/* Main content */}
      <main className="ml-64 p-8">
        <Outlet />
      </main>
    </div>
  );
}
