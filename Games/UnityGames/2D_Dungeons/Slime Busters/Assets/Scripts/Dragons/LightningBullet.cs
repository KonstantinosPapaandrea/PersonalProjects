using System.Collections.Generic;
using UnityEngine;using SlimeBusters.Internal;

namespace SlimeBusters
{

public class LightningBullet : MonoBehaviour
{
    Transform target;
    float baseDamage;
    float speed;

    int extraJumps;
    float chainRadius;
    float falloffPerHop = 0.85f;
    bool preferUnhit = true;
    LayerMask enemyMask;

    // visuals
    Material arcMat;
    float arcWidth;
    float arcLifetime;
    int jaggedPoints;

    // safety
    public float maxLifetime = 3f;
    float life;

    ILightningHitSink sink;

    public void Init(Transform firstTarget, float damage, float speed,
                     int extraJumps, float radius, float falloffPerHop, bool preferUnhit,
                     LayerMask mask, ILightningHitSink sink,
                     Material arcMaterial, float arcWidth, float arcLifetime, int jaggedPoints)
    {
        this.target = firstTarget;
        this.baseDamage = damage;
        this.speed = speed;
        this.extraJumps = Mathf.Max(0, extraJumps);
        this.chainRadius = Mathf.Max(0.01f, radius);
        this.falloffPerHop = Mathf.Clamp01(Mathf.Max(0.01f, falloffPerHop));
        this.preferUnhit = preferUnhit;
        this.enemyMask = mask;

        this.sink = sink;

        this.arcMat = arcMaterial;
        this.arcWidth = arcWidth;
        this.arcLifetime = arcLifetime;
        this.jaggedPoints = Mathf.Max(4, jaggedPoints);
    }

    void Update()
    {
        life += Time.deltaTime;
        if (life >= maxLifetime) { Destroy(gameObject); return; }

        if (!target) { Destroy(gameObject); return; }

        Vector3 dir = target.position - transform.position;
        float step = speed * Time.deltaTime;

        if (dir.magnitude <= step)
        {
            // impact → perform chain starting from this target
            DoChain(transform.position, target);
            Destroy(gameObject);
            return;
        }

        transform.position += dir.normalized * step;
    }

    void DoChain(Vector3 origin, Transform firstHit)
    {
        var hitOrder = new List<Enemy>();
        var visited = new HashSet<Enemy>();

        Enemy current = firstHit ? SLB_ComponentCache.Get<Enemy>(firstHit) : null;
        if (!current) return;

        int jumpsLeft = extraJumps;
        int hopIndex = 0;
        Vector3 lastPos = origin;

        while (current != null)
        {
            // damage with falloff
            float mult = Mathf.Pow(falloffPerHop, hopIndex);
            int dmg = Mathf.Max(1, Mathf.RoundToInt(baseDamage * mult));

            current.TakeDamage(dmg, DamageType.Lightning);
            sink?.OnLightningHit(current, dmg, current.transform.position);

            SpawnArc(lastPos, current.transform.position);

            visited.Add(current);
            hitOrder.Add(current);
            lastPos = current.transform.position;

            if (jumpsLeft-- <= 0) break;
            current = FindNext(current.transform.position, visited);
            hopIndex++;
        }
    }

    Enemy FindNext(Vector3 from, HashSet<Enemy> visited)
    {
        Collider2D[] hits = Physics2D.OverlapCircleAll(from, chainRadius, enemyMask);
        Enemy best = null;
        float bestScore = float.MaxValue;

        foreach (var h in hits)
        {
            var e = SLB_ComponentCache.Get<Enemy>(h);
            if (!e) continue;
            if (preferUnhit && visited.Contains(e)) continue;

            float dsq = (h.transform.position - from).sqrMagnitude;
            if (dsq < bestScore)
            {
                bestScore = dsq;
                best = e;
            }
        }

        // if we didn't find an unhit, allow any
        if (best == null && !preferUnhit)
            return best;

        if (best == null && preferUnhit)
        {
            // try again allowing revisits
            foreach (var h in hits)
            {
                var e = SLB_ComponentCache.Get<Enemy>(h);
                if (!e) continue;
                float dsq = (h.transform.position - from).sqrMagnitude;
                if (dsq < bestScore)
                {
                    bestScore = dsq;
                    best = e;
                }
            }
        }
        return best;
    }

    void SpawnArc(Vector3 a, Vector3 b)
    {
        var go = new GameObject("LightningArc");
        var lr = go.AddComponent<LineRenderer>();
        lr.useWorldSpace = true;
        lr.positionCount = jaggedPoints;
        lr.startWidth = arcWidth;
        lr.endWidth = arcWidth;
        lr.textureMode = LineTextureMode.Stretch;
        lr.sortingOrder = 50;
        if (arcMat) lr.material = arcMat;

        // Build a jagged line between a and b
        for (int i = 0; i < jaggedPoints; i++)
        {
            float t = i / (float)(jaggedPoints - 1);
            Vector3 p = Vector3.Lerp(a, b, t);

            Vector3 dir = (b - a).normalized;
            Vector3 perp = new Vector3(-dir.y, dir.x, 0f);
            float jitter = (Random.value - 0.5f) * 0.15f * Vector3.Distance(a, b);
            if (i != 0 && i != jaggedPoints - 1) p += perp * jitter;

            lr.SetPosition(i, p);
        }

        Destroy(go, arcLifetime);
    }

    // --------- Radial discharge helper ----------
    public void InitRadialBurst(Vector3 startPos, int damage, int hops, float radius, float falloffPerHop,
                                LayerMask mask, ILightningHitSink sink,
                                Material arcMaterial, float arcWidth, float arcLifetime, int jaggedPoints)
    {
        transform.position = startPos;
        this.baseDamage = damage;
        this.extraJumps = Mathf.Max(0, hops);
        this.chainRadius = Mathf.Max(0.01f, radius);
        this.falloffPerHop = Mathf.Clamp01(Mathf.Max(0.01f, falloffPerHop));
        this.enemyMask = mask;
        this.sink = sink;
        this.arcMat = arcMaterial;
        this.arcWidth = arcWidth;
        this.arcLifetime = arcLifetime;
        this.jaggedPoints = Mathf.Max(4, jaggedPoints);

        // pick nearest, start chaining immediately
        Collider2D[] hits = Physics2D.OverlapCircleAll(startPos, chainRadius, enemyMask);
        float best = float.MaxValue;
        Transform t = null;
        foreach (var h in hits)
        {
            float dsq = (h.transform.position - startPos).sqrMagnitude;
            if (dsq < best) { best = dsq; t = h.transform; }
        }

        if (!t) { Destroy(gameObject); return; }
        DoChain(startPos, t);
        Destroy(gameObject);
    }
}

}
