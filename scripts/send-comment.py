#!/usr/bin/env python3

import sys
from github import Github


def get_owner_repo(repo_url):
    pos = repo_url.rfind('/', 0, repo_url.rfind('/'))
    return repo_url[pos+1:]


def send_message(repo, token, pr_id, msg):
    g = Github(token)
    repo = g.get_repo(repo)
    pr = repo.get_pull(pr_id)
    print("Sending message to PR titled: {}".format(pr.title))
    pr.create_issue_comment(msg)


if __name__ == "__main__":
    token = sys.argv[1]
    repo_url = sys.argv[2]
    pr_id = int(sys.argv[3])
    msg = sys.argv[4]

    repo = get_owner_repo(repo_url)
    send_message(repo, token, pr_id, msg)
