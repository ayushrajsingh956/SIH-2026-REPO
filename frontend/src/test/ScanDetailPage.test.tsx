import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { BrowserRouter } from "react-router-dom";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { ScanDetailPage } from "@/pages/scans/ScanDetailPage";
import { apiClient } from "@/services/api";
import { useAuthStore } from "@/stores/authStore";

vi.mock("@/services/api", () => ({
  apiClient: {
    get: vi.fn(),
    patch: vi.fn(),
    post: vi.fn(),
  },
}));

vi.mock("react-router-dom", async () => {
  const actual = await vi.importActual("react-router-dom");
  return {
    ...actual,
    useParams: () => ({ id: "scan-uuid-1234" }),
  };
});

const mockScanData = {
  id: "scan-uuid-1234",
  mode: "retail",
  status: "completed",
  verdict: "non_compliant",
  compliance_score: 70.0,
  font_check_mode: "relative",
  surface_area_cm2: null,
  image_urls: ["original/scan-uuid-1234/original_0.png"],
  presigned_image_urls: ["http://localhost:9000/presigned/original_0.png"],
  scanned_at: "2026-09-11T12:00:00Z",
  extraction: {
    fields: {
      mrp: {
        raw: "₹ 150/-",
        value: 150,
        currency: "INR",
        confidence: 0.95,
        bbox: [100, 100, 200, 300],
        source: "gemini",
      },
      net_quantity: {
        raw: "500 ml",
        value: 500,
        unit: "ml",
        confidence: 0.9,
        bbox: [300, 100, 400, 300],
        source: "gemini",
      },
    },
  },
  violations: [
    {
      id: "viol-1",
      scan_id: "scan-uuid-1234",
      rule_code: "LMPC-R6-1b",
      rule_title: "Mandatory Net Quantity Declaration",
      citation: "Rule 6(1)(b), LMPC Rules 2011",
      severity: "critical",
      field_name: "net_quantity",
      observed_value: "500 ml",
      expected_value: "Standard SI unit declaration",
      bbox: [300, 100, 400, 300],
      overridden: false,
      override_reason: null,
    },
  ],
};

describe("ScanDetailPage Component", () => {
  let queryClient: QueryClient;

  beforeEach(() => {
    vi.clearAllMocks();
    queryClient = new QueryClient({
      defaultOptions: {
        queries: { retry: false },
      },
    });

    // Set inspector auth in zustand store
    useAuthStore.setState({
      user: {
        id: "inspector-1",
        name: "Officer Verma",
        email: "inspector@legalmetro.gov.in",
        role: "inspector",
        is_active: true,
        created_at: "2026-09-11T00:00:00Z",
      },
      isAuthenticated: true,
      accessToken: "mock-token",
    });
  });

  it("renders scan overview, score gauge, and extracted declarations", async () => {
    (apiClient.get as any).mockResolvedValueOnce({ data: mockScanData });

    render(
      <QueryClientProvider client={queryClient}>
        <BrowserRouter>
          <ScanDetailPage />
        </BrowserRouter>
      </QueryClientProvider>
    );

    expect(await screen.findByText(/Scan #scan-uui/i)).toBeInTheDocument();
    expect(screen.getByText("NON COMPLIANT")).toBeInTheDocument();
    expect(screen.getByText("70/100")).toBeInTheDocument();
    expect(screen.getByText("Extracted Declarations")).toBeInTheDocument();
    expect(screen.getByText("₹ 150/-")).toBeInTheDocument();
  });

  it("allows inspector to edit an extracted declaration and re-validate via PATCH", async () => {
    (apiClient.get as any).mockResolvedValue({ data: mockScanData });
    (apiClient.patch as any).mockResolvedValueOnce({ data: { ...mockScanData, compliance_score: 100 } });

    render(
      <QueryClientProvider client={queryClient}>
        <BrowserRouter>
          <ScanDetailPage />
        </BrowserRouter>
      </QueryClientProvider>
    );

    await screen.findByText("₹ 150/-");

    // Find and click edit button
    const editButtons = screen.getAllByTitle("Edit declaration");
    fireEvent.click(editButtons[0]);

    // Update raw text in textarea
    const textareas = screen.getAllByRole("textbox");
    fireEvent.change(textareas[0], { target: { value: "₹ 150/- Incl. of all taxes" } });

    // Save
    const saveButton = screen.getByTitle("Save & Re-evaluate");
    fireEvent.click(saveButton);

    await waitFor(() => {
      expect(apiClient.patch).toHaveBeenCalledWith(
        "/api/v1/scans/scan-uuid-1234/extraction",
        expect.objectContaining({
          fields: expect.objectContaining({
            mrp: expect.objectContaining({
              raw: "₹ 150/- Incl. of all taxes",
            }),
          }),
        })
      );
    });
  });

  it("allows inspector to apply override to a violation with written justification", async () => {
    (apiClient.get as any).mockResolvedValue({ data: mockScanData });
    (apiClient.post as any).mockResolvedValueOnce({
      data: {
        id: "viol-1",
        overridden: true,
        override_reason: "Special export batch certificate verified",
      },
    });

    render(
      <QueryClientProvider client={queryClient}>
        <BrowserRouter>
          <ScanDetailPage />
        </BrowserRouter>
      </QueryClientProvider>
    );

    // Expand violation accordion if needed
    const overrideBtn = await screen.findByText(/Apply Inspector Override/i);
    fireEvent.click(overrideBtn);

    // Modal should be open
    expect(await screen.findByText("Inspector Violation Override")).toBeInTheDocument();

    const textarea = screen.getByPlaceholderText(/e.g. Manufacturer possesses/i);
    fireEvent.change(textarea, {
      target: { value: "Special export batch certificate verified under order 402" },
    });

    const confirmBtn = screen.getByText("Confirm Override & Recalculate");
    fireEvent.click(confirmBtn);

    await waitFor(() => {
      expect(apiClient.post).toHaveBeenCalledWith(
        "/api/v1/scans/scan-uuid-1234/violations/viol-1/override",
        {
          reason: "Special export batch certificate verified under order 402",
        }
      );
    });
  });
});
