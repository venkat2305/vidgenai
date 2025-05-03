"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { Button } from "./ui/button";
import { Video, PlusCircle, Home } from "lucide-react";

export function Navigation() {
  const pathname = usePathname();

  return (
    <nav className="fixed bottom-0 left-0 right-0 z-50 flex justify-around items-center h-16 bg-background border-t border-border md:top-0 md:bottom-auto md:h-16 md:border-b md:border-t-0">
      <Link href="/">
        <Button 
          variant={pathname === "/" ? "default" : "ghost"} 
          className="flex flex-col items-center gap-1 h-full"
          size="sm"
        >
          <Home size={20} />
          <span className="text-xs">Home</span>
        </Button>
      </Link>
      <Link href="/explore">
        <Button 
          variant={pathname === "/explore" ? "default" : "ghost"} 
          className="flex flex-col items-center gap-1 h-full"
          size="sm"
        >
          <Video size={20} />
          <span className="text-xs">Explore</span>
        </Button>
      </Link>
      <Link href="/create">
        <Button 
          variant={pathname === "/create" ? "default" : "ghost"} 
          className="flex flex-col items-center gap-1 h-full"
          size="sm"
        >
          <PlusCircle size={20} />
          <span className="text-xs">Create</span>
        </Button>
      </Link>
    </nav>
  );
}