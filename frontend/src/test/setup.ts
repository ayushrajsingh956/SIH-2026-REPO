import "@testing-library/jest-dom";

// Mock ResizeObserver for BboxOverlay and responsive components
class MockResizeObserver {
  observe() {}
  unobserve() {}
  disconnect() {}
}
(window as any).ResizeObserver = (window as any).ResizeObserver || MockResizeObserver;

// Mock matchMedia
Object.defineProperty(window, "matchMedia", {
  writable: true,
  value: (query: string) => ({
    matches: false,
    media: query,
    onchange: null,
    addListener: () => {},
    removeListener: () => {},
    addEventListener: () => {},
    removeEventListener: () => {},
    dispatchEvent: () => false,
  }),
});

// Mock URL.createObjectURL / revokeObjectURL for file preview tests
if (!window.URL.createObjectURL) {
  window.URL.createObjectURL = () => "blob:http://localhost/mock-image-uuid";
}
if (!window.URL.revokeObjectURL) {
  window.URL.revokeObjectURL = () => {};
}

// Mock HTMLDialogElement for jsdom
if (typeof HTMLDialogElement !== "undefined") {
  HTMLDialogElement.prototype.showModal = function () {
    this.open = true;
  };
  HTMLDialogElement.prototype.close = function () {
    this.open = false;
  };
}
