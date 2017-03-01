#!/usr/bin/env python3

import sys
import json
import requests


def get_owner_repo(repo_url):
    pos = repo_url.rfind('/', 0, repo_url.rfind('/'))
    if repo_url.endswith('.git'):
        return repo_url[pos+1:len(repo_url)-len('.git')]
    else:
        return repo_url[pos+1:]


def send_message(repo, token, pr_id, msg):
    url = "https://api.github.com/repos/{}/issues/{}/comments".format(repo, pr_id)
    payload = {'body': msg}
    r = requests.post(url,
                      data=json.dumps(payload),
                      headers={'Authorization': 'token {}'.format(token)})
    print("Sending message to PR {}".format(url))


if __name__ == "__main__":
    token = sys.argv[1]
    repo_url = sys.argv[2]
    pr_id = int(sys.argv[3])
    msg = sys.argv[4]

    repo = get_owner_repo(repo_url)
    send_message(repo, token, pr_id, msg)
