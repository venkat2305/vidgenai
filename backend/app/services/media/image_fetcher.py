import aiohttp
import logging
import json
import re
from typing import List
from app.core.config import settings

logger = logging.getLogger("vidgenai.image_fetcher")


async def fetch_images(celebrity_name: str, script: str, num_images: int = 8) -> List[str]:
    """
    Fetch relevant images for a sports celebrity using SERP API.
    
    Args:
        celebrity_name: Name of the sports celebrity
        script: The generated script to extract relevant keywords
        num_images: Number of images to fetch
        
    Returns:
        List of image URLs
    """
    try:
        # Extract key moments/themes from the script to use as search terms
        search_terms = extract_search_terms(celebrity_name, script, num_images)
        
        image_urls = []
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
                
                async with session.get(url, params=params) as response:
                    if response.status == 200:
                        data = await response.json()
                        images = data.get("images_results", [])
                        
                        # Filter for high-quality images
                        filtered_images = [
                            img for img in images 
                            if img.get("original_width", 0) >= 800 and img.get("original_height", 0) >= 600
                        ]
                        
                        if filtered_images:
                            # Take the best image for this search term
                            image_urls.append(filtered_images[0]["original"])
                            logger.info(f"Found image for '{term}'")
                        else:
                            logger.warning(f"No suitable images found for '{term}'")
                    else:
                        logger.error(f"Error fetching images for '{term}': {response.status}")

        # If we didn't get enough images, add some generic ones of the celebrity
        if len(image_urls) < num_images:
            generic_terms = [
                f"{celebrity_name} action shot",
                f"{celebrity_name} career highlights",
                f"{celebrity_name} professional photo"
            ]
            async with aiohttp.ClientSession() as session:
                for term in generic_terms:
                    if len(image_urls) >= num_images:
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

                            filtered_images = [
                                img for img in images 
                                if img.get("original_width", 0) >= 800 and img.get("original_height", 0) >= 600
                            ]

                            for img in filtered_images:
                                if img["original"] not in image_urls:
                                    image_urls.append(img["original"])
                                    if len(image_urls) >= num_images:
                                        break

        logger.info(f"Fetched {len(image_urls)} images for {celebrity_name}")
        return image_urls[:num_images]  # Ensure we return exactly the requested number

    except Exception as e:
        logger.error(f"Error fetching images for {celebrity_name}: {str(e)}", exc_info=True)
        raise Exception(f"Failed to fetch images: {str(e)}")


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
    search_terms.append(f"{celebrity_name} sports")
    
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
        f"{celebrity_name} professional"
    ])
    
    # Remove duplicates and limit to requested number
    unique_terms = []
    for term in search_terms:
        if term not in unique_terms:
            unique_terms.append(term)
    
    return unique_terms[:num_terms]
