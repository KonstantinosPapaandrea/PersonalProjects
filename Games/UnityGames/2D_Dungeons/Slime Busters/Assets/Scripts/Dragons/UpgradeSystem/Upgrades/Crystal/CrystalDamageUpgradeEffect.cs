using UnityEngine;
using SlimeBusters;

[CreateAssetMenu(menuName = "TD/Upgrades/Effects/Crystal/Damage Upgrade", fileName = "FX_Crystal_Damage")]
public class CrystalDamageUpgradeEffect : UpgradeEffectSO
{
    [Header("Damage Scaling")]
    public int damageAdd = 0;
    public float damageMult = 1f;

    [Header("Pierce")]
    public int pierceMin = 0;

    [Header("Armor Shred (optional)")]
    public bool applyArmorShred = false;
    public float shredPercent = 0f;
    public float shredDuration = 0f;

    public override void Apply(Dragon d)
    {
        var ca = d.attack as CrystalAttack;
        if (!ca)
        {
            Debug.LogWarning("CrystalDamageUpgradeEffect applied to non-Crystal dragon.", d);
            return;
        }

        if (damageAdd != 0 || !Mathf.Approximately(damageMult, 1f))
        {
            d.damage = Mathf.RoundToInt((d.damage + damageAdd) * Mathf.Max(0.01f, damageMult));
        }

        if (pierceMin > 0) ca.SetPierceAtLeast(pierceMin);

        if (applyArmorShred && shredPercent > 0f && shredDuration > 0f)
            ca.EnableArmorShred(shredPercent, shredDuration);
    }

    public override void Remove(Dragon d) { }
}
