"use client";

import { useState, useEffect } from "react";
import { Card } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Play, Volume2, VolumeX, ExternalLink } from "lucide-react";
import { Avatar, AvatarFallback, AvatarImage } from "@/components/ui/avatar";
import InfiniteScroll from "react-infinite-scroll-component";
import { toast } from "sonner";
import { getVideos, Video, VideoStatus } from "@/lib/api";
import Link from "next/link";

export default function ExplorePage() {
  const [reels, setReels] = useState<Video[]>([]);
  const [hasMore, setHasMore] = useState(true);
  const [mutedVideos, setMutedVideos] = useState<Record<string, boolean>>({});
  const [loading, setLoading] = useState(true);
  const [playing, setPlaying] = useState<Record<string, boolean>>({});
  const [skip, setSkip] = useState(0);
  const LIMIT = 10;

  useEffect(() => {
    // Fetch videos when component mounts
    loadInitialVideos();
  }, []);

  const loadInitialVideos = async () => {
    try {
      const videos = await getVideos({ 
        skip: 0, 
        limit: LIMIT,
        status: VideoStatus.COMPLETED 
      });
      setReels(videos);
      
      // Initialize all videos as muted
      const initialMutedState: Record<string, boolean> = {};
      videos.forEach(video => {
        initialMutedState[video.id] = true;
      });
      setMutedVideos(initialMutedState);
      
      setSkip(videos.length);
      setLoading(false);
    } catch (error) {
      console.error("Failed to load videos:", error);
      setLoading(false);
      toast.error("Failed to load videos");
      
      // Fallback to empty state
      setReels([]);
    }
  };

  const loadMoreReels = async () => {
    try {
      const videos = await getVideos({ 
        skip, 
        limit: LIMIT,
        status: VideoStatus.COMPLETED 
      });
      
      if (videos.length === 0) {
        setHasMore(false);
        return;
      }
      
      // Initialize new videos as muted
      const newMutedState = {...mutedVideos};
      videos.forEach(video => {
        newMutedState[video.id] = true;
      });
      setMutedVideos(newMutedState);
      
      setReels((prev) => [...prev, ...videos]);
      setSkip(skip + videos.length);
    } catch (error) {
      console.error("Failed to load more videos:", error);
      toast.error("Failed to load more videos");
    }
  };

  const togglePlay = (reelId: string) => {
    setPlaying((prev) => ({
      ...prev,
      [reelId]: !prev[reelId],
    }));
  };

  const toggleMute = (reelId: string, e: React.MouseEvent) => {
    e.preventDefault();
    e.stopPropagation();
    
    setMutedVideos((prev) => ({
      ...prev,
      [reelId]: !prev[reelId],
    }));
    
    // If unmuting, make sure the video is playing
    if (mutedVideos[reelId]) {
      setPlaying((prev) => ({
        ...prev,
        [reelId]: true,
      }));
    }
  };

  // Intersection Observer to autoplay videos when in view
  useEffect(() => {
    const observer = new IntersectionObserver(
      (entries) => {
        entries.forEach((entry) => {
          const reelId = entry.target.id;
          if (entry.isIntersecting) {
            setPlaying((prev) => ({
              ...prev,
              [reelId]: true,
            }));
            
            // Pause other videos
            Object.keys(playing).forEach((id) => {
              if (id !== reelId && playing[id]) {
                setPlaying((prev) => ({
                  ...prev,
                  [id]: false,
                }));
              }
            });
          }
        });
      },
      { threshold: 0.7 }
    );

    document.querySelectorAll(".reel-container").forEach((reel) => {
      observer.observe(reel);
    });

    return () => {
      document.querySelectorAll(".reel-container").forEach((reel) => {
        observer.unobserve(reel);
      });
    };
  }, [reels, playing]);

  if (loading) {
    return (
      <div className="flex-1 flex items-center justify-center">
        <div className="loading">
          <div className="loading-dot"></div>
          <div className="loading-dot"></div>
          <div className="loading-dot"></div>
        </div>
        <style jsx>{`
          .loading {
            display: flex;
            align-items: center;
            gap: 8px;
          }
          .loading-dot {
            width: 12px;
            height: 12px;
            background-color: #ccc;
            border-radius: 50%;
            animation: loading 1.2s infinite ease-in-out;
          }
          @keyframes loading {
            0%, 80%, 100% {
              transform: scale(0);
            }
            40% {
              transform: scale(1);
            }
          }
        `}</style>
      </div>
    );
  }

  if (reels.length === 0) {
    return (
      <div className="flex-1 flex flex-col items-center justify-center p-4">
        <h2 className="text-2xl font-semibold mb-4">No Reels Available</h2>
        <p className="text-center text-muted-foreground mb-8">
          There are no reels to display yet. Be the first to create an AI-generated sports celebrity reel!
        </p>
        <Link href="/create">
          <Button className="flex items-center gap-2">
            Create Your First Reel
          </Button>
        </Link>
      </div>
    );
  }

  return (
    <div className="h-full w-full">
      <h1 className="sr-only">Explore Sports Celebrity Reels</h1>
      
      <InfiniteScroll
        dataLength={reels.length}
        next={loadMoreReels}
        hasMore={hasMore}
        loader={<div className="text-center py-4">Loading more reels...</div>}
        endMessage={<div className="text-center py-4">No more reels to show</div>}
        className="flex flex-col w-full"
      >
        {reels.map((reel) => (
          <div 
            key={reel.id}
            id={reel.id}
            className="reel-container snap-start h-[calc(100vh-4rem)] w-full flex items-center justify-center relative"
          >
            <Card className="w-full h-full max-w-md mx-auto overflow-hidden relative">
              {reel.video_url ? (
                <video
                  src={reel.video_url}
                  poster={reel.thumbnail_url}
                  className="absolute inset-0 w-full h-full object-cover"
                  autoPlay={playing[reel.id] || false}
                  loop
                  controls={false}
                  muted={mutedVideos[reel.id]}
                  playsInline
                />
              ) : (
                // Fallback to thumbnail if video URL is not available
                <div 
                  className="absolute inset-0 bg-cover bg-center"
                  style={{ backgroundImage: `url(${reel.thumbnail_url})` }}
                />
              )}
              
              <div className="absolute inset-0 bg-black/30" />
              
              <div className="absolute bottom-0 left-0 right-0 p-4 text-white z-10">
                <div className="flex items-center gap-3 mb-3">
                  <Avatar>
                    <AvatarImage src={reel.thumbnail_url || `/placeholder-avatar.png`} alt={reel.celebrity_name} />
                    <AvatarFallback>{reel.celebrity_name[0]}</AvatarFallback>
                  </Avatar>
                  <div>
                    <h3 className="font-semibold">{reel.celebrity_name}</h3>
                    <p className="text-sm opacity-90">{reel.title}</p>
                  </div>
                </div>
              </div>
              
              {/* Video controls */}
              <div className="absolute inset-0 flex items-center justify-center" onClick={() => togglePlay(reel.id)}>
                {!playing[reel.id] && (
                  <Button variant="ghost" size="icon" className="h-16 w-16 text-white bg-black/20 rounded-full">
                    <Play size={32} />
                  </Button>
                )}
              </div>
              
              {/* Sound control - now works directly on explore page */}
              <div className="absolute top-4 right-4 z-20">
                <Button 
                  variant="ghost" 
                  size="icon" 
                  className="text-white" 
                  onClick={(e) => toggleMute(reel.id, e)}
                >
                  {mutedVideos[reel.id] ? <VolumeX size={20} /> : <Volume2 size={20} />}
                </Button>
              </div>
              
              {/* Link to detail page is now a visible button instead of wrapping the whole card */}
              <Link href={`/video/${reel.id}`} className="z-20">
                <Button 
                  variant="ghost" 
                  size="icon" 
                  className="absolute top-4 left-4 text-white bg-black/20 rounded-full h-10 w-10 p-0"
                >
                  <ExternalLink size={18} />
                </Button>
              </Link>
              
              <Button 
                variant="ghost" 
                className="absolute bottom-24 right-4 text-white bg-black/20 rounded-full h-10 w-10 p-0 z-20"
                onClick={(e) => {
                  e.preventDefault();
                  e.stopPropagation();
                  navigator.clipboard.writeText(`${window.location.origin}/video/${reel.id}`);
                  toast.success("Link copied to clipboard!");
                }}
              >
                <svg xmlns="http://www.w3.org/2000/svg" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                  <path d="M4 12v8a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2v-8"></path>
                  <polyline points="16 6 12 2 8 6"></polyline>
                  <line x1="12" y1="2" x2="12" y2="15"></line>
                </svg>
              </Button>
            </Card>
          </div>
        ))}
      </InfiniteScroll>
    </div>
  );
}