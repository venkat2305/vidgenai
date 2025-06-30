import { useState, useCallback, useRef, useEffect } from 'react';

interface VideoBufferState {
  bufferedRanges: TimeRanges | null;
  bufferedPercentage: number;
  isBuffering: boolean;
  networkState: number;
  readyState: number;
}

export function useVideoBuffer(videoRef: React.RefObject<HTMLVideoElement>) {
  const [bufferState, setBufferState] = useState<VideoBufferState>({
    bufferedRanges: null,
    bufferedPercentage: 0,
    isBuffering: false,
    networkState: 0,
    readyState: 0
  });

  const updateIntervalRef = useRef<NodeJS.Timeout | null>(null);

  const updateBufferState = useCallback(() => {
    const video = videoRef.current;
    if (!video) return;

    const buffered = video.buffered;
    let bufferedPercentage = 0;

    if (buffered.length > 0 && video.duration > 0) {
      const bufferedEnd = buffered.end(buffered.length - 1);
      bufferedPercentage = (bufferedEnd / video.duration) * 100;
    }

    setBufferState({
      bufferedRanges: buffered,
      bufferedPercentage,
      isBuffering: video.readyState < 3,
      networkState: video.networkState,
      readyState: video.readyState
    });
  }, [videoRef]);

  const startBufferMonitoring = useCallback(() => {
    if (updateIntervalRef.current) {
      clearInterval(updateIntervalRef.current);
    }
    
    updateIntervalRef.current = setInterval(updateBufferState, 1000);
    updateBufferState(); // Initial update
  }, [updateBufferState]);

  const stopBufferMonitoring = useCallback(() => {
    if (updateIntervalRef.current) {
      clearInterval(updateIntervalRef.current);
      updateIntervalRef.current = null;
    }
  }, []);

  useEffect(() => {
    const video = videoRef.current;
    if (!video) return;

    const events = [
      'loadstart',
      'progress',
      'canplay',
      'canplaythrough',
      'waiting',
      'playing'
    ];

    const handleEvent = () => updateBufferState();

    events.forEach(event => {
      video.addEventListener(event, handleEvent);
    });

    return () => {
      events.forEach(event => {
        video.removeEventListener(event, handleEvent);
      });
      stopBufferMonitoring();
    };
  }, [videoRef, updateBufferState, stopBufferMonitoring]);

  return {
    ...bufferState,
    startBufferMonitoring,
    stopBufferMonitoring,
    updateBufferState
  };
}