# utils/database.py
import asyncpg
import logging

log = logging.getLogger(__name__)

# --- Schema ---
# CREATE TABLE IF NOT EXISTS users (
#     user_id BIGINT PRIMARY KEY,
#     wins INTEGER DEFAULT 0,
#     losses INTEGER DEFAULT 0,
#     total_fights INTEGER DEFAULT 0
# );
#
# CREATE TABLE IF NOT EXISTS user_weapons (
#     user_id BIGINT REFERENCES users(user_id) ON DELETE CASCADE,
#     weapon_name VARCHAR(50),
#     uses INTEGER DEFAULT 0,
#     wins INTEGER DEFAULT 0,
#     PRIMARY KEY (user_id, weapon_name)
# );
# --- -------- ---

async def setup_db(pool):
    """Creates necessary tables if they don't exist."""
    async with pool.acquire() as conn:
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS users (
                user_id BIGINT PRIMARY KEY,
                wins INTEGER DEFAULT 0,
                losses INTEGER DEFAULT 0,
                total_fights INTEGER DEFAULT 0
            );
        """)
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS user_weapons (
                user_id BIGINT REFERENCES users(user_id) ON DELETE CASCADE,
                weapon_name VARCHAR(50),
                uses INTEGER DEFAULT 0,
                wins INTEGER DEFAULT 0,
                PRIMARY KEY (user_id, weapon_name)
            );
        """)
    log.info("Database tables ensured.")


async def get_user_stats(pool, user_id: int):
    """Fetches user stats, creating the user if they don't exist."""
    async with pool.acquire() as conn:
        stats = await conn.fetchrow("SELECT wins, losses, total_fights FROM users WHERE user_id = $1", user_id)
        if stats is None:
            await conn.execute("INSERT INTO users (user_id) VALUES ($1)", user_id)
            log.info(f"Created new user entry for ID: {user_id}")
            return {'wins': 0, 'losses': 0, 'total_fights': 0}
        return dict(stats) # Convert record to dict

async def get_weapon_stats(pool, user_id: int, weapon_name: str):
    """Fetches weapon stats for a user, creating the entry if it doesn't exist."""
    async with pool.acquire() as conn:
        # Ensure user exists first (get_user_stats does this)
        await get_user_stats(pool, user_id)
        
        stats = await conn.fetchrow(
            "SELECT uses, wins FROM user_weapons WHERE user_id = $1 AND weapon_name = $2",
            user_id, weapon_name
        )
        if stats is None:
            await conn.execute(
                "INSERT INTO user_weapons (user_id, weapon_name) VALUES ($1, $2)",
                user_id, weapon_name
            )
            log.info(f"Created new weapon entry for User {user_id}, Weapon: {weapon_name}")
            return {'uses': 0, 'wins': 0}
        return dict(stats)

async def record_fight(pool, attacker_id: int, defender_id: int, weapon_name: str, attacker_won: bool):
    """Updates stats for both users and the attacker's weapon after a fight."""
    async with pool.acquire() as conn:
        async with conn.transaction():
            # Ensure users exist
            await get_user_stats(pool, attacker_id)
            await get_user_stats(pool, defender_id)
            # Ensure weapon exists for attacker
            await get_weapon_stats(pool, attacker_id, weapon_name)

            # Update attacker stats
            if attacker_won:
                await conn.execute(
                    "UPDATE users SET wins = wins + 1, total_fights = total_fights + 1 WHERE user_id = $1",
                    attacker_id
                )
                await conn.execute(
                    "UPDATE user_weapons SET uses = uses + 1, wins = wins + 1 WHERE user_id = $1 AND weapon_name = $2",
                    attacker_id, weapon_name
                )
            else:
                await conn.execute(
                    "UPDATE users SET losses = losses + 1, total_fights = total_fights + 1 WHERE user_id = $1",
                    attacker_id
                )
                await conn.execute(
                    "UPDATE user_weapons SET uses = uses + 1 WHERE user_id = $1 AND weapon_name = $2",
                    attacker_id, weapon_name
                )

            # Update defender stats
            if not attacker_won:
                 await conn.execute(
                    "UPDATE users SET wins = wins + 1, total_fights = total_fights + 1 WHERE user_id = $1",
                    defender_id
                )
            else:
                await conn.execute(
                    "UPDATE users SET losses = losses + 1, total_fights = total_fights + 1 WHERE user_id = $1",
                    defender_id
                )
    log.info(f"Recorded fight: Attacker {attacker_id}, Defender {defender_id}, Weapon {weapon_name}, Attacker Won: {attacker_won}")


async def get_top_weapons(pool, user_id: int, limit: int = 5):
    """Gets the most used (and potentially highest win rate) weapons for a user."""
    async with pool.acquire() as conn:
        # Order by uses, then wins as a tie-breaker
        rows = await conn.fetch(
            """
            SELECT weapon_name, uses, wins
            FROM user_weapons
            WHERE user_id = $1
            ORDER BY uses DESC, wins DESC
            LIMIT $2
            """,
            user_id, limit
        )
        return [dict(row) for row in rows]