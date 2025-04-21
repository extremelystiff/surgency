# utils/weapons.py
import random

# Using lowercase and simple names for easier matching/storage
WEAPONS = {
    "security": {
        "smg": ["grease gun", "mp5a5", "mp7", "vector"],
        "carbine": ["g36k", "mk18", "m4a1", "honey badger"],
        "rifle": ["m16a4", "l85a2", "vhs-2", "galil sar", "aug a3", "qts-11", "wcx", "f2000 tactical"],
        "battle rifle": ["mk17", "g3a3", "mk14", "tavor 7", "mdr"],
        "machine gun": ["m249", "m60e4", "m240b", "mg-338"],
        "shotgun": ["m870", "ksg"],
        "sniper": ["m24", "tac-338", "m110 sass"],
        "anti-materiel": ["m82a1 cq"],
        "handgun": ["tariq", "l106a1", "m45", "pf940", "mr 73"],
        "melee": ["baton", "combat knife", "tactical axe"],
    },
    "insurgent": {
        "smg": ["sterling", "mp5a2", "uzi", "p90"],
        "carbine": ["sks", "aks-74u", "sg 552", "as val"],
        "rifle": ["m16a2", "akm", "ak-74", "alpha ak", "qbz-03", "galil", "famas f1", "qbz-97", "ar7090", "f2000"],
        "battle rifle": ["fal", "ace 52", "m1 garand"],
        "machine gun": ["rpk", "pkm", "mg3", "hk-21"],
        "shotgun": ["ks-23", "toz-194"],
        "sniper": ["mosin-nagant", "l96a1", "svd"],
        "anti-materiel": ["m99"],
        "handgun": ["welrod", "makarov", "browning hp", "m1911", "m9", "desert eagle"],
        "melee": ["kukri", "shiv", "handjar"],
    }
}

ALL_WEAPONS_LIST = [weapon for side in WEAPONS.values() for category in side.values() for weapon in category]
ALL_WEAPONS_SET = set(ALL_WEAPONS_LIST) # Faster lookups

def get_random_weapon():
    """Returns a random weapon name."""
    return random.choice(ALL_WEAPONS_LIST)

def normalize_weapon_name(name: str) -> str | None:
    """Tries to normalize and validate a weapon name."""
    if not name:
        return None
    name_lower = name.lower().strip()
    # Simple check for now, could add more complex matching later
    if name_lower in ALL_WEAPONS_SET:
        return name_lower
    # Allow common variations maybe? e.g. 'm4' -> 'm4a1'
    if name_lower == 'm4': return 'm4a1'
    if name_lower == 'ak': return 'akm'
    # Add more aliases if needed
    return None # Not found / invalid

def get_all_weapon_names():
    """Returns the list of all normalized weapon names."""
    return ALL_WEAPONS_LIST

# --- Quips ---
WIN_QUIPS = [
    "{attacker} flanks {defender} with their {weapon}, securing the objective!",
    "A quick burst from {attacker}'s {weapon} catches {defender} completely off guard!",
    "{attacker} pushes through smoke, eliminating {defender} point-blank with the {weapon}!",
    "Pinned down, {attacker} lands a perfect headshot on {defender} with the {weapon}.",
    "Suppressive fire from {attacker}'s {weapon} forces {defender} out of cover for the easy kill.",
    "Hearing footsteps, {attacker} pre-fires the corner with the {weapon}, catching {defender} mid-sprint.",
    "A well-thrown grenade from {attacker} weakens {defender}, allowing the {weapon} to finish the job.",
    "{attacker} holds the angle patiently, dropping {defender} with a single shot from the {weapon} as they peek.",
]

LOSS_QUIPS = [
    "{defender} anticipates {attacker}'s push and lands a decisive shot!",
    "{attacker}'s {weapon} jams at the critical moment, giving {defender} the advantage!",
    "Despite a valiant effort with the {weapon}, {attacker} is outmaneuvered by {defender}.",
    "{defender} gets the drop on {attacker} during a reload.",
    "A stray bullet from elsewhere takes {attacker} out while engaging {defender}.",
    "{attacker} checks the wrong corner and {defender} capitalizes on the mistake.",
    "Lag spike! {attacker} freezes just long enough for {defender} to react.",
    "{defender}'s teammate provides covering fire, allowing {defender} to win the duel against {attacker}.",
]

def get_fight_quip(attacker_name: str, defender_name: str, weapon_name: str, attacker_won: bool) -> str:
    """Generates a random descriptive quip for the fight outcome."""
    if attacker_won:
        quip_template = random.choice(WIN_QUIPS)
    else:
        quip_template = random.choice(LOSS_QUIPS)
    
    return quip_template.format(attacker=attacker_name, defender=defender_name, weapon=weapon_name.upper())