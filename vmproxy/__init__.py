"""Proxy VictoriaMetrics' vmui and query API at the Home Assistant origin root.

vmui (the VictoriaMetrics web UI) hardcodes root-absolute URLs: every API
call goes to ``/api/v1/...`` and every in-app link to ``/vmui/...``, resolved
against the browser origin. Behind the HA ingress prefix
``/api/hassio_ingress/<token>/`` those requests escape the prefix and die on
Home Assistant's own router - which is why the add-on's ingress shows a dead
page after the login prompt.

This integration claims those exact paths on the HA origin instead:

    /vmui/...      the vmui dashboard (assets are relative - just proxied)
    /api/v1/...    the Prometheus-compatible query API

The browser is authenticated with the regular Home Assistant session
(``requires_auth``); requests are forwarded over the hassio network to the
VictoriaMetrics add-on, with optional basic-auth credentials for the add-on's
``-httpAuth.*`` flags.

No ingress is involved, no URL rewriting, one proxy hop.
"""

from __future__ import annotations

import base64
import logging

import aiohttp
from aiohttp import web
import voluptuous as vol
from yarl import URL

from homeassistant.components.http import KEY_HASS, HomeAssistantView
from homeassistant.const import CONF_HOST, CONF_PASSWORD, CONF_PORT, CONF_USERNAME
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.typing import ConfigType

_LOGGER = logging.getLogger(__name__)

DOMAIN = "vmproxy"

DEFAULT_PORT = 8428

CONFIG_SCHEMA = vol.Schema(
    {
        DOMAIN: vol.Schema(
            {
                vol.Required(CONF_HOST): cv.string,
                vol.Optional(CONF_PORT, default=DEFAULT_PORT): cv.port,
                vol.Optional(CONF_USERNAME): cv.string,
                vol.Optional(CONF_PASSWORD): cv.string,
            }
        )
    },
    extra=vol.ALLOW_EXTRA,
)

# Upstream response headers copied to the browser. Location matters because
# VictoriaMetrics redirects /vmui -> /vmui/ with a relative Location, which
# resolves correctly once we serve at the origin root.
FORWARDED_RESPONSE_HEADERS = ("cache-control", "content-disposition", "location")

# Conditional-request headers worth passing through so asset revalidation
# and CSV downloads behave normally.
FORWARDED_REQUEST_HEADERS = ("If-None-Match", "If-Modified-Since")

_CHUNK_SIZE = 64 * 1024


def _build_auth_header(conf: dict) -> str | None:
    """Build the Authorization header for the add-on's -httpAuth credentials."""
    username = conf.get(CONF_USERNAME)
    if not username:
        return None
    raw = f"{username}:{conf.get(CONF_PASSWORD, '')}".encode()
    return "Basic " + base64.b64encode(raw).decode()


class VMProxyView(HomeAssistantView):
    """Forward one root path tree to the VictoriaMetrics add-on."""

    requires_auth = True

    def __init__(self, base_url: URL, auth_header: str | None) -> None:
        self._base_url = base_url
        self._auth_header = auth_header

    async def _proxy(self, request: web.Request) -> web.StreamResponse:
        """Forward the request verbatim (path + query) and stream the reply."""
        hass = request.app[KEY_HASS]
        session = async_get_clientsession(hass)

        headers = {"Accept-Encoding": "identity"}
        for name in FORWARDED_REQUEST_HEADERS:
            if value := request.headers.get(name):
                headers[name] = value
        if content_type := request.headers.get("Content-Type"):
            headers["Content-Type"] = content_type
        if self._auth_header:
            headers["Authorization"] = self._auth_header

        # raw_path keeps the wire format: percent-encoding and query string.
        url = self._base_url.join(URL(request.raw_path))

        body = None if request.method in ("GET", "HEAD") else await request.read()

        try:
            async with session.request(
                request.method,
                url,
                headers=headers,
                data=body,
                timeout=aiohttp.ClientTimeout(total=None, sock_connect=10),
            ) as upstream:
                out_headers = {
                    name: value
                    for name, value in upstream.headers.items()
                    if name.lower() in FORWARDED_RESPONSE_HEADERS
                }
                response = web.StreamResponse(
                    status=upstream.status, headers=out_headers
                )
                if content_type := upstream.headers.get("Content-Type"):
                    try:
                        response.content_type = content_type.partition(";")[0].strip()
                    except ValueError:
                        pass

                await response.prepare(request)
                async for chunk in upstream.content.iter_chunked(_CHUNK_SIZE):
                    await response.write(chunk)
                await response.write_eof()
                return response

        except (TimeoutError, aiohttp.ServerTimeoutError):
            return self.json_message("VictoriaMetrics proxy timeout", status_code=504)
        except aiohttp.ClientError as err:
            _LOGGER.warning("Proxy error for %s: %s", request.raw_path, err)
            return self.json_message(
                f"VictoriaMetrics proxy error: {err}", status_code=502
            )

    # aiohttp passes the matched {path:.*} group as a kwarg on the main url;
    # the url_extra route ("/vmui" without slash) passes none. The path itself
    # is taken verbatim from request.raw_path, so the argument is unused.
    async def get(self, request: web.Request, path: str = "") -> web.StreamResponse:
        """Handle GET."""
        return await self._proxy(request)

    async def post(self, request: web.Request, path: str = "") -> web.StreamResponse:
        """Handle POST."""
        return await self._proxy(request)

    async def put(self, request: web.Request, path: str = "") -> web.StreamResponse:
        """Handle PUT."""
        return await self._proxy(request)

    async def delete(
        self, request: web.Request, path: str = ""
    ) -> web.StreamResponse:
        """Handle DELETE."""
        return await self._proxy(request)


class VmuiProxyView(VMProxyView):
    """Serve the vmui dashboard at /vmui."""

    url = "/vmui/{path:.*}"
    extra_urls = ["/vmui"]
    name = "vmproxy:vmui"


class ApiV1ProxyView(VMProxyView):
    """Serve the query API at /api/v1."""

    url = "/api/v1/{path:.*}"
    name = "vmproxy:apiv1"


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Register the proxy views."""
    conf = config[DOMAIN]
    base_url = URL(scheme="http", host=conf[CONF_HOST], port=conf[CONF_PORT])
    auth_header = _build_auth_header(conf)

    hass.http.register_view(VmuiProxyView(base_url, auth_header))
    hass.http.register_view(ApiV1ProxyView(base_url, auth_header))

    _LOGGER.info(
        "Proxying /vmui and /api/v1 to %s (%s)",
        base_url,
        "with basic auth" if auth_header else "without auth",
    )
    return True
