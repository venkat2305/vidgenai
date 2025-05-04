import aiohttp
import logging
import re
from typing import List, Dict, Any
from core.config import settings

logger = logging.getLogger("vidgenai.image_fetcher")


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
