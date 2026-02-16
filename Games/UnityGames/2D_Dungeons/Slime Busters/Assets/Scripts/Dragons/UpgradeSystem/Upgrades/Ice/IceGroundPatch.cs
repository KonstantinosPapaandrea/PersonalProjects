using UnityEngine;
using SlimeBusters;

public class IceGroundPatch : MonoBehaviour
{
    float radius = 1f;
    float life = 3f;
    float t;
    float auraSlowPct = 0.4f;
    float auraSlowDur = 0.6f;

    public LayerMask enemyMask = ~0;

    public void Configure(float auraSlowPct, float auraSlowDur, float radius, float life)
    {
        this.auraSlowPct = Mathf.Clamp01(auraSlowPct);
        this.auraSlowDur = Mathf.Max(0f, auraSlowDur);
        this.radius = Mathf.Max(0.25f, radius);
        this.life = Mathf.Max(0.1f, life);
    }

    void Update()
    {
        t += Time.deltaTime;
        if (t >= life) { Destroy(gameObject); return; }

        var hits = Physics2D.OverlapCircleAll(transform.position, radius, enemyMask);
        foreach (var h in hits)
        {
            var e = h.GetComponent<Enemy>();
            if (!e) continue;
            if (auraSlowPct > 0f && auraSlowDur > 0f) e.ApplySlow(auraSlowPct, auraSlowDur);
        }
    }

    void OnDrawGizmosSelected()
    {
        Gizmos.color = new Color(0.6f, 0.9f, 1f, 0.25f);
        Gizmos.DrawWireSphere(transform.position, radius);
    }
}
