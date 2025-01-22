import asyncio
import time


async def cpu_heavy_work():
    print(f"Starting CPU work at {time.strftime('%H:%M:%S')}")
    # Simulate CPU-heavy work with a loop
    result = 0
    for i in range(200_000_000):
        result += i
    print(f"Finished CPU work at {time.strftime('%H:%M:%S')}")


async def io_work():
    print(f"Starting I/O work at {time.strftime('%H:%M:%S')}")
    await asyncio.sleep(2)  # Simulates I/O operation like network call
    print(f"Finished I/O work at {time.strftime('%H:%M:%S')}")


async def main():
    # These will NOT run concurrently - CPU work blocks everything
    await asyncio.gather(cpu_heavy_work(), cpu_heavy_work(), cpu_heavy_work())

    print("\nNow trying I/O work...\n")

    # These WILL run concurrently
    await asyncio.gather(io_work(), io_work(), io_work())


asyncio.run(main())
