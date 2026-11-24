/// <reference types="vitest/globals" />
import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import App from "./App";
import { mockFetch, overviewFixture } from "./test/fixtures";

test("renders the command center with live overview data", async () => {
  mockFetch([
    {
      match: (url) => url.includes("/api/v1/overview"),
      response: overviewFixture,
    },
  ]);

  render(
    <MemoryRouter initialEntries={["/"]}>
      <App />
    </MemoryRouter>,
  );

  expect(await screen.findByRole("heading", { name: "Operations Overview" })).toBeInTheDocument();
  expect(await screen.findByText("Assets under management")).toBeInTheDocument();
  expect((await screen.findAllByText("2,600")).length).toBeGreaterThan(0);
  expect(screen.getAllByText("CB-00348").length).toBeGreaterThan(0);
  expect(screen.getByText(/Synthetic demonstration data/i)).toBeInTheDocument();
});

test("shows an actionable error when the API is unreachable", async () => {
  mockFetch([
    {
      match: (url) => url.includes("/api/v1/overview"),
      response: { detail: "database unavailable" },
      status: 503,
    },
  ]);

  render(
    <MemoryRouter initialEntries={["/"]}>
      <App />
    </MemoryRouter>,
  );

  expect(await screen.findByText("This view could not load")).toBeInTheDocument();
  expect(screen.getByRole("button", { name: /Retry/i })).toBeInTheDocument();
});
