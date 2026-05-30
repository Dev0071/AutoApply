"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import {
  LayoutDashboard,
  FileText,
  User,
  Settings,
  Zap,
} from "lucide-react";
import { cn } from "@/lib/utils";

const NAV = [
  { href: "/dashboard",    label: "Dashboard",     icon: LayoutDashboard },
  { href: "/applications", label: "Applications",  icon: FileText },
  { href: "/profile",      label: "Profile",        icon: User },
  { href: "/settings",     label: "Settings",       icon: Settings },
];

export function Sidebar() {
  const pathname = usePathname();

  return (
    <aside className="w-[220px] shrink-0 h-screen sticky top-0 flex flex-col bg-[#fafafa] border-r border-gray-200 overflow-hidden">
      {/* Logo */}
      <div className="flex items-center gap-2.5 px-4 h-12 border-b border-gray-200 shrink-0">
        <div className="flex h-6 w-6 items-center justify-center rounded-md bg-indigo-600">
          <Zap className="h-3.5 w-3.5 text-white" strokeWidth={2.5} />
        </div>
        <span className="text-sm font-semibold text-gray-900 tracking-tight">AutoApply</span>
      </div>

      {/* Navigation */}
      <nav className="flex-1 px-2 py-3 space-y-0.5 overflow-y-auto">
        {NAV.map(({ href, label, icon: Icon }) => {
          const active = pathname === href || pathname.startsWith(href + "/");
          return (
            <Link
              key={href}
              href={href}
              className={cn(
                "flex items-center gap-2.5 px-2.5 py-1.5 rounded-md text-sm transition-colors",
                active
                  ? "bg-white text-gray-900 font-medium shadow-sm border border-gray-200"
                  : "text-gray-600 hover:bg-white hover:text-gray-900 hover:shadow-sm hover:border hover:border-gray-200"
              )}
            >
              <Icon
                className={cn("h-4 w-4 shrink-0", active ? "text-indigo-600" : "text-gray-400")}
                strokeWidth={active ? 2.5 : 2}
              />
              {label}
            </Link>
          );
        })}
      </nav>

      {/* Footer */}
      <div className="px-3 py-3 border-t border-gray-200 shrink-0">
        <div className="flex items-center gap-2.5">
          <div className="h-6 w-6 rounded-full bg-indigo-100 flex items-center justify-center shrink-0">
            <span className="text-xs font-semibold text-indigo-700">K</span>
          </div>
          <div className="min-w-0">
            <p className="text-xs font-medium text-gray-800 truncate">Kabiru Gacheru</p>
            <p className="text-xs text-gray-400 truncate">user-123</p>
          </div>
        </div>
      </div>
    </aside>
  );
}
