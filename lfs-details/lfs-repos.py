import requests
import os
import base64
import time
import pandas as pd
import sys
from dotenv import load_dotenv
from requests.adapters import HTTPAdapter
from requests.packages.urllib3.util.retry import Retry

# Fix for Unicode output in Windows terminal
sys.stdout.reconfigure(encoding='utf-8')

# Load environment variables
load_dotenv()
GITHUB_TOKEN = os.getenv("GITHUB_TOKEN")
GHES_URL = os.getenv("GHES_URL")  # Example: https://github.company.com/api/v3
ORG_NAME = os.getenv("ORG_NAME")  # Example: Org-name

# Headers for authentication
HEADERS = {
    "Authorization": f"token {GITHUB_TOKEN}",
    "Accept": "application/vnd.github.v3+json"
}

# Create session with retry
session = requests.Session()
retry_strategy = Retry(
    total=5,
    backoff_factor=3,
    status_forcelist=[500, 502, 503, 504],
    allowed_methods=["GET"],
)
adapter = HTTPAdapter(max_retries=retry_strategy)
session.mount("https://", adapter)

def safe_request(url):
    """Perform a GET request with retry logic."""
    for attempt in range(3):
        try:
            response = session.get(url, headers=HEADERS, timeout=30)
            if response.status_code == 404:
                return response
            response.raise_for_status()
            return response
        except requests.exceptions.Timeout:
            print(f"Timeout. Retrying... ({attempt + 1}/3)")
            time.sleep(5)
        except requests.exceptions.ConnectionError:
            print(f"Connection error. Retrying... ({attempt + 1}/3)")
            time.sleep(5)
        except requests.exceptions.RequestException as e:
            print(f"Request failed: {e}")
            time.sleep(3)

    print(f"Failed after 3 attempts: {url}")
    return None

def get_repositories(org):
    repos = []
    page = 1
    while True:
        url = f"{GHES_URL}/orgs/{org}/repos?per_page=100&page={page}"
        response = safe_request(url)
        if not response:
            return repos

        data = response.json()
        if not data:
            break

        repos.extend(data)
        if len(repos) % 100 == 0:
            print("Processed 100 repositories, waiting for 10 seconds...")
            time.sleep(10)

        page += 1
        time.sleep(1)

    return repos

def get_branches(repo_name):
    branches = []
    page = 1
    while True:
        url = f"{GHES_URL}/repos/{ORG_NAME}/{repo_name}/branches?per_page=100&page={page}"
        response = safe_request(url)
        if not response:
            return branches

        data = response.json()
        if not data:
            break

        branches.extend([branch["name"] for branch in data])
        page += 1
        time.sleep(1)

    return branches

def check_lfs_usage(repo_name, branch_name):
    url = f"{GHES_URL}/repos/{ORG_NAME}/{repo_name}/contents/.gitattributes?ref={branch_name}"
    response = safe_request(url)

    if response:
        if response.status_code == 404:
            return False
        elif response.status_code == 200:
            try:
                file_content = response.json().get("content", "")
                decoded_content = base64.b64decode(file_content).decode("utf-8")
                if "filter=lfs" in decoded_content:
                    return True
            except Exception as e:
                print(f"Error decoding .gitattributes for {repo_name}: {e}")
    
    return False

def main():
    repositories = get_repositories(ORG_NAME)
    results = []

    print(f"\nChecking LFS usage for repositories in {ORG_NAME}")
    print("=" * 90)
    print(f"{'Repository':<30} | {'Branches':<40} | {'Using LFS'}")
    print("-" * 90)

    for index, repo in enumerate(repositories, start=1):
        repo_name = repo["name"]
        branches = get_branches(repo_name)

        lfs_used = "No"
        for branch in branches:
            if check_lfs_usage(repo_name, branch):
                lfs_used = "Yes"
                break

        print(f"{repo_name:<30} | {', '.join(branches):<40} | {lfs_used}")
        results.append([repo_name, ", ".join(branches), lfs_used])

        if index % 100 == 0:
            print("Processed 100 repositories, waiting for 10 seconds...")
            time.sleep(10)

    print("=" * 90)
    print("✅ LFS check completed.")

    csv_filename = f"{ORG_NAME}_lfs_usage.csv"
    df = pd.DataFrame(results, columns=["Repository", "Branches", "Using LFS"])
    df.to_csv(csv_filename, index=False)
    print(f"📂 Results saved to {csv_filename}")

if __name__ == "__main__":
    main()
