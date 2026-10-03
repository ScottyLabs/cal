import type { Metadata } from "next";

export const metadata: Metadata = {
  title: "Manager | CMUCal",
};

export default function ManagerLayout({ children }: { children: React.ReactNode }) {
  return children;
}
