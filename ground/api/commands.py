"""POST /api/commands, GET /api/commands/{id} — command uplink stub.
Real implementation (TC encode/send + ACK correlation) lands in M7."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

router = APIRouter()


class CommandIn(BaseModel):
    id: int
    arg: int


@router.post("/api/commands")
async def post_command(body: CommandIn):
    raise HTTPException(501, "command uplink not implemented yet — see milestone M7")


@router.get("/api/commands/{command_id}")
async def get_command(command_id: str):
    raise HTTPException(501, "command uplink not implemented yet — see milestone M7")
