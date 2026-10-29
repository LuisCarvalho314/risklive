import importlib.util
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]


def module(name):
    spec = importlib.util.spec_from_file_location(name, ROOT / f"{name}.py")
    value = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(value)
    return value


privacy = module("package_privacy")
metadata = module("candidate")


class PublicationTest(unittest.TestCase):
    def test_private_and_anonymous_denied(self):
        def get(url, token=None):
            if url.startswith("https://api.github.com/"):
                self.assertEqual(token, "credential")
                return 200, {"visibility": "private"}
            self.assertIsNone(token)
            return 403, {}
        privacy.verify("credential", get)

    def test_missing_public_and_unreadable_packages_block(self):
        for status, visibility in ((404, None), (200, "public"), (403, None)):
            with self.subTest(status=status, visibility=visibility), self.assertRaises(ValueError):
                privacy.verify("credential", lambda *args: (status, {"visibility": visibility}))

    def test_public_anonymous_token_is_followed(self):
        calls = []
        def get(url, token=None):
            calls.append((url, token))
            if "api.github.com" in url:
                return 200, {"visibility": "private"}
            if "/token?" in url:
                self.assertIsNone(token)
                return 200, {"token": "anonymous"}
            self.assertEqual(token, "anonymous")
            return 200, {"tags": ["seed"]}
        with self.assertRaises(ValueError):
            privacy.verify("credential", get)
        self.assertEqual(len(calls), 3)

    def test_anonymous_token_without_pull_access_is_safe(self):
        def get(url, token=None):
            if "api.github.com" in url:
                return 200, {"visibility": "private"}
            if "/token?" in url:
                return 200, {"token": "anonymous"}
            return 401, {}
        privacy.verify("credential", get)

    def test_inconclusive_anonymous_check_blocks(self):
        def get(url, token=None):
            if "api.github.com" in url:
                return 200, {"visibility": "private"}
            return 500, {}
        with self.assertRaises(ValueError):
            privacy.verify("credential", get)

    def test_candidate_captures_exact_digests(self):
        env = {"GITHUB_SHA": "a" * 40, "GITHUB_RUN_ID": "123", "GITHUB_RUN_ATTEMPT": "1"}
        refs = {key: [f"ghcr.io/luiscarvalho314/risklive-{key}@sha256:" + "b" * 64] for key in ("app", "web")}
        release = metadata.candidate(env, refs, "c" * 40, "d" * 40)
        self.assertEqual(release["images"]["app"], refs["app"][0])
        self.assertEqual(release["state"]["compatibility"], "unverified")
        refs["web"] = ["ghcr.io/luiscarvalho314/risklive-web:latest"]
        with self.assertRaises(ValueError):
            metadata.candidate(env, refs, "c" * 40, "d" * 40)


if __name__ == "__main__":
    unittest.main()
