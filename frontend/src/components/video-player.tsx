"use client";

import { useState, useRef, useEffect, useCallback } from "react";
import { Button } from "@/components/ui/button";
import { Play, Volume2, VolumeX, ExternalLink, Share, Heart, RotateCcw } from "lucide-react";
import { toast } from "sonner";
import Link from "next/link";
import type { Video as VideoType } from "@/lib/api";

interface VideoPlayerProps {
  reel: VideoType;
  isActive: boolean;
  isPlaying: boolean;
  isMuted: boolean;
  onPlayToggle: () => void;
  onMuteToggle: () => void;
  onVideoRef: (ref: HTMLVideoElement | null) => void;
}

export function VideoPlayer({
  reel,
  isActive,
  isPlaying,
  isMuted,
  onPlayToggle,
  onMuteToggle,
  onVideoRef,
}: VideoPlayerProps) {
  const [progress, setProgress] = useState(0);
  const [duration, setDuration] = useState(0);
  const [buffered, setBuffered] = useState(0);
  const [isLoading, setIsLoading] = useState(true);
  const [showControls, setShowControls] = useState(true);
  const [lastTap, setLastTap] = useState(0);
  const [liked, setLiked] = useState(false);
  const videoRef = useRef<HTMLVideoElement>(null);
  const controlsTimeoutRef = useRef<NodeJS.Timeout | null>(null);

  // Auto-hide controls
  const resetControlsTimeout = useCallback(() => {
    if (controlsTimeoutRef.current) {
      clearTimeout(controlsTimeoutRef.current);
    }
    setShowControls(true);
    controlsTimeoutRef.current = setTimeout(() => {
      if (isPlaying) {
        setShowControls(false);
      }
    }, 3000);
  }, [isPlaying]);

  useEffect(() => {
    if (videoRef.current) {
      onVideoRef(videoRef.current);
    }
  }, [onVideoRef]);

  useEffect(() => {
    resetControlsTimeout();
    return () => {
      if (controlsTimeoutRef.current) {
        clearTimeout(controlsTimeoutRef.current);
      }
    };
  }, [resetControlsTimeout]);

  // Update progress
  const handleTimeUpdate = useCallback(() => {
    if (videoRef.current) {
      const currentTime = videoRef.current.currentTime;
      const duration = videoRef.current.duration;
      if (duration > 0) {
        setProgress((currentTime / duration) * 100);
      }
    }
  }, []);

  // Update buffered
  const handleProgress = useCallback(() => {
    if (videoRef.current && videoRef.current.buffered.length > 0) {
      const bufferedEnd = videoRef.current.buffered.end(videoRef.current.buffered.length - 1);
      const duration = videoRef.current.duration;
      if (duration > 0) {
        setBuffered((bufferedEnd / duration) * 100);
      }
    }
  }, []);

  // Handle video metadata
  const handleLoadedMetadata = useCallback(() => {
    if (videoRef.current) {
      setDuration(videoRef.current.duration);
    }
  }, []);

  // Handle loading states
  const handleWaiting = useCallback(() => setIsLoading(true), []);
  const handleCanPlay = useCallback(() => setIsLoading(false), []);

  // Double tap to like
  const handleDoubleTap = useCallback((e: React.TouchEvent | React.MouseEvent) => {
    e.preventDefault();
    e.stopPropagation();
    
    const now = Date.now();
    const DOUBLE_TAP_DELAY = 300;
    
    if (now - lastTap < DOUBLE_TAP_DELAY) {
      setLiked(!liked);
      toast.success(liked ? "Removed from favorites" : "Added to favorites");
    } else {
      onPlayToggle();
    }
    
    setLastTap(now);
    resetControlsTimeout();
  }, [lastTap, liked, onPlayToggle, resetControlsTimeout]);

  // Seek to position
  const handleSeek = useCallback((e: React.MouseEvent<HTMLDivElement>) => {
    if (videoRef.current) {
      const rect = e.currentTarget.getBoundingClientRect();
      const pos = (e.clientX - rect.left) / rect.width;
      videoRef.current.currentTime = pos * videoRef.current.duration;
    }
  }, []);

  // Format time
  const formatTime = useCallback((seconds: number) => {
    const mins = Math.floor(seconds / 60);
    const secs = Math.floor(seconds % 60);
    return `${mins}:${secs.toString().padStart(2, '0')}`;
  }, []);

  return (
    <div className="relative w-full h-full group video-container">
      {/* Video Element */}
      <video
        ref={videoRef}
        src={reel.video_url}
        poster={reel.thumbnail_url}
        className="absolute inset-0 w-full h-full object-cover video-performance-optimized"
        autoPlay={isActive && isPlaying}
        loop
        muted={isMuted}
        playsInline
        preload="metadata"
        onTimeUpdate={handleTimeUpdate}
        onProgress={handleProgress}
        onLoadedMetadata={handleLoadedMetadata}
        onWaiting={handleWaiting}
        onCanPlay={handleCanPlay}
        onTouchStart={handleDoubleTap}
        onClick={handleDoubleTap}
        onMouseMove={resetControlsTimeout}
      />

      {/* Gradient overlay */}
      <div className="absolute inset-0 bg-gradient-to-t from-black/60 via-transparent to-black/20" />

      {/* Loading indicator */}
      {isLoading && (
        <div className="absolute inset-0 flex items-center justify-center bg-black/20 z-30">
          <div className="animate-spin rounded-full h-12 w-12 border-t-2 border-b-2 border-white" />
        </div>
      )}

      {/* Center play/pause button */}
      <div className="absolute inset-0 flex items-center justify-center z-20">
        {!isPlaying && (
          <Button
            variant="ghost"
            size="icon"
            className={`h-20 w-20 text-white glass-effect rounded-full transition-all duration-300 ${
              showControls ? 'scale-100 opacity-100' : 'scale-75 opacity-50'
            }`}
            onClick={onPlayToggle}
          >
            <Play size={40} className="ml-1" />
          </Button>
        )}
      </div>

      {/* Top controls */}
      <div className={`absolute top-6 left-6 right-6 flex justify-between items-center z-30 transition-opacity duration-300 ${
        showControls ? 'opacity-100' : 'opacity-0'
      }`}>
        <Link href={`/video/${reel.id}`}>
          <Button
            variant="ghost"
            size="icon"
            className="text-white glass-effect rounded-full h-12 w-12 hover:scale-110 transition-transform shadow-lg"
          >
            <ExternalLink size={20} />
          </Button>
        </Link>

        <div className="flex gap-2">
          <Button
            variant="ghost"
            size="icon"
            className="text-white glass-effect rounded-full h-12 w-12 hover:scale-110 transition-transform shadow-lg"
            onClick={onMuteToggle}
          >
            {isMuted ? <VolumeX size={22} /> : <Volume2 size={22} />}
          </Button>
        </div>
      </div>

      {/* Bottom controls and info */}
      <div className={`absolute bottom-6 left-6 right-6 z-30 transition-opacity duration-300 ${
        showControls ? 'opacity-100' : 'opacity-0'
      }`}>
        {/* Progress bar */}
        <div className="mb-4">
          <div 
            className="w-full h-1 bg-white/30 rounded-full cursor-pointer overflow-hidden"
            onClick={handleSeek}
          >
            {/* Buffered indicator */}
            <div 
              className="h-full bg-white/50 transition-all duration-200"
              style={{ width: `${buffered}%` }}
            />
            {/* Progress indicator */}
            <div 
              className="h-full bg-white -mt-1 transition-all duration-200"
              style={{ width: `${progress}%` }}
            />
          </div>
          <div className="flex justify-between items-center mt-2 text-white text-xs">
            <span>{formatTime(progress * duration / 100)}</span>
            <span>{formatTime(duration)}</span>
          </div>
        </div>

        {/* Video info */}
        <div className="flex justify-between items-end">
          <div className="flex-1">
            <h3 className="text-white font-semibold text-lg mb-1 line-clamp-2">
              {reel.title}
            </h3>
            <p className="text-white/80 text-sm line-clamp-1">
              {reel.celebrity_name}
            </p>
          </div>

          {/* Action buttons */}
          <div className="flex flex-col gap-3 ml-4">
            <Button
              variant="ghost"
              size="icon"
              className={`text-white glass-effect rounded-full h-12 w-12 hover:scale-110 transition-all shadow-lg ${
                liked ? 'text-red-500' : ''
              }`}
              onClick={() => {
                setLiked(!liked);
                toast.success(liked ? "Removed from favorites" : "Added to favorites");
              }}
            >
              <Heart size={20} className={liked ? 'fill-current' : ''} />
            </Button>

            <Button
              variant="ghost"
              size="icon"
              className="text-white glass-effect rounded-full h-12 w-12 hover:scale-110 transition-transform shadow-lg"
              onClick={(e) => {
                e.preventDefault();
                e.stopPropagation();
                navigator.clipboard.writeText(`${window.location.origin}/video/${reel.id}`);
                toast.success("Link copied to clipboard!");
              }}
            >
              <Share size={20} />
            </Button>

            <Button
              variant="ghost"
              size="icon"
              className="text-white glass-effect rounded-full h-12 w-12 hover:scale-110 transition-transform shadow-lg"
              onClick={() => {
                if (videoRef.current) {
                  videoRef.current.currentTime = 0;
                  setProgress(0);
                }
              }}
            >
              <RotateCcw size={20} />
            </Button>
          </div>
        </div>
      </div>

      {/* Like animation */}
      {liked && (
        <div className="absolute inset-0 flex items-center justify-center pointer-events-none z-40">
          <Heart 
            size={80} 
            className="text-red-500 fill-current animate-ping opacity-75" 
          />
        </div>
      )}
    </div>
  );
}