using System;
using System.Collections;
using System.Collections.Generic;
using UnityEngine;using SlimeBusters.Internal;

namespace SlimeBusters
{

public class Egg : MonoBehaviour
{
    [Serializable]
    public struct Params
    {
        public float damage;
        public float blastRadius;
        public float triggerRadius;
        public float fuse;
        public float lifetime;

        public float bossBonus;
        public bool ignoreShields;

        public float linkRadius;            // 0 = off
        public int shrapnelCount;           // 0 = off
        public float shrapnelDamageMult;
        public float shrapnelRange;

        public float vulnPct;               // 0 = off
        public float vulnDur;

        public LayerMask enemyMask;
    }

    public Action<Egg> OnDespawn;

    private Params P;
    private bool triggered = false;
    private float lifeTimer = 0f;

    // Small buffers to avoid allocs
    private static readonly Collider2D[] hitsBuf = new Collider2D[64];
    private static readonly Collider2D[] eggsBuf = new Collider2D[32];

    public void Init(Params prms)
    {
        P = prms;
        triggered = false;
        lifeTimer = Mathf.Max(0.05f, P.lifetime);
    }

    void Update()
    {
        if (triggered) return;

        lifeTimer -= Time.deltaTime;
        if (lifeTimer <= 0f)
        {
            Despawn(); // quietly disappear if never triggered
            return;
        }

        // Arm when an enemy gets close
        int n = Physics2D.OverlapCircleNonAlloc(transform.position, P.triggerRadius, hitsBuf, P.enemyMask);
        if (n > 0)
        {
            TriggerDetonation();
        }
    }

    public void TriggerDetonation()
    {
        if (triggered) return;
        triggered = true;

        if (P.fuse > 0f) StartCoroutine(FuseDelayThenExplode(P.fuse));
        else Explode();
    }

    private IEnumerator FuseDelayThenExplode(float wait)
    {
        yield return new WaitForSeconds(wait);
        Explode();
    }

    private void Explode()
    {
        int n = Physics2D.OverlapCircleNonAlloc(transform.position, P.blastRadius, hitsBuf, P.enemyMask);
        for (int i = 0; i < n; i++)
        {
            var c = hitsBuf[i];
            float dmg = AdjustForBossIfAny(c, P.damage, P.bossBonus);
            TryDealDamage(c, dmg, P.ignoreShields);

            if (P.vulnPct > 0f && P.vulnDur > 0f)
            {
                var enemy = SLB_ComponentCache.Get<Enemy>(c);
                if (enemy) enemy.ApplyArmorShred(P.vulnPct, P.vulnDur); // use your existing amplifier
                else c.SendMessage("ApplyVulnerability", new VulnerabilityData(P.vulnPct, P.vulnDur), SendMessageOptions.DontRequireReceiver);
            }
        }
        // Chain other eggs (next frame to avoid recursion this frame)
        if (P.linkRadius > 0.01f)
        {
            int m = Physics2D.OverlapCircleNonAlloc(transform.position, P.linkRadius, eggsBuf, ~0); // all layers
            for (int i = 0; i < m; i++)
            {
                var other = eggsBuf[i] ? eggsBuf[i].GetComponent<Egg>() : null;
                if (other != null && other != this)
                {
                    other.StartCoroutine(other.TriggerNextFrame());
                }
            }
        }

        // Shrapnel pings
        if (P.shrapnelCount > 0)
        {
            FireShrapnel(P.shrapnelCount, P.damage * P.shrapnelDamageMult, P.shrapnelRange);
        }

        Despawn();
    }

    private IEnumerator TriggerNextFrame()
    {
        yield return null;
        TriggerDetonation();
    }

    private void FireShrapnel(int count, float shardDamage, float range)
    {
        int n = Physics2D.OverlapCircleNonAlloc(transform.position, range, hitsBuf, P.enemyMask);
        if (n <= 0) return;

        var list = new List<(Collider2D c, float d2)>(n);
        for (int i = 0; i < n; i++)
        {
            var col = hitsBuf[i];
            float d2 = (col.transform.position - transform.position).sqrMagnitude;
            list.Add((col, d2));
        }
        list.Sort((a, b) => a.d2.CompareTo(b.d2));

        int shots = Mathf.Min(count, list.Count);
        for (int i = 0; i < shots; i++)
        {
            TryDealDamage(list[i].c, shardDamage, false);
        }
    }

    private static float AdjustForBossIfAny(Collider2D c, float baseDamage, float bossBonus)
    {
        if (bossBonus <= 0f) return baseDamage;
        if (c.TryGetComponent(out IEnemyDescriptor desc))
            return desc.IsBoss ? baseDamage * bossBonus : baseDamage;
        if (c.CompareTag("Boss")) return baseDamage * bossBonus;
        return baseDamage;
    }

    private static void TryDealDamage(Collider2D c, float amount, bool ignoreShields)
    {
        // 1) Direct Enemy component (your game’s main target)
        var enemy = SLB_ComponentCache.Get<Enemy>(c);
        if (enemy)
        {
            enemy.TakeDamage(Mathf.RoundToInt(amount), DamageType.Egg);
            return;
        }

        // 2) Generic interface (if you add it elsewhere)
        if (c.TryGetComponent(out IDamageable dmg))
        {
            dmg.TakeDamage(amount, ignoreShields);
            return;
        }

        // 3) Last-chance SendMessage fallbacks (kept, but most games won’t need these)
        int ai = Mathf.RoundToInt(amount);
        c.SendMessage("TakeDamage", amount, SendMessageOptions.DontRequireReceiver);
        c.SendMessage("TakeDamage", ai, SendMessageOptions.DontRequireReceiver);
        c.SendMessage("Damage", amount, SendMessageOptions.DontRequireReceiver);
        c.SendMessage("Damage", ai, SendMessageOptions.DontRequireReceiver);
        c.SendMessage("ApplyDamage", amount, SendMessageOptions.DontRequireReceiver);
        c.SendMessage("ApplyDamage", ai, SendMessageOptions.DontRequireReceiver);
    }

    private void Despawn()
    {
        OnDespawn?.Invoke(this);
        Destroy(gameObject);
    }

    void OnDrawGizmosSelected()
    {
        // just for tuning while selected
        Gizmos.color = new Color(1f, 0.6f, 0f, 0.25f);
        Gizmos.DrawWireSphere(transform.position, P.blastRadius > 0f ? P.blastRadius : 0.75f);
        Gizmos.color = new Color(0f, 0.8f, 1f, 0.25f);
        Gizmos.DrawWireSphere(transform.position, P.triggerRadius > 0f ? P.triggerRadius : 0.35f);
    }
}

/// Optional helper interfaces/structs your enemies can implement/use.
public interface IEnemyDescriptor { bool IsBoss { get; } }
public interface IDamageable { void TakeDamage(float amount, bool ignoreShields = false); }

public struct VulnerabilityData
{
    public readonly float pct;
    public readonly float dur;
    public VulnerabilityData(float pct, float dur) { this.pct = pct; this.dur = dur; }
}

}
