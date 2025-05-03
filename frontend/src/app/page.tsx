import { Button } from "@/components/ui/button";
import Link from "next/link";
import { Video, PlusCircle } from "lucide-react";

export default function Home() {
  return (
    <div className="flex flex-col items-center justify-center flex-1 px-4 py-12 text-center">
      <h1 className="text-4xl font-bold tracking-tight mb-4">VidGenAI</h1>
      <p className="text-xl mb-8">AI-Generated Sports Celebrity History Reels</p>
      
      <div className="flex flex-col sm:flex-row gap-4">
        <Link href="/explore">
          <Button size="lg" className="flex items-center gap-2">
            <Video size={18} />
            Explore Reels
          </Button>
        </Link>
        
        <Link href="/create">
          <Button size="lg" variant="outline" className="flex items-center gap-2">
            <PlusCircle size={18} />
            Create New Reel
          </Button>
        </Link>
      </div>
      
      <div className="mt-12 max-w-2xl">
        <h2 className="text-2xl font-semibold mb-4">How It Works</h2>
        <div className="grid grid-cols-1 md:grid-cols-3 gap-6 text-left">
          <div className="p-4 border rounded-lg">
            <h3 className="font-medium mb-2">1. Create</h3>
            <p className="text-sm opacity-80">Generate AI-powered scripts and videos about your favorite sports celebrities.</p>
          </div>
          
          <div className="p-4 border rounded-lg">
            <h3 className="font-medium mb-2">2. Store</h3>
            <p className="text-sm opacity-80">Your reels are securely stored in the cloud with all necessary metadata.</p>
          </div>
          
          <div className="p-4 border rounded-lg">
            <h3 className="font-medium mb-2">3. Share</h3>
            <p className="text-sm opacity-80">Browse and enjoy reels created by the community in a smooth, mobile-friendly interface.</p>
          </div>
        </div>
      </div>
    </div>
  );
}
