using UnityEngine;

[CreateAssetMenu(fileName = "SlimeDef", menuName = "TD/Slime Definition")]
public class SlimeDef : ScriptableObject
{// In SlimeDef.cs
 // SlimeDef.cs  (add near your other aura fields)

    [Header("Auras")]
    [Tooltip("If > 0, this slime emits a healing aura that heals self + allies in radius (HP/sec).")]
    public float healingAuraPerSecond = 0f;

    [Tooltip("If > 0, this slime emits an aura that increases Max HP by this percent (e.g., 0.2 = +20%).")]
    public float maxHpAuraPercent = 0f;

    [Tooltip("Extra resistance (percent points) granted to allies in radius. 0..100 per type. Stacks additively with other auras.")]
    public Resistances resistanceAuraBonus;

    [Tooltip("Aura radius for any auras set above.")]
    public float auraRadius = 0f;

    [Header("Identity")]
    public string displayName = "Slime";
    public Color tint = Color.white;   // tint your sprite for quick visual variation
    public int bounty = 1;             // coins on death
    public float scale = 1f;

    [Header("Stats")]
    public float maxHP = 2;
    public float moveSpeed = 2f;

    [Header("Behaviours")]
    public bool splitsOnDeath = false;
    public SlimeDef[] splitChilds;        // what it splits into
    public int splitCount = 2;

    public bool regenerates = false;
    public int regenPerSecond = 1;

    public bool camo = false;          // can only be targeted by towers with detection
    public bool slowImmune = false;    // ignore slow

    [System.Obsolete("Use resistances.lightning instead.")]
    public bool lightningResist = false; // legacy: halve lightning damage (now replaced by %)

    public bool shielded = false;
    public int shieldHP = 3;           // depletes before HP

    [Header("Resistances (0% = none, 100% = immune)")]
    public Resistances resistances = new();

    [System.Serializable]
    public struct Resistances
    {
        [Range(0, 100)] public int fire;
        [Range(0, 100)] public int ice;
        [Range(0, 100)] public int lightning;
        [Range(0, 100)] public int egg;
        [Range(0, 100)] public int crystal;
        // Optional: if you want a base Physical resistance too
        [Range(0, 100)] public int physical;
    }

    [Header("Visual/Prefab")]
    public Sprite overrideSprite;      // optional per-type sprite
}
