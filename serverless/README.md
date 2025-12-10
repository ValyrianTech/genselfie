# GenSelfie Serverless Worker

A RunPod serverless worker for GenSelfie image generation.

## Overview

This worker receives generation requests via RunPod's serverless API and processes them using ComfyUI. It's designed to scale to zero when not in use, reducing costs.

## Input Format

```json
{
    "input": {
        "fan_image": "https://example.com/fan.jpg or base64 encoded image",
        "influencer_image": "https://example.com/influencer.jpg or base64 encoded image",
        "width": 1024,
        "height": 1024,
        "prompt": "optional custom prompt",
        "return_base64": false
    }
}
```

### Parameters

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `fan_image` | string | Yes | URL or base64-encoded fan image |
| `influencer_image` | string | Yes | URL or base64-encoded influencer image |
| `width` | int | No | Output width (default: workflow default) |
| `height` | int | No | Output height (default: workflow default) |
| `prompt` | string | No | Custom prompt text |
| `return_base64` | bool | No | Return image as base64 instead of URL (default: false) |

## Output Format

### Success (URL)
```json
{
    "success": true,
    "image_url": "http://comfyui:8188/output/image.png",
    "filename": "image.png"
}
```

### Success (Base64)
```json
{
    "success": true,
    "image_base64": "iVBORw0KGgo...",
    "filename": "image.png"
}
```

### Error
```json
{
    "error": "Error message"
}
```

## Deployment

### 1. Build the Docker image

```bash
cd serverless
docker build --platform linux/amd64 -t yourusername/genselfie-worker:v1.0.0 .
```

### 2. Push to Docker Hub

```bash
docker login
docker push yourusername/genselfie-worker:v1.0.0
```

### 3. Create RunPod Endpoint

1. Go to [RunPod Serverless](https://www.runpod.io/console/serverless)
2. Click "New Endpoint"
3. Select "Import from Docker Registry"
4. Enter your image: `yourusername/genselfie-worker:v1.0.0`
5. Configure:
   - Select GPU type (RTX PRO 6000 recommended for FLUX.2)
   - Set environment variables if needed
6. Deploy

### 4. Send Requests

```bash
curl -X POST "https://api.runpod.ai/v2/YOUR_ENDPOINT_ID/runsync" \
  -H "Authorization: Bearer YOUR_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "input": {
      "fan_image": "https://example.com/fan.jpg",
      "influencer_image": "https://example.com/influencer.jpg",
      "width": 1024,
      "height": 1024
    }
  }'
```

## Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `COMFYUI_URL` | `http://127.0.0.1:8188` | ComfyUI server URL |
| `WORKFLOW_PATH` | `/workflows/genselfie.json` | Path to workflow JSON |

## Local Testing

Create a `test_input.json`:
```json
{
    "input": {
        "fan_image": "https://example.com/fan.jpg",
        "influencer_image": "https://example.com/influencer.jpg"
    }
}
```

Run:
```bash
python handler.py
```

The handler will automatically use `test_input.json` for local testing.
