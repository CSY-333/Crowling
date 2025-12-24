import { render, screen } from "@testing-library/react";
import Page from "../app/page";

describe("NACT-MVP UI", () => {
  it("shows run header metadata", () => {
    render(<Page />);
    expect(screen.getByText(/run_20250101_0900/i)).toBeInTheDocument();
    expect(screen.getByText(/config cf7d29/i)).toBeInTheDocument();
  });

  it("renders control steps and KPI cards", () => {
    render(<Page />);
    expect(screen.getByText("Data Sources")).toBeInTheDocument();
    expect(screen.getByText("Volume tracker suggests expanding search scope", { exact: false })).toBeInTheDocument();
  });

  it("shows failure gallery cards", () => {
    render(<Page />);
    expect(screen.getByText(/Failure Gallery/)).toBeInTheDocument();
    expect(screen.getAllByText(/Evidence/).length).toBeGreaterThan(0);
  });
});
