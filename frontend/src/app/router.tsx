import { createBrowserRouter, Navigate } from "react-router-dom";
import { RootLayout } from "@/app/layouts/RootLayout";
import { ProtectedRoute } from "@/app/guards/ProtectedRoute";
import { LoginPage } from "@/pages/auth/LoginPage";
import { RegisterPage } from "@/pages/auth/RegisterPage";
import { DashboardPage } from "@/pages/dashboard/DashboardPage";
import { NewScanPage } from "@/pages/scans/NewScanPage";
import { ScanDetailPage } from "@/pages/scans/ScanDetailPage";
import { ScansListPage } from "@/pages/scans/ScansListPage";
import { ProductsPage } from "@/pages/products/ProductsPage";
import { ProductDetailPage } from "@/pages/products/ProductDetailPage";
import { ViolationsExplorerPage } from "@/pages/violations/ViolationsExplorerPage";
import { RulesExplorerPage } from "@/pages/rules/RulesExplorerPage";
import { ReportsPage } from "@/pages/reports/ReportsPage";
import { UsersManagementPage } from "@/pages/admin/UsersManagementPage";
import { AuditLogPage } from "@/pages/admin/AuditLogPage";
import { RuleConfigPage } from "@/pages/admin/RuleConfigPage";

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
            <ScansListPage />
          </ProtectedRoute>
        ),
      },
      {
        path: "scans/new",
        element: (
          <ProtectedRoute allowedRoles={["admin", "inspector"]}>
            <NewScanPage />
          </ProtectedRoute>
        ),
      },
      {
        path: "scans/:id",
        element: (
          <ProtectedRoute>
            <ScanDetailPage />
          </ProtectedRoute>
        ),
      },
      {
        path: "products",
        element: (
          <ProtectedRoute>
            <ProductsPage />
          </ProtectedRoute>
        ),
      },
      {
        path: "products/:id",
        element: (
          <ProtectedRoute>
            <ProductDetailPage />
          </ProtectedRoute>
        ),
      },
      {
        path: "violations",
        element: (
          <ProtectedRoute>
            <ViolationsExplorerPage />
          </ProtectedRoute>
        ),
      },
      {
        path: "reports",
        element: (
          <ProtectedRoute>
            <ReportsPage />
          </ProtectedRoute>
        ),
      },
      {
        path: "rules",
        element: (
          <ProtectedRoute>
            <RulesExplorerPage />
          </ProtectedRoute>
        ),
      },
      {
        path: "admin",
        element: <Navigate to="/admin/users" replace />,
      },
      {
        path: "admin/users",
        element: (
          <ProtectedRoute allowedRoles={["admin"]}>
            <UsersManagementPage />
          </ProtectedRoute>
        ),
      },
      {
        path: "admin/audit-log",
        element: (
          <ProtectedRoute allowedRoles={["admin"]}>
            <AuditLogPage />
          </ProtectedRoute>
        ),
      },
      {
        path: "admin/rules",
        element: (
          <ProtectedRoute allowedRoles={["admin"]}>
            <RuleConfigPage />
          </ProtectedRoute>
        ),
      },
    ],
  },
]);
