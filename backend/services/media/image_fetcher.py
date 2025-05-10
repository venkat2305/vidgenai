import aiohttp
import logging
import re
from abc import ABC, abstractmethod
from typing import List, Dict, Any

from core.config import settings

logger = logging.getLogger("vidgenai.image_fetcher")


class ImageFetcher(ABC):
    @abstractmethod
    async def fetch_images(
        self,
        search_term: str,
        session: aiohttp.ClientSession,
        aspect_ratio: str = "9:16",
    ) -> List[Dict[str, Any]]:
        pass


class SerpApiImageFetcher(ImageFetcher):
    async def fetch_images(
        self,
        search_term: str,
        session: aiohttp.ClientSession,
        aspect_ratio: str = "9:16",
    ) -> List[Dict[str, Any]]:
        url = "https://serpapi.com/search.json"
        params = {
            "engine": "google_images",
            "q": search_term,
            "api_key": settings.SERP_API_KEY,
            "tbm": "isch",
            "ijn": "0",
            "safe": "active",
        }

        if aspect_ratio == "9:16":
            params["q"] = f"{search_term} vertical portrait"

        async with session.get(url, params=params) as response:
            if response.status == 200:
                data = await response.json()
                images = data.get("images_results", [])
                processed_images = []
                for img in images:
                    width = img.get("original_width", 0)
                    height = img.get("original_height", 0)
                    if width >= 400 and height >= 400:
                        processed_images.append({
                            "url": img["original"],
                            "width": width,
                            "height": height,
                            "aspect_ratio": ImageUtils.calculate_aspect_ratio(width, height),
                            "is_vertical": height > width,
                            "search_term": search_term,
                        })
                return processed_images
            else:
                logger.error(f"Error fetching images for '{search_term}': {response.status}")
                return []


class BraveImageFetcher(ImageFetcher):
    async def fetch_images(
        self,
        search_term: str,
        session: aiohttp.ClientSession,
        aspect_ratio: str = "9:16",
    ) -> List[Dict[str, Any]]:
        base_url = "https://api.search.brave.com/res/v1/images/search"
        headers = {
            "Accept": "application/json",
            "Accept-Encoding": "gzip",
            "X-Subscription-Token": settings.BRAVE_API_KEY,
        }
        params = {
            "q": search_term,
            "count": 20,  # You can adjust the count as needed
            "safesearch": "strict",
            "search_lang": "en",
            "spellcheck": 1,
        }

        async with session.get(base_url, headers=headers, params=params) as response:
            if response.status == 200:
                data = await response.json()
                # Brave returns image results in the "results" key.
                results = data.get("results", [])
                processed_images = []
                for result in results:
                    properties = result.get("properties", {})
                    image_url = properties.get("url")
                    if not image_url:
                        continue
                    # Brave's response might not include dimensions.
                    # Here, we assign default dimensions.
                    width = 600
                    height = 600
                    processed_images.append({
                        "url": image_url,
                        "width": width,
                        "height": height,
                        "aspect_ratio": ImageUtils.calculate_aspect_ratio(width, height),
                        "is_vertical": height > width,
                        "search_term": search_term,
                    })
                return processed_images
            else:
                logger.error(
                    f"Error fetching images for '{search_term}' using Brave: {response.status}"
                )
                return []


class ImageFetcherFactory:
    @staticmethod
    def get_fetcher(provider: str) -> ImageFetcher:
        if provider.lower() == "serp":
            return SerpApiImageFetcher()
        elif provider.lower() == "brave":
            return BraveImageFetcher()
        else:
            raise ValueError(f"Unsupported image fetcher provider: {provider}")

class ImageFetchService:
    def __init__(self):
        self.fetcher = ImageFetcherFactory.get_fetcher('brave')

    async def fetch_images(
        self,
        celebrity_name: str,
        script: str,
        num_images: int = 8,
        aspect_ratio: str = "9:16",
    ) -> List[Dict[str, Any]]:
        try:
            search_terms = ImageUtils.extract_search_terms(celebrity_name, script, num_images)
            image_results = []
            async with aiohttp.ClientSession() as session:
                for term in search_terms:
                    images = await self.fetcher.fetch_images(term, session, aspect_ratio)
                    image_results.extend(images)
                    if len(image_results) >= num_images * 2:
                        break

                # If not enough images, fetch additional generic ones
                if len(image_results) < num_images:
                    generic_terms = [
                        f"{celebrity_name} portrait vertical",
                        f"{celebrity_name} action shot vertical",
                        f"{celebrity_name} career highlights",
                        f"{celebrity_name} professional photo",
                    ]
                    for term in generic_terms:
                        if len(image_results) >= num_images * 2:
                            break
                        additional_images = await self.fetcher.fetch_images(
                            term, session, aspect_ratio
                        )
                        # Avoid duplicates
                        for img in additional_images:
                            if not any(
                                result["url"] == img["url"] for result in image_results
                            ):
                                image_results.append(img)

            sorted_images = ImageUtils.sort_images_by_aspect_ratio_match(image_results, aspect_ratio)
            logger.info(f"Fetched {len(sorted_images)} images for {celebrity_name}")
            return sorted_images[:num_images]

        except Exception as e:
            logger.error(
                f"Error fetching images for {celebrity_name}: {str(e)}", exc_info=True
            )
            raise Exception(f"Failed to fetch images: {str(e)}")


class ImageUtils:
    @staticmethod
    def calculate_aspect_ratio(width: int, height: int) -> str:
        """Calculate and format aspect ratio from dimensions."""
        if width == 0 or height == 0:
            return "1:1"
        from math import gcd
        divisor = gcd(width, height)
        return f"{width//divisor}:{height//divisor}"

    @staticmethod
    def sort_images_by_aspect_ratio_match(
        images: List[Dict[str, Any]], target_ratio: str = "9:16"
    ) -> List[Dict[str, Any]]:
        """Sort images by how closely they match the target aspect ratio."""
        target_width, target_height = map(int, target_ratio.split(":"))
        target_value = target_height / target_width

        def aspect_ratio_score(img):
            if target_value > 1 and img.get("is_vertical", False):
                base_score = 10
            elif target_value < 1 and not img.get("is_vertical", True):
                base_score = 10
            else:
                base_score = 0
            width = img.get("width", 1)
            height = img.get("height", 1)
            img_ratio = height / width
            difference = abs(img_ratio - target_value)
            return base_score - difference

        return sorted(images, key=aspect_ratio_score, reverse=True)

    @staticmethod
    def extract_search_terms(celebrity_name: str, script: str, num_terms: int) -> List[str]:
        """Extract search terms from the script to find relevant images."""
        import re
        sentences = re.split(r"[.!?]+", script)
        sentences = [s.strip() for s in sentences if s.strip()]
        search_terms = [f"{celebrity_name} portrait"]

        for sentence in sentences:
            year_match = re.search(r"\b(19|20)\d{2}\b", sentence)
            if year_match:
                year = year_match.group(0)
                search_terms.append(f"{celebrity_name} {year}")

            achievement_keywords = [
                "won", "champion", "record", "medal", "trophy", "award", "victory"
            ]
            for keyword in achievement_keywords:
                if keyword in sentence.lower():
                    search_terms.append(f"{celebrity_name} {keyword}")
                    break

        search_terms.extend([
            f"{celebrity_name} action",
            f"{celebrity_name} career highlight",
            f"{celebrity_name} portrait",
        ])

        unique_terms = []
        for term in search_terms:
            if term not in unique_terms:
                unique_terms.append(term)

        return unique_terms[:num_terms]
