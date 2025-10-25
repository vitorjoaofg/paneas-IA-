import asyncio

from vllm.entrypoints.openai.api_server import run_server
from vllm.entrypoints.openai.cli import make_arg_parser


def parse_args():
    parser = make_arg_parser()
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    asyncio.run(run_server(args))


if __name__ == "__main__":
    main()
