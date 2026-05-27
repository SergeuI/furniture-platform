import asyncio

from services.viyar_parser import run_parser


async def main():
    await run_parser()


if __name__ == "__main__":
    asyncio.run(main())