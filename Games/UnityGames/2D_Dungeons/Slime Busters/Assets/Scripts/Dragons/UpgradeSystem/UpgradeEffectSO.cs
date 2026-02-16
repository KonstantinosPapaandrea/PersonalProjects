using UnityEngine;
using SlimeBusters;

public abstract class UpgradeEffectSO : ScriptableObject
{
    // Called when the upgrade is purchased for a specific dragon instance
    public abstract void Apply(Dragon d);

    // Optional if you want to support sell/refund or respec (safe to leave empty)
    public virtual void Remove(Dragon d) { }
}
