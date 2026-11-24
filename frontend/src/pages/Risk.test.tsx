/// <reference types="vitest/globals" />
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import Risk from "./Risk";
import { mockFetch, riskDetailFixture, riskListFixture } from "../test/fixtures";

test("lists ranked risk and opens the explanation drawer", async () => {
  const fetchMock = mockFetch([
    {
      match: (url) => url.includes("/api/v1/risk/CB-00001"),
      response: riskDetailFixture,
    },
    {
      match: (url) => url.includes("/api/v1/risk?"),
      response: riskListFixture,
    },
  ]);

  render(
    <MemoryRouter initialEntries={["/risk"]}>
      <Risk />
    </MemoryRouter>,
  );

  expect(await screen.findByText("Ranked population")).toBeInTheDocument();
  const assetCells = await screen.findAllByText("CB-00001");
  fireEvent.click(assetCells[0]);

  expect(await screen.findByText("Why this asset is ranked here")).toBeInTheDocument();
  expect(await screen.findByText(/Load trend per day/)).toBeInTheDocument();
  expect(screen.getByText(/Robust z-scores against the persisted population baseline/i)).toBeInTheDocument();
  expect(screen.getByRole("button", { name: /Create decision for review/i })).toBeDisabled();
  expect(fetchMock).toHaveBeenCalled();
});

test("creates a human-owned decision only when a rationale is provided", async () => {
  const fetchMock = mockFetch([
    {
      match: (url) => url.includes("/api/v1/risk/CB-00001"),
      response: riskDetailFixture,
    },
    {
      match: (url) => url.includes("/api/v1/risk?"),
      response: riskListFixture,
    },
    {
      match: (url, init) => url.endsWith("/api/v1/decisions") && init?.method === "POST",
      response: {
        decision_id: "99999999-2222-3333-4444-555555555555",
        asset_id: "CB-00001",
        asset_type: "circuit_breakers",
        decision_status: "PENDING_REVIEW",
      },
      status: 201,
    },
  ]);

  render(
    <MemoryRouter initialEntries={["/risk?asset=CB-00001"]}>
      <Risk />
    </MemoryRouter>,
  );

  const assetCells = await screen.findAllByText("CB-00001");
  fireEvent.click(assetCells[0]);

  const rationale = await screen.findByLabelText(/Decision rationale/i);
  const submit = screen.getByRole("button", { name: /Create decision for review/i });
  expect(submit).toBeDisabled();

  fireEvent.change(rationale, {
    target: { value: "Reviewed the load trend, inspection findings, and maintenance history." },
  });
  expect(submit).toBeEnabled();
  fireEvent.click(submit);

  await waitFor(() =>
    expect(fetchMock).toHaveBeenCalledWith(
      "/api/v1/decisions",
      expect.objectContaining({ method: "POST" }),
    ),
  );
});
