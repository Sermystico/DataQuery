import '@testing-library/jest-dom/vitest';

// Polyfill ResizeObserver for jsdom (needed for Recharts ResponsiveContainer)
class MockResizeObserver {
  observe() {}
  unobserve() {}
  disconnect() {}
}

window.ResizeObserver = MockResizeObserver;
