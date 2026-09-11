import React from "react";
import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { BrowserRouter } from "react-router-dom";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { DashboardPage } from "@/pages/dashboard/DashboardPage";
import { apiClient } from "@/services/api";
import { useAuthStore } from "@/stores/authStore";

vi.mock("@/services/api", () => ({
  apiClient: {
    get: vi.fn(),
  },
}));

// Mock ResponsiveContainer for Recharts in jsdom
vi.mock("recharts", async () => {
  const original = await vi.importActual("recharts");
  return {
    ...original,
    ResponsiveContainer: ({ children }: { children: React.ReactNode }) => (
      <div style={{ width: 500, height: 300 }}>{children}</div>
    ),
  };
});

const mockSummary = {
  total_scans: 85,
  compliant_scans: 68,
  non_compliant_scans: 12,
  needs_review_scans: 5,
  compliance_rate: 80.0,
  avg_compliance_score: 79.5,
  pending_reviews: 4,
  total_violations: 28,
  critical_violations: 9,
  scans_comparison_pct: 12.5,
};

const mockViolationsByRule = [
  {
    rule_code: "LMPC-R9-1",
    rule_title: "MRP Statutory Formatting",
    citation: "Rule 9(1), LMPC Rules 2011",
    severity: "critical",
    count: 14,
  },
];

const mockSeverity = [
  { severity: "critical", count: 9, percentage: 32.1 },
  { severity: "major", count: 12, percentage: 42.9 },
  { severity: "minor", count: 5, percentage: 17.9 },
  { severity: "advisory", count: 2, percentage: 7.1 },
];

const mockTrend = [
  {
    date: "2026-09-01",
    total_scans: 10,
    compliant_scans: 8,
    non_compliant_scans: 2,
    compliance_rate: 80.0,
    avg_score: 82.0,
  },
];

const mockDistricts = [
  {
    district: "North Delhi",
    state: "Delhi",
    total_scans: 42,
    compliant_scans: 35,
    compliance_rate: 83.3,
    critical_violations: 4,
    last_activity: "2026-09-11T12:00:00Z",
  },
];

describe("DashboardPage Component", () => {
  let queryClient: QueryClient;

  beforeEach(() => {
    vi.clearAllMocks();
    queryClient = new QueryClient({
      defaultOptions: { queries: { retry: false } },
    });

    useAuthStore.setState({
      user: {
        id: "insp-1",
        name: "Officer Sharma",
        email: "inspector@legalmetro.gov.in",
        role: "inspector",
        is_active: true,
        created_at: "2026-09-11T00:00:00Z",
      },
      accessToken: "valid-jwt",
    });

    (apiClient.get as any).mockImplementation((url: string) => {
      if (url.includes("/summary")) return Promise.resolve({ data: mockSummary });
      if (url.includes("/violations/by-rule")) return Promise.resolve({ data: mockViolationsByRule });
      if (url.includes("/violations/by-severity")) return Promise.resolve({ data: mockSeverity });
      if (url.includes("/compliance/trend")) return Promise.resolve({ data: mockTrend });
      if (url.includes("/districts")) return Promise.resolve({ data: mockDistricts });
      return Promise.resolve({ data: {} });
    });
  });

  it("renders KPI stat tiles and district breakdown correctly", async () => {
    render(
      <QueryClientProvider client={queryClient}>
        <BrowserRouter>
          <DashboardPage />
        </BrowserRouter>
      </QueryClientProvider>
    );

    expect(screen.getByText("Compliance Analytics Dashboard")).toBeInTheDocument();

    await waitFor(() => {
      expect(screen.getByText("85")).toBeInTheDocument(); // total scans
      expect(screen.getByText("80%")).toBeInTheDocument(); // compliance rate
      expect(screen.getByText("79.5 / 100")).toBeInTheDocument(); // avg score
      expect(screen.getByText("North Delhi")).toBeInTheDocument(); // district
    });
  });

  it("allows switching time ranges and requests updated metrics", async () => {
    render(
      <QueryClientProvider client={queryClient}>
        <BrowserRouter>
          <DashboardPage />
        </BrowserRouter>
      </QueryClientProvider>
    );

    await waitFor(() => {
      expect(screen.getByText("30 Days")).toBeInTheDocument();
    });

    const btn7d = screen.getByText("7 Days");
    fireEvent.click(btn7d);

    await waitFor(() => {
      expect(apiClient.get).toHaveBeenCalledWith(expect.stringContaining("range=7d"));
    });
  });
});
