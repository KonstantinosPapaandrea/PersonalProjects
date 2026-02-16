using UnityEngine;
using SlimeBusters;

public class BurnDoT : MonoBehaviour
{
    float dps;
    float timeLeft;

    public void Apply(float newDps, float duration)
    {
        dps = Mathf.Max(dps, newDps);       // keep strongest
        timeLeft = Mathf.Max(timeLeft, duration);
    }

    void Update()
    {
        if (timeLeft <= 0f) { Destroy(this); return; }
        float dt = Time.deltaTime;
        timeLeft -= dt;

        var e = GetComponent<Enemy>();
        if (e && dps > 0f)
            e.TakeDamage(Mathf.CeilToInt(dps * dt));
    }
}
