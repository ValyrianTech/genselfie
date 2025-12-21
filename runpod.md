# GenSelfie on RunPod

AI-generated selfies with influencers. Fans upload a photo, pay via promo code/Stripe/Lightning, and get a selfie.

## Quick Start

1. **Deploy ComfyUI pod first** (required for image generation):
   - Use template: [Deploy ComfyUI](https://console.runpod.io/deploy?template=aomdggbx0y&ref=2vdt3dn9)
   - Select **RTX PRO 6000** GPU
   - Set `HF_TOKEN` env var with your Hugging Face token
   - After startup, run: `bash /download_Flux2.sh`

2. **Get ComfyUI URL**:
   - Find **Direct TCP Port Mappings** in RunPod dashboard
   - Copy the IP:port (e.g., `http://123.45.67.89:12345`)

3. **Configure GenSelfie**:
   - Go to `/admin` panel
   - Enter admin password (check console logs on first run, or `/workspace/.env` file)
   - Set ComfyUI URL
   - Upload influencer reference images
   - Create presets

## Environment Variables

| Variable | Description |
|----------|-------------|
| `ADMIN_PASSWORD` | Admin panel password (auto-generated if not set) |
| `COMFYUI_URL` | ComfyUI server URL |
| `STRIPE_SECRET_KEY` | Stripe secret key |
| `STRIPE_PUBLISHABLE_KEY` | Stripe publishable key |
| `PUBLIC_URL` | Your RunPod proxy URL (required for Stripe) |
| `LNBITS_URL` | LNbits instance URL |
| `LNBITS_API_KEY` | LNbits API key |

## Stripe Setup

For Stripe payments on RunPod, you **must** set `PUBLIC_URL`:

1. Find your proxy URL: `https://<POD_ID>-8000.proxy.runpod.net`
2. Set it in Admin → Stripe Settings → Public URL

Without this, Stripe redirects will fail.

## Data Persistence

All data is stored in `/workspace`:
- Database: `/workspace/genselfie.db`
- Uploads: `/workspace/uploads/`
- Config: `/workspace/.env`

Mount a network volume to `/workspace` to persist data across restarts.

## URLs

- **Fan page**: `http://localhost:8000/` or your proxy URL
- **Admin panel**: `http://localhost:8000/admin`

## Troubleshooting

- **Server Offline**: Check ComfyUI URL in admin panel
- **Stripe redirect fails**: Set PUBLIC_URL to your proxy URL
- **Password lost**: Check `/workspace/.env` file

## Links

- [Full Documentation](https://valyriantech.github.io/genselfie/)
- [GitHub](https://github.com/valyriantech/GenSelfie)
