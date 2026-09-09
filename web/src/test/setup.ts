import "@testing-library/jest-dom/vitest";
import { cleanup } from "@testing-library/react";
import { afterEach, vi } from "vitest";

afterEach(() => cleanup());

// jsdom lacks these; components reference them
vi.stubGlobal("EventSource", class {
  close() {}
  addEventListener() {}
} as unknown as typeof EventSource);

if (!window.matchMedia) {
  window.matchMedia = () =>
    ({ matches: false, addEventListener() {}, removeEventListener() {} }) as unknown as MediaQueryList;
}
