"use client";

// Account menu in the navbar: who is signed in, admin dashboard, sign out.
import { useEffect, useRef, useState } from "react";
import { FiLogOut } from "react-icons/fi";
import { GrUserManager } from "react-icons/gr";

import { useAuth } from "~/context/AuthContext";

type Props = {
  showAdminDashboard: boolean;
  onOpenAdminDashboard: () => void;
};

function initials(name?: string, email?: string): string {
  const source = [name?.trim(), email?.split("@")[0]].find(Boolean) ?? "?";
  const parts = source.split(/\s+/u).filter(Boolean);
  const letters = parts.length > 1 ? `${parts[0]![0]}${parts[parts.length - 1]![0]}` : source.slice(0, 2);
  return letters.toUpperCase();
}

export default function UserMenu({ showAdminDashboard, onOpenAdminDashboard }: Props) {
  const { user, signOut } = useAuth();
  const [open, setOpen] = useState(false);
  const ref = useRef<HTMLDivElement | null>(null);

  useEffect(() => {
    if (!open) return;
    const close = (e: MouseEvent) => {
      if (ref.current && !ref.current.contains(e.target as Node)) setOpen(false);
    };
    document.addEventListener("mousedown", close);
    return () => document.removeEventListener("mousedown", close);
  }, [open]);

  if (!user) return null;

  return (
    <div className="relative" ref={ref}>
      <button
        type="button"
        aria-label="Account menu"
        aria-expanded={open}
        onClick={() => setOpen((v) => !v)}
        className="flex h-8 w-8 items-center justify-center rounded-full bg-[#C41230] text-xs font-semibold text-white"
      >
        {initials(user.name, user.email)}
      </button>
      {open && (
        <div className="absolute right-0 z-50 mt-2 w-64 rounded-lg border border-gray-200 bg-white py-2 shadow-lg dark:border-[#262A32] dark:bg-[#1C1F26]">
          <div className="px-4 pb-2 text-sm">
            {user.name && <p className="font-medium text-gray-900 dark:text-gray-100">{user.name}</p>}
            {user.email && <p className="truncate text-gray-500 dark:text-gray-400">{user.email}</p>}
          </div>
          <div className="border-t border-gray-100 dark:border-[#262A32]" />
          {showAdminDashboard && (
            <button
              type="button"
              onClick={() => {
                setOpen(false);
                onOpenAdminDashboard();
              }}
              className="flex w-full items-center gap-3 px-4 py-2 text-left text-sm text-gray-700 hover:bg-gray-100 dark:text-gray-200 dark:hover:bg-[#232733]"
            >
              <GrUserManager /> Open Admin Dashboard
            </button>
          )}
          <button
            type="button"
            onClick={() => void signOut()}
            className="flex w-full items-center gap-3 px-4 py-2 text-left text-sm text-gray-700 hover:bg-gray-100 dark:text-gray-200 dark:hover:bg-[#232733]"
          >
            <FiLogOut /> Sign out
          </button>
        </div>
      )}
    </div>
  );
}
