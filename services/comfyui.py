"""ComfyUI API integration service.

Based on the generate_titlecard.py pattern:
1. Upload images to ComfyUI
2. Queue prompt with workflow JSON
3. Poll for completion
4. Get result image URL
"""

import json
import random
import asyncio
from pathlib import Path
from typing import Optional, List

import httpx

from config import settings

def get_comfyui_url() -> str:
    """Get the ComfyUI URL from .env config."""
    return settings.comfyui_url.rstrip("/")


async def upload_image_to_comfyui(image_path: Path, timeout: float = 60.0) -> bool:
    """Upload an image to ComfyUI's input folder.
    
    Args:
        image_path: Path to the image file
        timeout: Request timeout in seconds
    
    Returns:
        True if upload succeeded, False otherwise
    """
    base_url = get_comfyui_url()
    upload_url = f"{base_url}/upload/image"
    
    if not image_path.exists():
        print(f"[ERROR] Image not found: {image_path}")
        return False
    
    async with httpx.AsyncClient() as client:
        try:
            with image_path.open("rb") as f:
                files = {"image": (image_path.name, f, "image/png")}
                data = {"type": "input"}
                response = await client.post(
                    upload_url, 
                    files=files, 
                    data=data, 
                    timeout=timeout
                )
            return response.status_code == 200
        except httpx.RequestError as e:
            print(f"[ERROR] Upload failed: {e}")
            return False


async def upload_image_from_url(image_url: str, filename: str) -> bool:
    """Download an image from URL and upload to ComfyUI.
    
    Args:
        image_url: URL of the image to download
        filename: Filename to use when uploading
    
    Returns:
        True if successful, False otherwise
    """
    base_url = get_comfyui_url()
    upload_url = f"{base_url}/upload/image"
    
    async with httpx.AsyncClient(follow_redirects=True) as client:
        try:
            # Download image
            response = await client.get(image_url, timeout=30.0)
            if response.status_code != 200:
                return False
            
            image_data = response.content
            
            # Upload to ComfyUI
            files = {"image": (filename, image_data, "image/png")}
            data = {"type": "input"}
            upload_response = await client.post(
                upload_url,
                files=files,
                data=data,
                timeout=60.0
            )
            return upload_response.status_code == 200
        except httpx.RequestError as e:
            print(f"[ERROR] Upload from URL failed: {e}")
            return False


async def queue_prompt(workflow: dict) -> Optional[str]:
    """Queue a prompt/workflow on ComfyUI.
    
    Args:
        workflow: The workflow JSON as a dict
    
    Returns:
        The prompt_id if successful, None otherwise
    """
    base_url = get_comfyui_url()
    prompt_url = f"{base_url}/prompt"
    
    async with httpx.AsyncClient() as client:
        try:
            response = await client.post(
                prompt_url,
                json={"prompt": workflow},
                timeout=30.0
            )
            if response.status_code == 200:
                data = response.json()
                return data.get("prompt_id")
        except httpx.RequestError as e:
            print(f"[ERROR] Queue prompt failed: {e}")
    
    return None


async def get_queue_status() -> dict:
    """Get current ComfyUI queue status."""
    base_url = get_comfyui_url()
    queue_url = f"{base_url}/queue"
    
    async with httpx.AsyncClient() as client:
        try:
            response = await client.get(queue_url, timeout=10.0)
            if response.status_code == 200:
                return response.json()
        except httpx.RequestError:
            pass
    
    return {"queue_pending": [], "queue_running": []}


async def get_history(prompt_id: str) -> Optional[dict]:
    """Get history/result for a completed prompt.
    
    Args:
        prompt_id: The prompt ID to check
    
    Returns:
        History data if available, None otherwise
    """
    base_url = get_comfyui_url()
    history_url = f"{base_url}/history/{prompt_id}"
    
    async with httpx.AsyncClient() as client:
        try:
            response = await client.get(history_url, timeout=10.0)
            if response.status_code == 200:
                return response.json()
        except httpx.RequestError:
            pass
    
    return None


async def is_prompt_complete(prompt_id: str) -> bool:
    """Check if a prompt has finished processing."""
    queue = await get_queue_status()
    
    pending = queue.get("queue_pending", [])
    running = queue.get("queue_running", [])
    
    # Check if prompt is still in queue
    for item in pending + running:
        if len(item) > 1 and item[1] == prompt_id:
            return False
    
    return True


