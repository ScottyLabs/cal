// src/__tests__/page.test.tsx
import { describe, it, expect, vi, beforeEach } from "vitest";

import { render, screen } from "@testing-library/react";
import axios from "axios";
import Home from "../app/page";
import { api } from "../app/utils/api/api";
import { getSchedule } from "../app/utils/api/schedules";
import { Providers } from "./test-utils";

vi.mock("../app/components/Calendar", () => ({
  default: () => <div data-testid="calendar-mock" />,
}));

vi.mock("../app/utils/api/schedules", () => ({
  getSchedule: vi.fn().mockResolvedValue({
    courses: [],
    clubs: [],
  }),
  removeCategoryFromSchedule: vi.fn(),
}));

describe("Home page", () => {
  beforeEach(() => {
    // Saved event ids (EventStateProvider) and all events (UserProvider).
    vi.spyOn(axios, "get").mockResolvedValue({ data: [] });
    vi.spyOn(api, "get").mockResolvedValue({ data: [] });
  });

  it("renders loading state initially", async () => {
    const { container } = render(
      <Providers>
        <Home />
      </Providers>,
    );
    expect(container.querySelector(".animate-pulse")).toBeInTheDocument();
    expect(screen.queryByTestId("calendar-mock")).not.toBeInTheDocument();

    // The skeleton gives way to the calendar once the schedule has loaded.
    expect(await screen.findByTestId("calendar-mock")).toBeInTheDocument();
    expect(getSchedule).toHaveBeenCalledTimes(1);
    expect(container.querySelector(".animate-pulse")).not.toBeInTheDocument();
  });
});
