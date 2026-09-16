import "@testing-library/jest-dom/vitest";

// jsdom n'implémente pas ResizeObserver — nécessaire aux composants Radix
// (ex. Checkbox, via @radix-ui/react-use-size) dès qu'un test les monte.
if (typeof globalThis.ResizeObserver === "undefined") {
  globalThis.ResizeObserver = class ResizeObserver {
    observe() {}
    unobserve() {}
    disconnect() {}
  };
}
