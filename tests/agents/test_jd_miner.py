import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from backend.agents.jd_miner import JDMiner


@pytest.mark.asyncio
async def test_fetch_extracts_keywords():
    html = "<html><body><p>We need Python and React developers with PostgreSQL experience.</p></body></html>"
    mock_response = MagicMock()
    mock_response.text = html
    mock_response.raise_for_status = MagicMock()

    with patch("httpx.AsyncClient") as mock_client_cls:
        mock_client = AsyncMock()
        mock_client.get = AsyncMock(return_value=mock_response)
        mock_client_cls.return_value.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client_cls.return_value.__aexit__ = AsyncMock(return_value=False)

        miner = JDMiner()
        result = await miner.fetch("https://example.com/job")

    assert "python" in result["keywords"]
    assert "react" in result["keywords"]
    assert result["url"] == "https://example.com/job"


@pytest.mark.asyncio
async def test_fetch_raises_on_http_error():
    import httpx

    with patch("httpx.AsyncClient") as mock_client_cls:
        mock_client = AsyncMock()
        mock_response = MagicMock()
        mock_response.raise_for_status.side_effect = httpx.HTTPStatusError(
            "404", request=MagicMock(), response=MagicMock()
        )
        mock_client.get = AsyncMock(return_value=mock_response)
        mock_client_cls.return_value.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client_cls.return_value.__aexit__ = AsyncMock(return_value=False)

        miner = JDMiner()
        with pytest.raises(Exception):
            await miner.fetch("https://example.com/job")
