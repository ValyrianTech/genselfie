# GenSelfie

A single-tenant web application that allows influencers to let their fans generate AI selfies with them.

## Features

- **Fan-facing page**: Fans can enter their social media handle or upload a photo, pay via promo code/Stripe/Lightning, and generate a selfie
- **Admin panel**: Influencers can configure branding, pricing, upload reference images, manage promo codes, and upload ComfyUI workflows
- **Social media integration**: Fetch profile pictures from Twitter/X, Bluesky, GitHub, and Mastodon
- **Payment options**: Promo codes, Stripe, and Bitcoin Lightning (via LNbits)
- **ComfyUI backend**: Image generation is handled by a ComfyUI server

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
   
   Or with uvicorn:
   ```bash
   uvicorn main:app --reload
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

### ComfyUI Workflow

Upload your ComfyUI workflow JSON via the admin panel. The workflow should have:
- LoadImage nodes for fan and influencer images
- The node titles should contain "fan" or "influencer" to help the system identify which image goes where

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
└── genselfie.db           # SQLite database
```

## Supported Social Platforms

- **Twitter/X**: Uses unavatar.io service
- **Bluesky**: Uses AT Protocol public API
- **GitHub**: Direct avatar URL
- **Mastodon**: Uses instance API with WebFinger

## License

MIT
