from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from .blockchain import LocalBlockchain
from .errors import PipelineError
from .pipeline import FaceSearchPipeline

console = Console()


def _stage(title: str, detail: str) -> None:
    console.print(f"\n[bold cyan]●[/bold cyan] [bold]{title}[/bold]")
    console.print(f"  {detail}")


def run_command(args: argparse.Namespace) -> int:
    image_path = Path(args.image).expanduser().resolve()
    chain_path = Path(args.state).expanduser().resolve()
    _stage("UPLOAD FACE", str(image_path))
    _stage("FACE DETECTION", "InsightFace / buffalo_l on CPU")
    pipeline = FaceSearchPipeline(LocalBlockchain(chain_path))
    face_scan, search_results, record = pipeline.run(image_path)
    console.print(
        f"  detected={face_scan.face_count} face(s), "
        f"confidence={face_scan.primary_face_confidence:.3f}, "
        f"embedding={face_scan.embedding_dimensions} dimensions"
    )

    _stage("REVERSE IMAGE SEARCH", "Google Lens public upload flow")
    console.print(f"  discovered {len(search_results)} social result(s)")
    result_table = Table(show_header=True, header_style="bold magenta")
    result_table.add_column("Title", max_width=36)
    result_table.add_column("URL", max_width=68)
    for result in search_results[:5]:
        result_table.add_row(result.title, result.url)
    console.print(result_table)

    _stage("MATCHING POST + METADATA", record.payload["matching_post"]["title"])
    console.print(f"  source: {record.payload['matching_post']['url']}")
    _stage("SHA-256 HASH", record.data_hash)
    _stage("LOCAL BLOCKCHAIN", f"block #{record.block_index} · record {record.record_id}")
    _stage("VERIFY HASH", "recomputing payload and chain-link hashes")
    valid, problems = pipeline.chain.verify(record.record_id)
    if not valid:
        raise PipelineError("; ".join(problems))

    console.print(
        Panel(
            f"[bold green]✓ MATCHED[/bold green]\n\n"
            f"Record ID: {record.record_id}\n"
            f"Block hash: {record.block_hash}\n"
            f"State file: {chain_path}",
            title="VERIFICATION COMPLETE",
            border_style="green",
        )
    )
    if args.output:
        output_path = Path(args.output).expanduser().resolve()
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(
            json.dumps(
                {
                    "face_scan": face_scan.to_dict(),
                    "search_results": [item.to_dict() for item in search_results],
                    "anchor": record.to_dict(),
                    "verification": {"matched": valid, "problems": problems},
                },
                indent=2,
                sort_keys=True,
            )
            + "\n",
            encoding="utf-8",
        )
        console.print(f"\nSaved JSON evidence bundle to {output_path}")
    return 0


def verify_command(args: argparse.Namespace) -> int:
    chain = LocalBlockchain(Path(args.state).expanduser().resolve())
    matched, problems = chain.verify(args.record_id)
    if matched:
        console.print(
            Panel(
                f"[bold green]✓ MATCHED[/bold green]\n"
                f"Record ID: {args.record_id}\n"
                f"Payload and chain links are intact.",
                title="BLOCKCHAIN VERIFICATION",
                border_style="green",
            )
        )
        return 0
    console.print(
        Panel(
            "[bold red]✗ MISMATCHED[/bold red]\n" + "\n".join(problems),
            title="BLOCKCHAIN VERIFICATION",
            border_style="red",
        )
    )
    return 1


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="face-chain",
        description="Authorized face scan → genuine reverse-image search → local-chain verification",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    run_parser = subparsers.add_parser("run", help="run the full pipeline")
    run_parser.add_argument("--image", required=True, help="authorized face image path")
    run_parser.add_argument(
        "--state",
        default=".face-chain/chain.json",
        help="local blockchain state path (default: .face-chain/chain.json)",
    )
    run_parser.add_argument(
        "--output",
        default="evidence/result.json",
        help="JSON evidence bundle path",
    )
    run_parser.set_defaults(handler=run_command)

    verify_parser = subparsers.add_parser("verify", help="re-verify an anchored record")
    verify_parser.add_argument("--record-id", required=True)
    verify_parser.add_argument(
        "--state",
        default=".face-chain/chain.json",
        help="local blockchain state path",
    )
    verify_parser.set_defaults(handler=verify_command)
    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()
    try:
        raise SystemExit(args.handler(args))
    except PipelineError as exc:
        console.print(f"\n[bold red]Pipeline stopped:[/bold red] {exc}")
        raise SystemExit(1) from exc


if __name__ == "__main__":
    main()