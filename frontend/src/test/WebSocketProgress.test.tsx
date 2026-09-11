import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { render, screen, act } from "@testing-library/react";
import { PipelineStatusBanner } from "@/components/scan/PipelineStatusBanner";
import { apiClient } from "@/services/api";

vi.mock("@/services/api", () => ({
  apiClient: {
    get: vi.fn(),
  },
}));

class MockWebSocket {
  url: string;
  onmessage: ((event: any) => void) | null = null;
  onerror: ((event: any) => void) | null = null;
  onclose: ((event: any) => void) | null = null;
  close = vi.fn();

  constructor(url: string) {
    this.url = url;
    MockWebSocket.instances.push(this);
  }

  static instances: MockWebSocket[] = [];
  static clear() {
    MockWebSocket.instances = [];
  }
}

describe("PipelineStatusBanner & WebSocket Progress", () => {
  const originalWebSocket = window.WebSocket;

  beforeEach(() => {
    vi.clearAllMocks();
    MockWebSocket.clear();
    (window as any).WebSocket = MockWebSocket;
  });

  afterEach(() => {
    (window as any).WebSocket = originalWebSocket;
  });

  it("renders initial preprocessing step for queued scan", () => {
    render(
      <PipelineStatusBanner
        scanId="scan-123"
        initialStatus="processing"
        initialStage="preprocessing"
      />
    );

    expect(screen.getByText("Compliance Analysis In Progress")).toBeInTheDocument();
    expect(screen.getByText("Preprocess")).toBeInTheDocument();
    expect(screen.getByText("Extract")).toBeInTheDocument();
    expect(screen.getByText("Validate")).toBeInTheDocument();
    expect(screen.getByText("Score")).toBeInTheDocument();
  });

  it("advances progress steps as WebSocket messages arrive", async () => {
    const onStatusChange = vi.fn();

    render(
      <PipelineStatusBanner
        scanId="scan-123"
        initialStatus="processing"
        initialStage="preprocessing"
        onStatusChange={onStatusChange}
      />
    );

    expect(MockWebSocket.instances.length).toBe(1);
    const wsInstance = MockWebSocket.instances[0];

    // Simulate extraction stage arrival from Celery pipeline
    act(() => {
      wsInstance.onmessage?.({
        data: JSON.stringify({
          scan_id: "scan-123",
          status: "processing",
          stage: "extracting",
        }),
      });
    });

    expect(onStatusChange).toHaveBeenCalledWith("processing", expect.objectContaining({ stage: "extracting" }));

    // Simulate completion event
    act(() => {
      wsInstance.onmessage?.({
        data: JSON.stringify({
          scan_id: "scan-123",
          status: "completed",
          verdict: "compliant",
          compliance_score: 95.0,
        }),
      });
    });

    expect(onStatusChange).toHaveBeenCalledWith("completed", expect.objectContaining({ verdict: "compliant" }));
  });

  it("falls back to HTTP polling when WebSocket encounters an error", async () => {
    vi.useFakeTimers();

    (apiClient.get as any).mockResolvedValue({
      data: {
        id: "scan-123",
        status: "completed",
        verdict: "compliant",
      },
    });

    const onStatusChange = vi.fn();

    render(
      <PipelineStatusBanner
        scanId="scan-123"
        initialStatus="processing"
        initialStage="preprocessing"
        onStatusChange={onStatusChange}
      />
    );

    const wsInstance = MockWebSocket.instances[0];

    // Trigger WebSocket error
    act(() => {
      wsInstance.onerror?.(new Event("error"));
    });

    // Advance timer to trigger polling interval (2000ms)
    await act(async () => {
      vi.advanceTimersByTime(2500);
    });

    expect(apiClient.get).toHaveBeenCalledWith("/api/v1/scans/scan-123");

    vi.useRealTimers();
  });
});
