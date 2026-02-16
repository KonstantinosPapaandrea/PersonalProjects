using System;
using System.Collections.Generic;
using UnityEngine;

public static class MetaUpgradeService
{
    [Serializable] public class UpgradeEntry { public string key; public int level; }

    // Adapters so we don't depend on any specific wallet/save classes
    public static Func<int> GetEssence;
    public static Action<int> SpendEssence; // pass positive to spend, negative to refund
    public static Func<List<UpgradeEntry>> GetUpgradeLevels; // returns the underlying save list
    public static Action Save; // call your SaveSafe()

    public static int GetLevel(string nodeId)
    {
        var list = GetUpgradeLevels?.Invoke();
        if (list == null) return 0;
        var e = list.Find(u => u.key == nodeId);
        return e != null ? e.level : 0;
    }

    public static bool IsOwned(MetaUpgradeNode node) => GetLevel(node.id) > 0;

    public static bool PrereqSatisfied(MetaUpgradeNode node)
    {
        if (!node.prerequisite) return true;
        return IsOwned(node.prerequisite);
    }

    // Optional policy: allow Tier1 across all paths; Tier2+ must stay in one path (per-dragonClass)
    public static bool PathLockSatisfied(MetaUpgradeNode node)
    {
        if (node.tier <= 1) return true; // T1 free
        // Find any owned Tier>=2 node for same dragonClass: must match path
        foreach (var n in MetaUpgradeDatabase.Instance.nodes)
        {
            if (n.dragonClass != node.dragonClass) continue;
            if (n.tier <= 1) continue;
            if (IsOwned(n))
                return n.path == node.path; // lock to first chosen path
        }
        return true;
    }

    public static bool CanBuy(MetaUpgradeNode node, out string reason)
    {
        if (!PrereqSatisfied(node)) { reason = "Prerequisite not owned."; return false; }
        if (!PathLockSatisfied(node)) { reason = "Locked to another path."; return false; }
        if (IsOwned(node)) { reason = "Already owned."; return false; }
        if (GetEssence == null || SpendEssence == null) { reason = "Wallet not bound."; return false; }
        if (GetEssence() < node.baseCost) { reason = "Not enough essence."; return false; }
        reason = null; return true;
    }

    public static bool Buy(MetaUpgradeNode node, out string error)
    {
        if (!CanBuy(node, out error)) return false;
        SpendEssence(node.baseCost);
        var list = GetUpgradeLevels?.Invoke();
        if (list == null) { error = "Save not bound."; SpendEssence(-node.baseCost); return false; }

        var e = list.Find(u => u.key == node.id);
        if (e == null) { e = new UpgradeEntry { key = node.id, level = 1 }; list.Add(e); }
        else e.level = Mathf.Max(e.level, 1); // this node represents a tier asset → level>0 means owned

        Save?.Invoke();
        return true;
    }
}
