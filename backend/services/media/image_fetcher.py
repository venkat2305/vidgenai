import aiohttp
import logging
import re
import json
from typing import List, Dict, Any
from core.config import settings
from groq import Groq

logger = logging.getLogger("vidgenai.image_fetcher")

# Initialize Groq client
groq_client = Groq(api_key=settings.GROQ_API_KEY)


async def fetch_images(celebrity_name: str, script: str, num_images: int = 8, aspect_ratio: str = "9:16") -> List[Dict[str, Any]]:
    """
    Fetch relevant images for a sports celebrity using SERP API.
    
    Args:
        celebrity_name: Name of the sports celebrity
        script: The generated script to extract relevant keywords
        num_images: Number of images to fetch
        aspect_ratio: Preferred aspect ratio for images (e.g., "9:16", "4:3", "1:1")
        
    Returns:
        List of dictionaries containing image URLs and metadata
    """
    try:
        # Extract key moments/themes from the script to use as search terms
        search_terms = extract_search_terms(celebrity_name, script, num_images)
        
        image_results = []
        async with aiohttp.ClientSession() as session:
            for term in search_terms:
                # Use SERP API to search for images
                url = "https://serpapi.com/search.json"
                params = {
                    "engine": "google_images",
                    "q": term,
                    "api_key": settings.SERP_API_KEY,
                    "tbm": "isch",
                    "ijn": "0",
                    "safe": "active"
                }
                
                # Add aspect ratio preference if specified
                if aspect_ratio == "9:16":
                    # For vertical videos, try to find vertical images
                    params["q"] = f"{term} vertical portrait"
                
                async with session.get(url, params=params) as response:
                    if response.status == 200:
                        data = await response.json()
                        images = data.get("images_results", [])
                        
                        # Process and filter images
                        for img in images:
                            if img.get("original_width", 0) >= 400 and img.get("original_height", 0) >= 400:
                                # Calculate actual aspect ratio
                                width = img.get("original_width", 0)
                                height = img.get("original_height", 0)
                                img_aspect = calculate_aspect_ratio(width, height)
                                
                                image_results.append({
                                    "url": img["original"],
                                    "width": width,
                                    "height": height,
                                    "aspect_ratio": img_aspect,
                                    "is_vertical": height > width,
                                    "search_term": term
                                })
                                
                                if len(image_results) >= num_images * 2:  # Fetch extra for filtering
                                    break
                    else:
                        logger.error(f"Error fetching images for '{term}': {response.status}")

        # If we don't have enough images, add generic ones
        if len(image_results) < num_images:
            generic_terms = [
                f"{celebrity_name} portrait vertical",
                f"{celebrity_name} action shot vertical",
                f"{celebrity_name} career highlights",
                f"{celebrity_name} professional photo"
            ]
            
            await fetch_additional_images(generic_terms, image_results, num_images, session, aspect_ratio)

        # Prioritize images with aspect ratios close to the target
        sorted_images = sort_images_by_aspect_ratio_match(image_results, aspect_ratio)
        
        logger.info(f"Fetched {len(sorted_images)} images for {celebrity_name}")
        return sorted_images[:num_images]  # Return the best matching images

    except Exception as e:
        logger.error(f"Error fetching images for {celebrity_name}: {str(e)}", exc_info=True)
        raise Exception(f"Failed to fetch images: {str(e)}")


async def fetch_additional_images(terms, image_results, num_images, session, aspect_ratio="9:16"):
    """Fetch additional images using provided search terms."""
    for term in terms:
        if len(image_results) >= num_images * 2:
            break

        url = "https://serpapi.com/search.json"
        params = {
            "engine": "google_images",
            "q": term,
            "api_key": settings.SERP_API_KEY,
            "tbm": "isch",
            "ijn": "0",
            "safe": "active"
        }

        async with session.get(url, params=params) as response:
            if response.status == 200:
                data = await response.json()
                images = data.get("images_results", [])

                for img in images:
                    if img.get("original_width", 0) >= 400 and img.get("original_height", 0) >= 400:
                        width = img.get("original_width", 0)
                        height = img.get("original_height", 0)
                        img_aspect = calculate_aspect_ratio(width, height)
                        
                        # Check if this image URL is already in the results
                        if not any(result["url"] == img["original"] for result in image_results):
                            image_results.append({
                                "url": img["original"],
                                "width": width,
                                "height": height,
                                "aspect_ratio": img_aspect,
                                "is_vertical": height > width,
                                "search_term": term
                            })
                            
                            if len(image_results) >= num_images * 2:
                                break


