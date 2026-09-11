import React from "react";
import { Link, Outlet, useNavigate } from "react-router-dom";
import { ShieldCheck, LogOut, Package, AlertTriangle, FileText, LayoutDashboard } from "lucide-react";
import { useAuthStore } from "@/stores/authStore";

export const RootLayout: React.FC = () => {
  const { user, isAuthenticated, logout } = useAuthStore();
  const navigate = useNavigate();

  const handleLogout = () => {
    logout();
    navigate("/login");
  };

  return (
    <div className="min-h-screen flex flex-col bg-slate-50 text-slate-900">
      {/* Top Gov Header */}
      <div className="bg-slate-900 text-slate-200 text-xs px-6 py-1.5 flex justify-between items-center border-b border-slate-800">
        <div className="flex items-center gap-2">
          <span className="font-semibold tracking-wide">GOVERNMENT OF INDIA</span>
          <span className="text-slate-500">|</span>
          <span className="text-slate-300">Department of Consumer Affairs (DoCA)</span>
        </div>
        <div className="flex items-center gap-4 text-[11px]">
          <span>Legal Metrology (Packaged Commodities) Rules, 2011</span>
        </div>
      </div>

      {/* Main Navigation Bar */}
      <header className="bg-white border-b border-slate-200 shadow-sm sticky top-0 z-50">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 h-16 flex justify-between items-center">
          <div className="flex items-center gap-6">
            <Link to="/" className="flex items-center gap-2.5">
              <div className="bg-blue-600 text-white p-1.5 rounded-lg shadow-sm">
                <ShieldCheck className="w-6 h-6" />
              </div>
              <div>
                <span className="font-bold text-lg text-slate-900 leading-tight block">
                  LegalMetro<span className="text-blue-600">Shield</span>
                </span>
                <span className="text-[10px] uppercase font-semibold text-slate-500 tracking-wider block">
                  Compliance Verification Portal
                </span>
              </div>
            </Link>

            {isAuthenticated && (
              <nav className="hidden md:flex items-center gap-1 pl-6 border-l border-slate-200">
                <Link
                  to="/dashboard"
                  className="flex items-center gap-1.5 px-3 py-2 text-sm font-medium text-slate-700 hover:text-blue-600 rounded-md hover:bg-slate-100 transition-colors"
                >
                  <LayoutDashboard className="w-4 h-4" />
                  Dashboard
                </Link>
                <Link
                  to="/scans"
                  className="flex items-center gap-1.5 px-3 py-2 text-sm font-medium text-slate-700 hover:text-blue-600 rounded-md hover:bg-slate-100 transition-colors"
                >
                  <Package className="w-4 h-4" />
                  Scans
                </Link>
                <Link
                  to="/violations"
                  className="flex items-center gap-1.5 px-3 py-2 text-sm font-medium text-slate-700 hover:text-blue-600 rounded-md hover:bg-slate-100 transition-colors"
                >
                  <AlertTriangle className="w-4 h-4" />
                  Violations
                </Link>
                <Link
                  to="/reports"
                  className="flex items-center gap-1.5 px-3 py-2 text-sm font-medium text-slate-700 hover:text-blue-600 rounded-md hover:bg-slate-100 transition-colors"
                >
                  <FileText className="w-4 h-4" />
                  Reports
                </Link>
              </nav>
            )}
          </div>

          <div className="flex items-center gap-4">
            {isAuthenticated && user ? (
              <div className="flex items-center gap-3">
                <div className="text-right hidden sm:block">
                  <div className="text-xs font-bold text-slate-800">{user.name}</div>
                  <div className="text-[10px] text-slate-500 uppercase tracking-wide">
                    {user.role} &bull; {user.district || "HQ"}
                  </div>
                </div>
                <button
                  onClick={handleLogout}
                  className="p-2 text-slate-500 hover:text-red-600 hover:bg-red-50 rounded-md transition-colors"
                  title="Logout"
                >
                  <LogOut className="w-4 h-4" />
                </button>
              </div>
            ) : (
              <Link
                to="/login"
                className="text-sm font-medium text-blue-600 hover:text-blue-700 hover:underline"
              >
                Sign In
              </Link>
            )}
          </div>
        </div>
      </header>

      {/* Main Content Viewport */}
      <main className="flex-1 max-w-7xl w-full mx-auto px-4 sm:px-6 lg:px-8 py-8">
        <Outlet />
      </main>

      {/* Footer */}
      <footer className="bg-white border-t border-slate-200 py-6 text-center text-xs text-slate-500">
        <p>LegalMetro Shield &copy; 2026. Department of Consumer Affairs. For Official Enforcement Use Only.</p>
      </footer>
    </div>
  );
};
