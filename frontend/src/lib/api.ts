import axios from 'axios';
import { getBackendUrl } from '../config/api-config';

// Base API URL that works with Next.js in both development and production
const BASE_URL = getBackendUrl();
console.log('Base URL for API:', BASE_URL);

// Create an axios instance for API calls
const api = axios.create({
  baseURL: BASE_URL,
  headers: {
    'Content-Type': 'application/json',
  },
  // Add a longer timeout for video generation operations
  timeout: 30000,
});

// For debugging: log requests in development
api.interceptors.request.use(request => {
  console.log('API Request:', request.method?.toUpperCase(), request.url);
  return request;
});

// Types based on backend models
export interface Video {
  id: string;
  title: string;
  celebrity_name: string;
  description?: string;
  status: VideoStatus;
  progress: number;
  error_message?: string;
  script?: string;
  image_urls: string[];
  audio_url?: string;
  video_url?: string;
  thumbnail_url?: string;
  duration?: number;
  created_at: string;
  updated_at: string;
}

export enum VideoStatus {
  PENDING = "pending",
  GENERATING_SCRIPT = "generating_script",
  FETCHING_IMAGES = "fetching_images",
  GENERATING_AUDIO = "generating_audio",
  GENERATING_SUBTITLES = "generating_subtitles",
  COMPOSING_VIDEO = "composing_video",
  UPLOADING = "uploading",
  COMPLETED = "completed",
  FAILED = "failed"
}

export interface VideoCreateRequest {
  celebrity_name: string;
  title?: string;
  description?: string;
}

// API functions

// Get all videos with optional filtering
export const getVideos = async (params?: {
  skip?: number;
  limit?: number;
  status?: VideoStatus;
}): Promise<Video[]> => {
  try {
    // Use hardcoded full URL as a fallback for local development
    const url = '/api/videos/';
    console.log('Fetching videos from:', url, 'with params:', params);
    
    const response = await api.get(url, { params });
    console.log('Videos API response:', response.status, response.data?.length || 0, 'videos');
    return response.data;
  } catch (error: unknown) {
    console.error('Error fetching videos:', error);
    if (axios.isAxiosError(error)) {
      console.error('Error details:', error.response?.data || error.message);
    }
    throw error;
  }
};

// Get a single video by ID
export const getVideo = async (videoId: string): Promise<Video> => {
  try {
    const response = await api.get(`/api/videos/${videoId}`);
    return response.data;
  } catch (error: unknown) {
    console.error(`Error fetching video ${videoId}:`, error);
    if (axios.isAxiosError(error)) {
      console.error('Error details:', error.response?.data || error.message);
    }
    throw error;
  }
};

// Create a new video generation
export const createVideo = async (
  videoData: VideoCreateRequest,
  aspectRatio: string = '9:16',
  applyEffects: boolean = true
): Promise<Video> => {
  try {
    const response = await api.post('/api/generation/', videoData, {
      params: {
        aspect_ratio: aspectRatio,
        apply_effects: applyEffects
      }
    });
    return response.data;
  } catch (error: unknown) {
    console.error('Error creating video:', error);
    if (axios.isAxiosError(error)) {
      console.error('Error details:', error.response?.data || error.message);
    }
    throw error;
  }
};

// Check the status of a video generation
export const getGenerationStatus = async (jobId: string): Promise<Video> => {
  try {
    const response = await api.get(`/api/generation/${jobId}`);
    return response.data;
  } catch (error: unknown) {
    console.error(`Error checking generation status for job ${jobId}:`, error);
    if (axios.isAxiosError(error)) {
      console.error('Error details:', error.response?.data || error.message);
    }
    throw error;
  }
};

export default api;