import { createBrowserRouter, Navigate } from "react-router-dom";
import { RootLayout } from "@/app/layouts/RootLayout";
import { ProtectedRoute } from "@/app/guards/ProtectedRoute";
import { LoginPage } from "@/pages/auth/LoginPage";
import { RegisterPage } from "@/pages/auth/RegisterPage";
import { DashboardPage } from "@/pages/dashboard/DashboardPage";

export const router = createBrowserRouter([
  {
    path: "/",
    element: <RootLayout />,
    children: [
      {
        index: true,
        element: <Navigate to="/dashboard" replace />,
      },
      {
        path: "login",
        element: <LoginPage />,
      },
      {
        path: "register",
        element: <RegisterPage />,
      },
      {
        path: "dashboard",
        element: (
          <ProtectedRoute>
            <DashboardPage />
          </ProtectedRoute>
        ),
      },
      {
        path: "scans",
        element: (
          <ProtectedRoute>
            <div className="bg-white p-8 rounded-xl border border-slate-200">
              <h2 className="text-xl font-bold">Scans Repository</h2>
              <p className="text-slate-500 text-sm mt-1">
                Scan listing and ingestion pipelines (Phase 2).
              </p>
            </div>
          </ProtectedRoute>
        ),
      },
      {
        path: "violations",
        element: (
          <ProtectedRoute>
            <div className="bg-white p-8 rounded-xl border border-slate-200">
              <h2 className="text-xl font-bold">Violations Explorer</h2>
              <p className="text-slate-500 text-sm mt-1">
                Cross-scan violation search and filters (Phase 3).
              </p>
            </div>
          </ProtectedRoute>
        ),
      },
      {
        path: "reports",
        element: (
          <ProtectedRoute>
            <div className="bg-white p-8 rounded-xl border border-slate-200">
              <h2 className="text-xl font-bold">Generated Compliance Reports</h2>
              <p className="text-slate-500 text-sm mt-1">
                Downloadable PDF and DOCX reports (Phase 3).
              </p>
            </div>
          </ProtectedRoute>
        ),
      },
      {
        path: "admin/users",
        element: (
          <ProtectedRoute allowedRoles={["admin"]}>
            <div className="bg-white p-8 rounded-xl border border-slate-200">
              <h2 className="text-xl font-bold">User Management (Admin)</h2>
              <p className="text-slate-500 text-sm mt-1">
                Manage user roles and approve pending viewer accounts.
              </p>
            </div>
          </ProtectedRoute>
        ),
      },
    ],
  },
]);
