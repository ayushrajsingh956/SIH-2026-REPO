import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { BrowserRouter } from "react-router-dom";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { ScansListPage } from "@/pages/scans/ScansListPage";
import { apiClient } from "@/services/api";
import { useAuthStore } from "@/stores/authStore";

vi.mock("@/services/api", () => ({
  apiClient: {
    get: vi.fn(),
  },
}));

const mockScansResponse = {
  total: 2,
  items: [
    {
      id: "scan-1111-aaaa",
      mode: "retail",
      status: "completed",
      verdict: "compliant",
      compliance_score: 95.0,
      font_check_mode: "relative",
      image_urls: ["original/scan-1/0.png"],
      scanned_at: "2026-09-11T10:00:00Z",
      violations: [],
    },
    {
      id: "scan-2222-bbbb",
      mode: "ecommerce",
      status: "needs_review",
      verdict: "non_compliant",
      compliance_score: 65.0,
      font_check_mode: "relative",
      image_urls: ["original/scan-2/0.png", "original/scan-2/1.png"],
      scanned_at: "2026-09-11T11:00:00Z",
      violations: [{ id: "v-1" }],
    },
  ],
};

describe("ScansListPage Component", () => {
  let queryClient: QueryClient;

  beforeEach(() => {
    vi.clearAllMocks();
    queryClient = new QueryClient({
      defaultOptions: { queries: { retry: false } },
    });

    useAuthStore.setState({
      user: {
        id: "insp-1",
        name: "Officer",
        email: "officer@doca.gov.in",
        role: "inspector",
        is_active: true,
        created_at: "2026-09-11T00:00:00Z",
      },
      isAuthenticated: true,
    });
  });

  it("renders scans list table and filters", async () => {
    (apiClient.get as any).mockResolvedValueOnce({ data: mockScansResponse });

    render(
      <QueryClientProvider client={queryClient}>
        <BrowserRouter>
          <ScansListPage />
        </BrowserRouter>
      </QueryClientProvider>
    );

    expect(screen.getByText("Packaged Commodities Scans")).toBeInTheDocument();
    expect(screen.getByText("New Label Scan")).toBeInTheDocument();

    expect(await screen.findByText("#scan-111")).toBeInTheDocument();
    expect(screen.getByText("#scan-222")).toBeInTheDocument();
    expect(screen.getByText("COMPLIANT")).toBeInTheDocument();
    expect(screen.getByText("NON COMPLIANT")).toBeInTheDocument();
    expect(screen.getByText("95%")).toBeInTheDocument();
    expect(screen.getByText("65%")).toBeInTheDocument();
  });

  it("updates query params when filters change", async () => {
    (apiClient.get as any).mockResolvedValue({ data: mockScansResponse });

    render(
      <QueryClientProvider client={queryClient}>
        <BrowserRouter>
          <ScansListPage />
        </BrowserRouter>
      </QueryClientProvider>
    );

    await screen.findByText("#scan-111");

    const statusSelect = screen.getByDisplayValue("Status: All");
    fireEvent.change(statusSelect, { target: { value: "completed" } });

    await waitFor(() => {
      expect(apiClient.get).toHaveBeenCalledWith(
        "/api/v1/scans",
        expect.objectContaining({
          params: expect.objectContaining({
            status: "completed",
          }),
        })
      );
    });
  });
});
