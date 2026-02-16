// DragonUpgrades.cs
using System.Collections.Generic;
using UnityEngine;
using System;

using SlimeBusters;

public class DragonUpgrades : MonoBehaviour
{
    Dragon d;
    public List<DragonUpgradeSO> purchased = new();

    // Generic path lock: -1 means not committed yet
    public bool hasCommittedPath;
    public int committedPath = -1;
    public string upgradeId;
    public void Bind(Dragon dragon) { d = dragon; }

    public bool CanBuy(DragonUpgradeSO upg, int coins, System.Func<SlimeType, int> slimeCount)
    {
        if (!upg) return false;

        // Check if the dragon type matches
        if (upg.dragonType != d.dragonType) return false;

        // Check if the upgrade is already purchased
        if (purchased.Contains(upg)) return false;

        // Check if the player has enough coins (but only check essence if it's not unlocked yet)
        if (!IsUpgradeUnlocked(upg) && coins < upg.coinCost) return false;

        // Check if the player has enough essence for the upgrade (only if it's not unlocked yet)
        if (!IsUpgradeUnlocked(upg) && DragonEssenceManager.Instance.Balance < upg.essenceCost) return false;

        // Check for path uniqueness
        if (HasTierInPath(upg.tier, upg.pathIndex)) return false;

        // Slime gating
        if (upg.slimeRequirements != null)
            foreach (var req in upg.slimeRequirements)
                if (slimeCount(req.type) < req.count) return false;

        // Prerequisite checks
        if (upg.prerequisites != null)
            foreach (var pre in upg.prerequisites)
            {
               
                if (!purchased.Contains(pre)) return false;
            }

        return true;
    }

    private bool IsUpgradeUnlocked(DragonUpgradeSO upg)
    {
        // Check if the upgrade has already been unlocked (either by essence or coins)
        bool unlockedByEssence = DragonEssenceManager.Instance.UpgradeLevels.Exists(u => u.key == upg.upgradeId);
        bool unlockedByCoins = purchased.Contains(upg);

        return unlockedByEssence || unlockedByCoins;
    }



    public bool Buy(DragonUpgradeSO upg)
    {
        if (!upg) return false;
        if (purchased.Contains(upg)) return false;

        // Apply the upgrade effects
        foreach (var fx in upg.effects) fx?.Apply(d);

        // Add the upgrade to the list of purchased upgrades
        purchased.Add(upg);

        // If it's a Tier2 upgrade, commit the path if not already done
        if (upg.tier == UpgradeTier.Tier2 && !hasCommittedPath)
        {
            hasCommittedPath = true;
            committedPath = upg.pathIndex;
        }

        // Save the progress
        DragonEssenceManager.Instance.SaveSafe();

        return true;
    }


    bool HasTierInPath(UpgradeTier tier, int pathIndex)
    {
        // Tier 1 is always allowed across all paths (no blocking)
        if (tier == UpgradeTier.Tier1)
            return false;

        // For Tier 2+ we enforce path lock
        if (hasCommittedPath)
        {
            // If committed to a path, block any Tier 2/3 in other paths
            if (pathIndex != committedPath)
                return true;
        }

        // Regardless of commitment, still prevent buying a second upgrade
        // of the same tier in the same path
        foreach (var u in purchased)
            if (u.tier == tier && u.pathIndex == pathIndex)
                return true;

        return false;
    }

}
