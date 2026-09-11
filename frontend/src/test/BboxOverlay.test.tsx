import { describe, it, expect } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import { BboxOverlay, BboxItem } from "@/components/scan/BboxOverlay";

describe("BboxOverlay Component", () => {
  const sampleItems: BboxItem[] = [
    {
      id: "box-mrp",
      fieldName: "mrp",
      label: "MRP",
      coords: [100, 150, 200, 450], // 0-1000 scale
      confidence: 0.95,
      rawValue: "₹ 250/-",
    },
    {
      id: "box-qty",
      fieldName: "net_quantity",
      label: "Net Quantity",
      coords: [300, 150, 400, 500],
      confidence: 0.88,
      rawValue: "100 g",
    },
  ];

  it("renders overlay header with toggle buttons", () => {
    render(
      <BboxOverlay
        imageUrl="http://localhost/test.jpg"
        items={sampleItems}
      />
    );

    expect(screen.getByText("Bounding Box Overlays")).toBeInTheDocument();
    expect(screen.getByText("Show All")).toBeInTheDocument();
    expect(screen.getByText("Hide All")).toBeInTheDocument();
    expect(screen.getByText("mrp")).toBeInTheDocument();
    expect(screen.getByText("net quantity")).toBeInTheDocument();
  });

  it("toggles field visibility when toggle chip is clicked", () => {
    render(
      <BboxOverlay
        imageUrl="http://localhost/test.jpg"
        items={sampleItems}
      />
    );

    const mrpToggle = screen.getByText("mrp");
    // Initially active
    expect(screen.getByText("2 of 2 active")).toBeInTheDocument();

    // Toggle off
    fireEvent.click(mrpToggle);
    expect(screen.getByText("1 of 2 active")).toBeInTheDocument();

    // Hide all
    fireEvent.click(screen.getByText("Hide All"));
    expect(screen.getByText("0 of 2 active")).toBeInTheDocument();

    // Show all
    fireEvent.click(screen.getByText("Show All"));
    expect(screen.getByText("2 of 2 active")).toBeInTheDocument();
  });

  it("handles zoom controls", () => {
    render(
      <BboxOverlay
        imageUrl="http://localhost/test.jpg"
        items={sampleItems}
      />
    );

    const zoomInBtn = screen.getByTitle("Zoom In");
    const zoomDisplay = screen.getByText("100%");

    expect(zoomDisplay).toBeInTheDocument();

    fireEvent.click(zoomInBtn);
    expect(screen.getByText("125%")).toBeInTheDocument();

    fireEvent.click(screen.getByTitle("Reset Zoom"));
    expect(screen.getByText("100%")).toBeInTheDocument();
  });
});
