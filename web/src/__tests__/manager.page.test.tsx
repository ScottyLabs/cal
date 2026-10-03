import { describe, it, expect, vi, beforeEach } from "vitest";
import type { ReactNode } from "react";
import { render, screen, waitFor } from "@testing-library/react";
import ManagerPage from "../app/manager/page";
import { getUserRole, type RoleResponse } from "../app/utils/api/users";

// IMPORTANT: mocks
const { push } = vi.hoisted(() => ({ push: vi.fn() }));
vi.mock("next/navigation", () => ({
  useRouter: () => ({ push, replace: vi.fn(), prefetch: vi.fn() }),
  usePathname: () => "/manager",
}));
vi.mock("../app/utils/api/users");
vi.mock("../app/components/TwoColumnLayout", () => ({
  default: ({ leftContent, rightContent }: { leftContent: ReactNode; rightContent: ReactNode }) => (
    <div>
      <div data-testid="left">{leftContent}</div>
      <div data-testid="right">{rightContent}</div>
    </div>
  ),
}));
vi.mock("../app/components/ManagerSidebar", () => ({
  default: ({ allowedOrgIds }: { allowedOrgIds: Set<number> | null }) => (
    <div data-testid="manager-sidebar">{[...(allowedOrgIds ?? [])].join(",")}</div>
  ),
}));
vi.mock("../app/components/ManagerDashboard", () => ({
  default: () => <div data-testid="manager-content" />,
}));

function roleResponse(overrides: Partial<RoleResponse>): RoleResponse {
  return { is_manager: false, is_admin: false, is_site_admin: false, roles: [], ...overrides };
}

describe("ManagerPage", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("shows loading state initially", () => {
    vi.mocked(getUserRole).mockReturnValue(new Promise<RoleResponse>(() => undefined));

    const { container } = render(<ManagerPage />);

    expect(container.querySelector(".animate-pulse")).toBeInTheDocument();
    expect(screen.queryByTestId("manager-sidebar")).not.toBeInTheDocument();
    expect(getUserRole).toHaveBeenCalledTimes(1);
  });

  it("renders manager layout when role is manager", async () => {
    vi.mocked(getUserRole).mockResolvedValue(
      roleResponse({ is_manager: true, roles: [{ role: "manager", org_id: 7 }] }),
    );

    const { container } = render(<ManagerPage />);

    expect(await screen.findByTestId("manager-sidebar")).toHaveTextContent("7");
    expect(screen.getByTestId("manager-content")).toBeInTheDocument();
    expect(container.querySelector(".animate-pulse")).not.toBeInTheDocument();
    expect(push).not.toHaveBeenCalled();
  });

  it("does not redirect when user is admin", async () => {
    vi.mocked(getUserRole).mockResolvedValue(
      roleResponse({ is_admin: true, roles: [{ role: "admin", org_id: 3 }] }),
    );

    render(<ManagerPage />);

    expect(await screen.findByTestId("manager-sidebar")).toHaveTextContent("3");
    expect(push).not.toHaveBeenCalled();
  });

  it("redirects when user is user", async () => {
    vi.mocked(getUserRole).mockResolvedValue(roleResponse({}));

    render(<ManagerPage />);

    await waitFor(() => {
      expect(push).toHaveBeenCalledWith("/unauthorized");
    });
  });
});
