"use client";

import { useState, useEffect, useRef, useCallback } from "react";
import { Button } from "@/components/ui/button";
import { Video, PlusCircle, ChevronUp, ChevronDown } from "lucide-react";
import { VideoPlayer } from "@/components/video-player";
import { useVideoIntersection } from "@/hooks/useVideoIntersection";
import { toast } from "sonner";
import { getVideos, VideoStatus } from "@/lib/api";
import type { Video as VideoType } from "@/lib/api";
import Link from "next/link";

export default function ExplorePage() {
  const [reels, setReels] = useState<VideoType[]>([]);
  const [hasMore, setHasMore] = useState(true);
  const [loading, setLoading] = useState(true);
  const [loadingMore, setLoadingMore] = useState(false);
  const [mutedVideos, setMutedVideos] = useState<Record<string, boolean>>({});
  const [playing, setPlaying] = useState<Record<string, boolean>>({});
  const [activeReelId, setActiveReelId] = useState<string | null>(null);
  const [skip, setSkip] = useState(0);
  const [currentIndex, setCurrentIndex] = useState(0);
  const LIMIT = 5;
  const videoRefs = useRef<Record<string, HTMLVideoElement | null>>({});
  const containerRef = useRef<HTMLDivElement>(null);
  const scrollTimeoutRef = useRef<NodeJS.Timeout | null>(null);

  // Video intersection handling
  const handleVideoEnter = useCallback((id: string) => {
    setActiveReelId(id);
    setPlaying(prev => ({ ...prev, [id]: true }));
    
    // Pause other videos
    Object.keys(playing).forEach(videoId => {
      if (videoId !== id && playing[videoId]) {
        const videoEl = videoRefs.current[videoId];
        if (videoEl) {
          videoEl.pause();
          setPlaying(prev => ({ ...prev, [videoId]: false }));
        }
      }
    });

    // Play current video
    const videoEl = videoRefs.current[id];
    if (videoEl) {
      const playPromise = videoEl.play();
      if (playPromise) {
        playPromise.catch(err => {
          console.warn("Autoplay prevented:", err);
          setMutedVideos(prev => ({ ...prev, [id]: true }));
          videoEl.muted = true;
          videoEl.play().catch(e => console.error("Muted autoplay failed:", e));
        });
      }
    }
  }, [playing]);

  const handleVideoLeave = useCallback((id: string) => {
    const videoEl = videoRefs.current[id];
    if (videoEl) {
      videoEl.pause();
      setPlaying(prev => ({ ...prev, [id]: false }));
    }
  }, []);

  const { observeElement, unobserveElement } = useVideoIntersection({
    onVideoEnter: handleVideoEnter,
    onVideoLeave: handleVideoLeave,
    threshold: 0.8,
    rootMargin: '-5% 0px'
  });

  useEffect(() => {
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
      
      // Initialize all videos as muted by default for autoplay
      const initialMutedState: Record<string, boolean> = {};
      videos.forEach(video => {
        initialMutedState[video.id] = true;
      });
      setMutedVideos(initialMutedState);
      
      setSkip(videos.length);
      setLoading(false);
      
      if (videos.length > 0) {
        setActiveReelId(videos[0].id);
      }
    } catch (error) {
      console.error("Failed to load videos:", error);
      setLoading(false);
      toast.error("Failed to load videos");
      setReels([]);
    }
  };

  const loadMoreReels = useCallback(async () => {
    if (loadingMore || !hasMore) return;
    
    setLoadingMore(true);
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
      
      // Initialize new videos as muted by default
      const newMutedState = {...mutedVideos};
      videos.forEach(video => {
        newMutedState[video.id] = true;
      });
      setMutedVideos(newMutedState);
      
      setReels((prev) => [...prev, ...videos]);
      setSkip(prev => prev + videos.length);
    } catch (error) {
      console.error("Failed to load more videos:", error);
      toast.error("Failed to load more videos");
    } finally {
      setLoadingMore(false);
    }
  }, [loadingMore, hasMore, skip, mutedVideos]);

  // Smooth scroll to next/previous video
  const scrollToVideo = useCallback((index: number) => {
    if (containerRef.current && index >= 0 && index < reels.length) {
      const container = containerRef.current;
      const targetScrollTop = index * window.innerHeight;
      
      container.scrollTo({
        top: targetScrollTop,
        behavior: 'smooth'
      });
      setCurrentIndex(index);
    }
  }, [reels.length]);

  // Video control handlers
  const handlePlayToggle = useCallback((reelId: string) => {
    const videoEl = videoRefs.current[reelId];
    const isCurrentlyPlaying = playing[reelId];

    if (videoEl) {
      if (isCurrentlyPlaying) {
        videoEl.pause();
        setPlaying(prev => ({ ...prev, [reelId]: false }));
      } else {
        const playPromise = videoEl.play();
        if (playPromise) {
          playPromise
            .then(() => {
              setPlaying(prev => ({ ...prev, [reelId]: true }));
            })
            .catch(err => {
              console.warn("Play failed:", err);
              setMutedVideos(prev => ({ ...prev, [reelId]: true }));
              videoEl.muted = true;
              videoEl.play().then(() => {
                setPlaying(prev => ({ ...prev, [reelId]: true }));
              });
            });
        }
      }
    }
  }, [playing]);

  const handleMuteToggle = useCallback((reelId: string) => {
    const videoEl = videoRefs.current[reelId];
    const newMutedState = !mutedVideos[reelId];
    
    setMutedVideos(prev => ({ ...prev, [reelId]: newMutedState }));
    
    if (videoEl) {
      videoEl.muted = newMutedState;
    }
  }, [mutedVideos]);

  // Handle keyboard navigation
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      switch (e.key) {
        case 'ArrowUp':
          e.preventDefault();
          scrollToVideo(Math.max(0, currentIndex - 1));
          break;
        case 'ArrowDown':
          e.preventDefault();
          if (currentIndex === reels.length - 2 && hasMore) {
            loadMoreReels();
          }
          scrollToVideo(Math.min(reels.length - 1, currentIndex + 1));
          break;
        case ' ':
          e.preventDefault();
          if (activeReelId) {
            handlePlayToggle(activeReelId);
          }
          break;
        case 'm':
        case 'M':
          e.preventDefault();
          if (activeReelId) {
            handleMuteToggle(activeReelId);
          }
          break;
      }
    };

    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [currentIndex, reels.length, hasMore, activeReelId, loadMoreReels, scrollToVideo, handlePlayToggle, handleMuteToggle]);

  // Handle scroll events for auto-loading
  const handleScroll = useCallback(() => {
    if (!containerRef.current) return;
    
    const { scrollTop, scrollHeight, clientHeight } = containerRef.current;
    const scrollPercentage = (scrollTop + clientHeight) / scrollHeight;
    
    // Load more when 80% scrolled
    if (scrollPercentage > 0.8 && hasMore && !loadingMore) {
      loadMoreReels();
    }

    // Update current index based on scroll position
    const newIndex = Math.round(scrollTop / window.innerHeight);
    if (newIndex !== currentIndex && newIndex >= 0 && newIndex < reels.length) {
      setCurrentIndex(newIndex);
    }

    // Debounced scroll handling for snap effect
    if (scrollTimeoutRef.current) {
      clearTimeout(scrollTimeoutRef.current);
    }
    scrollTimeoutRef.current = setTimeout(() => {
      const snapIndex = Math.round(scrollTop / window.innerHeight);
      if (Math.abs(scrollTop - snapIndex * window.innerHeight) > 10) {
        scrollToVideo(snapIndex);
      }
    }, 150);
  }, [currentIndex, reels.length, hasMore, loadingMore, loadMoreReels, scrollToVideo]);

  const handleVideoRef = useCallback((reelId: string) => (ref: HTMLVideoElement | null) => {
    videoRefs.current[reelId] = ref;
  }, []);

  // Setup intersection observer for video elements
  useEffect(() => {
    reels.forEach((reel) => {
      const element = document.querySelector(`[data-video-id="${reel.id}"]`);
      if (element) {
        observeElement(reel.id, element);
      }
    });

    return () => {
      reels.forEach(reel => {
        unobserveElement(reel.id);
      });
    };
  }, [reels, observeElement, unobserveElement]);

  // Add scroll listener
  useEffect(() => {
    const container = containerRef.current;
    if (container) {
      container.addEventListener('scroll', handleScroll, { passive: true });
      return () => container.removeEventListener('scroll', handleScroll);
    }
  }, [handleScroll]);

  // Loading state
  if (loading) {
    return (
      <div className="flex-1 flex items-center justify-center gradient-bg min-h-screen">
        <div className="text-center">
          <div className="inline-flex items-center justify-center p-4 rounded-full sports-gradient text-white mb-4 animate-pulse-slow">
            <Video size={32} />
          </div>
          <h2 className="text-xl font-semibold mb-2">Loading Amazing Reels...</h2>
          <div className="flex items-center justify-center gap-2">
            <div className="w-3 h-3 bg-primary rounded-full animate-bounce" style={{ animationDelay: '0ms' }}></div>
            <div className="w-3 h-3 bg-primary rounded-full animate-bounce" style={{ animationDelay: '150ms' }}></div>
            <div className="w-3 h-3 bg-primary rounded-full animate-bounce" style={{ animationDelay: '300ms' }}></div>
          </div>
        </div>
      </div>
    );
  }

  // Empty state
  if (reels.length === 0) {
    return (
      <div className="flex-1 flex flex-col items-center justify-center p-4 gradient-bg min-h-screen">
        <div className="text-center max-w-md animate-fade-in">
          <div className="inline-flex items-center justify-center p-4 rounded-full sports-gradient text-white mb-6 animate-float">
            <Video size={48} />
          </div>
          <h2 className="text-3xl font-bold mb-4 bg-clip-text text-transparent sports-gradient">No Reels Yet</h2>
          <p className="text-center text-muted-foreground mb-8 text-lg">
            Be the first to create an amazing AI-generated sports celebrity reel and inspire others!
          </p>
          <Link href="/create">
            <Button className="sports-gradient text-white px-8 py-4 text-lg hover:scale-105 transition-transform">
              <PlusCircle size={20} className="mr-2" />
              Create Your First Reel
            </Button>
          </Link>
        </div>
      </div>
    );
  }

  return (
    <div className="h-screen w-full overflow-hidden relative bg-black video-container">
      {/* Main scroll container */}
      <div 
        ref={containerRef}
        className="h-full w-full overflow-y-auto snap-y snap-mandatory scroll-smooth contain-layout"
        style={{ scrollbarWidth: 'none', msOverflowStyle: 'none' }}
      >
        <style jsx>{`
          div::-webkit-scrollbar {
            display: none;
          }
        `}</style>
        
        {reels.map((reel) => (
          <div 
            key={reel.id}
            data-video-id={reel.id}
            className="w-full h-screen snap-start snap-always flex items-center justify-center relative gpu-accelerated"
          >
            <div className="w-full h-full max-w-md mx-auto relative contain-paint">
              <VideoPlayer
                reel={reel}
                isActive={activeReelId === reel.id}
                isPlaying={playing[reel.id] || false}
                isMuted={mutedVideos[reel.id] || false}
                onPlayToggle={() => handlePlayToggle(reel.id)}
                onMuteToggle={() => handleMuteToggle(reel.id)}
                onVideoRef={handleVideoRef(reel.id)}
              />
            </div>
          </div>
        ))}

        {/* Loading more indicator */}
        {loadingMore && (
          <div className="w-full h-32 flex items-center justify-center">
            <div className="flex items-center gap-2 text-white">
              <div className="animate-spin rounded-full h-6 w-6 border-t-2 border-b-2 border-white"></div>
              <span>Loading more reels...</span>
            </div>
          </div>
        )}

        {/* End message */}
        {!hasMore && reels.length > 0 && (
          <div className="w-full h-32 flex items-center justify-center">
            <div className="text-center text-white/70">
              <p className="text-sm">You&apos;ve reached the end!</p>
              <Link href="/create">
                <Button variant="outline" className="mt-2 text-white border-white/30 hover:bg-white/10">
                  Create New Reel
                </Button>
              </Link>
            </div>
          </div>
        )}
      </div>

      {/* Navigation hints */}
      <div className="fixed right-4 top-1/2 transform -translate-y-1/2 z-40 flex flex-col gap-2">
        <Button
          variant="ghost"
          size="icon"
          className="text-white/60 glass-effect rounded-full h-10 w-10 hover:text-white hover:scale-110 transition-all"
          onClick={() => scrollToVideo(Math.max(0, currentIndex - 1))}
          disabled={currentIndex === 0}
        >
          <ChevronUp size={20} />
        </Button>
        <Button
          variant="ghost"
          size="icon"
          className="text-white/60 glass-effect rounded-full h-10 w-10 hover:text-white hover:scale-110 transition-all"
          onClick={() => {
            if (currentIndex === reels.length - 2 && hasMore) {
              loadMoreReels();
            }
            scrollToVideo(Math.min(reels.length - 1, currentIndex + 1));
          }}
          disabled={currentIndex === reels.length - 1 && !hasMore}
        >
          <ChevronDown size={20} />
        </Button>
      </div>

      {/* Video index indicator */}
      <div className="fixed bottom-6 left-1/2 transform -translate-x-1/2 z-40">
        <div className="flex gap-1">
          {reels.slice(Math.max(0, currentIndex - 2), Math.min(reels.length, currentIndex + 3)).map((_, idx) => {
            const realIndex = Math.max(0, currentIndex - 2) + idx;
            return (
              <div
                key={realIndex}
                className={`h-1 rounded-full transition-all duration-300 ${
                  realIndex === currentIndex 
                    ? 'w-8 bg-white' 
                    : 'w-2 bg-white/40'
                }`}
              />
            );
          })}
        </div>
      </div>

      {/* Keyboard shortcuts hint */}
      <div className="fixed top-4 left-4 z-40 text-white/60 text-xs">
        <div className="glass-effect p-2 rounded-lg">
          <p>↑↓ Navigate • Space Play/Pause • M Mute</p>
        </div>
      </div>
    </div>
  );
}