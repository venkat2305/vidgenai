import { Button } from "@/components/ui/button";
import Link from "next/link";
import { Video, PlusCircle, Zap, Trophy, Star, Play } from "lucide-react";

export default function Home() {
  return (
    <div className="flex flex-col items-center justify-center flex-1 px-4 py-12 text-center gradient-bg min-h-screen">
      <div className="animate-fade-in">
        <div className="flex items-center justify-center mb-6">
          <div className="relative">
            <div className="absolute -inset-4 sports-gradient rounded-full blur opacity-30 animate-pulse-slow"></div>
            <div className="relative bg-background rounded-full p-4 border-2 border-primary/20">
              <Play size={40} className="text-primary animate-float" />
            </div>
          </div>
        </div>
        
        <h1 className="text-5xl md:text-6xl font-bold tracking-tight mb-4 bg-clip-text text-transparent sports-gradient">
          VidGenAI
        </h1>
        <p className="text-xl md:text-2xl mb-8 text-muted-foreground max-w-3xl">
          Create Epic Sports Celebrity History Reels with AI
        </p>
      </div>
      
      <div className="flex flex-col sm:flex-row gap-4 mb-16 animate-slide-up">
        <Link href="/explore">
          <Button size="lg" className="flex items-center gap-2 text-lg px-8 py-6 hover-lift sports-gradient">
            <Video size={20} />
            Explore Reels
          </Button>
        </Link>
        
        <Link href="/create">
          <Button size="lg" variant="outline" className="flex items-center gap-2 text-lg px-8 py-6 hover-lift glass-effect">
            <PlusCircle size={20} />
            Create New Reel
          </Button>
        </Link>
      </div>
      
      <div className="max-w-6xl w-full animate-scale-in">
        <h2 className="text-3xl font-semibold mb-8 text-center">How It Works</h2>
        <div className="grid grid-cols-1 md:grid-cols-3 gap-8">
          <div className="sports-card p-6 rounded-2xl hover-lift group">
            <div className="flex items-center justify-center mb-4">
              <div className="p-3 rounded-full sports-gradient text-white group-hover:scale-110 transition-transform">
                <Zap size={24} />
              </div>
            </div>
            <h3 className="font-semibold text-lg mb-3">1. AI-Powered Creation</h3>
            <p className="text-muted-foreground">
              Generate compelling scripts and videos about your favorite sports celebrities using advanced AI technology.
            </p>
          </div>
          
          <div className="sports-card p-6 rounded-2xl hover-lift group">
            <div className="flex items-center justify-center mb-4">
              <div className="p-3 rounded-full sports-gradient text-white group-hover:scale-110 transition-transform">
                <Trophy size={24} />
              </div>
            </div>
            <h3 className="font-semibold text-lg mb-3">2. Professional Quality</h3>
            <p className="text-muted-foreground">
              Your reels are professionally composed with dynamic effects, subtitles, and stored securely in the cloud.
            </p>
          </div>
          
          <div className="sports-card p-6 rounded-2xl hover-lift group">
            <div className="flex items-center justify-center mb-4">
              <div className="p-3 rounded-full sports-gradient text-white group-hover:scale-110 transition-transform">
                <Star size={24} />
              </div>
            </div>
            <h3 className="font-semibold text-lg mb-3">3. Share & Discover</h3>
            <p className="text-muted-foreground">
              Browse incredible reels from the community and share your creations in a smooth, mobile-optimized experience.
            </p>
          </div>
        </div>
      </div>
      
      <div className="mt-16 max-w-4xl animate-fade-in">
        <div className="glass-effect p-8 rounded-3xl">
          <h3 className="text-2xl font-semibold mb-4">Ready to Create Your First Reel?</h3>
          <p className="text-muted-foreground mb-6">
            Join thousands of sports fans creating amazing AI-generated content about their favorite athletes.
          </p>
          <Link href="/create">
            <Button size="lg" className="sports-gradient text-white hover:scale-105 transition-transform">
              Get Started Now
            </Button>
          </Link>
        </div>
      </div>
    </div>
  );
}
