import "@testing-library/jest-dom";
import { afterEach, vi } from "vitest";

// jsdom does not implement layout APIs that the shell and charts touch.
Object.defineProperty(window, "scrollTo", { value: () => {}, writable: true });

class ResizeObserverStub {
  observe() {}
  unobserve() {}
  disconnect() {}
}

class IntersectionObserverStub {
  observe() {}
  unobserve() {}
  disconnect() {}
  takeRecords() {
    return [];
  }
}

// Keep these installed for every test; fetch is re-stubbed per test.
globalThis.ResizeObserver = ResizeObserverStub as unknown as typeof ResizeObserver;
globalThis.IntersectionObserver = IntersectionObserverStub as unknown as typeof IntersectionObserver;

afterEach(() => {
  vi.restoreAllMocks();
});
