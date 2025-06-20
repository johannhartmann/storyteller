#\!/bin/bash
# This script will remove the secrets from git history

echo "WARNING: This will rewrite git history\!"
echo "Make sure you have a backup of your repository."
echo "Press Ctrl+C to cancel, or Enter to continue..."
read

# Use git filter-branch to remove the @ file from the specific commit
git filter-branch --force --index-filter \
  'git rm --cached --ignore-unmatch "@"' \
  --prune-empty --tag-name-filter cat -- --all

echo "Done\! Now you need to:"
echo "1. git push --force-with-lease origin main"
echo "2. Make sure all team members re-clone the repository"