def calculate_aspect_ratio(width: int, height: int) -> str:
    """Calculate and format aspect ratio from dimensions."""
    if width == 0 or height == 0:
        return "1:1"  # Default in case of invalid dimensions
        
    # Get GCD for simplification
    from math import gcd
    divisor = gcd(width, height)
    
    return f"{width//divisor}:{height//divisor}"


def sort_images_by_aspect_ratio_match(images: List[Dict[str, Any]], target_ratio: str = "9:16") -> List[Dict[str, Any]]:
    """Sort images by how closely they match the target aspect ratio."""
    target_width, target_height = map(int, target_ratio.split(':'))
    target_value = target_height / target_width  # For 9:16 this would be 16/9 = 1.778
    
    def aspect_ratio_score(img):
        # Prioritize vertical images for 9:16 videos
        if target_value > 1 and img.get("is_vertical", False):
            base_score = 10
        elif target_value < 1 and not img.get("is_vertical", True):
            base_score = 10
        else:
            base_score = 0
            
        # Calculate how close the aspect ratio is to target
        width = img.get("width", 1)
        height = img.get("height", 1)
        img_ratio = height / width
        difference = abs(img_ratio - target_value)
        
        # Return a score (lower is better)
        return base_score - difference
    
    # Sort images by score (highest score first)
    return sorted(images, key=aspect_ratio_score, reverse=True)


def extract_search_terms(celebrity_name: str, script: str, num_terms: int) -> List[str]:
    """
    Extract search terms from the script to find relevant images.
    """
    # Split script into sentences
    sentences = re.split(r'[.!?]+', script)
    sentences = [s.strip() for s in sentences if s.strip()]
    
    # Create search terms based on sentences and celebrity name
    search_terms = []
    
    # Add the celebrity name as the first search term
    search_terms.append(f"{celebrity_name} portrait")
    
    # Extract key phrases from each sentence
    for sentence in sentences:
        # Look for years (likely significant moments)
        year_match = re.search(r'\b(19|20)\d{2}\b', sentence)
        if year_match:
            year = year_match.group(0)
            search_terms.append(f"{celebrity_name} {year}")
        
        # Look for achievements or events
        achievement_keywords = ["won", "champion", "record", "medal", "trophy", "award", "victory"]
        for keyword in achievement_keywords:
            if keyword in sentence.lower():
                # Extract a phrase around the keyword
                search_terms.append(f"{celebrity_name} {keyword}")
                break
    
    # Add some generic but useful search terms
    search_terms.extend([
        f"{celebrity_name} action",
        f"{celebrity_name} career highlight",
        f"{celebrity_name} portrait"
    ])
    
    # Remove duplicates and limit to requested number
    unique_terms = []
    for term in search_terms:
        if term not in unique_terms:
            unique_terms.append(term)
    
    return unique_terms[:num_terms]


