#!/bin/bash

# Start the GenSelfie application in the background
python main.py --host 0.0.0.0 --port 8000 &

# Keep the container running for web terminal access
sleep infinity
