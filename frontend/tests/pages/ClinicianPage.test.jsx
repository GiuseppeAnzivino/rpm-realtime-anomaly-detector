import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { test, expect } from "vitest";
import ClinicianPage from "../../src/pages/ClinicianPage.jsx";

test("renders the clinician area and its sections", () => {
  render(
    <MemoryRouter
      future={{
        v7_startTransition: true,
        v7_relativeSplatPath: true,
      }}
    >
      <ClinicianPage />
    </MemoryRouter>
  );

  expect(screen.getByText("Clinician Area")).toBeInTheDocument();
  expect(screen.getByRole("link", { name: "Real-time anomalies" })).toHaveAttribute("href", "#anomalies");
  expect(screen.getByRole("link", { name: "History" })).toHaveAttribute("href", "#history");
});