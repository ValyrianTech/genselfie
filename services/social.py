"""Social media profile image fetching service.

Supports: Twitter/X, Bluesky, GitHub, Mastodon
"""

import httpx
from typing import Optional
from urllib.parse import urlparse


async def fetch_profile_image(platform: str, handle: str) -> Optional[str]:
    """Fetch profile image URL from a social media platform.
    
    Args:
        platform: One of 'twitter', 'bluesky', 'github', 'mastodon'
        handle: The user's handle (without @ prefix for most platforms)
    
    Returns:
        URL to the profile image, or None if not found
    """
    # Clean handle
    handle = handle.strip().lstrip("@")
    
    platform = platform.lower()
    
    if platform in ("twitter", "x"):
        return await fetch_twitter_profile(handle)
    elif platform == "bluesky":
        return await fetch_bluesky_profile(handle)
    elif platform == "github":
        return await fetch_github_profile(handle)
    elif platform == "mastodon":
        return await fetch_mastodon_profile(handle)
    else:
        raise ValueError(f"Unsupported platform: {platform}")


async def fetch_twitter_profile(handle: str) -> Optional[str]:
    """Fetch Twitter/X profile image using unavatar.io service."""
    # unavatar.io provides a reliable way to get Twitter profile pics
    # It returns a redirect to the actual image
    url = f"https://unavatar.io/twitter/{handle}"
    
    async with httpx.AsyncClient(follow_redirects=True) as client:
        try:
            # Just verify it exists by doing a HEAD request
            response = await client.head(url, timeout=10.0)
            if response.status_code == 200:
                return url
        except httpx.RequestError:
            pass
    
    return None


async def fetch_bluesky_profile(handle: str) -> Optional[str]:
    """Fetch Bluesky profile image via AT Protocol API."""
    # Handle can be like 'user.bsky.social' or just 'user'
    if "." not in handle:
        handle = f"{handle}.bsky.social"
    
    url = f"https://public.api.bsky.app/xrpc/app.bsky.actor.getProfile?actor={handle}"
    
    async with httpx.AsyncClient() as client:
        try:
            response = await client.get(url, timeout=10.0)
            if response.status_code == 200:
                data = response.json()
                avatar = data.get("avatar")
                if avatar:
                    return avatar
        except (httpx.RequestError, ValueError):
            pass
    
    return None


async def fetch_github_profile(handle: str) -> Optional[str]:
    """Fetch GitHub profile image - simplest of all."""
    # GitHub provides direct avatar URLs
    url = f"https://github.com/{handle}.png"
    
    async with httpx.AsyncClient(follow_redirects=True) as client:
        try:
            response = await client.head(url, timeout=10.0)
            if response.status_code == 200:
                return url
        except httpx.RequestError:
            pass
    
    return None


async def fetch_mastodon_profile(handle: str) -> Optional[str]:
    """Fetch Mastodon profile image via WebFinger and instance API.
    
    Handle format: user@instance.social
    """
    if "@" not in handle:
        return None
    
    parts = handle.split("@")
    if len(parts) != 2:
        return None
    
    username, instance = parts
    
    # Use the instance's API to get profile
    url = f"https://{instance}/api/v1/accounts/lookup?acct={username}"
    
    async with httpx.AsyncClient() as client:
        try:
            response = await client.get(url, timeout=10.0)
            if response.status_code == 200:
                data = response.json()
                avatar = data.get("avatar") or data.get("avatar_static")
                if avatar:
                    return avatar
        except (httpx.RequestError, ValueError):
            pass
    
    return None


# Platform metadata for frontend
PLATFORMS = {
    "twitter": {
        "name": "Twitter / X",
        "placeholder": "username",
        "icon": "twitter",
        "help": "Enter your Twitter/X username without @"
    },
    "bluesky": {
        "name": "Bluesky",
        "placeholder": "user.bsky.social",
        "icon": "cloud",
        "help": "Enter your Bluesky handle (e.g., user.bsky.social)"
    },
    "github": {
        "name": "GitHub",
        "placeholder": "username",
        "icon": "github",
        "help": "Enter your GitHub username"
    },
    "mastodon": {
        "name": "Mastodon",
        "placeholder": "user@instance.social",
        "icon": "mastodon",
        "help": "Enter your full Mastodon handle (user@instance)"
    }
}
