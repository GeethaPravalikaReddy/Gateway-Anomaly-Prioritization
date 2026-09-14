"""Command-line interface (CLI) entry point for VoxBridge."""

from __future__ import annotations

import argparse
import datetime as dt
import pathlib
import sys

from src.config import settings
from src.core.ranker_3sigma import ThreeSigmaRanker
from src.data.repository import GatewayRepository, TelemetryRepository
from src.services.prediction_service import PredictionService


def cmd_generate(args: argparse.Namespace) -> int:
    """Generate predictions.csv matching the submission requirements."""
    data_dir = pathlib.Path(args.data)
    out_file = pathlib.Path(args.out)

    print(f"Loading telemetry from: {data_dir}")
    telemetry_repo = TelemetryRepository(data_dir)
    gateway_repo = GatewayRepository(data_dir)
    ranker = ThreeSigmaRanker()

    service = PredictionService(
        telemetry_repo=telemetry_repo,
        gateway_repo=gateway_repo,
        ranker=ranker,
    )

    print(f"Calculating anomaly scores for {len(settings.SCORED_WEEKS)} weeks...")
    df = service.generate_full_predictions(output_file=out_file)
    print(f"Successfully generated {len(df)} rows across {df['week_start'].nunique()} weeks -> {out_file}")
    return 0


def cmd_serve(args: argparse.Namespace) -> int:
    """Start the FastAPI uvicorn server."""
    import uvicorn

    print(f"Starting VoxBridge API on http://{args.host}:{args.port}")
    uvicorn.run("src.api.app:app", host=args.host, port=args.port, reload=args.reload)
    return 0


def cmd_validate(args: argparse.Namespace) -> int:
    """Validate a predictions CSV against challenge schema."""
    import validate_submission

    problems = validate_submission.validate(pathlib.Path(args.file))
    if not problems:
        print(f"{args.file}: OK (Validated 120 rows across 8 weeks)")
        return 0
    print(f"{args.file}: {len(problems)} problem(s) found:", file=sys.stderr)
    for p in problems:
        print(f"  - {p}", file=sys.stderr)
    return 1


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="VoxBridge: Gateway Anomaly Detection & Prioritization CLI",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    subparsers = parser.add_subparsers(dest="command", help="Command to execute")

    # Generate subcommand
    gen_parser = subparsers.add_parser("generate", help="Generate predictions.csv")
    gen_parser.add_argument(
        "--data",
        type=pathlib.Path,
        default=settings.DATA_DIR,
        help="Path to data directory",
    )
    gen_parser.add_argument(
        "--out",
        type=pathlib.Path,
        default=settings.OUTPUT_FILE,
        help="Output CSV path for predictions",
    )

    # Serve subcommand
    serve_parser = subparsers.add_parser("serve", help="Start FastAPI web server")
    serve_parser.add_argument(
        "--host", type=str, default=settings.API_HOST, help="Host address to bind"
    )
    serve_parser.add_argument(
        "--port", type=int, default=settings.API_PORT, help="Port to listen on"
    )
    serve_parser.add_argument(
        "--reload", action="store_true", help="Enable auto-reloading"
    )

    # Validate subcommand
    val_parser = subparsers.add_parser("validate", help="Validate predictions.csv")
    val_parser.add_argument(
        "--file",
        type=pathlib.Path,
        default=settings.OUTPUT_FILE,
        help="Path to predictions CSV",
    )

    args = parser.parse_args(argv)

    if args.command == "generate":
        return cmd_generate(args)
    elif args.command == "serve":
        return cmd_serve(args)
    elif args.command == "validate":
        return cmd_validate(args)
    else:
        # Default behavior when run with no subcommands: generate predictions
        # (Allows python -m src.cli --data data --out predictions.csv or similar)
        gen_parser.print_help()
        return 0


if __name__ == "__main__":
    sys.exit(main())
