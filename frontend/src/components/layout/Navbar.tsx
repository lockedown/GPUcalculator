"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { Cpu, Grid3X3, LayoutDashboard, Menu, TrendingDown, BookOpen } from "lucide-react";
import { cn } from "@/lib/utils";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Sheet, SheetTrigger, SheetContent } from "@/components/ui/sheet";
import { useState } from "react";

const NAV_ITEMS = [
  { href: "/", label: "Dashboard", icon: LayoutDashboard },
  { href: "/hardware", label: "Hardware", icon: Cpu },
  { href: "/benchmarks", label: "Benchmarks", icon: Grid3X3 },
  { href: "/prices", label: "Prices", icon: TrendingDown },
  { href: "/methodology", label: "Methodology", icon: BookOpen },
];

export default function Navbar() {
  const pathname = usePathname();
  const [open, setOpen] = useState(false);

  const navLinks = NAV_ITEMS.map(({ href, label, icon: Icon }) => {
    const active = pathname === href;
    return (
      <Link
        key={href}
        href={href}
        onClick={() => setOpen(false)}
        className={cn(
          "flex items-center gap-2 rounded-md px-3 py-2 text-xs font-medium transition-colors",
          active
            ? "bg-blue-50 text-blue-700"
            : "text-gray-500 hover:bg-gray-50 hover:text-gray-900"
        )}
      >
        <Icon className="h-3.5 w-3.5" />
        {label}
      </Link>
    );
  });

  return (
    <header className="sticky top-0 z-50 border-b border-gray-200 bg-white/80 backdrop-blur-md">
      <div className="mx-auto flex h-14 max-w-[1800px] items-center gap-4 px-4 sm:gap-6 sm:px-6">
        {/* Mobile menu */}
        <Sheet open={open} onOpenChange={setOpen}>
          <SheetTrigger asChild>
            <Button variant="ghost" size="icon" className="sm:hidden">
              <Menu className="h-5 w-5" />
              <span className="sr-only">Menu</span>
            </Button>
          </SheetTrigger>
          <SheetContent side="left">
            <div className="flex items-center gap-2 mb-6">
              <Cpu className="h-5 w-5 text-blue-600" />
              <span className="text-sm font-semibold text-gray-900">GPU Optimizer</span>
            </div>
            <nav className="flex flex-col gap-1">{navLinks}</nav>
          </SheetContent>
        </Sheet>

        <Link href="/" className="flex items-center gap-2 font-semibold tracking-tight text-gray-900">
          <Cpu className="h-5 w-5 text-blue-600" />
          <span className="text-sm hidden xs:inline">GPU Optimizer</span>
        </Link>

        <nav className="hidden sm:flex items-center gap-1">{navLinks}</nav>

        <div className="ml-auto flex items-center gap-3">
          <Badge variant="success" className="rounded-full">
            API Connected
          </Badge>
        </div>
      </div>
    </header>
  );
}
