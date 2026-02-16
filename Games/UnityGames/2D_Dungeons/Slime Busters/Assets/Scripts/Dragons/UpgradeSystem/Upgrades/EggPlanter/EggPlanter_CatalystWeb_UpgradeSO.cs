using UnityEngine;
using SlimeBusters;

[CreateAssetMenu(menuName = "TD/Upgrades/Effects/EggPlanter/Catalyst", fileName = "FX_Egg_Catalyst")]
public class EggPlanterCatalystEffect : UpgradeEffectSO
{
    [Header("Chain Link")]
    public float linkRadius = 0f;              // 1.2 to enable; 0 = off
    public float damageMult = 1f;              // e.g., 0.9 tradeoff for chains

    [Header("Shrapnel")]
    public int shrapnelCount = 0;              // 6 to enable
    public float shrapnelDamageMult = 0.25f;   // per shard vs egg damage
    public float shrapnelRange = 1.8f;

    [Header("Remote + Vulnerability (amplification only)")]
    public bool enableRemote = false;
    public float remoteCooldown = 8f;
    [Range(0f, 1f)] public float vulnPct = 0f; // 0.2 = +20% damage taken
    public float vulnDur = 0f;                 // 2.0s, etc.

    [Header("General Tweaks (optional)")]
    public float blastRadiusMult = 1f;

    public override void Apply(Dragon d)
    {
        var atk = FindEggPlanter(d);
        if (!atk) return;

        if (linkRadius > 0f) atk.EnableTrapLink(linkRadius);
        if (!Mathf.Approximately(damageMult, 1f)) atk.MulEggDamage(damageMult);

        if (shrapnelCount > 0) atk.EnableShrapnel(shrapnelCount, shrapnelDamageMult, shrapnelRange);

        if (enableRemote) atk.EnableRemoteDetonate(remoteCooldown);
        if (vulnPct > 0f && vulnDur > 0f) atk.EnableVulnerability(vulnPct, vulnDur);

        if (!Mathf.Approximately(blastRadiusMult, 1f)) atk.MulBlastRadius(blastRadiusMult);
    }

    EggPlanterAttack FindEggPlanter(Dragon d)
    {
        if (!d) { Debug.LogWarning("EggPlanterCatalystEffect.Apply: null Dragon."); return null; }
        var atk = d.attack as EggPlanterAttack
               ?? d.GetComponent<EggPlanterAttack>()
               ?? d.GetComponentInChildren<EggPlanterAttack>(true);
        if (!atk) Debug.LogWarning("EggPlanterCatalystEffect: EggPlanterAttack not found on Dragon.", d);
        return atk;
    }


    public override void Remove(Dragon d) { }
}
