using UnityEngine;

public static class MetaStatProvider
{
    // Returns final multiplier to apply to a given stat (1.0 means no change)
    public static float GetMultiplier(string dragonClass, string statKey)
    {
        float add = 0f, mul = 1f;
        foreach (var node in MetaUpgradeDatabase.ActiveNodesFor(dragonClass))
        {
            if (node.statKey != statKey) continue;
            switch (node.modType)
            {
                case ModType.Additive: add += node.value; break;
                case ModType.Multiplicative: mul *= (1f + node.value); break;
                case ModType.Toggle: /* handle toggles per-stat in your tower */ break;
            }
        }
        return (1f + add) * mul;
    }
}
