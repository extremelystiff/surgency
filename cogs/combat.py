# cogs/combat.py
import discord
from discord.ext import commands


import random
import math
import logging

from utils import database as db
from utils import weapons

log = logging.getLogger(__name__)

# --- Autocomplete ---
async def weapon_autocomplete(ctx: discord.AutocompleteContext):
    """Provides autocomplete options for weapon names."""
    current_input = ctx.value.lower()
    all_weps = weapons.get_all_weapon_names()
    
    # Filter suggestions based on user input
    suggestions = [
        wep for wep in all_weps 
        if current_input in wep
    ][:25] # Discord limits autocomplete to 25 choices
    
    # If exact match is typed, maybe prioritize it or show it first?
    # For simplicity now, just return the filtered list.
    return suggestions

# --- Cog Class ---
class CombatCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.db_pool = bot.db_pool # Access the pool stored in the bot instance

    def calculate_win_chance(self, attacker_stats, defender_stats, weapon_stats):
        """Calculates the attacker's win chance based on stats."""
        base_chance = 0.50  # 50% base chance

        # --- User Win Rate Modifier ---
        # Avoid division by zero
        attacker_wr = (attacker_stats['wins'] / attacker_stats['total_fights']) if attacker_stats['total_fights'] > 0 else 0.3 # Slight disadvantage if no history
        defender_wr = (defender_stats['wins'] / defender_stats['total_fights']) if defender_stats['total_fights'] > 0 else 0.3

        # Compare win rates, scaling the effect. Max +/- 15% adjustment from overall win rate diff.
        # More fights = more confidence in WR, less impact from single fights
        # Less fights = less confidence, less impact
        # Using tanh to scale the effect non-linearly and bound it
        # We want difference to matter more when close to 50% WR for both
        # Let's try a simpler approach first: direct difference scaling
        wr_diff = attacker_wr - defender_wr
        # Scale difference: Max influence of +/- 20% based on win rate difference
        # More fights means WR is more reliable, apply more weight
        # Let's use a simple confidence factor (can be improved)
        attacker_confidence = min(1.0, attacker_stats['total_fights'] / 20.0) # Max confidence after 20 fights
        defender_confidence = min(1.0, defender_stats['total_fights'] / 20.0)
        avg_confidence = (attacker_confidence + defender_confidence) / 2.0

        user_modifier = wr_diff * 0.25 * avg_confidence # Max +/- 25% adjustment based on WR diff and confidence
        user_modifier = max(-0.20, min(0.20, user_modifier)) # Clamp modifier to +/- 20%

        # --- Weapon Proficiency Modifier ---
        weapon_modifier = 0.0
        if weapon_stats['uses'] > 0:
            # How much better/worse is this weapon WR compared to user's overall WR?
            weapon_wr = weapon_stats['wins'] / weapon_stats['uses']
            relative_weapon_wr = weapon_wr - attacker_wr
            
            # Scale modifier based on usage count (more uses = more reliable)
            weapon_confidence = min(1.0, weapon_stats['uses'] / 10.0) # Max confidence after 10 uses
            
            # Max +/- 15% adjustment based on relative weapon performance & confidence
            weapon_modifier = relative_weapon_wr * 0.20 * weapon_confidence 
            weapon_modifier = max(-0.15, min(0.15, weapon_modifier)) # Clamp modifier

        # --- Final Calculation ---
        win_chance = base_chance + user_modifier + weapon_modifier
        
        # Clamp final win chance (e.g., between 10% and 90%)
        win_chance = max(0.10, min(0.90, win_chance))

        log.debug(f"Win Chance Calculation: Base={base_chance:.2f}, UserMod={user_modifier:.2f} (AttWR={attacker_wr:.2f}, DefWR={defender_wr:.2f}), WeapMod={weapon_modifier:.2f} -> Final={win_chance:.2f}")
        return win_chance

    @commands.slash_command(name="attack", description="Engage another user in simulated Sandstorm combat!")
    @discord.option("target", description="The user you want to attack.", required=True) # ADD discord.
    @discord.option("weapon", description="Weapon to use (optional, random if not specified).", # ADD discord.
            required=False, autocomplete=weapon_autocomplete)
    async def attack(self, ctx: discord.ApplicationContext, target: discord.Member, weapon: str = None):
        """Handler for the /attack command."""
        attacker = ctx.author
        defender = target

        if attacker.id == defender.id:
            await ctx.respond("You can't attack yourself, that's not very tactical!", ephemeral=True)
            return
        if defender.bot:
            await ctx.respond(f"Attacking bots like {defender.mention}? Easy target, but where's the challenge?", ephemeral=True)
            return

        # --- Weapon Selection ---
        chosen_weapon = None
        if weapon:
            normalized_weapon = weapons.normalize_weapon_name(weapon)
            if normalized_weapon:
                chosen_weapon = normalized_weapon
            else:
                await ctx.respond(f"'{weapon}' is not a recognized weapon. Try using the autocomplete!", ephemeral=True)
                return
        else:
            # Pick a random weapon if none specified
            chosen_weapon = weapons.get_random_weapon()
            await ctx.send_followup(f"No weapon specified, grabbing a random {chosen_weapon.upper()}!", ephemeral=True) # Send as followup if needed

        # --- Fetch Stats ---
        try:
            attacker_stats = await db.get_user_stats(self.db_pool, attacker.id)
            defender_stats = await db.get_user_stats(self.db_pool, defender.id)
            weapon_stats = await db.get_weapon_stats(self.db_pool, attacker.id, chosen_weapon)
        except Exception as e:
            log.error(f"Database error during stat fetch for attack: {e}", exc_info=True)
            await ctx.respond("Failed to retrieve combatant stats. Please try again later.", ephemeral=True)
            return
            
        # --- Determine Winner ---
        win_chance = self.calculate_win_chance(attacker_stats, defender_stats, weapon_stats)
        attacker_won = random.random() < win_chance

        # --- Generate Quip ---
        quip = weapons.get_fight_quip(attacker.display_name, defender.display_name, chosen_weapon, attacker_won)

        # --- Record Fight Results ---
        try:
            await db.record_fight(self.db_pool, attacker.id, defender.id, chosen_weapon, attacker_won)
        except Exception as e:
            log.error(f"Database error during fight recording: {e}", exc_info=True)
            # Don't necessarily stop the response, but log the error
            await ctx.respond(f"{quip}\n*(Failed to save fight results due to a database error)*") # Notify user if save failed
            return # Stop here if recording failed.

        # --- Send Response ---
        embed = discord.Embed(title="💥 Combat Report! 💥", color=discord.Color.green() if attacker_won else discord.Color.red())
        embed.description = quip
        
        winner_name = attacker.display_name if attacker_won else defender.display_name
        loser_name = defender.display_name if attacker_won else attacker.display_name
        
        embed.add_field(name="Attacker", value=f"{attacker.mention} ({chosen_weapon.upper()})", inline=True)
        embed.add_field(name="Defender", value=defender.mention, inline=True)
        embed.add_field(name="Outcome", value=f"**{winner_name}** defeated **{loser_name}**!", inline=False)
        embed.add_field(name="Attacker Win Chance", value=f"{win_chance:.1%}", inline=False)
        
        embed.set_footer(text="Use /stats to check your combat record.")

        await ctx.respond(embed=embed)


    @commands.slash_command(name="stats", description="Check your or another user's combat stats.")
    @discord.option("user", description="The user whose stats you want to see (optional, defaults to you).", required=False) # ADD discord.
    async def stats(self, ctx: discord.ApplicationContext, user: discord.Member = None):
        """Handler for the /stats command."""
        target_user = user or ctx.author # Default to command user if none specified

        if target_user.bot:
             await ctx.respond("Bots don't participate in firefights... usually.", ephemeral=True)
             return

        try:
            user_stats = await db.get_user_stats(self.db_pool, target_user.id)
            top_weapons = await db.get_top_weapons(self.db_pool, target_user.id, limit=5)
        except Exception as e:
            log.error(f"Database error fetching stats for {target_user.id}: {e}", exc_info=True)
            await ctx.respond("Failed to retrieve stats. Please try again later.", ephemeral=True)
            return

        # Calculate Win Rate
        total_fights = user_stats['total_fights']
        wins = user_stats['wins']
        losses = user_stats['losses']
        win_rate = (wins / total_fights * 100) if total_fights > 0 else 0

        embed = discord.Embed(title=f"Combat Record: {target_user.display_name}", color=discord.Color.blue())
        embed.set_thumbnail(url=target_user.display_avatar.url)

        embed.add_field(name="Overall Record", value=f"**Wins:** {wins}\n**Losses:** {losses}\n**Total Fights:** {total_fights}", inline=True)
        embed.add_field(name="Win Rate", value=f"{win_rate:.2f}%", inline=True)

        if top_weapons:
            weapon_stats_str = ""
            for wep in top_weapons:
                 wep_wr = (wep['wins'] / wep['uses'] * 100) if wep['uses'] > 0 else 0
                 weapon_stats_str += f"**{wep['weapon_name'].upper()}**: {wep['wins']}W / {wep['uses']}U ({wep_wr:.1f}% WR)\n"
            embed.add_field(name=f"Top {len(top_weapons)} Weapons (by uses)", value=weapon_stats_str, inline=False)
        else:
             embed.add_field(name="Top Weapons", value="No weapon usage recorded yet.", inline=False)
             
        embed.set_footer(text=f"User ID: {target_user.id}")
        await ctx.respond(embed=embed)


def setup(bot):
    bot.add_cog(CombatCog(bot))
