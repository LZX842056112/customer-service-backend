"""
定义Http客户端
IO/网络传输使用异步
同步、异步
"""

import asyncio
from httpx import AsyncClient

http_client: AsyncClient | None = None


def init_http_client():
    global http_client

    http_client = AsyncClient(timeout=120)


async def dispose_http_client():
    await http_client.aclose()


async def main():
    init_http_client()

    response = await http_client.get(url="http://111.228.53.183:18081/orders/A20260410001")
    # response = await http_client.get(url="http://192.168.200.125:18081/orders/A20260410001")

    data = response.json()

    print(data)


if __name__ == '__main__':
    asyncio.run(main())
