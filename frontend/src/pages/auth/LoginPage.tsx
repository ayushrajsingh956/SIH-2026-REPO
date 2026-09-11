import React, { useState } from "react";
import { useNavigate, useLocation } from "react-router-dom";
import { ShieldCheck, Lock, Mail, ArrowRight } from "lucide-react";
import { useAuthStore } from "@/stores/authStore";

export const LoginPage: React.FC = () => {
  const [email, setEmail] = useState("inspector.doca@nic.in");
  const [password, setPassword] = useState("password123");
  const [role, setRole] = useState<"inspector" | "admin" | "viewer">("inspector");
  const { login } = useAuthStore();
  const navigate = useNavigate();
  const location = useLocation();

  const from = (location.state as any)?.from?.pathname || "/dashboard";

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    login(
      {
        accessToken: "dev-mock-access-token",
        refreshToken: "dev-mock-refresh-token",
      },
      {
        id: "00000000-0000-0000-0000-000000000001",
        name: role === "admin" ? "Admin Officer" : "Inspector Sharma",
        email,
        role,
        district: "New Delhi",
        state: "Delhi",
      }
    );
    navigate(from, { replace: true });
  };

  return (
    <div className="min-h-[70vh] flex flex-col justify-center items-center">
      <div className="w-full max-w-md bg-white border border-slate-200 rounded-xl shadow-sm p-8">
        <div className="text-center mb-8">
          <div className="inline-flex bg-blue-50 p-3 rounded-xl mb-3 text-blue-600">
            <ShieldCheck className="w-8 h-8" />
          </div>
          <h1 className="text-xl font-bold text-slate-900">Enforcement Portal Login</h1>
          <p className="text-xs text-slate-500 mt-1">
            Sign in with your official departmental credentials
          </p>
        </div>

        <form onSubmit={handleSubmit} className="space-y-4">
          <div>
            <label className="block text-xs font-semibold text-slate-700 mb-1">
              Official Email Address
            </label>
            <div className="relative">
              <Mail className="w-4 h-4 text-slate-400 absolute left-3 top-3" />
              <input
                type="email"
                required
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                className="w-full pl-9 pr-3 py-2 text-sm border border-slate-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500"
                placeholder="officer@nic.in"
              />
            </div>
          </div>

          <div>
            <label className="block text-xs font-semibold text-slate-700 mb-1">
              Password
            </label>
            <div className="relative">
              <Lock className="w-4 h-4 text-slate-400 absolute left-3 top-3" />
              <input
                type="password"
                required
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                className="w-full pl-9 pr-3 py-2 text-sm border border-slate-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500"
                placeholder="••••••••"
              />
            </div>
          </div>

          <div>
            <label className="block text-xs font-semibold text-slate-700 mb-1">
              Select Role (Development Mode)
            </label>
            <select
              value={role}
              onChange={(e) => setRole(e.target.value as any)}
              className="w-full px-3 py-2 text-sm border border-slate-300 rounded-lg bg-white focus:outline-none focus:ring-2 focus:ring-blue-500"
            >
              <option value="inspector">Enforcement Inspector</option>
              <option value="admin">Super Admin</option>
              <option value="viewer">Analyst / Viewer</option>
            </select>
          </div>

          <button
            type="submit"
            className="w-full mt-4 flex items-center justify-center gap-2 py-2.5 px-4 bg-blue-600 hover:bg-blue-700 text-white text-sm font-semibold rounded-lg shadow transition-colors"
          >
            <span>Proceed to Dashboard</span>
            <ArrowRight className="w-4 h-4" />
          </button>
        </form>

        <div className="mt-6 pt-4 border-t border-slate-100 text-center text-xs text-slate-400">
          Authorized personnel only. All access is logged for audit compliance.
        </div>
      </div>
    </div>
  );
};
