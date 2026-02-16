using UnityEngine;
using System.Collections;
using SlimeBusters;

public class EggThrow : MonoBehaviour
{
    [Header("Arc")]
    public float travelTime = 0.5f;
    public float arcHeight = 0.6f;

    [Header("Visuals (optional)")]
    public Transform spriteRoot;
    public bool faceVelocity = true;

    // payload
    Egg eggPrefab;
    Egg.Params eggParams;
    Vector3 startPos, endPos;

    // host to register landed eggs (so cap is respected)
    public EggPlanterAttack host;

    /// <summary>Launch a throw that spawns and INITs a real Egg on landing.</summary>
    public void LaunchWithParams(
        Vector3 start, Vector3 end,
        Egg eggPrefab, Egg.Params p,
        EggPlanterAttack host,
        float travelTimeOverride = -1f,
        float arcHeightOverride = -1f)
    {
        this.startPos = start;
        this.endPos = end;
        this.eggPrefab = eggPrefab;
        this.eggParams = p;
        this.host = host;

        if (travelTimeOverride > 0f) travelTime = travelTimeOverride;
        if (arcHeightOverride > 0f) arcHeight = arcHeightOverride;

        transform.position = start;
        StopAllCoroutines();
        StartCoroutine(FlyCo());
    }

    IEnumerator FlyCo()
    {
        Vector3 mid = (startPos + endPos) * 0.5f;
        Vector3 control = mid + Vector3.up * arcHeight;

        float t = 0f;
        while (t < 1f)
        {
            t += Time.deltaTime / Mathf.Max(0.01f, travelTime);
            float u = Mathf.Clamp01(t);

            Vector3 pA = Vector3.Lerp(startPos, control, u);
            Vector3 pB = Vector3.Lerp(control, endPos, u);
            Vector3 p = Vector3.Lerp(pA, pB, u);

            if (faceVelocity && spriteRoot)
            {
                Vector3 v = (pB - pA);
                if (v.sqrMagnitude > 1e-6f)
                {
                    float ang = Mathf.Atan2(v.y, v.x) * Mathf.Rad2Deg;
                    spriteRoot.rotation = Quaternion.Euler(0, 0, ang);
                }
            }

            transform.position = p;
            yield return null;
        }

        // Land → spawn ARMED egg
        var egg = Instantiate(eggPrefab, endPos, Quaternion.identity);
        egg.Init(eggParams);

        // Let host track cap & despawn
        if (host) host.RegisterEgg(egg);

        Destroy(gameObject);
    }
}
