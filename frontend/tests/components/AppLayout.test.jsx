import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { test, expect } from "vitest";
import AppLayout from "../../src/components/AppLayout.jsx";

const SECTIONS = [
  { id: "one", label: "First" },
  { id: "two", label: "Second" },
];

test("renders the title, navigation links and sections", () => {
  render(
    <MemoryRouter
      future={{
        v7_startTransition: true,
        v7_relativeSplatPath: true,
      }}
    >
      <AppLayout title="Test area" sections={SECTIONS} />
    </MemoryRouter>
  );

  expect(screen.getByText("Test area")).toBeInTheDocument();
  expect(screen.getByRole("link", { name: "First" })).toHaveAttribute("href", "#one");
  expect(screen.getByRole("heading", { name: "Second" })).toBeInTheDocument();
  expect(screen.getByRole("button", { name: "Sign out" })).toBeInTheDocument();
});