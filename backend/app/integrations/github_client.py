"""
GitHub REST API client and token encryption manager — Phase 6.

Key responsibilities:
- Token encryption / decryption using AES-GCM (SecretKey derived from TOKEN_ENCRYPTION_KEY)
- GitHub OAuth token exchange (auth code -> access token)
- Authenticated GitHub REST API requests:
  - get_user_profile
  - list_user_repos
  - get_repo_details
  - list_repo_tree (git trees API recursive)
  - fetch_file_content (blob / raw)
"""
import base64
import os
import httpx
from typing import Any
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

from app.core.config import get_settings

GITHUB_API_BASE = "https://api.github.com"
GITHUB_OAUTH_BASE = "https://github.com/login/oauth"


def _get_aes_key() -> bytes:
    """Derive 256-bit key from settings.GITHUB_TOKEN_ENCRYPTION_KEY or JWT_SECRET."""
    settings = get_settings()
    key_str = settings.GITHUB_TOKEN_ENCRYPTION_KEY or settings.JWT_SECRET
    raw_key = key_str.encode("utf-8")
    # Ensure 32 bytes via hashing
    import hashlib
    return hashlib.sha256(raw_key).digest()


def encrypt_token(plain_token: str) -> str:
    """Encrypt plain token string using AES-256-GCM. Returns format 'nonce_hex:ciphertext_hex'."""
    aesgcm = AESGCM(_get_aes_key())
    nonce = os.urandom(12)  # 96-bit nonce
    ct = aesgcm.encrypt(nonce, plain_token.encode("utf-8"), None)
    return f"{nonce.hex()}:{ct.hex()}"


def decrypt_token(encrypted_str: str) -> str:
    """Decrypt AES-256-GCM string formatted as 'nonce_hex:ciphertext_hex'."""
    try:
        parts = encrypted_str.split(":", 1)
        if len(parts) != 2:
            raise ValueError("Invalid encrypted token format")
        nonce = bytes.fromhex(parts[0])
        ct = bytes.fromhex(parts[1])
        aesgcm = AESGCM(_get_aes_key())
        pt = aesgcm.decrypt(nonce, ct, None)
        return pt.decode("utf-8")
    except Exception as e:
        raise ValueError(f"Failed to decrypt GitHub token: {e}")


class GitHubClient:
    """Async wrapper for GitHub REST API calls."""

    def __init__(self, access_token: str):
        self.access_token = access_token
        self.headers = {
            "Authorization": f"Bearer {access_token}",
            "Accept": "application/vnd.github.v3+json",
            "User-Agent": "CareerForge-AI-Client",
        }

    @staticmethod
    async def exchange_code_for_token(code: str) -> dict[str, Any]:
        """Exchange OAuth code for an access token."""
        settings = get_settings()
        url = f"{GITHUB_OAUTH_BASE}/access_token"
        payload = {
            "client_id": settings.GITHUB_CLIENT_ID,
            "client_secret": settings.GITHUB_CLIENT_SECRET,
            "code": code,
            "redirect_uri": settings.GITHUB_OAUTH_REDIRECT_URI,
        }
        headers = {"Accept": "application/json"}
        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.post(url, json=payload, headers=headers)
            resp.raise_for_status()
            data = resp.json()
            if "error" in data:
                raise ValueError(f"GitHub OAuth error: {data.get('error_description', data['error'])}")
            return data

    async def get_user_profile(self) -> dict[str, Any]:
        """Fetch authenticated user profile."""
        url = f"{GITHUB_API_BASE}/user"
        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.get(url, headers=self.headers)
            resp.raise_for_status()
            return resp.json()

    async def list_repositories(self, page: int = 1, per_page: int = 100) -> list[dict[str, Any]]:
        """List repositories accessible to the user (owned and accessible)."""
        url = f"{GITHUB_API_BASE}/user/repos"
        params = {
            "sort": "updated",
            "direction": "desc",
            "per_page": per_page,
            "page": page,
            "affiliation": "owner,collaborator,organization_member",
        }
        async with httpx.AsyncClient(timeout=20.0) as client:
            resp = await client.get(url, headers=self.headers, params=params)
            resp.raise_for_status()
            return resp.json()

    async def get_repository(self, owner: str, repo: str) -> dict[str, Any]:
        """Get repository details."""
        url = f"{GITHUB_API_BASE}/repos/{owner}/{repo}"
        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.get(url, headers=self.headers)
            resp.raise_for_status()
            return resp.json()

    async def get_tree(self, owner: str, repo: str, branch: str = "main") -> list[dict[str, Any]]:
        """Fetch full recursive tree for a repository branch using Git Trees API."""
        url = f"{GITHUB_API_BASE}/repos/{owner}/{repo}/git/trees/{branch}"
        params = {"recursive": "1"}
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.get(url, headers=self.headers, params=params)
            resp.raise_for_status()
            data = resp.json()
            return data.get("tree", [])

    async def get_file_content(self, owner: str, repo: str, path: str, branch: str = "main") -> str | None:
        """Fetch file content from GitHub repository."""
        url = f"{GITHUB_API_BASE}/repos/{owner}/{repo}/contents/{path}"
        params = {"ref": branch}
        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.get(url, headers=self.headers, params=params)
            if resp.status_code == 404:
                return None
            resp.raise_for_status()
            data = resp.json()
            if data.get("encoding") == "base64" and "content" in data:
                return base64.b64decode(data["content"]).decode("utf-8", errors="replace")
            elif "content" in data:
                return data["content"]
            return None
