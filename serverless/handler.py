"""RunPod Serverless Handler for GenSelfie.

This handler receives generation requests and processes them using a local ComfyUI instance.
Expected to run on a RunPod serverless worker with ComfyUI pre-installed.
"""

import os
import json
import random
import asyncio
import base64
from pathlib import Path
from typing import Optional
from io import BytesIO

import runpod
import httpx

# ComfyUI is expected to be running locally on the same pod
COMFYUI_URL = os.environ.get("COMFYUI_URL", "http://127.0.0.1:8188")
WORKFLOW_PATH = os.environ.get("WORKFLOW_PATH", "/workflows/genselfie.json")


def get_workflow() -> dict:
    """Load the workflow JSON."""
    if os.path.exists(WORKFLOW_PATH):
        with open(WORKFLOW_PATH, "r") as f:
            return json.load(f)
    raise FileNotFoundError(f"Workflow not found at {WORKFLOW_PATH}")


async def upload_image_from_base64(image_data: str, filename: str) -> bool:
    """Upload a base64-encoded image to ComfyUI."""
    upload_url = f"{COMFYUI_URL}/upload/image"
    
    # Decode base64
    if "," in image_data:
        # Handle data URL format: data:image/png;base64,xxxxx
        image_data = image_data.split(",", 1)[1]
    
    image_bytes = base64.b64decode(image_data)
    
    async with httpx.AsyncClient() as client:
        files = {"image": (filename, image_bytes, "image/png")}
        data = {"type": "input"}
        response = await client.post(upload_url, files=files, data=data, timeout=60.0)
        return response.status_code == 200


async def upload_image_from_url(image_url: str, filename: str) -> bool:
    """Download an image from URL and upload to ComfyUI."""
    upload_url = f"{COMFYUI_URL}/upload/image"
    
    async with httpx.AsyncClient(follow_redirects=True) as client:
        # Download image
        response = await client.get(image_url, timeout=30.0)
        if response.status_code != 200:
            return False
        
        image_data = response.content
        
        # Upload to ComfyUI
        files = {"image": (filename, image_data, "image/png")}
        data = {"type": "input"}
        upload_response = await client.post(upload_url, files=files, data=data, timeout=60.0)
        return upload_response.status_code == 200


async def queue_prompt(workflow: dict) -> Optional[str]:
    """Queue a prompt on ComfyUI and return the prompt_id."""
    prompt_url = f"{COMFYUI_URL}/prompt"
    
    async with httpx.AsyncClient() as client:
        response = await client.post(
            prompt_url,
            json={"prompt": workflow},
            timeout=30.0
        )
        if response.status_code == 200:
            data = response.json()
            return data.get("prompt_id")
    return None


async def get_queue_status() -> dict:
    """Get ComfyUI queue status."""
    async with httpx.AsyncClient() as client:
        try:
            response = await client.get(f"{COMFYUI_URL}/queue", timeout=10.0)
            if response.status_code == 200:
                return response.json()
        except httpx.RequestError:
            pass
    return {"queue_pending": [], "queue_running": []}


async def is_prompt_complete(prompt_id: str) -> bool:
    """Check if a prompt has finished processing."""
    queue = await get_queue_status()
    pending = queue.get("queue_pending", [])
    running = queue.get("queue_running", [])
    
    for item in pending + running:
        if len(item) > 1 and item[1] == prompt_id:
            return False
    return True


async def get_history(prompt_id: str) -> Optional[dict]:
    """Get history for a completed prompt."""
    async with httpx.AsyncClient() as client:
        try:
            response = await client.get(f"{COMFYUI_URL}/history/{prompt_id}", timeout=10.0)
            if response.status_code == 200:
                return response.json()
        except httpx.RequestError:
            pass
    return None


async def wait_for_completion(prompt_id: str, timeout: int = 300) -> dict:
    """Wait for generation to complete and return the result."""
    for _ in range(timeout):
        if await is_prompt_complete(prompt_id):
            history = await get_history(prompt_id)
            if history and prompt_id in history:
                prompt_history = history[prompt_id]
                outputs = prompt_history.get("outputs", {})
                
                # Find output image
                for node_id in outputs:
                    node_output = outputs[node_id]
                    images = node_output.get("images", [])
                    if images:
                        img = images[0]
                        filename = img.get("filename")
                        subfolder = img.get("subfolder", "")
                        if filename:
                            if subfolder:
                                image_url = f"{COMFYUI_URL}/output/{subfolder}/{filename}"
                            else:
                                image_url = f"{COMFYUI_URL}/output/{filename}"
                            return {"success": True, "image_url": image_url, "filename": filename}
                
                return {"success": False, "error": "No output image found"}
        await asyncio.sleep(1)
    
    return {"success": False, "error": "Generation timed out"}


