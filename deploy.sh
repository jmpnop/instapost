#!/bin/zsh

# Deploy script for instapost
# Syncs code to EC2 instance

set -e

REMOTE_HOST="instapost-deploy"
REMOTE_DIR="/home/ironsirens/instapost"

# Files/dirs to sync (code only, not .env - VM has its own credentials)
SYNC_ITEMS=(
    "instapost"
    "pyproject.toml"
    "crontab.example"
)

echo "Deploying to $REMOTE_HOST..."

for item in "${SYNC_ITEMS[@]}"; do
    if [[ -e "$item" ]]; then
        echo "  Syncing $item..."
        rsync -avz --delete \
            --exclude="__pycache__" \
            --exclude="*.pyc" \
            --exclude=".git" \
            --exclude="*.pem" \
            --exclude="logs/*" \
            --exclude="images/*" \
            --exclude="processed/*" \
            "$item" "$REMOTE_HOST:$REMOTE_DIR/"
    else
        echo "  Skipping $item (not found)"
    fi
done

echo "Done!"
