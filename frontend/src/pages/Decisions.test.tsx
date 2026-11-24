/// <reference types="vitest/globals" />
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import Decisions from "./Decisions";
import { decisionDetailFixture, decisionFixture, mockFetch } from "../test/fixtures";

const summary = {
  total: 1,
  active: 1,
  by_status: { PENDING_REVIEW: 1, APPROVED: 0, IN_REVIEW: 0 },
  synthetic: true,
  note: "All decisions require a human reviewer; the platform never auto-approves.",
};

function routes(extra: Parameters<typeof mockFetch>[0] = []) {
  return mockFetch([
    ...extra,
    {
      match: (url) => url.includes("/api/v1/decisions/summary"),
      response: summary,
    },
    {
      match: (url) => url.includes("/api/v1/decisions/") && url.includes("/detail"),
      response: {
        ...decisionDetailFixture,
        decision: { ...decisionFixture, decision_status: "IN_REVIEW" },
      },
    },
    {
      match: (url) => url.includes("/api/v1/decisions?"),
      response: { items: [decisionFixture], total: 1, limit: 25, offset: 0 },
    },
  ]);
}

test("opens a decision and requires a rationale before approving", async () => {
  const fetchMock = routes([
    {
      match: (url, init) => url.endsWith("/approve") && init?.method === "POST",
      response: { ...decisionFixture, decision_status: "APPROVED" },
    },
  ]);

  render(
    <MemoryRouter initialEntries={["/decisions"]}>
      <Decisions />
    </MemoryRouter>,
  );

  expect(await screen.findByText("Decision records")).toBeInTheDocument();
  const assetCells = await screen.findAllByText("CB-00001");
  fireEvent.click(assetCells[0]);

  expect(await screen.findByText("Record a review outcome")).toBeInTheDocument();
  const approve = screen.getByRole("button", { name: "Approve" });
  expect(approve).toBeDisabled();

  fireEvent.change(screen.getByLabelText("Rationale"), {
    target: { value: "Evidence reviewed and the condition is acceptable." },
  });
  expect(approve).toBeEnabled();
  fireEvent.click(approve);

  await waitFor(() =>
    expect(fetchMock).toHaveBeenCalledWith(
      expect.stringMatching(/\/api\/v1\/decisions\/.+\/approve$/),
      expect.objectContaining({ method: "POST" }),
    ),
  );
});

test("prevents decision creation without an asset and rationale", async () => {
  routes();

  render(
    <MemoryRouter initialEntries={["/decisions"]}>
      <Decisions />
    </MemoryRouter>,
  );

  fireEvent.click(await screen.findByRole("button", { name: /New decision/i }));
  expect(await screen.findByText("Create a decision record")).toBeInTheDocument();
  expect(screen.getByRole("button", { name: /Create and review/i })).toBeDisabled();
});