async def generate_selfie(
    fan_image_url: str,
    influencer_images: List[str],
    workflow_json: Optional[str] = None
) -> str:
    """Generate a selfie using ComfyUI.
    
    Args:
        fan_image_url: URL or path to the fan's image
        influencer_images: List of influencer image filenames
        workflow_json: Optional custom workflow JSON
    
    Returns:
        The prompt_id for tracking the generation
    
    Raises:
        Exception if generation fails to start
    """
    # Upload fan image to ComfyUI
    fan_filename = f"fan_{random.randint(100000, 999999)}.png"
    
    if fan_image_url.startswith("http"):
        success = await upload_image_from_url(fan_image_url, fan_filename)
    else:
        # Local file path
        local_path = Path(fan_image_url.lstrip("/"))
        if not local_path.is_absolute():
            local_path = settings.base_dir / local_path
        success = await upload_image_to_comfyui(local_path)
        fan_filename = local_path.name
    
    if not success:
        raise Exception("Failed to upload fan image to ComfyUI")
    
    # Upload influencer images if they're local
    for img_filename in influencer_images:
        img_path = settings.upload_dir / img_filename
        if img_path.exists():
            await upload_image_to_comfyui(img_path)
    
    # Load workflow
    if workflow_json:
        workflow = json.loads(workflow_json)
    else:
        # Use default workflow template
        workflow = get_default_workflow()
    
    # Inject images into workflow
    # This is workflow-specific - adjust node IDs based on your actual workflow
    workflow = inject_images_into_workflow(
        workflow,
        fan_image=fan_filename,
        influencer_image=influencer_images[0] if influencer_images else None
    )
    
    # Set random seed
    workflow = set_random_seed(workflow)
    
    # Queue the prompt
    prompt_id = await queue_prompt(workflow)
    
    if not prompt_id:
        raise Exception("Failed to queue prompt on ComfyUI")
    
    return prompt_id


async def get_generation_status(prompt_id: str) -> dict:
    """Get the status and result of a generation.
    
    Args:
        prompt_id: The prompt ID to check
    
    Returns:
        Dict with 'completed' bool and 'image_url' if completed
    """
    base_url = get_comfyui_url()
    
    # Check if still processing
    if not await is_prompt_complete(prompt_id):
        return {"completed": False}
    
    # Get history for result
    history = await get_history(prompt_id)
    
    if not history or prompt_id not in history:
        return {"completed": False}
    
    prompt_history = history[prompt_id]
    outputs = prompt_history.get("outputs", {})
    
    # Find the output image - this depends on your workflow structure
    # Common output node IDs to check
    for node_id in outputs:
        node_output = outputs[node_id]
        
        # Check for images
        images = node_output.get("images", [])
        if images:
            img = images[0]
            filename = img.get("filename")
            subfolder = img.get("subfolder", "")
            
            if filename:
                if subfolder:
                    image_url = f"{base_url}/output/{subfolder}/{filename}"
                else:
                    image_url = f"{base_url}/output/{filename}"
                
                return {"completed": True, "image_url": image_url}
        
        # Check for gifs (video output)
        gifs = node_output.get("gifs", [])
        if gifs:
            gif = gifs[0]
            filename = gif.get("filename")
            subfolder = gif.get("subfolder", "")
            
            if filename:
                if subfolder:
                    image_url = f"{base_url}/output/{subfolder}/{filename}"
                else:
                    image_url = f"{base_url}/output/{filename}"
                
                return {"completed": True, "image_url": image_url}
    
    return {"completed": True, "image_url": None}


def get_default_workflow() -> dict:
    """Load the default workflow from workflows/genselfie.json."""
    workflow_path = settings.base_dir / "workflows" / "genselfie.json"
    
    if workflow_path.exists():
        with open(workflow_path, "r") as f:
            return json.load(f)
    
    return {
        "error": "No workflow configured. Please add workflows/genselfie.json"
    }


def inject_images_into_workflow(
    workflow: dict,
    fan_image: str,
    influencer_image: Optional[str] = None
) -> dict:
    """Inject image filenames into the workflow.
    
    Based on genselfie.json workflow structure:
    - Node 42: Influencer image (LoadImage)
    - Node 46: Fan image (LoadImage)
    """
    # Node 42: Influencer image
    if "42" in workflow and influencer_image:
        workflow["42"]["inputs"]["image"] = influencer_image
    
    # Node 46: Fan image
    if "46" in workflow:
        workflow["46"]["inputs"]["image"] = fan_image
    
    return workflow


def set_random_seed(workflow: dict) -> dict:
    """Set a random seed in the RandomNoise node.
    
    Based on genselfie.json workflow structure:
    - Node 25: RandomNoise with noise_seed
    """
    # Node 25: RandomNoise
    if "25" in workflow:
        workflow["25"]["inputs"]["noise_seed"] = random.randint(0, 2**53 - 1)
    
    return workflow
