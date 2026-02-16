using UnityEngine;
using SlimeBusters;

[CreateAssetMenu(menuName = "TD/Upgrades/Effects/Ice/Shards Upgrade", fileName = "FX_Ice_Shards")]
public class IceShardsUpgradeEffect : UpgradeEffectSO
{
    [Header("Shard Payload (very light DPS)")]
    public GameObject shardPrefab;      // assign a prefab with IceShard
    public int shardCount = 3;          // small fan
    public float shardSpeed = 12f;
    public float shardSpreadDeg = 20f;
    public int shardDamage = 1;         // keep tiny

    [Header("Breath Damage (optional tiny)")]
    public bool setBreathDamage;
    public int breathDamage = 1;        // still tiny

    [Header("Cadence (optional)")]
    public bool tweakFireCooldown;
    public float fireCooldown = 0.40f;

    public override void Apply(Dragon d)
    {
        var ia = d.attack as IceAttack;
        if (!ia)
        {
            Debug.LogWarning("IceShardsUpgradeEffect applied to non-Ice dragon.", d);
            return;
        }

        ia.EnableShards(shardPrefab, shardCount, shardSpeed, shardSpreadDeg, shardDamage);
        if (setBreathDamage) ia.SetBaseDamage(Mathf.Max(0, breathDamage));
        if (tweakFireCooldown) ia.SetFireCooldown(fireCooldown);
    }

    public override void Remove(Dragon d) { }
}
