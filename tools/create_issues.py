import os
import re
import json
import time
import urllib.request
import urllib.error
import argparse

# Configuration
DEFAULT_REPO = "CSY-333/Crowling"
TASK_FILE = "docs/task2.md"

def parse_markdown_to_issues(filepath):
    """
    Parses the task.md file.
    Returns a list of dicts: {'title': str, 'body': str}
    Logic:
    - Splits by '## ' (Project Phases/Sections).
    - Use the Header as Title.
    - Use variables content as Body.
    """
    if not os.path.exists(filepath):
        # Fallback to docs/task.md if task2.md doesn't exist
        fallback = "docs/task.md"
        if os.path.exists(fallback):
            print(f"Warning: {filepath} not found, using {fallback}")
            filepath = fallback
        else:
            raise FileNotFoundError(f"Could not find task file: {filepath}")

    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()

    # Split by level 2 headers (## )
    # Regex to split but keep the delimiter is tricky, so manual line processing is safer.
    lines = content.split('\n')
    
    issues = []
    current_issue = None
    
    for line in lines:
        if line.strip().startswith('## '):
            # Save previous if exists
            if current_issue:
                issues.append(current_issue)
            
            # Start new issue
            title = line.strip().replace('## ', '').strip()
            current_issue = {'title': title, 'body_lines': []}
        
        elif current_issue:
            current_issue['body_lines'].append(line)
            
    # Append last one
    if current_issue:
        issues.append(current_issue)
        
    # Format bodies
    formatted_issues = []
    for i in issues:
        body = "\n".join(i['body_lines']).strip()
        # Ensure checklists are properly formatted for GitHub
        # (Usually markdown is compatible, but let's just clean up excessive newlines)
        if body or i['title']:
            formatted_issues.append({
                'title': i['title'],
                'body': body
            })
            
    return formatted_issues

def create_github_issue(repo, token, title, body):
    url = f"https://api.github.com/repos/{repo}/issues"
    headers = {
        "Authorization": f"token {token}",
        "Accept": "application/vnd.github.v3+json",
        "Content-Type": "application/json"
    }
    data = json.dumps({"title": title, "body": body}).encode("utf-8")
    
    req = urllib.request.Request(url, data=data, headers=headers, method="POST")
    
    try:
        with urllib.request.urlopen(req) as response:
            result = json.loads(response.read().decode())
            print(f"[SUCCESS] Created Issue #{result['number']}: {title}")
            return True
            
    except urllib.error.HTTPError as e:
        print(f"[ERROR] Failed to create issue '{title}': {e.code} {e.reason}")
        print(e.read().decode())
        return False
    except Exception as e:
        print(f"[ERROR] Unexpected error: {e}")
        return False

def main():
    parser = argparse.ArgumentParser(description="Batch create GitHub issues from task.md")
    parser.add_argument("--token", help="GitHub Personal Access Token (or set GITHUB_TOKEN env var)")
    parser.add_argument("--repo", default=DEFAULT_REPO, help=f"Target repo (default: {DEFAULT_REPO})")
    parser.add_argument("--file", default=TASK_FILE, help=f"Input markdown file (default: {TASK_FILE})")
    parser.add_argument("--no-confirm", action="store_true", help="Skip confirmation prompts")
    
    args = parser.parse_args()
    
    token = args.token or os.environ.get("GITHUB_TOKEN")
    
    if not token:
        print("Error: GitHub Token is required. Use --token or set GITHUB_TOKEN environment variable.")
        print("Quick Tip: Generate one at https://github.com/settings/tokens (Need 'repo' scope)")
        return

    print(f"Reading tasks from {args.file}...")
    try:
        issues = parse_markdown_to_issues(args.file)
    except FileNotFoundError as e:
        print(e)
        return

    print(f"Found {len(issues)} sections to turn into issues.")
    print(f"Target Repo: {args.repo}")
    
    if not args.no_confirm:
        confirm = input("Proceed? (y/n): ")
        if confirm.lower() != 'y':
            print("Aborted.")
            return

    for idx, issue in enumerate(issues, 1):
        print(f"({idx}/{len(issues)}) Creating: {issue['title']}...")
        success = create_github_issue(args.repo, token, issue['title'], issue['body'])
        if success:
            time.sleep(1) # Rate limit politeness
        else:
            if not args.no_confirm:
                retry = input("Retry this issue? (y/n): ")
                if retry.lower() == 'y':
                    create_github_issue(args.repo, token, issue['title'], issue['body'])

if __name__ == "__main__":
    main()
