#!/usr/bin/env python3
"""Refuse to publish application layers without verified private GHCR packages.

Provision the two package namespaces using non-application seed images, set them
private, disable repository permission inheritance and grant this repository's
Actions access. Missing or unreadable packages block first application publication.
No credential or HTTP response body is printed.
"""
import json
import os
import urllib.error
import urllib.parse
import urllib.request

OWNER = "luiscarvalho314"
PACKAGES = ("risklive-app", "risklive-web")


def request(url, token=None):
    headers = {"Accept": "application/vnd.github+json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    try:
        with urllib.request.urlopen(urllib.request.Request(url, headers=headers), timeout=20) as response:
            return response.status, json.load(response)
    except urllib.error.HTTPError as error:
        return error.code, {}


def verify(token, get=request):
    if not token:
        raise ValueError("GITHUB_TOKEN is required to verify package privacy")
    for package in PACKAGES:
        status, metadata = get(f"https://api.github.com/users/{OWNER}/packages/container/{package}", token)
        if status != 200 or metadata.get("visibility") != "private":
            raise ValueError(f"SETUP REQUIRED: {package}: existing package privacy cannot be confirmed; provision a private non-application seed package and grant Actions access")
        scope = urllib.parse.urlencode({"service": "ghcr.io", "scope": f"repository:{OWNER}/{package}:pull"})
        # Request a genuinely anonymous registry token. A direct unauthenticated
        # manifest request alone returns 401 for public images too.
        status, body = get(f"https://ghcr.io/token?{scope}")
        if status in (401, 403):
            continue
        if status != 200 or not body.get("token"):
            raise ValueError(f"{package}: anonymous access check inconclusive")
        status, _ = get(f"https://ghcr.io/v2/{OWNER}/{package}/tags/list", body["token"])
        if status not in (401, 403):
            raise ValueError(f"{package}: anonymous access was allowed or could not be ruled out")


if __name__ == "__main__":
    try:
        verify(os.environ.get("GH_TOKEN"))
    except (ValueError, OSError, json.JSONDecodeError) as error:
        raise SystemExit(str(error)) from None
    print("Both GHCR packages are private and anonymous access is denied")
