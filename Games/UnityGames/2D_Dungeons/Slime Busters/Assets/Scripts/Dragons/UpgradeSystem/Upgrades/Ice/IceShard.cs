using UnityEngine;
using SlimeBusters;

public class IceShard : MonoBehaviour
{
    Vector3 dir = Vector3.right;
    float speed = 10f;
    int damage = 1;
    float slowPct, slowDur;

    public float maxLifetime = 2.5f;
    float t;

    public LayerMask enemyMask = ~0;

    public void Init(Vector3 direction, float speed, int damage, float slowPct, float slowDur)
    {
        this.dir = direction.normalized;
        this.speed = Mathf.Max(0.1f, speed);
        this.damage = Mathf.Max(0, damage);
        this.slowPct = Mathf.Clamp01(slowPct);
        this.slowDur = Mathf.Max(0f, slowDur);
    }

    void Update()
    {
        t += Time.deltaTime;
        if (t >= maxLifetime) { Destroy(gameObject); return; }

        Vector3 step = dir * speed * Time.deltaTime;
        transform.position += step;
    }

    void OnTriggerEnter2D(Collider2D other)
    {
        if (((1 << other.gameObject.layer) & enemyMask) == 0) return;
        var e = other.GetComponent<Enemy>();
        if (!e) return;

        if (damage > 0) e.TakeDamage(damage);
        if (slowPct > 0f && slowDur > 0f) e.ApplySlow(slowPct, slowDur);
        Destroy(gameObject);
    }
}