async def segment_script(script: str, num_segments: int) -> List[Dict[str, Any]]:
    """
    Segment the script into contextual parts with estimated timing.
    
    Args:
        script: The full script text
        num_segments: Target number of segments to divide the script into
        
    Returns:
        List of dictionaries with segment text and timing information
    """
    # Simple approach: estimate timing based on character count
    # On average, people speak about 150 words per minute or about 900 characters per minute
    chars_per_second = 15  # 900 chars / 60 seconds
    total_chars = len(script)
    total_duration = total_chars / chars_per_second
    
    # Split script into sentences
    sentences = re.split(r'[.!?]+', script)
    sentences = [s.strip() for s in sentences if s.strip()]
    
    # Calculate approximate timing for each sentence
    sentence_timings = []
    current_time = 0
    
    for sentence in sentences:
        sentence_duration = len(sentence) / chars_per_second
        sentence_timings.append({
            "text": sentence,
            "start_time": current_time,
            "end_time": current_time + sentence_duration
        })
        current_time += sentence_duration
    
    # Group sentences into segments
    segments = []
    target_segment_duration = total_duration / num_segments
    
    current_segment = {
        "text": "",
        "start_time": 0,
        "end_time": 0,
        "sentences": []
    }
    
    for sentence_data in sentence_timings:
        # If this is the first sentence in the segment or if adding this sentence doesn't exceed target duration
        if not current_segment["sentences"] or (sentence_data["end_time"] - current_segment["start_time"]) <= target_segment_duration * 1.2:
            # Add sentence to current segment
            if not current_segment["sentences"]:
                current_segment["start_time"] = sentence_data["start_time"]
            
            current_segment["sentences"].append(sentence_data["text"])
            current_segment["text"] += (" " if current_segment["text"] else "") + sentence_data["text"]
            current_segment["end_time"] = sentence_data["end_time"]
        else:
            # Finalize current segment and start a new one
            segments.append(current_segment)
            
            current_segment = {
                "text": sentence_data["text"],
                "start_time": sentence_data["start_time"],
                "end_time": sentence_data["end_time"],
                "sentences": [sentence_data["text"]]
            }
    
    # Add the last segment if it's not empty
    if current_segment["sentences"]:
        segments.append(current_segment)
    
    # If we have fewer segments than requested, that's okay
    # If we have more, merge some smaller segments
    while len(segments) > num_segments:
        # Find the smallest segment
        smallest_idx = min(range(len(segments) - 1), key=lambda i: segments[i]["end_time"] - segments[i]["start_time"])
        
        # Merge it with the next segment
        segments[smallest_idx]["text"] += " " + segments[smallest_idx + 1]["text"]
        segments[smallest_idx]["end_time"] = segments[smallest_idx + 1]["end_time"]
        segments[smallest_idx]["sentences"].extend(segments[smallest_idx + 1]["sentences"])
        
        # Remove the merged segment
        segments.pop(smallest_idx + 1)
    
    return segments


async def extract_segment_keywords(celebrity_name: str, segments: List[Dict[str, Any]], keywords_per_segment: int = 3) -> List[List[str]]:
    """
    Extract relevant keywords for each script segment using Groq's Llama 3.3 70b model.
    
    Args:
        celebrity_name: Name of the sports celebrity
        segments: List of script segments
        keywords_per_segment: Number of keywords to extract per segment
        
    Returns:
        List of lists containing keywords for each segment
    """
    all_segment_keywords = []
    
    for i, segment in enumerate(segments):
        segment_text = segment["text"]
        
        # Use Groq's Llama 3.3 70b model for context-aware keyword extraction
        try:
            prompt = f"""Given the following segment from a script about cricketer {celebrity_name}, extract {keywords_per_segment} specific and meaningful keywords or phrases that would be helpful for finding relevant images.
            
            Focus on:
            - Specific achievements or milestones
            - Life stages (school years, early career)
            - Important matches or tournaments
            - Specific skills or playing style mentioned
            - Notable locations or venues
            - Important years or time periods
            
            Script segment:
            "{segment_text}"
            
            Return only a JSON array of {keywords_per_segment} keywords or short phrases, nothing else.
            Example: ["first century", "school cricket captain", "under-19 world cup"]
            """
            
            response = groq_client.chat.completions.create(
                model="llama-3.3-70b-versatile",
                messages=[{"role": "user", "content": prompt}],
                temperature=0.2,
                max_tokens=200,
                top_p=0.9
            )
            
            result = response.choices[0].message.content.strip()
            
            # Try to parse the JSON array
            try:
                # Remove any markdown code block markers if present
                clean_result = re.sub(r'```json|```', '', result).strip()
                keywords = json.loads(clean_result)
                
                if not isinstance(keywords, list):
                    raise ValueError("Result is not a list")
                    
                # Ensure we have the requested number of keywords
                if len(keywords) < keywords_per_segment:
                    # Fill with generic keywords if needed
                    generic = [f"{celebrity_name} cricket", "cricket match", "cricketer"]
                    keywords.extend(generic[:keywords_per_segment - len(keywords)])
                
                all_segment_keywords.append(keywords[:keywords_per_segment])
                
            except (json.JSONDecodeError, ValueError) as e:
                # Fallback: extract keywords using regex
                logger.warning(f"Failed to parse JSON keywords from Groq: {e}. Using fallback method.")
                
                # Try to extract any bracketed or quoted items
                extracted = re.findall(r'"([^"]+)"|\[([^]]+)\]|\'([^\']+)\'', result)
                keywords = []
                
                for match in extracted:
                    # Each match is a tuple with groups, take the non-empty one
                    for group in match:
                        if group:
                            keywords.append(group)
                    
                    if len(keywords) >= keywords_per_segment:
                        break
                
                # If we still don't have enough, use the original method
                if len(keywords) < keywords_per_segment:
                    fallback_keywords = extract_search_terms(celebrity_name, segment_text, keywords_per_segment)
                    keywords.extend(fallback_keywords[:keywords_per_segment - len(keywords)])
                
                all_segment_keywords.append(keywords[:keywords_per_segment])
                
        except Exception as e:
            logger.error(f"Error extracting keywords with Groq: {str(e)}")
            # Fallback to traditional keyword extraction
            fallback_keywords = extract_search_terms(celebrity_name, segment_text, keywords_per_segment)
            all_segment_keywords.append(fallback_keywords[:keywords_per_segment])
    
    return all_segment_keywords


