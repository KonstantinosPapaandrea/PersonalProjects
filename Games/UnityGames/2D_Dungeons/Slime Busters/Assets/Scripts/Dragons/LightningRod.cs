using System.Collections;
using UnityEngine;
using SlimeBusters;

public class LightningRod : MonoBehaviour
{
    LayerMask enemyMask;
    float zapDps = 2f;
    float zapInterval = 0.5f;
    bool preferChains = true;

    bool auraOn = false;
    float auraRadius = 1.0f;
    float auraDps = 2f;

    Coroutine tick;

    public void Init(LayerMask ownerMask, float zapDps, float zapInterval, bool preferChains,
                     bool auraOn, float auraRadius, float auraDps)
    {
        this.enemyMask = ownerMask;
        this.zapDps = Mathf.Max(0f, zapDps);
        this.zapInterval = Mathf.Max(0.05f, zapInterval);
        this.preferChains = preferChains;

        this.auraOn = auraOn;
        this.auraRadius = Mathf.Max(0.1f, auraRadius);
        this.auraDps = Mathf.Max(0f, auraDps);

        if (tick == null) tick = StartCoroutine(Tick());
    }

    IEnumerator Tick()
    {
        var wait = new WaitForSeconds(zapInterval);
        while (true)
        {
            // zap nearest
            var hits = Physics2D.OverlapCircleAll(transform.position, 2.0f, enemyMask);
            Transform t = null;
            float best = float.MaxValue;
            foreach (var h in hits)
            {
                float dsq = (h.transform.position - transform.position).sqrMagnitude;
                if (dsq < best) { best = dsq; t = h.transform; }
            }
            if (t)
            {
                // small zap (no chain here, keep it lightweight)
                var e = t.GetComponent<Enemy>();
                if (e) e.TakeDamage(Mathf.Max(1, Mathf.RoundToInt(zapDps * zapInterval)),DamageType.Lightning);

                // tiny arc visual
                SpawnArc(transform.position, t.position);
            }

            // aura damage
            if (auraOn && auraDps > 0f)
            {
                var around = Physics2D.OverlapCircleAll(transform.position, auraRadius, enemyMask);
                foreach (var c in around)
                {
                    var e = c.GetComponent<Enemy>();
                    if (!e) continue;
                    int dmg = Mathf.Max(1, Mathf.RoundToInt(auraDps * zapInterval));
                    e.TakeDamage(dmg, DamageType.Lightning);
                }
            }
            yield return wait;
        }
    }

    void SpawnArc(Vector3 a, Vector3 b)
    {
        var go = new GameObject("RodArc");
        var lr = go.AddComponent<LineRenderer>();
        lr.useWorldSpace = true;
        lr.positionCount = 2;
        lr.startWidth = 0.06f;
        lr.endWidth = 0.06f;
        lr.sortingOrder = 40;
        lr.SetPosition(0, a);
        lr.SetPosition(1, b);
        Destroy(go, 0.08f);
    }
}
