from typing import Any, Optional, List, Dict
import aiomysql


class Database:
    def __init__(self):
        """ Simple database class object. """
        self.pool = None

    async def connect(self, config: Dict[str, str]) -> None:
        self.pool = await aiomysql.create_pool(**config)

    async def disconnect(self) -> None:
        self.pool.close()
        await self.pool.wait_close()

    async def execute(self, query: str, params: Optional[List[Any]] = None) -> int:
        async with self.pool.acquire() as conn:
            async with conn.cursor(aiomysql.Cursor) as cur:
                await cur.execute(query, params)
                await conn.commit()

                return cur.lastrowid

    async def fetchall(
        self, query: str, params: Optional[List[Any]] = None, _dict: bool = False
    ) -> Dict[str, Any]:
        if _dict:
            cursor = aiomysql.DictCursor
        else:
            cursor = aiomysql.Cursor

        async with self.pool.acquire() as conn:
            async with conn.cursor(cursor) as cur:
                await cur.execute(query, params)
                return await cur.fetchall()

    async def fetch(
        self, query: str, params: Optional[List[Any]] = None, _dict: bool = True
    ) -> Dict[str, Any]:
        if _dict:
            cursor = aiomysql.DictCursor
        else:
            cursor = aiomysql.Cursor

        async with self.pool.acquire() as conn:
            async with conn.cursor(cursor) as cur:
                await cur.execute(query, params)
                return await cur.fetchone()

    async def iterall(
        self, query: str, params: Optional[List[Any]] = None, _dict: bool = True
    ) -> Dict[str, Any]:
        if _dict:
            cursor = aiomysql.DictCursor
        else:
            cursor = aiomysql.Cursor

        async with self.pool.acquire() as conn:
            async with conn.cursor(cursor) as cur:
                await cur.execute(query, params)

                async for row in cur:
                    yield row
