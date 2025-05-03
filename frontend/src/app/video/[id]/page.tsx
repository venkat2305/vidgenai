"use client";

import { useState, useEffect, useRef } from "react";
import { useParams, useRouter } from "next/navigation";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Avatar, AvatarFallback, AvatarImage } from "@/components/ui/avatar";
import { Volume2, VolumeX, ArrowLeft, Share2 } from "lucide-react";
import Link from "next/link";
import { toast } from "sonner";
import { getVideo, Video, VideoStatus } from "@/lib/api";

export default function VideoPage() {
  const { id } = useParams();
  const videoId = Array.isArray(id) ? id[0] : id;
  const [videoData, setVideoData] = useState<Video | null>(null);
  const [loading, setLoading] = useState(true);
  const [muted, setMuted] = useState(false);
  const [playing, setPlaying] = useState(true);
  const videoRef = useRef<HTMLVideoElement>(null);
  const router = useRouter();
  const pollingIntervalRef = useRef<NodeJS.Timeout | null>(null);

  useEffect(() => {
    // Fetch the video data initially
    fetchVideoData();

    // Set up polling for video status updates if needed
    pollingIntervalRef.current = setInterval(() => {
      fetchVideoData();
    }, 5000); // Poll every 5 seconds

    return () => {
      // Clean up the polling interval when component unmounts
      if (pollingIntervalRef.current) {
        clearInterval(pollingIntervalRef.current);
      }
    };
  }, [videoId]);

  // Function to fetch video data from API
  const fetchVideoData = async () => {
    try {
      const data = await getVideo(videoId);
      setVideoData(data);

      // If video is completed or failed, we can stop polling
      if (data.status === VideoStatus.COMPLETED || data.status === VideoStatus.FAILED) {
        if (pollingIntervalRef.current) {
          clearInterval(pollingIntervalRef.current);
          pollingIntervalRef.current = null;
        }
      }

      setLoading(false);
    } catch (error) {
      console.error(`Error fetching video ${videoId}:`, error);
      setLoading(false);
      toast.error("Failed to load video data");
    }
  };

  const toggleMute = () => {
    setMuted(!muted);
    if (videoRef.current) {
      videoRef.current.muted = !muted;
    }
  };

  const togglePlay = () => {
    setPlaying(!playing);
    if (videoRef.current) {
      if (playing) {
        videoRef.current.pause();
      } else {
        videoRef.current.play();
      }
    }
  };

  const handleShare = () => {
    const shareUrl = window.location.href;
    navigator.clipboard.writeText(shareUrl);
    toast.success("Link copied to clipboard", {
      description: "Share this reel with friends",
    });
  };

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
            border-radius: 50%;
            background-color: currentColor;
            opacity: 0.3;
            animation: loading 1.4s infinite ease-in-out both;
          }
          .loading-dot:nth-child(1) {
            animation-delay: -0.32s;
          }
          .loading-dot:nth-child(2) {
            animation-delay: -0.16s;
          }
          @keyframes loading {
            0%, 80%, 100% {
              transform: scale(0);
            }
            40% {
              transform: scale(1);
              opacity: 1;
            }
          }
        `}</style>
      </div>
    );
  }

  if (!videoData) {
    return (
      <div className="flex flex-col items-center justify-center flex-1 p-4">
        <h2 className="text-2xl font-semibold mb-4">Video Not Found</h2>
        <p className="text-center text-muted-foreground mb-6">
          The video you're looking for doesn't exist or has been removed.
        </p>
        <Link href="/explore">
          <Button>Back to Explore</Button>
        </Link>
      </div>
    );
  }

  // Render different UI based on video status
  if (videoData.status !== VideoStatus.COMPLETED) {
    // Video is still being generated
    return (
      <div className="container max-w-md mx-auto flex flex-col flex-1 p-4">
        <div className="flex items-center mb-6">
          <Link href="/explore">
            <Button variant="ghost" size="icon" className="rounded-full">
              <ArrowLeft />
            </Button>
          </Link>
          <h1 className="text-xl font-semibold ml-2">Video Generation</h1>
        </div>

        <Card className="p-6">
          <h2 className="text-lg font-medium mb-4">{videoData.title}</h2>
          <p className="text-sm text-muted-foreground mb-6">
            Celebrity: {videoData.celebrity_name}
          </p>

          <div className="mb-8">
            <div className="flex justify-between text-sm mb-2">
              <span>
                {videoData.status === VideoStatus.FAILED 
                  ? "Generation Failed" 
                  : "Generating your video..."}
              </span>
              <span>{videoData.progress}%</span>
            </div>
            <div className="w-full bg-gray-200 rounded-full h-2.5">
              <div 
                className={`h-2.5 rounded-full transition-all duration-300 ${
                  videoData.status === VideoStatus.FAILED 
                    ? "bg-red-600" 
                    : "bg-blue-600"
                }`} 
                style={{ width: `${videoData.progress}%` }}
              ></div>
            </div>
            {videoData.status !== VideoStatus.FAILED && (
              <div className="text-xs mt-2 text-muted-foreground">
                {videoData.status === VideoStatus.PENDING && "Preparing to generate..."}
                {videoData.status === VideoStatus.GENERATING_SCRIPT && "Creating script..."}
                {videoData.status === VideoStatus.FETCHING_IMAGES && "Gathering visuals..."}
                {videoData.status === VideoStatus.GENERATING_AUDIO && "Generating audio..."}
                {videoData.status === VideoStatus.GENERATING_SUBTITLES && "Creating subtitles..."}
                {videoData.status === VideoStatus.COMPOSING_VIDEO && "Composing video..."}
                {videoData.status === VideoStatus.UPLOADING && "Finalizing and uploading..."}
              </div>
            )}
            {videoData.status === VideoStatus.FAILED && videoData.error_message && (
              <div className="text-xs mt-2 text-red-500">
                Error: {videoData.error_message}
              </div>
            )}
          </div>

          {/* Show generation steps */}
          <div className="space-y-3">
            <div className={`flex items-center gap-3 ${videoData.progress >= 10 ? "text-green-600" : "text-muted-foreground"}`}>
              <div className={`w-6 h-6 flex items-center justify-center rounded-full text-white ${videoData.progress >= 10 ? "bg-green-600" : "bg-muted"}`}>
                1
              </div>
              <span>Generating script</span>
            </div>
            <div className={`flex items-center gap-3 ${videoData.progress >= 30 ? "text-green-600" : "text-muted-foreground"}`}>
              <div className={`w-6 h-6 flex items-center justify-center rounded-full text-white ${videoData.progress >= 30 ? "bg-green-600" : "bg-muted"}`}>
                2
              </div>
              <span>Finding relevant images</span>
            </div>
            <div className={`flex items-center gap-3 ${videoData.progress >= 50 ? "text-green-600" : "text-muted-foreground"}`}>
              <div className={`w-6 h-6 flex items-center justify-center rounded-full text-white ${videoData.progress >= 50 ? "bg-green-600" : "bg-muted"}`}>
                3
              </div>
              <span>Creating voiceover audio</span>
            </div>
            <div className={`flex items-center gap-3 ${videoData.progress >= 70 ? "text-green-600" : "text-muted-foreground"}`}>
              <div className={`w-6 h-6 flex items-center justify-center rounded-full text-white ${videoData.progress >= 70 ? "bg-green-600" : "bg-muted"}`}>
                4
              </div>
              <span>Adding subtitles</span>
            </div>
            <div className={`flex items-center gap-3 ${videoData.progress >= 80 ? "text-green-600" : "text-muted-foreground"}`}>
              <div className={`w-6 h-6 flex items-center justify-center rounded-full text-white ${videoData.progress >= 80 ? "bg-green-600" : "bg-muted"}`}>
                5
              </div>
              <span>Composing final video</span>
            </div>
          </div>

          {videoData.status === VideoStatus.FAILED && (
            <Button 
              onClick={() => router.push('/create')}
              className="w-full mt-6"
            >
              Try Again
            </Button>
          )}
        </Card>
      </div>
    );
  }

  // Video is completed and ready to view
  return (
    <div className="flex flex-col min-h-screen">
      <div className="fixed top-0 left-0 z-40 p-4">
        <Link href="/explore">
          <Button variant="ghost" size="icon" className="bg-black/20 text-white rounded-full">
            <ArrowLeft />
          </Button>
        </Link>
      </div>
      
      <div className="flex-1 relative">
        <Card className="w-full h-full max-w-md mx-auto overflow-hidden relative">
          {videoData.video_url ? (
            <video
              ref={videoRef}
              src={videoData.video_url}
              poster={videoData.thumbnail_url}
              className="w-full h-full object-cover"
              autoPlay
              loop
              playsInline
              muted={muted}
              onClick={togglePlay}
            />
          ) : (
            // Fallback to thumbnail if video URL is not available
            <div 
              className="absolute inset-0 bg-cover bg-center"
              style={{ backgroundImage: `url(${videoData.thumbnail_url})` }}
            />
          )}
          
          <div className="absolute inset-0 bg-black/30" />
          
          <div className="absolute bottom-0 left-0 right-0 p-4 text-white z-10">
            <div className="flex items-center gap-3 mb-3">
              <Avatar>
                <AvatarImage src={videoData.thumbnail_url || `/placeholder-avatar.png`} alt={videoData.celebrity_name} />
                <AvatarFallback>{videoData.celebrity_name[0]}</AvatarFallback>
              </Avatar>
              <div>
                <h3 className="font-semibold">{videoData.celebrity_name}</h3>
                <p className="text-sm opacity-90">{videoData.title}</p>
              </div>
            </div>
            <p className="text-sm opacity-80 line-clamp-3 mb-4">
              {videoData.description}
            </p>
            <div className="flex items-center justify-between text-xs opacity-70">
              <div>{new Date(videoData.created_at).toLocaleDateString()}</div>
              <div>{videoData.duration ? `${Math.round(videoData.duration)}s` : "Video"}</div>
            </div>
          </div>
        </Card>
      </div>
      
      <div className="fixed top-4 right-4 flex gap-2">
        <Button variant="ghost" size="icon" className="bg-black/20 text-white rounded-full" onClick={toggleMute}>
          {muted ? <VolumeX size={20} /> : <Volume2 size={20} />}
        </Button>
        <Button variant="ghost" size="icon" className="bg-black/20 text-white rounded-full" onClick={handleShare}>
          <Share2 size={20} />
        </Button>
      </div>
      
      {!playing && (
        <div className="absolute inset-0 flex items-center justify-center">
          <Button 
            variant="ghost" 
            size="icon" 
            className="h-16 w-16 text-white bg-black/20 rounded-full"
            onClick={togglePlay}
          >
            <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" className="w-8 h-8">
              <polygon points="5 3 19 12 5 21 5 3"></polygon>
            </svg>
          </Button>
        </div>
      )}
    </div>
  );
}