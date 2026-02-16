using System;
using System.Collections.Generic;
using UnityEngine;
using SlimeBusters;

[CreateAssetMenu(menuName = "TD/Upgrades/Dragon Upgrade", fileName = "DragonUpgrade")]
public class DragonUpgradeSO : ScriptableObject
{
    [Header("Identity")]
    public string upgradeId;
    public string displayName;
    [TextArea] public string description;
    public Sprite icon;

    [Header("Who/Where")]
    public DragonType dragonType;         // Fire, Crystal, etc.
    public UpgradeTier tier;              // Tier1 / Tier2 / Tier3

    [Header("Path (generic)")]
    [Tooltip("0..N path index within this dragon (e.g., 0=Damage, 1=Rapid, 2=Control).")]
    public int pathIndex = 0;
    [Tooltip("Optional human label for UI (e.g., 'Damage', 'Rapid', 'Control').")]
    public string pathName = "";

    [Header("Cost & Gating")]
    public int coinCost = 100;
    public int essenceCost = 50; // Essence cost added
    public List<SlimeRequirement> slimeRequirements;
    public List<DragonUpgradeSO> prerequisites;

    [Header("Effects")]
    public List<UpgradeEffectSO> effects;

    [Serializable]
    public class SlimeRequirement
    {
        public SlimeType type;
        public int count;
    }
}
