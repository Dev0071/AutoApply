from unittest.mock import patch

from backend.services.anthropic_client import build_anthropic_client


def test_workspace_header_sent_when_configured():
    """Identity-linked keys are rejected with a 400 unless the request names
    the workspace it acts in."""
    with patch("backend.services.anthropic_client.settings") as s:
        s.anthropic_api_key = "sk-ant-test"
        s.anthropic_workspace_id = "wrkspc_abc123"
        client = build_anthropic_client()

    assert client.default_headers["anthropic-workspace-id"] == "wrkspc_abc123"


def test_no_workspace_header_when_blank():
    """A plain org key must not receive an empty workspace header."""
    with patch("backend.services.anthropic_client.settings") as s:
        s.anthropic_api_key = "sk-ant-test"
        s.anthropic_workspace_id = ""
        client = build_anthropic_client()

    assert "anthropic-workspace-id" not in client.default_headers


def test_whitespace_only_workspace_id_is_ignored():
    with patch("backend.services.anthropic_client.settings") as s:
        s.anthropic_api_key = "sk-ant-test"
        s.anthropic_workspace_id = "   "
        client = build_anthropic_client()

    assert "anthropic-workspace-id" not in client.default_headers
