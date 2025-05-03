import numpy as np


class VideoEffect:
    """Base class for video effects."""
    def apply(self, frame, t, duration):
        """Apply effect to a frame at time t."""
        return frame


class ZoomEffect(VideoEffect):
    """Zoom in or out effect."""
    def __init__(self, zoom_start: float = 1.0, zoom_end: float = 1.2):
        self.zoom_start = zoom_start
        self.zoom_end = zoom_end
    
    def apply(self, frame, t, duration):
        """Apply zoom effect to frame."""
        h, w = frame.shape[:2]
        zoom_factor = self.zoom_start + (self.zoom_end - self.zoom_start) * (t / duration)
        
        # Calculate new dimensions
        new_h, new_w = int(h * zoom_factor), int(w * zoom_factor)
        
        # Calculate crop area
        y1 = max(0, (new_h - h) // 2)
        x1 = max(0, (new_w - w) // 2)
        y2 = y1 + h
        x2 = x1 + w
        
        # Resize image
        import cv2
        resized = cv2.resize(frame, (new_w, new_h), interpolation=cv2.INTER_LINEAR)
        
        # Crop to original size
        if zoom_factor > 1.0:
            result = resized[y1:y2, x1:x2]
            # Ensure result has the same shape as the original frame
            if result.shape[:2] != (h, w):
                result = cv2.resize(result, (w, h), interpolation=cv2.INTER_LINEAR)
            return result
        else:
            # For zoom out, we need to pad the image
            result = np.zeros_like(frame)
            y_offset = (h - new_h) // 2
            x_offset = (w - new_w) // 2
            result[y_offset:y_offset+new_h, x_offset:x_offset+new_w] = resized
            return result


class PanEffect(VideoEffect):
    """Pan across the image horizontally or vertically."""
    def __init__(self, direction: str = "right", speed: float = 0.2):
        """
        Initialize pan effect.
        
        Args:
            direction: One of "left", "right", "up", "down"
            speed: Pan speed factor (0.0 to 1.0)
        """
        self.direction = direction
        self.speed = speed
    
    def apply(self, frame, t, duration):
        """Apply pan effect to frame."""
        h, w = frame.shape[:2]
        
        # Calculate offset based on time and direction
        progress = t / duration
        max_offset = int(w * self.speed) if self.direction in ["left", "right"] else int(h * self.speed)
        offset = int(max_offset * progress)
        
        # Create result frame
        result = np.zeros_like(frame)
        
        # Apply pan based on direction
        if self.direction == "right":
            # Pan from left to right
            result[:, offset:] = frame[:, :(w-offset)]
            result[:, :offset] = frame[:, (w-offset):]
        elif self.direction == "left":
            # Pan from right to left
            result[:, :(w-offset)] = frame[:, offset:]
            result[:, (w-offset):] = frame[:, :offset]
        elif self.direction == "down":
            # Pan from top to bottom
            result[offset:, :] = frame[:(h-offset), :]
            result[:offset, :] = frame[(h-offset):, :]
        elif self.direction == "up":
            # Pan from bottom to top
            result[:(h-offset), :] = frame[offset:, :]
            result[(h-offset):, :] = frame[:offset, :]
            
        return result

def get_random_effect() -> VideoEffect:
    """Return a random video effect with appropriate parameters."""
    import random
    
    effect_type = random.choice(["zoom", "pan"])
    
    if effect_type == "zoom":
        # Randomly choose between zoom in and zoom out
        if random.random() > 0.5:
            return ZoomEffect(1.0, 1.2)  # Zoom in
        else:
            return ZoomEffect(1.2, 1.0)  # Zoom out
    else:
        # Random pan direction
        direction = random.choice(["left", "right", "up", "down"])
        return PanEffect(direction, speed=0.15)
