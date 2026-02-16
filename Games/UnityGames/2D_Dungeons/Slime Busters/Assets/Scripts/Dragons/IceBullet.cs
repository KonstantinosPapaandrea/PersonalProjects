using UnityEngine;
using SlimeBusters;

public class IceBullet : MonoBehaviour
{
    Transform target;
    int damage;
    float speed;
    float slowPct, slowDur;

    public void Init(Transform t, int dmg, float spd, float pct, float dur)
    {
        target = t;
        damage = dmg;
        speed = spd;
        slowPct = Mathf.Clamp01(pct);
        slowDur = Mathf.Max(0f, dur);
    }

    void Update()
    {
        if (!target) { Destroy(gameObject); return; }

        Vector3 dir = target.position - transform.position;
        float step = speed * Time.deltaTime;

        if (dir.magnitude <= step) { Hit(); return; }
        transform.position += dir.normalized * step;
    }

    void Hit()
    {
        var e = target.GetComponent<Enemy>();  // use your enemy script type
        if (e != null)
        {
            e.TakeDamage(damage);
            e.ApplySlow(slowPct, slowDur);     // requires ApplySlow on Enemy (we added earlier)
        }
        Destroy(gameObject);
    }
}
