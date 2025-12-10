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

from config import settings, logger

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
        logger.error(f"Image not found: {image_path}")
        return False
    
    logger.debug(f"Uploading image to ComfyUI: {image_path.name}")
    
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
            if response.status_code != 200:
                logger.error(f"Upload failed with status {response.status_code}: {response.text}")
                return False
            logger.debug(f"Upload successful: {image_path.name}")
            return True
        except httpx.RequestError as e:
            logger.error(f"Upload failed: {type(e).__name__}: {e}")
            return False
        except Exception as e:
            logger.error(f"Upload failed unexpectedly: {type(e).__name__}: {e}")
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
    
    logger.debug(f"Downloading image from URL: {image_url}")
    
    async with httpx.AsyncClient(follow_redirects=True) as client:
        try:
            # Download image
            response = await client.get(image_url, timeout=30.0)
            if response.status_code != 200:
                logger.error(f"Failed to download image: status {response.status_code}")
                return False
            
            image_data = response.content
            logger.debug(f"Downloaded {len(image_data)} bytes, uploading as {filename}")
            
            # Upload to ComfyUI
            files = {"image": (filename, image_data, "image/png")}
            data = {"type": "input"}
            upload_response = await client.post(
                upload_url,
                files=files,
                data=data,
                timeout=60.0
            )
            if upload_response.status_code != 200:
                logger.error(f"Upload failed with status {upload_response.status_code}: {upload_response.text}")
                return False
            logger.debug(f"Upload from URL successful: {filename}")
            return True
        except httpx.RequestError as e:
            logger.error(f"Upload from URL failed: {type(e).__name__}: {e}")
            return False
        except Exception as e:
            logger.error(f"Upload from URL failed unexpectedly: {type(e).__name__}: {e}")
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
    
    logger.debug("Queueing prompt on ComfyUI...")
    
    async with httpx.AsyncClient() as client:
        try:
            response = await client.post(
                prompt_url,
                json={"prompt": workflow},
                timeout=30.0
            )
            if response.status_code == 200:
                data = response.json()
                prompt_id = data.get("prompt_id")
                logger.debug(f"Prompt queued successfully: {prompt_id}")
                return prompt_id
            else:
                logger.error(f"Queue prompt failed with status {response.status_code}: {response.text}")
        except httpx.RequestError as e:
            logger.error(f"Queue prompt failed: {e}")
    
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
    width: Optional[int] = None,
    height: Optional[int] = None,
    prompt: Optional[str] = None
) -> str:
    """Generate a selfie using ComfyUI.
    
    Args:
        fan_image_url: URL or path to the fan's image
        influencer_images: List of influencer image filenames
        width: Optional output width (from preset)
        height: Optional output height (from preset)
        prompt: Optional custom prompt (from preset)
    
    Returns:
        The prompt_id for tracking the generation
    
    Raises:
        Exception if generation fails to start
    """
    logger.info("Starting selfie generation...")
    logger.debug(f"Fan image: {fan_image_url}")
    logger.debug(f"Influencer images: {influencer_images}")
    if width and height:
        logger.debug(f"Preset dimensions: {width}x{height}")
    if prompt:
        logger.debug(f"Preset prompt: {prompt[:50]}...")
    
    # Upload fan image to ComfyUI
    fan_filename = f"fan_{random.randint(100000, 999999)}.png"
    
    if fan_image_url.startswith("http"):
        logger.debug(f"Fan image is URL, downloading and uploading...")
        success = await upload_image_from_url(fan_image_url, fan_filename)
    else:
        # Local file path
        local_path = Path(fan_image_url)
        if not local_path.is_absolute():
            # Relative path - could be /uploads/... or just a filename
            path_str = local_path.as_posix().lstrip("/")
            if path_str.startswith("uploads/"):
                # Map /uploads/... to the actual upload_dir
                local_path = settings.upload_dir / path_str[8:]  # Remove "uploads/" prefix
            else:
                local_path = settings.base_dir / path_str
        logger.debug(f"Fan image is local file: {local_path}")
        success = await upload_image_to_comfyui(local_path)
        fan_filename = local_path.name
    
    if not success:
        logger.error("Failed to upload fan image to ComfyUI")
        raise Exception("Failed to upload fan image to ComfyUI")
    
    # Upload influencer images if they're local
    logger.debug("Uploading influencer images...")
    for img_filename in influencer_images:
        img_path = settings.upload_dir / img_filename
        if img_path.exists():
            await upload_image_to_comfyui(img_path)
    
    # Load default workflow
    logger.debug("Loading workflow...")
    workflow = get_default_workflow()
    
    # Inject images into workflow
    logger.debug("Injecting images into workflow...")
    workflow = inject_images_into_workflow(
        workflow,
        fan_image=fan_filename,
        influencer_image=influencer_images[0] if influencer_images else None
    )
    
    # Apply preset settings if provided
    if width and height:
        workflow = set_dimensions(workflow, width, height)
    if prompt:
        workflow = set_prompt(workflow, prompt)
    
    # Set random seed
    workflow = set_random_seed(workflow)
    
    # Queue the prompt
    prompt_id = await queue_prompt(workflow)
    
    if not prompt_id:
        logger.error("Failed to queue prompt on ComfyUI")
        raise Exception("Failed to queue prompt on ComfyUI")
    
    logger.info(f"Generation started with prompt_id: {prompt_id}")
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
        logger.debug(f"Prompt {prompt_id} still processing...")
        return {"completed": False}
    
    logger.debug(f"Prompt {prompt_id} complete, fetching result...")
    
    # Get history for result
    history = await get_history(prompt_id)
    
    if not history or prompt_id not in history:
        logger.debug(f"No history found for prompt {prompt_id}")
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
                
                logger.info(f"Generation complete: {image_url}")
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
                
                logger.info(f"Generation complete (gif): {image_url}")
                return {"completed": True, "image_url": image_url}
    
    logger.warning(f"Generation complete but no output found for prompt {prompt_id}")
    return {"completed": True, "image_url": None}


