import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { BrowserRouter } from "react-router-dom";
import { NewScanPage } from "@/pages/scans/NewScanPage";
import { apiClient } from "@/services/api";

const mockedNavigate = vi.fn();
vi.mock("react-router-dom", async () => {
  const actual = await vi.importActual("react-router-dom");
  return {
    ...actual,
    useNavigate: () => mockedNavigate,
  };
});

vi.mock("@/services/api", () => ({
  apiClient: {
    post: vi.fn(),
  },
}));

describe("NewScanPage Component", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("renders upload tabs and dropzone by default", () => {
    render(
      <BrowserRouter>
        <NewScanPage />
      </BrowserRouter>
    );

    expect(screen.getByText("Physical Photo Upload")).toBeInTheDocument();
    expect(screen.getByText("E-Commerce Listing URL")).toBeInTheDocument();
    expect(screen.getByText(/Drag and drop label photographs here/i)).toBeInTheDocument();
  });

  it("displays validation error when submitting with no files attached", async () => {
    render(
      <BrowserRouter>
        <NewScanPage />
      </BrowserRouter>
    );

    const submitBtn = screen.getByText("Submit for Statutory Verification");
    fireEvent.click(submitBtn);

    expect(
      await screen.findByText(/Please upload at least one photograph/i)
    ).toBeInTheDocument();
    expect(apiClient.post).not.toHaveBeenCalled();
  });

  it("shows conditional surface area input only when surface_area mode is selected", async () => {
    render(
      <BrowserRouter>
        <NewScanPage />
      </BrowserRouter>
    );

    expect(screen.queryByLabelText(/Package Principal Display Surface Area/i)).not.toBeInTheDocument();

    const fontCheckSelect = screen.getByLabelText(/Font Size Verification Strategy/i);
    fireEvent.change(fontCheckSelect, { target: { value: "surface_area" } });

    expect(
      screen.getByText(/Package Principal Display Surface Area/i)
    ).toBeInTheDocument();
  });

  it("validates surface area range if surface_area mode is selected", async () => {
    render(
      <BrowserRouter>
        <NewScanPage />
      </BrowserRouter>
    );

    // Switch to URL tab so we can test validation without file drop mocking
    fireEvent.click(screen.getByText("E-Commerce Listing URL"));

    const urlInput = screen.getByPlaceholderText(/https:\/\/www.amazon.in/i);
    fireEvent.change(urlInput, { target: { value: "https://example.com/product" } });

    const fontCheckSelect = screen.getByLabelText(/Font Size Verification Strategy/i);
    fireEvent.change(fontCheckSelect, { target: { value: "surface_area" } });

    const submitBtn = screen.getByText("Submit for Statutory Verification");
    fireEvent.click(submitBtn);

    expect(
      await screen.findByText(/Surface area is required when Font Check Mode is set/i)
    ).toBeInTheDocument();

    // Invalid range (< 5 cm²)
    const surfaceInput = screen.getByPlaceholderText(/e.g. 150.0/i);
    fireEvent.change(surfaceInput, { target: { value: "2" } });
    fireEvent.click(submitBtn);

    expect(
      await screen.findByText(/between 5 cm² and 50,000 cm²/i)
    ).toBeInTheDocument();
  });

  it("successfully submits URL scan and optimistically navigates to detail view", async () => {
    (apiClient.post as any).mockResolvedValueOnce({
      data: {
        scan_id: "33333333-3333-3333-3333-333333333333",
        status: "queued",
      },
    });

    render(
      <BrowserRouter>
        <NewScanPage />
      </BrowserRouter>
    );

    fireEvent.click(screen.getByText("E-Commerce Listing URL"));

    const urlInput = screen.getByPlaceholderText(/https:\/\/www.amazon.in/i);
    fireEvent.change(urlInput, { target: { value: "https://blinkit.com/prn/123" } });

    const submitBtn = screen.getByText("Submit for Statutory Verification");
    fireEvent.click(submitBtn);

    await waitFor(() => {
      expect(apiClient.post).toHaveBeenCalledWith(
        "/api/v1/scans/url",
        expect.objectContaining({
          url: "https://blinkit.com/prn/123",
          font_check_mode: "relative",
        })
      );
      expect(mockedNavigate).toHaveBeenCalledWith(
        "/scans/33333333-3333-3333-3333-333333333333"
      );
    });
  });
});
