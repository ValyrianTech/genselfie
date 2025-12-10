#!/bin/bash
# Build script for GenSelfie serverless worker
# Run from the repository root: ./serverless/build.sh

set -e

# Configuration
IMAGE_NAME="${DOCKER_USERNAME:-yourusername}/genselfie-worker"
VERSION="${VERSION:-latest}"

echo "Building GenSelfie serverless worker..."
echo "Image: ${IMAGE_NAME}:${VERSION}"

# Create a temporary build context
BUILD_DIR=$(mktemp -d)
trap "rm -rf $BUILD_DIR" EXIT

# Copy necessary files
cp serverless/Dockerfile "$BUILD_DIR/"
cp serverless/handler.py "$BUILD_DIR/"
cp serverless/requirements.txt "$BUILD_DIR/"
cp workflows/genselfie.json "$BUILD_DIR/"

# Update Dockerfile to include workflow
cat >> "$BUILD_DIR/Dockerfile" << 'EOF'

# Copy workflow (added by build script)
COPY genselfie.json /workflows/genselfie.json
EOF

# Build the image
docker build --platform linux/amd64 \
    -t "${IMAGE_NAME}:${VERSION}" \
    "$BUILD_DIR"

echo ""
echo "Build complete!"
echo ""
echo "To push to Docker Hub:"
echo "  docker login"
echo "  docker push ${IMAGE_NAME}:${VERSION}"