async def download_output_image(image_url: str, save_path: Path) -> bool:
    """Download an output image from ComfyUI and save it locally.
    
    Args:
        image_url: URL of the image on ComfyUI server
        save_path: Local path to save the image
    
    Returns:
        True if successful, False otherwise
    """
    logger.debug(f"Downloading output image: {image_url}")
    
    async with httpx.AsyncClient() as client:
        try:
            response = await client.get(image_url, timeout=60.0)
            if response.status_code == 200:
                save_path.parent.mkdir(parents=True, exist_ok=True)
                with open(save_path, "wb") as f:
                    f.write(response.content)
                logger.debug(f"Image saved to: {save_path}")
                return True
            else:
                logger.error(f"Failed to download image: status {response.status_code}")
        except httpx.RequestError as e:
            logger.error(f"Failed to download image: {e}")
    return False


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


def set_dimensions(workflow: dict, width: int, height: int) -> dict:
    """Set output dimensions in the workflow.
    
    Looks for nodes that have width/height inputs.
    """
    for node_id, node in workflow.items():
        if not isinstance(node, dict):
            continue
        inputs = node.get("inputs", {})
        class_type = node.get("class_type", "")
        
        # Common node types that have width/height
        if class_type in [
            "EmptyLatentImage", "EmptySD3LatentImage", "EmptyImage",
            "EmptyFlux2LatentImage", "Flux2Scheduler"
        ]:
            if "width" in inputs:
                inputs["width"] = width
            if "height" in inputs:
                inputs["height"] = height
        # Workflows that scale input image by total megapixels
        if class_type == "ImageScaleToTotalPixels":
            try:
                mp = max(0.1, min(16.0, round((width * height) / 1_000_000.0, 3)))
                inputs["megapixels"] = mp
            except Exception:
                pass
    
    return workflow


def set_prompt(workflow: dict, prompt_text: str) -> dict:
    """Set the prompt text in the workflow.
    
    Looks for CLIPTextEncode or similar nodes that have text inputs.
    """
    for node_id, node in workflow.items():
        if not isinstance(node, dict):
            continue
        inputs = node.get("inputs", {})
        class_type = node.get("class_type", "")
        
        # Common prompt node types
        if class_type in ["CLIPTextEncode", "CLIPTextEncodeSDXL"]:
            if "text" in inputs:
                inputs["text"] = prompt_text
    
    return workflow
