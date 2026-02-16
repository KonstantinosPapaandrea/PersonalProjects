using SlimeBusters;
﻿using UnityEngine;

public class CrystalBullet : MonoBehaviour
{
    Transform target;
    float damage;
    float speed;

    // Pierce / retarget
    int pierceRemaining = 0;
    public float retargetRadius = 2.5f;
    public LayerMask enemyMask = ~0;
    public bool allowRetarget = true;

    // Safety
    public float maxLifetime = 3f;
    float life;
    Vector3 lastDir = Vector3.right;

    // Debuffs
    float slowPercent, slowDuration;
    float stunDuration;
    float armorShredPct, armorShredDur;
    float prisonStunDur; // overrides stun if >0

    public void Init(
        Transform target,
        float damage,
        float speed,
        int pierce,
        LayerMask mask,
        float slowPercent = 0f, float slowDuration = 0f,
        float stunDuration = 0f,
        float armorShredPct = 0f, float armorShredDur = 0f,
        float prisonStunDur = 0f
    )
    {
        this.target = target;
        this.damage = damage;
        this.speed = speed;
        this.pierceRemaining = Mathf.Max(0, pierce);
        this.enemyMask = mask;

        this.slowPercent = slowPercent;
        this.slowDuration = slowDuration;
        this.stunDuration = stunDuration;
        this.armorShredPct = armorShredPct;
        this.armorShredDur = armorShredDur;
        this.prisonStunDur = prisonStunDur;

        if (target)
            lastDir = (target.position - transform.position).normalized;
    }

    void Update()
    {
        life += Time.deltaTime;
        if (life >= maxLifetime) { Destroy(gameObject); return; }

        if (target != null)
        {
            lastDir = (target.position - transform.position).normalized;

            Vector3 dir = target.position - transform.position;
            float step = speed * Time.deltaTime;
            if (dir.magnitude <= step) { Impact(target); return; }

            transform.position += dir.normalized * step;
            return;
        }

        // Try retargeting
        if (allowRetarget && TryFindNewTarget(out Transform newT))
        {
            target = newT;
            return;
        }

        // Fly straight
        transform.position += lastDir * (speed * Time.deltaTime);
    }

    void Impact(Transform t)
    {
        var e = t ? t.GetComponent<Enemy>() : null;
        if (e)
        {
            e.TakeDamage(damage, DamageType.Crystal);

            // Apply debuffs if Enemy has support
            if (slowPercent > 0f && slowDuration > 0f) e.ApplySlow(slowPercent, slowDuration);
            if (armorShredPct > 0f && armorShredDur > 0f) e.ApplyArmorShred(armorShredPct, armorShredDur);

            // Prison overrides normal stun
            if (prisonStunDur > 0f) e.ApplyStun(prisonStunDur);
            else if (stunDuration > 0f) e.ApplyStun(stunDuration);
        }

        if (pierceRemaining > 0)
        {
            pierceRemaining--;
            target = null; // retarget next frame
            return;        // don't destroy yet
        }

        Destroy(gameObject);
    }

    bool TryFindNewTarget(out Transform newTarget)
    {
        newTarget = null;
        Collider2D[] hits = Physics2D.OverlapCircleAll(transform.position, retargetRadius, enemyMask);
        float best = float.MaxValue;

        foreach (var h in hits)
        {
            var e = h.GetComponent<Enemy>();
            if (!e) continue;

            float d = (h.transform.position - transform.position).sqrMagnitude;
            if (d < best)
            {
                best = d;
                newTarget = e.transform;
            }
        }
        return newTarget != null;
    }

    void OnDrawGizmosSelected()
    {
        if (pierceRemaining > 0)
        {
            Gizmos.color = new Color(0.5f, 0.8f, 1f, 0.25f);
            Gizmos.DrawWireSphere(transform.position, retargetRadius);
        }
    }
}
