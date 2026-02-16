using SlimeBusters.Internal;
namespace SlimeBusters
{
﻿using UnityEngine;

public class FireBullet : MonoBehaviour
{
    // ---- runtime state ----
    Transform target;
    float damage;
    float speed;

    int pierceRemaining;        // hits left after the first
    float splashRadius;         // 0 = no splash
    float burnDps;              // 0 = no burn
    float burnDuration;         // 0 = no burn
    LayerMask enemyMask;

    // ---- tuning ----
    public float maxLifetime = 3f;
    public float retargetRadius = 2.5f;
    public bool allowRetarget = true;

    // internal
    float life;
    Vector3 lastDir = Vector3.right;

    /// <summary>
    /// Initialize bullet at spawn.
    /// </summary>
    public void Init(Transform target, float damage, float speed,
                     float splashRadius, float burnDps, float burnDuration,
                     int pierce, LayerMask mask)
    {
        this.target = target;
        this.damage = damage;
        this.speed = speed;

        this.splashRadius = Mathf.Max(0f, splashRadius);
        this.burnDps = Mathf.Max(0f, burnDps);
        this.burnDuration = Mathf.Max(0f, burnDuration);
        this.pierceRemaining = Mathf.Max(0, pierce);
        this.enemyMask = mask;

        if (target)
            lastDir = (target.position - transform.position).normalized;
    }

    void Update()
    {
        life += Time.deltaTime;
        if (life >= maxLifetime) { Destroy(gameObject); return; }

        if (target)
        {
            Vector3 to = target.position - transform.position;
            float step = speed * Time.deltaTime;

            if (to.magnitude <= step)
            {
                ImpactAt(target.position, target);
                return;
            }

            lastDir = to.normalized;
            transform.position += lastDir * step;
            return;
        }

        // no target: try to retarget (for pierce continuation)
        if (allowRetarget && TryFindNewTarget(out var t))
        {
            target = t;
            return;
        }

        // drift forward if nobody to track
        transform.position += lastDir * (speed * Time.deltaTime);
    }

    void ImpactAt(Vector3 pos, Transform primary)
    {
        // primary hit
        if (primary)
        {
            var e = SLB_ComponentCache.Get<Enemy>(primary);
            if (e)
            {
                e.TakeDamage(damage,DamageType.Fire);
                TryApplyBurn(e, burnDps, burnDuration);
            }
        }

        // splash
        if (splashRadius > 0f)
        {
            var hits = Physics2D.OverlapCircleAll(pos, splashRadius, enemyMask);
            foreach (var h in hits)
            {
                if (h.transform == primary) continue;

                var e2 = SLB_ComponentCache.Get<Enemy>(h);
                if (!e2) continue;

                // splash is typically reduced damage; tweak as needed
                int splashDmg = Mathf.Max(1, Mathf.RoundToInt(damage * 0.5f));
                e2.TakeDamage(splashDmg, DamageType.Fire);
                // optional half-burn on splash; comment out if not desired
                TryApplyBurn(e2, burnDps * 0.5f, burnDuration);
            }
        }

        // piercing: keep flying and re-acquire a target
        if (pierceRemaining > 0)
        {
            pierceRemaining--;
            target = null; // Update() will attempt to retarget
            return;        // don't destroy
        }

        Destroy(gameObject);
    }

    bool TryFindNewTarget(out Transform best)
    {
        best = null;
        var hits = Physics2D.OverlapCircleAll(transform.position, retargetRadius, enemyMask);
        float bestDsq = float.MaxValue;

        foreach (var h in hits)
        {
            var e = SLB_ComponentCache.Get<Enemy>(h);
            if (!e) continue;

            float dsq = (h.transform.position - transform.position).sqrMagnitude;
            if (dsq < bestDsq)
            {
                bestDsq = dsq;
                best = e.transform;
            }
        }
        return best != null;
    }

    // Safe burn hook (works even if Enemy has no burn system)
    void TryApplyBurn(Enemy e, float dps, float duration)
    {
        if (e == null) return;
        if (dps <= 0f || duration <= 0f) return;

        // If you add a burn API on Enemy later, call it here:
        // e.ApplyBurn(dps, duration);

        // Temporary lightweight fallback (optional):
        // StartCoroutine(SimpleBurn(e, dps, duration));
    }

    // Example fallback burn (commented out by default)
    /*
    System.Collections.IEnumerator SimpleBurn(Enemy e, float dps, float duration)
    {
        float tick = 0.25f;
        float t = duration;
        while (t > 0f && e)
        {
            e.TakeDamage(Mathf.CeilToInt(dps * tick));
            yield return new WaitForSeconds(tick);
            t -= tick;
        }
    }
    */

    void OnDrawGizmosSelected()
    {
        if (splashRadius > 0f)
        {
            Gizmos.color = new Color(1f, 0.35f, 0f, 0.25f);
            Gizmos.DrawWireSphere(transform.position, splashRadius);
        }
    }
}

}