async def fetch_contextual_images(celebrity_name: str, script: str, num_segments: int = 5, images_per_segment: int = 3, 
                                 aspect_ratio: str = "9:16") -> List[Dict[str, Any]]:
    """
    Fetch images that correspond to different contextual segments of a script.
    Images will change as the script progresses through different parts of a celebrity's journey.
    
    Args:
        celebrity_name: Name of the sports celebrity
        script: The generated script to extract relevant keywords
        num_segments: Number of script segments to identify
        images_per_segment: Number of images to fetch per segment
        aspect_ratio: Preferred aspect ratio for images
        
    Returns:
        List of dictionaries containing image information with timestamps
    """
    try:
        # Segment the script into contextual parts
        segments = await segment_script(script, num_segments)
        
        # Extract context-aware keywords for each segment using Groq's Llama 3.3 model
        segment_keywords = await extract_segment_keywords(celebrity_name, segments)
        
        all_images = []
        
        # Fetch images for each segment
        async with aiohttp.ClientSession() as session:
            for segment_idx, keywords in enumerate(segment_keywords):
                segment_images = []
                
                # Process each keyword for this segment
                for keyword in keywords:
                    search_term = f"{celebrity_name} {keyword}"
                    
                    # Use SERP API to search for images
                    url = "https://serpapi.com/search.json"
                    params = {
                        "engine": "google_images",
                        "q": search_term,
                        "api_key": settings.SERP_API_KEY,
                        "tbm": "isch",
                        "ijn": "0",
                        "safe": "active"
                    }
                    
                    # Add aspect ratio preference if specified
                    if aspect_ratio == "9:16":
                        params["q"] = f"{search_term} vertical portrait"
                    
                    async with session.get(url, params=params) as response:
                        if response.status == 200:
                            data = await response.json()
                            images = data.get("images_results", [])
                            
                            # Process and filter images
                            for img in images:
                                if img.get("original_width", 0) >= 400 and img.get("original_height", 0) >= 400:
                                    width = img.get("original_width", 0)
                                    height = img.get("original_height", 0)
                                    img_aspect = calculate_aspect_ratio(width, height)
                                    
                                    segment_images.append({
                                        "url": img["original"],
                                        "width": width,
                                        "height": height,
                                        "aspect_ratio": img_aspect,
                                        "is_vertical": height > width,
                                        "search_term": search_term,
                                        "segment_idx": segment_idx,
                                        "segment_text": segments[segment_idx]["text"],
                                        "segment_start_time": segments[segment_idx]["start_time"],
                                        "segment_end_time": segments[segment_idx]["end_time"],
                                        "context": keyword
                                    })
                                    
                                    if len(segment_images) >= images_per_segment * 2:
                                        break
                                        
                        else:
                            logger.error(f"Error fetching images for segment {segment_idx}, term '{search_term}': {response.status}")
                
                # Sort and pick the best images for this segment
                sorted_segment_images = sort_images_by_aspect_ratio_match(segment_images, aspect_ratio)
                all_images.extend(sorted_segment_images[:images_per_segment])
                
                logger.info(f"Fetched {len(sorted_segment_images[:images_per_segment])} images for segment {segment_idx}")
        
        return all_images
        
    except Exception as e:
        logger.error(f"Error fetching contextual images for {celebrity_name}: {str(e)}", exc_info=True)
        raise Exception(f"Failed to fetch contextual images: {str(e)}")
