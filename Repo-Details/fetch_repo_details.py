import requests
import csv
import time
import logging
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()
GITHUB_URL = os.getenv('GITHUB_URL')
ORG_NAME = os.getenv('ORG_NAME')
TOKEN = os.getenv('GITHUB_TOKEN')

# Logging setup
if not os.path.exists('logs'):
    os.makedirs('logs')
logging.basicConfig(filename='logs/repo_fetch.log', level=logging.INFO,
                    format='%(asctime)s:%(levelname)s:%(message)s')

# API endpoint setup
if "github.com" in GITHUB_URL:
    API_URL = "https://api.github.com/graphql"
else:
    API_URL = f"{GITHUB_URL}/api/graphql"

headers = {
    "Authorization": f"Bearer {TOKEN}",
    "Accept": "application/vnd.github+json"
}

# Updated GraphQL query with aliases for refs
query = """
query($org: String!, $cursor: String) {
  organization(login: $org) {
    repositories(first: 50, after: $cursor) {
      pageInfo {
        hasNextPage
        endCursor
      }
      nodes {
        name
        diskUsage
        visibility
        defaultBranchRef {
          target {
            ... on Commit {
              history {
                totalCount
              }
            }
          }
        }
        branches: refs(refPrefix: "refs/heads/") {
          totalCount
        }
        pullRequests(states: OPEN) {
          totalCount
        }
        mergedPRs: pullRequests(states: MERGED) {
          totalCount
        }
        closedPRs: pullRequests(states: CLOSED) {
          totalCount
        }
        issues(states: OPEN) {
          totalCount
        }
        closedIssues: issues(states: CLOSED) {
          totalCount
        }
        releases {
          totalCount
        }
        tags: refs(refPrefix: "refs/tags/") {
          totalCount
        }
        languages(first: 5) {
          nodes {
            name
          }
        }
        pushedAt
        updatedAt
      }
    }
  }
}
"""

def fetch_data():
    has_next_page = True
    cursor = None
    repo_data = []

    while has_next_page:
        try:
            variables = {"org": ORG_NAME, "cursor": cursor}
            response = requests.post(API_URL, json={'query': query, 'variables': variables}, headers=headers)

            if response.status_code == 200:
                json_data = response.json()
                if 'errors' in json_data:
                    logging.error(f"GraphQL errors: {json_data['errors']}")
                    print(f"Error: {json_data['errors']}")
                    break

                repos = json_data['data']['organization']['repositories']['nodes']
                page_info = json_data['data']['organization']['repositories']['pageInfo']

                for repo in repos:
                    languages = ", ".join([lang['name'] for lang in repo['languages']['nodes']]) if repo['languages']['nodes'] else "N/A"
                    repo_data.append({
                        "repo_name": repo['name'],
                        "repo_size_mb": round((repo['diskUsage'] or 0) / 1024, 2),
                        "visibility": repo['visibility'],
                        "total_commits": repo['defaultBranchRef']['target']['history']['totalCount'] if repo['defaultBranchRef'] else 0,
                        "total_branches": repo['branches']['totalCount'],
                        "open_prs": repo['pullRequests']['totalCount'],
                        "merged_prs": repo['mergedPRs']['totalCount'],
                        "closed_prs": repo['closedPRs']['totalCount'],
                        "open_issues": repo['issues']['totalCount'],
                        "closed_issues": repo['closedIssues']['totalCount'],
                        "releases": repo['releases']['totalCount'],
                        "tags": repo['tags']['totalCount'],
                        "languages": languages,
                        "last_pushed_at": repo['pushedAt'],
                        "last_updated_at": repo['updatedAt']
                    })

                has_next_page = page_info['hasNextPage']
                cursor = page_info['endCursor']

                logging.info(f"Fetched {len(repos)} repositories, has_next_page: {has_next_page}")
                print(f"Fetched {len(repos)} repositories...")

                # API Rate limiting
                remaining = int(response.headers.get('X-RateLimit-Remaining', 1))
                if remaining < 10:
                    reset_time = int(response.headers.get('X-RateLimit-Reset', time.time() + 60))
                    wait_time = reset_time - time.time() + 5
                    logging.warning(f"Rate limit hit. Sleeping for {wait_time} seconds...")
                    print(f"Rate limit hit. Sleeping for {wait_time} seconds...")
                    time.sleep(wait_time)

            else:
                logging.error(f"HTTP error {response.status_code}: {response.text}")
                print(f"HTTP Error {response.status_code}: {response.text}")
                break

        except Exception as e:
            logging.error(f"Exception: {str(e)}")
            print(f"Exception occurred: {str(e)}")
            break

    return repo_data

def write_csv(data):
    filename = f"{ORG_NAME}_repository_details.csv"
    keys = list(data[0].keys()) if data else []
    with open(filename, "w", newline='') as f:
        writer = csv.DictWriter(f, fieldnames=keys)
        writer.writeheader()
        for row in data:
            writer.writerow(row)

    print(f"CSV file '{filename}' created successfully.")
    logging.info(f"CSV file '{filename}' created.")

if __name__ == "__main__":
    print("Starting to fetch repository details...")
    logging.info("Script started.")
    repo_details = fetch_data()
    if repo_details:
        write_csv(repo_details)
    else:
        print("No repository data fetched.")
        logging.warning("No repository data fetched.")
    logging.info("Script completed.")
