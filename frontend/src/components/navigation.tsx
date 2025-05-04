"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { Button } from "./ui/button";
import { Video, PlusCircle, Home } from "lucide-react";

export function Navigation() {
  const pathname = usePathname();

  return (
    <nav className="fixed bottom-0 left-0 right-0 z-50 flex justify-evenly items-center h-16 bg-background border-t border-border md:top-0 md:bottom-auto md:h-16 md:border-b md:border-t-0 shadow-sm">
      <Link href="/" className="flex-1 md:flex-initial">
        <Button
          variant={pathname === "/" ? "default" : "ghost"}
          className={`flex flex-col items-center justify-center gap-2 h-full w-full md:w-auto px-4 py-2 rounded-none md:rounded-lg transition-all duration-200 ${
            pathname === "/" ? "bg-primary text-primary-foreground" : "bg-secondary/50"
          }`}
          size="sm"
        >
          <Home size={24} />
          <span className="text-sm font-medium">Home</span>
        </Button>
      </Link>
      <Link href="/explore" className="flex-1 md:flex-initial">
        <Button
          variant={pathname === "/explore" ? "default" : "ghost"}
          className={`flex flex-col items-center justify-center gap-2 h-full w-full md:w-auto px-4 py-2 rounded-none md:rounded-lg transition-all duration-200 ${
            pathname === "/explore" ? "bg-primary text-primary-foreground" : "bg-secondary/50"
          }`}
          size="sm"
        >
          <Video size={24} />
          <span className="text-sm font-medium">Explore</span>
        </Button>
      </Link>
      <Link href="/create" className="flex-1 md:flex-initial">
        <Button
          variant={pathname === "/create" ? "default" : "ghost"}
          className={`flex flex-col items-center justify-center gap-2 h-full w-full md:w-auto px-4 py-2 rounded-none md:rounded-lg transition-all duration-200 ${
            pathname === "/create" ? "bg-primary text-primary-foreground" : "bg-secondary/50"
          }`}
          size="sm"
        >
          <PlusCircle size={24} />
          <span className="text-sm font-medium">Create</span>
        </Button>
      </Link>
    </nav>
  );
}