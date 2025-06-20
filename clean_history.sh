#\!/bin/bash
echo "This will remove the @ file from git history"
echo "WARNING: This will rewrite git history\!"
echo "Press Enter to continue or Ctrl+C to cancel..."
read

# Remove the @ file from all commits
git filter-branch --force --index-filter \
  'git rm --cached --ignore-unmatch "@"' \
  --prune-empty --tag-name-filter cat -- --all

echo "Done\! The @ file has been removed from history."
echo "Now you need to force push: git push --force origin main"
