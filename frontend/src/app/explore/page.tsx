"use client";

import { useState, useEffect, useRef, useCallback } from "react";
import { Card } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Play, Volume2, VolumeX, ExternalLink } from "lucide-react";
// import { Avatar, AvatarFallback, AvatarImage } from "@/components/ui/avatar";
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
  const [audioLoading, setAudioLoading] = useState<Record<string, boolean>>({});
  const [activeReelId, setActiveReelId] = useState<string | null>(null);
  const [skip, setSkip] = useState(0);
  const LIMIT = 10;
  const videoRefs = useRef<Record<string, HTMLVideoElement | null>>({});

  useEffect(() => {
    // Fetch videos when component mounts
    loadInitialVideos();
  }, []);

  const handleAudioLoading = useCallback((reelId: string, isLoading: boolean) => {
    setAudioLoading((prev) => ({ ...prev, [reelId]: isLoading }));
  }, []);

  const loadInitialVideos = async () => {
    try {
      const videos = await getVideos({ 
        skip: 0, 
        limit: LIMIT,
        status: VideoStatus.COMPLETED 
      });
      setReels(videos);
      
      // Initialize all videos as unmuted by default
      const initialMutedState: Record<string, boolean> = {};
      videos.forEach(video => {
        initialMutedState[video.id] = false;
      });
      setMutedVideos(initialMutedState);

      // Initialize audio loading state
      const initialAudioLoadingState: Record<string, boolean> = {};
      videos.forEach(video => {
        initialAudioLoadingState[video.id] = true;
      });
      setAudioLoading(initialAudioLoadingState);
      
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
      
      // Initialize new videos as unmuted by default
      const newMutedState = {...mutedVideos};
      videos.forEach(video => {
        newMutedState[video.id] = false;
      });
      setMutedVideos(newMutedState);

      // Initialize new audio loading state
      const newAudioLoadingState = { ...audioLoading };
      videos.forEach(video => {
        newAudioLoadingState[video.id] = true;
      });
      setAudioLoading(newAudioLoadingState);
      
      setReels((prev) => [...prev, ...videos]);
      setSkip(skip + videos.length);
    } catch (error) {
      console.error("Failed to load more videos:", error);
      toast.error("Failed to load more videos");
    }
  };

  const togglePlay = (reelId: string) => {
    // If turning on this video
    if (!playing[reelId]) {
      // Set this as active reel
      setActiveReelId(reelId);
      
      // Pause all other videos
      Object.keys(playing).forEach((id) => {
        if (id !== reelId && playing[id]) {
          pauseVideo(id);
        }
      });
    }
    
    setPlaying((prev) => ({
      ...prev,
      [reelId]: !prev[reelId],
    }));
  };

  const toggleMute = (reelId: string, e: React.MouseEvent) => {
    e.preventDefault();
    e.stopPropagation();
  
    setMutedVideos((m) => {
      const newMuted = !m[reelId];
      // Sync actual <video> element
      const videoEl = videoRefs.current[reelId];
      if (videoEl) {
        videoEl.muted = newMuted;
        // if unmuting, ensure it’s playing
        if (!newMuted && !playing[reelId]) {
          playVideo(reelId);
        }
      }
      return { ...m, [reelId]: newMuted };
    });
  };

  // Play the video for a specific reel
  const playVideo = useCallback(
    (reelId: string) => {
      const videoEl = videoRefs.current[reelId];
      if (!videoEl) return;
  
      // mark as playing
      setPlaying((prev) => ({ ...prev, [reelId]: true }));
  
      const playPromise = videoEl.play();
      if (playPromise !== undefined) {
        playPromise.catch((err) => {
          console.warn("Autoplay prevented:", err);
          // Mute via state to allow muted autoplay
          setMutedVideos((m) => ({ ...m, [reelId]: true }));
          // Try again muted
          videoEl.muted = true;
          videoEl
            .play()
            .catch((e) =>
              console.error("Muted autoplay still failed:", e)
            );
        });
      }
    },
    [setPlaying, setMutedVideos]
  );

  // Pause the video for a specific reel
  const pauseVideo = useCallback((reelId: string) => {
    const videoElement = videoRefs.current[reelId];
    if (videoElement) {
      videoElement.pause();
      setPlaying(prev => ({ ...prev, [reelId]: false }));
    }
  }, []);

  // Intersection Observer to autoplay videos when in view
  useEffect(() => {
    if (reels.length === 0) return;

    const observer = new IntersectionObserver(
      (entries) => {
        entries.forEach((entry) => {
          const reelId = entry.target.id;
          
          if (entry.isIntersecting) {
            // Only change active reel if it's different
            if (activeReelId !== reelId) {
              // Pause the current active reel if there is one
              if (activeReelId) {
                pauseVideo(activeReelId);
              }
              
              // Set new active reel and play it
              setActiveReelId(reelId);
              playVideo(reelId);
            } else if (!playing[reelId]) {
              // If same reel but not playing, play it
              playVideo(reelId);
            }
          } else if (playing[reelId]) {
            // Pause video when scrolling away
            pauseVideo(reelId);
          }
        });
      },
      { 
        threshold: 0.7, // Video is visible at 70%
        rootMargin: "-10% 0px" // Adds a bit of margin to improve scroll detection
      }
    );

    document.querySelectorAll(".reel-container").forEach((reel) => {
      observer.observe(reel);
    });

    return () => {
      document.querySelectorAll(".reel-container").forEach((reel) => {
        observer.unobserve(reel);
      });
    };
  }, [reels, playing, activeReelId, playVideo, pauseVideo]);

  // Track user interaction with the page to enable audio
  useEffect(() => {
    const handleUserInteraction = () => {
      document.documentElement.setAttribute('data-user-interacted', 'true');
      
      // Try to unmute current video if it exists
      if (activeReelId) {
        const videoElement = videoRefs.current[activeReelId];
        if (videoElement && videoElement.muted && !mutedVideos[activeReelId]) {
          videoElement.muted = false;
        }
      }
    };
    
    // Add listeners for common user interactions
    const events = ['click', 'touchstart', 'keydown'];
    events.forEach(event => {
      document.addEventListener(event, handleUserInteraction, { once: true });
    });
    
    return () => {
      events.forEach(event => {
        document.removeEventListener(event, handleUserInteraction);
      });
    };
  }, [activeReelId, mutedVideos]);

  // Reset videoRefs when reels change
  useEffect(() => {
    reels.forEach(reel => {
      if (!videoRefs.current[reel.id]) {
        videoRefs.current[reel.id] = null;
      }
    });
  }, [reels]);

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
        className="flex flex-col w-full snap-y snap-mandatory"
      >
        {reels.map((reel) => (
          <div 
            key={reel.id}
            id={reel.id}
            className="reel-container snap-start snap-always h-[calc(100vh-4rem)] w-full flex items-center justify-center relative"
          >
            {/* Audio loading overlay for individual reel */}
            {audioLoading[reel.id] && (
              <div className="absolute inset-0 bg-black/50 flex items-center justify-center z-30">
                <div className="animate-spin rounded-full h-8 w-8 border-t-2 border-b-2 border-white" />
              </div>
            )}
            <Card className="w-full h-full max-w-md mx-auto overflow-hidden relative">
              {reel.video_url ? (
                <video
                  ref={(el) => {
                    videoRefs.current[reel.id] = el;
                  }}
                  src={reel.video_url}
                  poster={reel.thumbnail_url}
                  className="absolute inset-0 w-full h-full object-cover"
                  autoPlay={playing[reel.id] || false}
                  loop
                  controls={false}
                  onWaiting={() => handleAudioLoading(reel.id, true)}
                  onCanPlay={() => handleAudioLoading(reel.id, false)}
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
              
              {/* <div className="absolute bottom-0 left-0 right-0 p-4 text-white z-10">
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
              </div> */}
              
              {/* Video controls */}
              <div className="absolute inset-0 flex items-center justify-center" onClick={() => togglePlay(reel.id)}>
                {!playing[reel.id] && (
                  <Button variant="ghost" size="icon" className="h-16 w-16 text-white bg-black/20 rounded-full">
                    <Play size={32} />
                  </Button>
                )}
              </div>
              
              {/* Sound control - unmuted by default */}
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
              
              {/* Link to detail page */}
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