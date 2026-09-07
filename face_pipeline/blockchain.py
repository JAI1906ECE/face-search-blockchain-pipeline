from __future__ import annotations

import hashlib
import json
import secrets
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from web3 import Web3

from .errors import PipelineError
from .models import AnchorRecord


def canonical_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def sha256_json(value: Any) -> str:
    return hashlib.sha256(canonical_json(value).encode("utf-8")).hexdigest()


def web3_keccak_json(value: Any) -> str:
    """Use Web3.py's Keccak implementation for local block integrity."""

    return Web3.keccak(text=canonical_json(value)).hex()


class LocalBlockchain:
    """A tiny append-only Web3.py-backed local chain for a wallet-free demo."""

    def __init__(self, state_path: Path) -> None:
        self.state_path = state_path
        self.state = self._load()

    def _load(self) -> dict[str, Any]:
        if not self.state_path.exists():
            genesis = {
                "index": 0,
                "created_at": datetime.now(UTC).isoformat(),
                "previous_hash": "0" * 64,
                "data_hash": "GENESIS",
                "record_id": "genesis",
            }
            genesis["block_hash"] = web3_keccak_json(genesis)
            return {"chain": [genesis]}
        try:
            with self.state_path.open("r", encoding="utf-8") as handle:
                state = json.load(handle)
        except (OSError, json.JSONDecodeError) as exc:
            raise PipelineError(f"Could not read blockchain state: {self.state_path}") from exc
        if not isinstance(state, dict) or not isinstance(state.get("chain"), list):
            raise PipelineError(f"Invalid local blockchain state: {self.state_path}")
        return state

    def _persist(self) -> None:
        self.state_path.parent.mkdir(parents=True, exist_ok=True)
        temporary = self.state_path.with_suffix(".tmp")
        with temporary.open("w", encoding="utf-8") as handle:
            json.dump(self.state, handle, indent=2, sort_keys=True)
            handle.write("\n")
        temporary.replace(self.state_path)

    def anchor(self, payload: dict[str, Any]) -> AnchorRecord:
        latest = self.state["chain"][-1]
        data_hash = sha256_json(payload)
        created_at = datetime.now(UTC).isoformat()
        record_id = secrets.token_hex(8)
        block = {
            "index": len(self.state["chain"]),
            "created_at": created_at,
            "previous_hash": latest["block_hash"],
            "data_hash": data_hash,
            "record_id": record_id,
        }
        block["block_hash"] = web3_keccak_json(block)
        self.state["chain"].append(block)
        self._persist()
        return AnchorRecord(
            record_id=record_id,
            data_hash=data_hash,
            block_index=block["index"],
            block_hash=block["block_hash"],
            previous_block_hash=block["previous_hash"],
            created_at=created_at,
            payload=payload,
        )

    def get_record(self, record_id: str) -> AnchorRecord:
        block = next(
            (item for item in self.state["chain"] if item.get("record_id") == record_id),
            None,
        )
        if block is None or block.get("record_id") == "genesis":
            raise PipelineError(f"No anchored record found for id: {record_id}")
        payload_path = self.state_path.with_name(f"{record_id}.json")
        if not payload_path.exists():
            raise PipelineError(
                f"Chain block exists, but its payload file is missing: {payload_path}"
            )
        try:
            with payload_path.open("r", encoding="utf-8") as handle:
                payload = json.load(handle)
        except (OSError, json.JSONDecodeError) as exc:
            raise PipelineError(f"Could not read anchored payload: {payload_path}") from exc
        return AnchorRecord(
            record_id=record_id,
            data_hash=block["data_hash"],
            block_index=block["index"],
            block_hash=block["block_hash"],
            previous_block_hash=block["previous_hash"],
            created_at=block["created_at"],
            payload=payload,
        )

    def save_payload(self, record: AnchorRecord) -> None:
        payload_path = self.state_path.with_name(f"{record.record_id}.json")
        with payload_path.open("w", encoding="utf-8") as handle:
            json.dump(record.payload, handle, indent=2, sort_keys=True)
            handle.write("\n")

    def verify(self, record_id: str) -> tuple[bool, list[str]]:
        record = self.get_record(record_id)
        problems: list[str] = []
        expected_data_hash = sha256_json(record.payload)
        if expected_data_hash != record.data_hash:
            problems.append("payload hash does not match the on-chain data hash")

        block = next(item for item in self.state["chain"] if item["record_id"] == record_id)
        block_without_hash = {key: value for key, value in block.items() if key != "block_hash"}
        if web3_keccak_json(block_without_hash) != record.block_hash:
            problems.append("block hash is invalid")

        index = record.block_index
        if index == 0:
            problems.append("record cannot be the genesis block")
        else:
            previous = self.state["chain"][index - 1]
            if previous["block_hash"] != record.previous_block_hash:
                problems.append("previous block link is invalid")

        return not problems, problems