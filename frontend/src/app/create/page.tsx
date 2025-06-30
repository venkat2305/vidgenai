"use client";

import { useState } from "react";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardFooter, CardHeader, CardTitle } from "@/components/ui/card";
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle, DialogTrigger } from "@/components/ui/dialog";
import { toast } from "sonner";
import { Loader2, Info, PlusCircle, Zap } from "lucide-react";
import { useRouter } from "next/navigation";
import { createVideo, VideoCreateRequest } from "@/lib/api";

// Types for form state
interface FormState {
  celebrity_name: string;
  title?: string;
  description?: string;
  sportType: string;
  focus: string;
  duration: string;
  aspectRatio: string;
  applyEffects: boolean;
}

// Initial form values
const initialFormState: FormState = {
  celebrity_name: "",
  title: "",
  description: "",
  sportType: "",
  focus: "career",
  duration: "30",
  aspectRatio: "9:16",
  applyEffects: true,
};

export default function CreatePage() {
  const [formState, setFormState] = useState<FormState>(initialFormState);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const router = useRouter();

  // Handle form input changes
  const handleInputChange = (e: React.ChangeEvent<HTMLInputElement | HTMLSelectElement | HTMLTextAreaElement>) => {
    const { name, value } = e.target;
    setFormState((prev) => ({
      ...prev,
      [name]: value,
    }));
  };

  // Handle checkbox changes
  const handleCheckboxChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const { name, checked } = e.target;
    setFormState((prev) => ({
      ...prev,
      [name]: checked,
    }));
  };

  // Handle form submission
  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!formState.celebrity_name || !formState.sportType) {
      toast.error("Please fill in all required fields");
      return;
    }

    // Create a title if not provided
    const title = formState.title || 
      `${formState.celebrity_name}&apos;s ${formState.focus === 'career' ? 'Career' : 
        formState.focus === 'personal' ? 'Personal Life' :
        formState.focus === 'achievements' ? 'Achievements' :
        formState.focus === 'legacy' ? 'Legacy' : 'Early Life'} Highlight`;
    
    // Create a description if not provided
    const description = formState.description || 
      `AI-generated sports reel about ${formState.celebrity_name}&apos;s ${
        formState.focus === 'career' ? 'professional career' : 
        formState.focus === 'personal' ? 'personal journey' :
        formState.focus === 'achievements' ? 'awards and achievements' :
        formState.focus === 'legacy' ? 'impact and legacy' : 'early life and journey'
      } in ${formState.sportType}.`;

    setIsSubmitting(true);
    
    try {
      // Prepare the request data
      const videoData: VideoCreateRequest = {
        celebrity_name: formState.celebrity_name,
        title,
        description,
      };

      // Call the API to create the video
      const response = await createVideo(
        videoData, 
        formState.aspectRatio, 
        formState.applyEffects
      );
      
      // Show success toast
      toast.success("Video generation started!", {
        description: "You'll be redirected to view the progress",
      });
      
      // Redirect to the video page after a short delay
      setTimeout(() => {
        router.push(`/video/${response.id}`);
      }, 2000);
      
    } catch (error) {
      console.error("Error creating video:", error);
      toast.error("Failed to start video generation. Please try again.");
      setIsSubmitting(false);
    }
  };

  return (
    <div className="container max-w-2xl py-8 mx-auto px-4 gradient-bg min-h-screen">
      <div className="animate-fade-in">
        <div className="text-center mb-8">
          <div className="inline-flex items-center justify-center p-3 rounded-full sports-gradient text-white mb-4">
            <PlusCircle size={32} />
          </div>
          <h1 className="text-4xl font-bold mb-2 bg-clip-text text-transparent sports-gradient">
            Create New Sports Reel
          </h1>
          <p className="text-muted-foreground text-lg">
            Bring your favorite athlete&apos;s story to life with AI
          </p>
        </div>
      </div>
      
      <Card className="sports-card animate-slide-up">
        <CardHeader className="text-center">
          <CardTitle className="text-2xl">Generate AI Sports Celebrity Reel</CardTitle>
          <CardDescription className="text-base">
            Fill in the details below to create an AI-generated history reel about your favorite sports celebrity.
          </CardDescription>
        </CardHeader>
        
        <CardContent>
          <form id="create-form" onSubmit={handleSubmit} className="space-y-6">
            <div className="space-y-3 group">
              <label htmlFor="celebrity_name" className="text-sm font-semibold text-foreground">
                Celebrity Name <span className="text-accent">*</span>
              </label>
              <input
                type="text"
                id="celebrity_name"
                name="celebrity_name"
                value={formState.celebrity_name}
                onChange={handleInputChange}
                placeholder="e.g., Michael Jordan, Serena Williams"
                className="w-full px-4 py-3 border rounded-xl bg-background focus:ring-2 focus:ring-primary/20 focus:border-primary transition-all hover:border-primary/50"
                required
              />
            </div>
            
            <div className="space-y-3 group">
              <label htmlFor="sportType" className="text-sm font-semibold text-foreground">
                Sport <span className="text-accent">*</span>
              </label>
              <select
                id="sportType"
                name="sportType"
                value={formState.sportType}
                onChange={handleInputChange}
                className="w-full px-4 py-3 border rounded-xl bg-background focus:ring-2 focus:ring-primary/20 focus:border-primary transition-all hover:border-primary/50"
                required
              >
                <option value="">Select a sport</option>
                <option value="basketball">🏀 Basketball</option>
                <option value="football">🏈 Football</option>
                <option value="soccer">⚽ Soccer</option>
                <option value="tennis">🎾 Tennis</option>
                <option value="golf">⛳ Golf</option>
                <option value="baseball">⚾ Baseball</option>
                <option value="cricket">🏏 Cricket</option>
                <option value="hockey">🏒 Hockey</option>
                <option value="other">🏆 Other</option>
              </select>
            </div>
            
            {/* <div className="space-y-2">
              <label htmlFor="title" className="text-sm font-medium">Title (Optional)</label>
              <input
                type="text"
                id="title"
                name="title"
                value={formState.title}
                onChange={handleInputChange}
                placeholder="e.g., Michael Jordan's Rise to Fame"
                className="w-full px-3 py-2 border rounded-md"
              />
            </div> */}
            
            {/* <div className="space-y-2">
              <label htmlFor="description" className="text-sm font-medium">Description (Optional)</label>
              <textarea
                id="description"
                name="description"
                value={formState.description}
                onChange={handleInputChange}
                placeholder="Brief description of the content..."
                className="w-full px-3 py-2 border rounded-md"
                rows={3}
              />
            </div> */}
            
            <div className="space-y-3 group">
              <label htmlFor="focus" className="text-sm font-semibold text-foreground">Content Focus</label>
              <select
                id="focus"
                name="focus"
                value={formState.focus}
                onChange={handleInputChange}
                className="w-full px-4 py-3 border rounded-xl bg-background focus:ring-2 focus:ring-primary/20 focus:border-primary transition-all hover:border-primary/50"
              >
                <option value="career">🎯 Career Highlights</option>
                <option value="personal">💭 Personal Life</option>
                <option value="achievements">🏆 Awards & Achievements</option>
                <option value="legacy">⭐ Legacy & Impact</option>
                <option value="early-life">🌟 Early Life & Journey</option>
              </select>
            </div>
            
            <div className="space-y-3 group">
              <label htmlFor="aspectRatio" className="text-sm font-semibold text-foreground">Aspect Ratio</label>
              <select
                id="aspectRatio"
                name="aspectRatio"
                value={formState.aspectRatio}
                onChange={handleInputChange}
                className="w-full px-4 py-3 border rounded-xl bg-background focus:ring-2 focus:ring-primary/20 focus:border-primary transition-all hover:border-primary/50"
              >
                <option value="9:16">📱 Vertical (9:16) - Best for mobile</option>
                <option value="16:9">💻 Landscape (16:9) - Best for desktop</option>
                <option value="1:1">📷 Square (1:1) - Best for social media</option>
              </select>
            </div>
            
            <div className="flex items-start space-x-3 p-4 rounded-xl bg-secondary/50 border border-secondary group hover:bg-secondary/70 transition-colors">
              <input
                type="checkbox"
                id="applyEffects"
                name="applyEffects"
                checked={formState.applyEffects}
                onChange={handleCheckboxChange}
                className="mt-1 rounded w-4 h-4 text-primary focus:ring-primary"
              />
              <div>
                <label htmlFor="applyEffects" className="text-sm font-semibold text-foreground cursor-pointer">
                  ✨ Apply Dynamic Visual Effects
                </label>
                <p className="text-xs text-muted-foreground mt-1">
                  Add professional zoom and pan effects to make your video more engaging
                </p>
              </div>
            </div>
          </form>
          
          <div className="mt-6">
            <Dialog>
              <DialogTrigger asChild>
                <Button variant="outline" size="sm" className="flex items-center gap-2 glass-effect hover:scale-105 transition-transform">
                  <Info size={16} />
                  How it works
                </Button>
              </DialogTrigger>
              <DialogContent>
                <DialogHeader>
                  <DialogTitle>How Reel Generation Works</DialogTitle>
                  <DialogDescription>
                    Here&apos;s how our AI creates your sports celebrity history reels:
                  </DialogDescription>
                </DialogHeader>
                <div className="space-y-4 py-4">
                  <div className="flex gap-3">
                    <span className="font-bold">1.</span>
                    <p>Generate an engaging script about your selected sports celebrity using AI.</p>
                  </div>
                  <div className="flex gap-3">
                    <span className="font-bold">2.</span>
                    <p>Automatically source relevant images from our database.</p>
                  </div>
                  <div className="flex gap-3">
                    <span className="font-bold">3.</span>
                    <p>Create a professional voiceover narration using text-to-speech.</p>
                  </div>
                  <div className="flex gap-3">
                    <span className="font-bold">4.</span>
                    <p>Compose the final video with dynamic visual effects and subtitles.</p>
                  </div>
                  <div className="flex gap-3">
                    <span className="font-bold">5.</span>
                    <p>Store the completed reel in the cloud for easy sharing and viewing.</p>
                  </div>
                </div>
                <DialogFooter>
                  <Button variant="outline" onClick={() => document.querySelector<HTMLButtonElement>("[data-state='open'] button")?.click()}>
                    Close
                  </Button>
                </DialogFooter>
              </DialogContent>
            </Dialog>
          </div>
        </CardContent>
        
        <CardFooter>
          <Button 
            type="submit"
            form="create-form"
            className="w-full sports-gradient text-white text-lg py-6 hover:scale-105 transition-all duration-300 disabled:opacity-50 disabled:scale-100"
            disabled={isSubmitting}
          >
            {isSubmitting ? (
              <>
                <Loader2 size={20} className="mr-2 animate-spin" />
                Starting Generation...
              </>
            ) : (
              <>
                <Zap size={20} className="mr-2" />
                Generate Reel
              </>
            )}
          </Button>
        </CardFooter>
      </Card>
    </div>
  );
}