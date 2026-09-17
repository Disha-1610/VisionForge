# backend/app/routers/system.py
"""
System Router — Dev & Environment Metadata (Anil).

Endpoints:
  GET /api/v1/system/network  - Resolve the dev machine's LAN IP for mobile handoff QR codes
"""

from __future__ import annotations

import socket

from fastapi import APIRouter, Depends

from app.core.security import get_current_user
from app.models.user import User

router = APIRouter(prefix="/system", tags=["system"])

_PUBLIC_PROBE = ("8.8.8.8", 80)


def _get_lan_ip() -> str:
    """Best-effort LAN IP via a UDP probe (no packets actually sent)."""
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        sock.connect(_PUBLIC_PROBE)
        return str(sock.getsockname()[0])
    except Exception:
        return "localhost"
    finally:
        sock.close()


@router.get("/network")
async def get_network_info(current_user: User = Depends(get_current_user)) -> dict:
    """Return the host LAN IP so mobile devices can reach the dev server."""
    return {"ip": _get_lan_ip(), "hostname": socket.gethostname()}