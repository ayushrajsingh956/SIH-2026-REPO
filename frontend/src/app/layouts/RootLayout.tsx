import React, { useState } from "react";
import { Link, NavLink, Outlet, useNavigate, useLocation } from "react-router-dom";
import {
  ShieldCheck,
  LogOut,
  Package,
  AlertTriangle,
  FileText,
  LayoutDashboard,
  PlusCircle,
  Scale,
  Settings,
  Menu,
  X,
  Boxes,
} from "lucide-react";
import { Badge } from "@/components/ui/Badge";
import { useAuthStore } from "@/stores/authStore";
import { apiClient } from "@/services/api";
import { cn } from "@/lib/utils";
import { PwaInstallBanner } from "@/components/pwa/PwaInstallBanner";
import { OfflineIndicator } from "@/components/pwa/OfflineIndicator";

export const RootLayout: React.FC = () => {
  const { user, isAuthenticated, logout } = useAuthStore();
  const navigate = useNavigate();
  const location = useLocation();

  const [mobileMenuOpen, setMobileMenuOpen] = useState(false);

  const handleLogout = async () => {
    try {
      await apiClient.post("/api/v1/auth/logout");
    } catch {
      // Token may already be invalid; proceed with local cleanup
    }
    logout();
    navigate("/login");
  };

  const navItems = [
    {
      to: "/dashboard",
      label: "Dashboard",
      icon: LayoutDashboard,
      roles: ["admin", "inspector", "viewer"],
    },
    {
      to: "/scans/new",
      label: "New Scan",
      icon: PlusCircle,
      roles: ["admin", "inspector"],
      highlight: true,
    },
    {
      to: "/scans",
      label: "Scans",
      icon: Package,
      roles: ["admin", "inspector", "viewer"],
    },
    {
      to: "/products",
      label: "Products",
      icon: Boxes,
      roles: ["admin", "inspector", "viewer"],
    },
    {
      to: "/violations",
      label: "Violations",
      icon: AlertTriangle,
      roles: ["admin", "inspector", "viewer"],
    },
    {
      to: "/reports",
      label: "Reports",
      icon: FileText,
      roles: ["admin", "inspector", "viewer"],
    },
    {
      to: "/rules",
      label: "Rules",
      icon: Scale,
      roles: ["admin", "inspector", "viewer"],
    },
    {
      to: "/admin/users",
      label: "Admin",
      icon: Settings,
      roles: ["admin"],
    },
  ];

  const filteredNavItems = navItems.filter(
    (item) => !user || item.roles.includes(user.role)
  );

  return (
    <div className="min-h-screen flex flex-col bg-slate-100 text-slate-900 font-sans antialiased">
      {/* 1. Official National Gov Header Bar */}
      <header className="bg-slate-950 text-slate-300 text-xs px-4 sm:px-6 py-1.5 flex justify-between items-center border-b border-slate-800 z-50">
        <div className="flex items-center gap-2">
          <span className="font-semibold tracking-wider text-slate-200">
            GOVERNMENT OF INDIA
          </span>
          <span className="text-slate-600">|</span>
          <span className="hidden sm:inline text-slate-400">
            Ministry of Consumer Affairs &bull; DoCA
          </span>
        </div>
        <div className="flex items-center gap-3 text-[11px] text-slate-400">
          <span className="hidden md:inline">
            Legal Metrology (Packaged Commodities) Rules, 2011
          </span>
          <span className="font-mono text-[10px] bg-slate-800 px-1.5 py-0.5 rounded text-slate-300">
            PS ID 26034
          </span>
        </div>
      </header>

      {/* PWA Mobile Install Banner */}
      <PwaInstallBanner />

      {/* Top Application Bar */}
      <div className="bg-white border-b border-slate-200 sticky top-0 z-40 shadow-xs">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 h-15 flex justify-between items-center">
          <div className="flex items-center gap-4">
            {/* Mobile menu hamburger toggle */}
            {isAuthenticated && (
              <button
                type="button"
                onClick={() => setMobileMenuOpen(!mobileMenuOpen)}
                className="p-1.5 rounded-lg text-slate-500 hover:text-slate-800 hover:bg-slate-100 lg:hidden focus:outline-none"
                aria-label="Toggle navigation"
              >
                {mobileMenuOpen ? <X className="w-5 h-5" /> : <Menu className="w-5 h-5" />}
              </button>
            )}

            <Link to="/" className="flex items-center gap-2.5">
              <div className="bg-blue-600 text-white p-1.5 rounded-lg shadow-xs flex-shrink-0">
                <ShieldCheck className="w-5 h-5" />
              </div>
              <div>
                <span className="font-bold text-base text-slate-900 tracking-tight leading-tight block">
                  LegalMetro<span className="text-blue-600">Shield</span>
                </span>
                <span className="text-[10px] uppercase font-semibold text-slate-500 tracking-wider block">
                  Enforcement Portal
                </span>
              </div>
            </Link>
          </div>

          {/* User Profile & Actions */}
          <div className="flex items-center gap-3">
            {/* Offline Connectivity & Outbox Sync Indicator */}
            <OfflineIndicator />

            {isAuthenticated && user ? (
              <div className="flex items-center gap-3">
                <div className="text-right hidden sm:block">
                  <div className="flex items-center gap-2 justify-end">
                    <span className="text-xs font-bold text-slate-800">{user.name}</span>
                    <Badge variant={user.role} size="sm">
                      {user.role.toUpperCase()}
                    </Badge>
                  </div>
                  <div className="text-[10px] text-slate-500">
                    {user.district ? `${user.district}, ${user.state || ""}` : "National Enforcement Cell"}
                  </div>
                </div>

                <button
                  type="button"
                  onClick={() => void handleLogout()}
                  className="p-2 text-slate-500 hover:text-rose-600 hover:bg-rose-50 rounded-lg transition-colors"
                  title="Logout"
                  aria-label="Logout"
                >
                  <LogOut className="w-4 h-4" />
                </button>
              </div>
            ) : (
              <Link
                to="/login"
                className="text-xs font-semibold text-blue-600 hover:text-blue-700 bg-blue-50 px-3 py-1.5 rounded-lg border border-blue-200 transition-colors"
              >
                Officer Sign In
              </Link>
            )}
          </div>
        </div>
      </div>

      {/* Main Workspace with Responsive Sidebar */}
      <div className="flex-1 flex w-full max-w-7xl mx-auto px-2 sm:px-4 lg:px-8 py-4 sm:py-6 gap-6">
        {/* Left Sidebar Nav (Desktop & Tablet) */}
        {isAuthenticated && (
          <aside
            className={cn(
              "flex-shrink-0 transition-all duration-200 z-30",
              // Desktop: 220px; Large Tablet: 64px icon rail; Mobile: offcanvas drawer
              "hidden lg:block w-56",
              "md:block md:w-16 lg:w-56"
            )}
          >
            <div className="sticky top-20 bg-white rounded-xl border border-slate-200/90 shadow-xs p-2 space-y-1">
              {filteredNavItems.map((item) => {
                const Icon = item.icon;
                const isActive =
                  item.to === "/dashboard"
                    ? location.pathname === "/dashboard"
                    : location.pathname.startsWith(item.to);

                return (
                  <NavLink
                    key={item.to}
                    to={item.to}
                    className={cn(
                      "flex items-center gap-3 px-3 py-2.5 rounded-lg text-xs font-semibold transition-all group",
                      isActive
                        ? "bg-blue-50 text-blue-700 font-bold border-l-3 border-blue-600 shadow-xs"
                        : "text-slate-600 hover:text-slate-900 hover:bg-slate-50",
                      item.highlight && !isActive
                        ? "text-blue-600 bg-blue-50/50 hover:bg-blue-50"
                        : ""
                    )}
                    title={item.label}
                  >
                    <Icon
                      className={cn(
                        "w-4 h-4 flex-shrink-0 transition-colors",
                        isActive ? "text-blue-600" : "text-slate-400 group-hover:text-slate-700"
                      )}
                    />
                    <span className="truncate md:hidden lg:inline">{item.label}</span>
                  </NavLink>
                );
              })}
            </div>
          </aside>
        )}

        {/* Mobile Slide-over Drawer */}
        {isAuthenticated && mobileMenuOpen && (
          <div
            className="fixed inset-0 z-50 bg-slate-900/60 backdrop-blur-xs lg:hidden"
            onClick={() => setMobileMenuOpen(false)}
          >
            <div
              className="w-64 h-full bg-white p-4 shadow-xl flex flex-col justify-between"
              onClick={(e) => e.stopPropagation()}
            >
              <div className="space-y-4">
                <div className="flex items-center justify-between pb-3 border-b border-slate-100">
                  <div className="flex items-center gap-2">
                    <ShieldCheck className="w-5 h-5 text-blue-600" />
                    <span className="font-bold text-sm text-slate-800">Navigation</span>
                  </div>
                  <button
                    onClick={() => setMobileMenuOpen(false)}
                    className="p-1 text-slate-400 hover:text-slate-600 rounded-md"
                  >
                    <X className="w-5 h-5" />
                  </button>
                </div>

                <nav className="space-y-1">
                  {filteredNavItems.map((item) => {
                    const Icon = item.icon;
                    const isActive = location.pathname.startsWith(item.to);

                    return (
                      <Link
                        key={item.to}
                        to={item.to}
                        onClick={() => setMobileMenuOpen(false)}
                        className={cn(
                          "flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm font-semibold transition-colors",
                          isActive
                            ? "bg-blue-50 text-blue-700"
                            : "text-slate-700 hover:bg-slate-50"
                        )}
                      >
                        <Icon className={cn("w-4 h-4", isActive ? "text-blue-600" : "text-slate-400")} />
                        <span>{item.label}</span>
                      </Link>
                    );
                  })}
                </nav>
              </div>

              {/* Mobile Drawer Footer User info */}
              {user && (
                <div className="pt-4 border-t border-slate-100 flex items-center justify-between">
                  <div>
                    <div className="text-xs font-bold text-slate-900">{user.name}</div>
                    <div className="text-[10px] text-slate-500 uppercase">{user.role}</div>
                  </div>
                  <button
                    type="button"
                    onClick={() => void handleLogout()}
                    className="p-2 text-rose-600 hover:bg-rose-50 rounded-lg"
                    title="Logout"
                  >
                    <LogOut className="w-4 h-4" />
                  </button>
                </div>
              )}
            </div>
          </div>
        )}

        {/* Center Content Viewport */}
        <main className="flex-1 min-w-0 pb-16 md:pb-8">
          {location.pathname.startsWith("/admin") && (
            <div className="flex items-center gap-2 mb-4 bg-white p-1.5 rounded-xl border border-slate-200 shadow-xs overflow-x-auto text-xs font-semibold">
              <NavLink
                to="/admin/users"
                className={({ isActive }) =>
                  cn(
                    "px-3.5 py-1.5 rounded-lg transition-colors",
                    isActive
                      ? "bg-blue-50 text-blue-700 font-bold border border-blue-200"
                      : "text-slate-600 hover:text-slate-900 hover:bg-slate-50"
                  )
                }
              >
                Officers &amp; Users
              </NavLink>
              <NavLink
                to="/admin/audit-log"
                className={({ isActive }) =>
                  cn(
                    "px-3.5 py-1.5 rounded-lg transition-colors",
                    isActive
                      ? "bg-blue-50 text-blue-700 font-bold border border-blue-200"
                      : "text-slate-600 hover:text-slate-900 hover:bg-slate-50"
                  )
                }
              >
                Audit Trail
              </NavLink>
              <NavLink
                to="/admin/rules"
                className={({ isActive }) =>
                  cn(
                    "px-3.5 py-1.5 rounded-lg transition-colors",
                    isActive
                      ? "bg-blue-50 text-blue-700 font-bold border border-blue-200"
                      : "text-slate-600 hover:text-slate-900 hover:bg-slate-50"
                  )
                }
              >
                Rules Engine Config
              </NavLink>
            </div>
          )}
          <Outlet />
        </main>
      </div>

      {/* Bottom Safe Bar on Tablet/Mobile Field View */}
      {isAuthenticated && (
        <nav
          aria-label="Field navigation"
          className="lg:hidden fixed bottom-0 left-0 right-0 z-40 bg-white/95 backdrop-blur-sm border-t border-slate-200 px-3 py-1.5 flex justify-around items-center shadow-lg"
        >
          <NavLink
            to="/dashboard"
            className={({ isActive }) =>
              cn(
                "flex flex-col items-center py-1 px-3 text-[10px] font-semibold transition-colors",
                isActive ? "text-blue-600" : "text-slate-500 hover:text-slate-800"
              )
            }
          >
            <LayoutDashboard className="w-4 h-4 mb-0.5" />
            <span>Dashboard</span>
          </NavLink>

          {user && ["admin", "inspector"].includes(user.role) && (
            <NavLink
              to="/scans/new"
              className={({ isActive }) =>
                cn(
                  "flex flex-col items-center py-1 px-3 text-[10px] font-semibold transition-colors",
                  isActive ? "text-blue-600" : "text-slate-500 hover:text-slate-800"
                )
              }
            >
              <PlusCircle className="w-4 h-4 mb-0.5 text-blue-600" />
              <span>New Scan</span>
            </NavLink>
          )}

          <NavLink
            to="/scans"
            className={({ isActive }) =>
              cn(
                "flex flex-col items-center py-1 px-3 text-[10px] font-semibold transition-colors",
                isActive ? "text-blue-600" : "text-slate-500 hover:text-slate-800"
              )
            }
          >
            <Package className="w-4 h-4 mb-0.5" />
            <span>Scans</span>
          </NavLink>

          <NavLink
            to="/violations"
            className={({ isActive }) =>
              cn(
                "flex flex-col items-center py-1 px-3 text-[10px] font-semibold transition-colors",
                isActive ? "text-blue-600" : "text-slate-500 hover:text-slate-800"
              )
            }
          >
            <AlertTriangle className="w-4 h-4 mb-0.5" />
            <span>Violations</span>
          </NavLink>
        </nav>
      )}

      {/* Footer */}
      <footer className="bg-white border-t border-slate-200 py-4 px-6 text-center text-xs text-slate-500 mt-auto">
        <p>
          LegalMetro Shield &copy; 2026. Ministry of Consumer Affairs, Food & Public Distribution / DoCA. For Official Enforcement Use Only.
        </p>
      </footer>
    </div>
  );
};
