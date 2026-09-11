import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { BrowserRouter } from "react-router-dom";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { ViolationsExplorerPage } from "@/pages/violations/ViolationsExplorerPage";
import { RulesExplorerPage } from "@/pages/rules/RulesExplorerPage";
import { apiClient } from "@/services/api";
import { useAuthStore } from "@/stores/authStore";

vi.mock("@/services/api", () => ({
  apiClient: {
    get: vi.fn(),
    put: vi.fn(),
  },
}));

const mockViolations = {
  total: 1,
  severity_summary: { critical: 1, major: 0, minor: 0, advisory: 0 },
  items: [
    {
      id: "viol-123",
      scan_id: "scan-999",
      rule_code: "LMPC-R9-1",
      rule_title: "Maximum Retail Price (MRP) Statutory Formatting",
      citation: "Rule 9(1), LMPC Rules 2011",
      severity: "critical",
      field_name: "mrp",
      observed_value: "Rs. 250",
      expected_value: "Inclusive of all taxes",
      scanned_at: "2026-09-11T10:00:00Z",
      mode: "retail",
      district: "Central Delhi",
      state: "Delhi",
      product_name: "Royal Herbal",
    },
  ],
};

const mockRules = [
  {
    id: "LMPC-R9-1",
    title: "Maximum Retail Price (MRP) Statutory Formatting",
    citation: "Rule 9(1), LMPC Rules 2011",
    severity: "critical",
    effective_severity: "critical",
    applies_to: ["retail", "ecommerce"],
    check: "mrp_format",
    description_plain: "MRP must include taxes statement and Rupee symbol",
    mandatory: true,
    is_enabled: true,
    trigger_count: 24,
  },
];

const mockRecentScans = [
  {
    scan_id: "scan-999",
    violation_id: "viol-123",
    mode: "retail",
    scanned_at: "2026-09-11T10:00:00Z",
    verdict: "non_compliant",
    observed_value: "Rs. 250",
    expected_value: "Inclusive of all taxes",
    field_name: "mrp",
    overridden: false,
    inspector_name: "Officer Sharma",
    product_name: "Royal Herbal",
  },
];

describe("Violations & Rules Explorer Suites", () => {
  let queryClient: QueryClient;

  beforeEach(() => {
    vi.clearAllMocks();
    queryClient = new QueryClient({
      defaultOptions: { queries: { retry: false } },
    });

    useAuthStore.setState({
      user: {
        id: "admin-1",
        name: "Administrator",
        email: "admin@legalmetro.gov.in",
        role: "admin",
        is_active: true,
        created_at: "2026-09-11T00:00:00Z",
      },
      accessToken: "admin-jwt",
    });
  });

  it("ViolationsExplorer renders multi-filters and deep link to scan", async () => {
    (apiClient.get as any).mockResolvedValue({ data: mockViolations });

    render(
      <QueryClientProvider client={queryClient}>
        <BrowserRouter>
          <ViolationsExplorerPage />
        </BrowserRouter>
      </QueryClientProvider>
    );

    expect(screen.getByText("Statutory Violations Explorer")).toBeInTheDocument();

    await waitFor(() => {
      expect(screen.getByText("LMPC-R9-1")).toBeInTheDocument();
      expect(screen.getByText("Rule 9(1), LMPC Rules 2011")).toBeInTheDocument();
      expect(screen.getByText("Inspect")).toBeInTheDocument();
    });

    // Verify filter change triggers API call
    const severitySelect = screen.getByDisplayValue("All Severities");
    fireEvent.change(severitySelect, { target: { value: "critical" } });

    await waitFor(() => {
      expect(apiClient.get).toHaveBeenCalledWith(expect.stringContaining("severity=critical"));
    });
  });

  it("RulesExplorer renders rules catalog and opens slide-over drawer with recent scans", async () => {
    (apiClient.get as any).mockImplementation((url: string) => {
      if (url.includes("/recent-scans")) return Promise.resolve({ data: mockRecentScans });
      if (url.includes("/rules")) return Promise.resolve({ data: mockRules });
      return Promise.resolve({ data: {} });
    });

    render(
      <QueryClientProvider client={queryClient}>
        <BrowserRouter>
          <RulesExplorerPage />
        </BrowserRouter>
      </QueryClientProvider>
    );

    await waitFor(() => {
      expect(screen.getByText("LMPC-R9-1")).toBeInTheDocument();
      expect(screen.getByText("24")).toBeInTheDocument(); // trigger count
    });

    // Click rule row to open drawer
    const row = screen.getByText("LMPC-R9-1");
    fireEvent.click(row);

    await waitFor(() => {
      expect(screen.getByText("Verbatim Statutory Citation")).toBeInTheDocument();
      expect(screen.getByText("Recent Non-Compliant Scans")).toBeInTheDocument();
      expect(screen.getByText("Scan")).toBeInTheDocument();
    });
  });
});
