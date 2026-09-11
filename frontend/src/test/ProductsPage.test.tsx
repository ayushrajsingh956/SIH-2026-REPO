import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { BrowserRouter, MemoryRouter, Route, Routes } from "react-router-dom";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { ProductsPage } from "@/pages/products/ProductsPage";
import { ProductDetailPage } from "@/pages/products/ProductDetailPage";
import { apiClient } from "@/services/api";

vi.mock("@/services/api", () => ({
  apiClient: {
    get: vi.fn(),
  },
}));

const mockProductsList = {
  total: 2,
  items: [
    {
      id: "prod-1",
      name: "Tata Tea Gold 500g",
      brand: "Tata Tea",
      manufacturer_name: "Tata Consumer Products",
      category: "Beverages",
      barcode: "8901052001018",
      total_scans: 5,
      compliance_badge: "compliant",
      latest_score: 96.0,
      last_scanned_at: "2026-09-10T10:00:00Z",
    },
    {
      id: "prod-2",
      name: "Royal Herbal Ayurvedic Hair Tonic 200ml",
      brand: "Royal Herbal",
      manufacturer_name: "Royal Herbs Remedies",
      category: "Personal Care",
      barcode: "8909999000011",
      total_scans: 4,
      compliance_badge: "non_compliant",
      latest_score: 45.0,
      last_scanned_at: "2026-09-11T09:00:00Z",
    },
  ],
};

const mockProductScans = {
  product: {
    id: "prod-2",
    name: "Royal Herbal Ayurvedic Hair Tonic 200ml",
    brand: "Royal Herbal",
    manufacturer_name: "Royal Herbs Remedies",
    category: "Personal Care",
    barcode: "8909999000011",
    total_scans: 4,
    compliance_rate: 0.0,
    is_repeat_offender: true,
  },
  is_repeat_offender: true,
  recurrent_violations: [
    {
      rule_code: "LMPC-R9-1",
      rule_title: "MRP Statutory Formatting",
      citation: "Rule 9(1), LMPC Rules 2011",
      severity: "critical",
      count: 4,
      scan_ids: ["scan-1", "scan-2", "scan-3", "scan-4"],
    },
  ],
  scans: [
    {
      id: "scan-1",
      mode: "retail",
      status: "completed",
      verdict: "non_compliant",
      compliance_score: 45.0,
      scanned_at: "2026-09-11T09:00:00Z",
      inspector_name: "Officer Sharma",
      violations: [
        {
          id: "v-1",
          rule_code: "LMPC-R9-1",
          rule_title: "MRP Statutory Formatting",
          citation: "Rule 9(1), LMPC Rules 2011",
          severity: "critical",
          field_name: "mrp",
          overridden: false,
        },
      ],
    },
  ],
};

describe("Products Catalog & Detail Flow", () => {
  let queryClient: QueryClient;

  beforeEach(() => {
    vi.clearAllMocks();
    queryClient = new QueryClient({
      defaultOptions: { queries: { retry: false } },
    });
  });

  it("renders commodities table and triggers search", async () => {
    (apiClient.get as any).mockResolvedValue({ data: mockProductsList });

    render(
      <QueryClientProvider client={queryClient}>
        <BrowserRouter>
          <ProductsPage />
        </BrowserRouter>
      </QueryClientProvider>
    );

    expect(screen.getByText("Packaged Commodities Repository")).toBeInTheDocument();

    await waitFor(() => {
      expect(screen.getByText("Tata Tea Gold 500g")).toBeInTheDocument();
      expect(screen.getByText("Royal Herbal Ayurvedic Hair Tonic 200ml")).toBeInTheDocument();
      expect(screen.getByText("8901052001018")).toBeInTheDocument();
    });

    // Enter search query
    const searchInput = screen.getByPlaceholderText(/Search by product name/);
    fireEvent.change(searchInput, { target: { value: "Herbal" } });

    await waitFor(() => {
      expect(apiClient.get).toHaveBeenCalledWith(expect.stringContaining("q=Herbal"));
    });
  });

  it("renders repeat offender recurrence alert on product detail", async () => {
    (apiClient.get as any).mockResolvedValue({ data: mockProductScans });

    render(
      <QueryClientProvider client={queryClient}>
        <MemoryRouter initialEntries={["/products/prod-2"]}>
          <Routes>
            <Route path="/products/:id" element={<ProductDetailPage />} />
          </Routes>
        </MemoryRouter>
      </QueryClientProvider>
    );

    await waitFor(() => {
      expect(screen.getByText("Royal Herbal Ayurvedic Hair Tonic 200ml")).toBeInTheDocument();
      expect(screen.getByText("Statutory Violation Recurrence Alert (Repeat Offender)")).toBeInTheDocument();
      expect(screen.getByText("4 Repeat Citations")).toBeInTheDocument();
      expect(screen.getByText("Chronological Inspection & Scan Timeline")).toBeInTheDocument();
    });
  });
});
