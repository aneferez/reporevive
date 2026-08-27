import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it } from "vitest";
import App from "./App";
import { SeverityBadge } from "./components/SeverityBadge";

describe("RepoRevive client", () => {
  it("validates repository intake before contacting the API", async () => {
    const user = userEvent.setup();
    render(<App />);

    await user.click(screen.getByRole("button", { name: /analyze repository/i }));

    expect(screen.getByRole("alert")).toHaveTextContent("valid public GitHub repository URL");
  });

  it("loads the explicit sample analysis and navigates through findings", async () => {
    const user = userEvent.setup();
    render(<App />);

    await user.click(screen.getByRole("button", { name: /view sample/i }));

    expect(screen.getByRole("heading", { name: "atlas-workbench" })).toBeInTheDocument();
    expect(screen.getByText("Sample analysis")).toBeInTheDocument();
    expect(screen.getByRole("img", { name: "57% readiness heuristic based on 9 findings" })).toBeInTheDocument();
    expect(screen.getAllByText("09")).toHaveLength(2);

    await user.click(screen.getAllByRole("button", { name: /findings/i })[0]);
    expect(screen.getByRole("heading", { name: "Findings" })).toBeInTheDocument();
    expect(screen.getByText("Frontend request has no matching backend route")).toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: /frontend request has no matching backend route/i }));
    expect(screen.getByText("POST /api/jobs/search")).toBeInTheDocument();
  });

  it("supports grounded chat in sample mode", async () => {
    const user = userEvent.setup();
    render(<App />);

    await user.click(screen.getByRole("button", { name: /view sample/i }));
    await user.click(screen.getAllByRole("button", { name: /codebase chat/i })[0]);

    expect(screen.getByText("Repository-grounded answers")).toBeInTheDocument();
    expect(screen.getByText(/The job search flow appears incomplete/)).toBeInTheDocument();
    expect(screen.getByText("frontend/src/features/search/searchApi.ts:24")).toBeInTheDocument();
  });

  it("opens workspace settings from the sidebar", async () => {
    const user = userEvent.setup();
    render(<App />);

    await user.click(screen.getByRole("button", { name: /view sample/i }));
    await user.click(screen.getAllByRole("button", { name: /workspace settings/i })[0]);

    expect(screen.getByRole("heading", { name: "Workspace settings" })).toBeInTheDocument();
    expect(screen.getByText("Assistant boundary")).toBeInTheDocument();
    expect(screen.getByText("The owner token is kept only in this browser session and is never shown in workspace settings.")).toBeInTheDocument();
  });

  it("renders the defensive info severity", () => {
    render(<SeverityBadge severity="info" />);

    expect(screen.getByText("Info")).toHaveClass("severity-info");
  });
});