def inject_images_into_workflow(workflow: dict, fan_image: str, influencer_image: str) -> dict:
    """Inject image filenames into the workflow."""
    # Node 42: Influencer image
    if "42" in workflow and influencer_image:
        workflow["42"]["inputs"]["image"] = influencer_image
    
    # Node 46: Fan image
    if "46" in workflow:
        workflow["46"]["inputs"]["image"] = fan_image
    
    return workflow


def set_random_seed(workflow: dict) -> dict:
    """Set a random seed in the workflow."""
    if "25" in workflow:
        workflow["25"]["inputs"]["noise_seed"] = random.randint(0, 2**53 - 1)
    return workflow


def set_dimensions(workflow: dict, width: int, height: int) -> dict:
    """Set output dimensions in the workflow."""
    for node_id, node in workflow.items():
        if not isinstance(node, dict):
            continue
        inputs = node.get("inputs", {})
        class_type = node.get("class_type", "")
        
        if class_type in [
            "EmptyLatentImage", "EmptySD3LatentImage", "EmptyImage",
            "EmptyFlux2LatentImage", "Flux2Scheduler"
        ]:
            if "width" in inputs:
                inputs["width"] = width
            if "height" in inputs:
                inputs["height"] = height
        
        if class_type == "ImageScaleToTotalPixels":
            try:
                mp = max(0.1, min(16.0, round((width * height) / 1_000_000.0, 3)))
                inputs["megapixels"] = mp
            except Exception:
                pass
    
    return workflow


def set_prompt(workflow: dict, prompt_text: str) -> dict:
    """Set the prompt text in the workflow."""
    for node_id, node in workflow.items():
        if not isinstance(node, dict):
            continue
        inputs = node.get("inputs", {})
        class_type = node.get("class_type", "")
        
        if class_type in ["CLIPTextEncode", "CLIPTextEncodeSDXL"]:
            if "text" in inputs:
                inputs["text"] = prompt_text
    
    return workflow


async def generate_selfie(job_input: dict) -> dict:
    """Main generation function.
    
    Expected input:
    {
        "fan_image": "base64 encoded image or URL",
        "influencer_image": "base64 encoded image or URL",
        "width": 1024,  # optional
        "height": 1024,  # optional
        "prompt": "custom prompt",  # optional
        "return_base64": false  # optional, if true returns base64 instead of URL
    }
    """
    fan_image = job_input.get("fan_image")
    influencer_image = job_input.get("influencer_image")
    width = job_input.get("width")
    height = job_input.get("height")
    prompt = job_input.get("prompt")
    return_base64 = job_input.get("return_base64", False)
    
    if not fan_image:
        return {"error": "fan_image is required"}
    if not influencer_image:
        return {"error": "influencer_image is required"}
    
    # Generate unique filenames
    fan_filename = f"fan_{random.randint(100000, 999999)}.png"
    influencer_filename = f"influencer_{random.randint(100000, 999999)}.png"
    
    # Upload fan image
    if fan_image.startswith("http"):
        success = await upload_image_from_url(fan_image, fan_filename)
    else:
        success = await upload_image_from_base64(fan_image, fan_filename)
    
    if not success:
        return {"error": "Failed to upload fan image"}
    
    # Upload influencer image
    if influencer_image.startswith("http"):
        success = await upload_image_from_url(influencer_image, influencer_filename)
    else:
        success = await upload_image_from_base64(influencer_image, influencer_filename)
    
    if not success:
        return {"error": "Failed to upload influencer image"}
    
    # Load and configure workflow
    workflow = get_workflow()
    workflow = inject_images_into_workflow(workflow, fan_filename, influencer_filename)
    workflow = set_random_seed(workflow)
    
    if width and height:
        workflow = set_dimensions(workflow, width, height)
    if prompt:
        workflow = set_prompt(workflow, prompt)
    
    # Queue the prompt
    prompt_id = await queue_prompt(workflow)
    if not prompt_id:
        return {"error": "Failed to queue prompt on ComfyUI"}
    
    # Wait for completion
    result = await wait_for_completion(prompt_id)
    
    if not result.get("success"):
        return result
    
    # Optionally convert to base64
    if return_base64:
        async with httpx.AsyncClient() as client:
            response = await client.get(result["image_url"], timeout=60.0)
            if response.status_code == 200:
                image_base64 = base64.b64encode(response.content).decode("utf-8")
                return {
                    "success": True,
                    "image_base64": image_base64,
                    "filename": result["filename"]
                }
            return {"error": "Failed to download result image"}
    
    return result


def handler(job):
    """RunPod handler function."""
    job_input = job.get("input", {})
    
    # Run the async generation
    result = asyncio.get_event_loop().run_until_complete(generate_selfie(job_input))
    
    return result


# Start the serverless worker
runpod.serverless.start({"handler": handler})
