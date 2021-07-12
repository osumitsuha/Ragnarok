from typing import Any, Optional, List, Dict
import aiomysql


class Database:
    def __init__(self):
        """Simple database class object."""
        self.pool = None

    async def connect(self, config: Dict[str, str]) -> None:
        self.pool = await aiomysql.create_pool(**config)

    async def disconnect(self) -> None:
        self.pool.close()
        await self.pool.wait_close()

    async def _fetch(self, query: str, params: Optional[list[Any]] = None, _dict: bool = False):
        if _dict:
            cursor = aiomysql.DictCursor
        else:
            cursor = aiomysql.Cursor

        async with self.pool.acquire() as conn:
            async with conn.cursor(cursor) as cur:
                await cur.execute(query, params)

                return conn, cur

    async def execute(self, query: str, params: Optional[List[Any]] = None) -> int:
        conn, cur = await self._fetch(query, params)

        await conn.commit()
        return cur.lastrowid

    async def fetchall(
        self, query: str, params: Optional[List[Any]] = None, _dict: bool = False
    ) -> Dict[str, Any]:
        _, cur = await self._fetch(query, params)

        return await cur.fetchall()

    async def fetch(
        self, query: str, params: Optional[List[Any]] = None, _dict: bool = True
    ) -> Dict[str, Any]:
        _, cur = await self._fetch(query, params, _dict)
        
        return await cur.fetchone()

    async def iterall(
        self, query: str, params: Optional[List[Any]] = None, _dict: bool = True
    ) -> Dict[str, Any]:
        _, cur = await self._fetch(query, params, _dict)
        
        async for row in cur:
            yield row
