"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { Button } from "./ui/button";
import { Video, PlusCircle, Home } from "lucide-react";

export function Navigation() {
  const pathname = usePathname();

  return (
    <nav className="fixed bottom-0 left-0 right-0 z-50 flex justify-evenly items-center h-20 glass-effect border-t border-border/20 md:top-0 md:bottom-auto md:h-16 md:border-b md:border-t-0 shadow-lg">
      <Link href="/" className="flex-1 md:flex-initial">
        <Button
          variant="ghost"
          className={`flex flex-col items-center justify-center gap-1 h-full w-full md:w-auto px-4 py-2 rounded-none md:rounded-xl transition-all duration-300 hover:scale-105 ${
            pathname === "/" 
              ? "sports-gradient text-white shadow-lg transform scale-105" 
              : "hover:bg-accent/50"
          }`}
          size="sm"
        >
          <Home size={pathname === "/" ? 26 : 24} className={`transition-all ${pathname === "/" ? "animate-pulse-slow" : ""}`} />
          <span className={`text-xs font-medium ${pathname === "/" ? "font-semibold" : ""}`}>Home</span>
        </Button>
      </Link>
      <Link href="/explore" className="flex-1 md:flex-initial">
        <Button
          variant="ghost"
          className={`flex flex-col items-center justify-center gap-1 h-full w-full md:w-auto px-4 py-2 rounded-none md:rounded-xl transition-all duration-300 hover:scale-105 ${
            pathname === "/explore" 
              ? "sports-gradient text-white shadow-lg transform scale-105" 
              : "hover:bg-accent/50"
          }`}
          size="sm"
        >
          <Video size={pathname === "/explore" ? 26 : 24} className={`transition-all ${pathname === "/explore" ? "animate-pulse-slow" : ""}`} />
          <span className={`text-xs font-medium ${pathname === "/explore" ? "font-semibold" : ""}`}>Explore</span>
        </Button>
      </Link>
      <Link href="/create" className="flex-1 md:flex-initial">
        <Button
          variant="ghost"
          className={`flex flex-col items-center justify-center gap-1 h-full w-full md:w-auto px-4 py-2 rounded-none md:rounded-xl transition-all duration-300 hover:scale-105 ${
            pathname === "/create" 
              ? "sports-gradient text-white shadow-lg transform scale-105" 
              : "hover:bg-accent/50"
          }`}
          size="sm"
        >
          <PlusCircle size={pathname === "/create" ? 26 : 24} className={`transition-all ${pathname === "/create" ? "animate-pulse-slow" : ""}`} />
          <span className={`text-xs font-medium ${pathname === "/create" ? "font-semibold" : ""}`}>Create</span>
        </Button>
      </Link>
    </nav>
  );
}