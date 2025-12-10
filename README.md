# GenSelfie

A web application that allows influencers to let their fans generate AI selfies with them. Fans can upload a photo or fetch their profile picture from social media, pay via promo code or payment, and receive an AI-generated selfie with the influencer.

## Features

- **Fan-facing page**: Fans can enter their social media handle or upload a photo, pay via promo code/Stripe/Lightning, and generate a selfie
- **Admin panel**: Influencers can configure branding, pricing, upload reference images, and manage promo codes
- **Social media integration**: Fetch profile pictures from Twitter/X, Bluesky, GitHub, Mastodon, and Nostr
- **Payment options**: Promo codes, Stripe, and Bitcoin Lightning (via LNbits)
- **ComfyUI backend**: Image generation is handled by a ComfyUI server
- **Presets**: Configure multiple generation presets with different influencer images, dimensions, prompts, and pricing

## Prerequisites

### ComfyUI Server (RunPod)

This application requires a ComfyUI server for image generation. You must use the **ValyrianTech ComfyUI template**, which includes an nginx server for serving output images.

Docker images:
- `valyriantech/comfyui-with-flux:latest` - Includes FLUX.1 models pre-installed
- `valyriantech/comfyui-without-flux:latest` - Without FLUX models

**Note:** The template comes with FLUX.1 pre-installed, but GenSelfie requires **FLUX.2**. You will need to download the FLUX.2 models after deployment.

**Note:** FLUX.2 requires an **RTX PRO 6000 GPU** or equivalent.

Deploy on RunPod:

1. **Get Hugging Face access**:
   - Create a [Hugging Face](https://huggingface.co) account if you don't have one
   - Go to [FLUX.2-dev](https://huggingface.co/black-forest-labs/FLUX.2-dev) and request access to the gated repository
   - Create an access token at [Hugging Face Settings](https://huggingface.co/settings/tokens)

2. **Deploy the ComfyUI pod**:
   - Click this link to deploy: [Deploy ComfyUI on RunPod](https://console.runpod.io/deploy?template=rzg5z3pls5&ref=2vdt3dn9)
   - Select an **RTX PRO 6000** GPU (or equivalent with sufficient VRAM)
   - Set your Hugging Face token in the pod's environment variables as `HF_TOKEN`

3. **Download the models**:
   - Once the pod is running, open a terminal in the pod
   - Run: `bash /download_Flux2.sh`
   - Wait for the models to download (this may take a while)

4. **Get the ComfyUI URL**:
   - In the RunPod dashboard, find the **Direct TCP Port Mappings** section (not the proxy URL)
   - Copy the IP and port (e.g., `http://123.45.67.89:12345`)
   - You'll need this for the `COMFYUI_URL` environment variable

## Quick Start

1. **Install dependencies**:
   ```bash
   pip install -r requirements.txt
   ```

2. **Configure environment**:
   ```bash
   cp .env.example .env
   # Edit .env with your settings
   ```

3. **Run the app**:
   ```bash
   python main.py
   ```
   
   With verbose logging:
   ```bash
   python main.py --verbose
   ```
   
   All CLI options:
   ```bash
   python main.py --help
   # Options:
   #   -v, --verbose   Enable verbose logging
   #   --host HOST     Host to bind to (default: 0.0.0.0)
   #   --port PORT     Port to bind to (default: 8000)
   #   --reload        Enable auto-reload for development
   ```

4. **Access the app**:
   - Fan page: http://localhost:8000
   - Admin panel: http://localhost:8000/admin

5. **First-time setup**:
   - On first run, an admin password will be auto-generated and saved to `.env`
   - Check the console output or `.env` file for the password
   - Log in to the admin panel and configure your settings

## Configuration

### Environment Variables

| Variable | Description | Required |
|----------|-------------|----------|
| `ADMIN_PASSWORD` | Admin panel password | Auto-generated |
| `COMFYUI_URL` | ComfyUI server URL | Yes |
| `STRIPE_SECRET_KEY` | Stripe secret key | For Stripe payments |
| `STRIPE_PUBLISHABLE_KEY` | Stripe publishable key | For Stripe payments |
| `LNBITS_URL` | LNbits instance URL | For Lightning payments |
| `LNBITS_API_KEY` | LNbits API key | For Lightning payments |
| `DEBUG` | Enable debug mode | No (default: false) |
| `VERBOSE` | Enable verbose logging | No (default: false) |

## Project Structure

```
GenSelfie/
├── main.py                 # FastAPI entry point
├── config.py               # Settings & environment
├── database.py             # SQLite models
├── routers/
│   ├── admin.py            # Admin panel routes
│   └── public.py           # Fan-facing routes
├── services/
│   ├── comfyui.py          # ComfyUI API client
│   ├── social.py           # Social media profile fetching
│   ├── payments.py         # Stripe & LNbits integration
│   └── codes.py            # Promo code validation
├── templates/              # Jinja2 templates
├── static/                 # CSS, JS, uploads
├── workflows/              # ComfyUI workflow JSON files
├── input_examples/         # Example input images
├── serverless/             # RunPod serverless worker
└── genselfie.db           # SQLite database (created on first run)
```

## Serverless Deployment

For a serverless deployment that scales to zero when not in use, see the [serverless worker documentation](serverless/README.md).

Build and deploy:
```bash
# Set your Docker username
export DOCKER_USERNAME=yourusername

# Build the worker image
./serverless/build.sh

# Push to Docker Hub
docker push $DOCKER_USERNAME/genselfie-worker:latest
```

Then create a serverless endpoint on [RunPod Serverless](https://www.runpod.io/console/serverless).

## Supported Social Platforms

- **Twitter/X**: Uses unavatar.io service
- **Bluesky**: Uses AT Protocol public API
- **GitHub**: Direct avatar URL
- **Mastodon**: Uses instance API with WebFinger
- **Nostr**: Uses nostrhttp.com API (supports npub, hex pubkey, and NIP-05 identifiers)

## License

MIT
