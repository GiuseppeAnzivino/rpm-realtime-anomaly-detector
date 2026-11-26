import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { test, expect } from "vitest";
import AdminPage from "../../src/pages/AdminPage.jsx";

test("renders the administrator area and its sections", () => {
  render(
    <MemoryRouter
      future={{
        v7_startTransition: true,
        v7_relativeSplatPath: true,
      }}
    >
      <AdminPage />
    </MemoryRouter>
  );

  expect(screen.getByText("Administrator Area")).toBeInTheDocument();
  expect(screen.getByRole("link", { name: "Overview" })).toHaveAttribute("href", "#overview");
  expect(screen.getByRole("link", { name: "Clinician accounts" })).toHaveAttribute("href", "#accounts");
});