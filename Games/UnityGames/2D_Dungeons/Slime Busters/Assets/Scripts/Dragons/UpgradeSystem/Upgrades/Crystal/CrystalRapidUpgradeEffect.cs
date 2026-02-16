using UnityEngine;
using SlimeBusters;

[CreateAssetMenu(menuName = "TD/Upgrades/Effects/Crystal/Rapid Upgrade", fileName = "FX_Crystal_Rapid")]
public class CrystalRapidUpgradeEffect : UpgradeEffectSO
{
    [Header("Fire Rate / Damage")]
    public float fireRateMult = 1f;
    public float damageMult = 1f;

    [Header("Burst / MultiShot")]
    public int extraShotsEveryN = 0; // e.g. 1 extra every 3rd shot
    public int multiShotCount = 0;   // e.g. 3 shots rapid-fire

    public override void Apply(Dragon d)
    {
        var ca = d.attack as CrystalAttack;
        if (!ca)
        {
            Debug.LogWarning("CrystalRapidUpgradeEffect applied to non-Crystal dragon.", d);
            return;
        }

        if (!Mathf.Approximately(fireRateMult, 1f)) d.fireRate *= fireRateMult;
        if (!Mathf.Approximately(damageMult, 1f)) d.damage = Mathf.RoundToInt(d.damage * damageMult);

        if (extraShotsEveryN > 0) ca.EnableExtraShots(extraShotsEveryN);
        if (multiShotCount > 0) ca.EnableMultiShot(multiShotCount);
    }

    public override void Remove(Dragon d) { }
}
