#!/usr/bin/env python3
"""Record only immutable pushed references, source pins and successful CI identity."""
import json
import os
import re
from pathlib import Path


def candidate(env, digest_lists, seca_revision, seca_v2_revision):
    revision = env["GITHUB_SHA"]
    if not re.fullmatch(r"[0-9a-f]{40}", revision) or not re.fullmatch(r"[0-9a-f]{40}", seca_revision):
        raise ValueError("Invalid source revision")
    if not re.fullmatch(r"[0-9a-f]{40}", seca_v2_revision):
        raise ValueError("Invalid SECA V2 revision")
    images = {}
    for component in ("app", "web"):
        expected = rf"ghcr\.io/luiscarvalho314/risklive-{component}@sha256:[0-9a-f]{{64}}"
        refs = [ref for ref in digest_lists[component] if re.fullmatch(expected, ref)]
        if len(refs) != 1:
            raise ValueError(f"Missing or ambiguous {component} immutable image digest")
        images[component] = refs[0]
    return {
        "schema_version": 1,
        "release_id": f"sha-{revision}-run{env['GITHUB_RUN_ID']}-{env['GITHUB_RUN_ATTEMPT']}",
        "source": {"repository": "LuisCarvalho314/risklive", "revision": revision, "seca_revision": seca_revision, "seca_v2_revision": seca_v2_revision},
        "images": images,
        "ci": {"conclusion": "success", "run_id": env["GITHUB_RUN_ID"],
               "run_url": f"https://github.com/LuisCarvalho314/risklive/actions/runs/{env['GITHUB_RUN_ID']}",
               "run_attempt": env["GITHUB_RUN_ATTEMPT"], "workflow": "ci.yml"},
        # Compatibility requires a separately reviewed infra assertion; a build
        # must never declare its own production database migrations safe.
        "state": {"compatibility": "unverified"},
    }


if __name__ == "__main__":
    refs = {component: json.loads(Path(f"{component}-digests.json").read_text()) for component in ("app", "web")}
    data = candidate(os.environ, refs, Path("docker/seca/SOURCE_REVISION").read_text().strip(), Path("docker/seca-v2/SOURCE_REVISION").read_text().strip())
    Path("candidate.json").write_text(json.dumps(data, indent=2) + "\n")
