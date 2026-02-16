using UnityEngine;
using SlimeBusters;

[CreateAssetMenu(menuName = "TD/Upgrades/Effects/Crystal/Control Upgrade", fileName = "FX_Crystal_Control")]
public class CrystalControlUpgradeEffect : UpgradeEffectSO
{
    [Header("Slow")]
    public bool applySlow = false;
    public float slowPercent = 0f;
    public float slowDuration = 0f;

    [Header("Stun")]
    public bool applyStun = false;
    public float stunDuration = 0f;

    [Header("Prison Shot")]
    public bool enablePrisonShot = false;
    public float prisonCooldown = 0f;
    public float prisonDuration = 0f;

    public override void Apply(Dragon d)
    {
        var ca = d.attack as CrystalAttack;
        if (!ca)
        {
            Debug.LogWarning("CrystalControlUpgradeEffect applied to non-Crystal dragon.", d);
            return;
        }

        if (applySlow && slowPercent > 0f && slowDuration > 0f)
            ca.EnableSlow(slowPercent, slowDuration);

        if (applyStun && stunDuration > 0f)
            ca.EnableStun(stunDuration);

        if (enablePrisonShot && prisonCooldown > 0f && prisonDuration > 0f)
            ca.EnablePrisonShot(prisonCooldown, prisonDuration);
    }

    public override void Remove(Dragon d) { }
}
