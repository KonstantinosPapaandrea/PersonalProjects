using System.Collections;
using System.Collections.Generic;
using UnityEngine;
using UnityEngine.UI;

public class JarBubblesUI : MonoBehaviour
{
    [Header("Setup")]
    [Tooltip("Rect area of the jar (usually the Button/Image covering the jar).")]
    public RectTransform jarRect;

    [Tooltip("UI Image prefab for a single bubble (small circle sprite).")]
    public Image bubblePrefab;

    [Header("Appearance")]
    [Tooltip("If true, overrides the prefab's color for all spawned bubbles from THIS jar.")]
    public bool overridePrefabColor = true;

    [Tooltip("Tint to apply when overridePrefabColor is true (alpha is respected).")]
    public Color bubbleColor = new Color(1f, 1f, 1f, 0.7f);

    [Header("Spawn")]
    [Min(1)] public int maxConcurrentBubbles = 16;

    [Tooltip("Seconds between spawns (randomized ±25%).")]
    public float spawnInterval = 0.15f;

    [Tooltip("Horizontal padding inside jar (in pixels).")]
    public float xPadding = 10f;

    [Tooltip("Vertical padding inside jar (in pixels). Keeps bubbles from touching top/bottom edges.")]
    public float yPadding = 10f;

    [Header("Motion")]
    [Tooltip("Min/Max vertical speed (px/sec).")]
    public Vector2 riseSpeedRange = new Vector2(35f, 90f);

    [Tooltip("Min/Max starting size (scale 1 = prefab size).")]
    public Vector2 scaleRange = new Vector2(0.4f, 1.2f);

    [Tooltip("Horizontal drift amplitude (px).")]
    public float driftAmplitude = 8f;

    [Tooltip("Horizontal drift frequency (cycles/sec).")]
    public float driftFrequency = 0.7f;

    [Header("Fade")]
    [Tooltip("Enable fade-in/out.")]
    public bool fade = true;

    [Tooltip("Fade-in duration (sec).")]
    public float fadeIn = 0.15f;

    [Tooltip("Fade-out duration (sec) near the top (sec).")]
    public float fadeOut = 0.25f;

    readonly List<Image> pool = new List<Image>();
    int aliveCount;
    Coroutine spawner;
    static readonly Vector3[] _corners = new Vector3[4]; // kept for potential extensions

    void Reset()
    {
        jarRect = GetComponent<RectTransform>();
    }

    void OnEnable()
    {
        if (!jarRect) jarRect = GetComponent<RectTransform>();
        if (spawner == null) spawner = StartCoroutine(SpawnLoop());
    }

    void OnDisable()
    {
        if (spawner != null) { StopCoroutine(spawner); spawner = null; }
        foreach (var b in pool)
            if (b) b.gameObject.SetActive(false);
        aliveCount = 0;
    }

    IEnumerator SpawnLoop()
    {
        while (true)
        {
            if (aliveCount < maxConcurrentBubbles)
                SpawnOne();

            float jitter = spawnInterval * Random.Range(0.75f, 1.25f);
            yield return new WaitForSeconds(jitter);
        }
    }

    void SpawnOne()
    {
        if (!bubblePrefab || !jarRect) return;

        var bubble = GetFromPool();
        bubble.transform.SetParent(jarRect, false);
        bubble.raycastTarget = false;
        bubble.gameObject.SetActive(true);

        // Apply color override per jar (including alpha)
        if (overridePrefabColor)
            bubble.color = bubbleColor;
        else
            bubble.color = bubblePrefab.color; // keep prefab's tint

        float halfW = jarRect.rect.width * 0.5f;
        float halfH = jarRect.rect.height * 0.5f;

        // Start slightly inside the bottom (yPadding) and a tiny offset below for nicer entrance
        float x = Random.Range(-halfW + xPadding, halfW - xPadding);
        float y = -halfH + yPadding - 6f;

        var rt = (RectTransform)bubble.transform;
        rt.anchoredPosition = new Vector2(x, y);

        float scale = Random.Range(scaleRange.x, scaleRange.y);
        rt.localScale = Vector3.one * scale;

        float speed = Random.Range(riseSpeedRange.x, riseSpeedRange.y);
        float phase = Random.Range(0f, 1f); // drift phase offset

        var cg = bubble.GetComponent<CanvasGroup>();
        if (!cg) cg = bubble.gameObject.AddComponent<CanvasGroup>();
        cg.alpha = fade ? 0f : 1f;

        aliveCount++;
        StartCoroutine(RiseRoutine(rt, cg, speed, phase, halfH));
    }

    IEnumerator RiseRoutine(RectTransform rt, CanvasGroup cg, float speed, float phase, float halfH)
    {
        float elapsed = 0f;
        float endY = halfH - yPadding + 6f; // stop before the top padding

        // Fade-in
        if (fade && fadeIn > 0f)
        {
            float t = 0f;
            while (t < fadeIn)
            {
                t += Time.deltaTime;
                cg.alpha = Mathf.Lerp(0f, 1f, t / fadeIn);
                yield return null;
            }
            cg.alpha = 1f;
        }

        // Rise with gentle horizontal drift
        while (rt && rt.anchoredPosition.y < endY)
        {
            float dy = speed * Time.deltaTime;
            float y = rt.anchoredPosition.y + dy;
            float drift = Mathf.Sin((elapsed + phase) * Mathf.PI * 2f * driftFrequency) * driftAmplitude;

            rt.anchoredPosition = new Vector2(rt.anchoredPosition.x + drift * Time.deltaTime, y);

            // Fade-out near the top zone
            if (fade && fadeOut > 0f)
            {
                float topZoneStart = endY - Mathf.Max(8f, (halfH * 0.18f)); // small safety band
                if (y >= topZoneStart)
                {
                    float k = Mathf.InverseLerp(topZoneStart, endY, y);
                    cg.alpha = Mathf.Clamp01(1f - k);
                }
            }

            elapsed += Time.deltaTime;
            yield return null;
        }

        ReturnToPool(rt ? rt.GetComponent<Image>() : null);
    }

    void ReturnToPool(Image img)
    {
        if (img)
        {
            img.gameObject.SetActive(false);
            if (!pool.Contains(img)) pool.Add(img);
        }
        aliveCount = Mathf.Max(0, aliveCount - 1);
    }

    Image GetFromPool()
    {
        for (int i = pool.Count - 1; i >= 0; --i)
        {
            if (pool[i] && !pool[i].gameObject.activeSelf)
                return pool[i];
        }
        var inst = Instantiate(bubblePrefab);
        pool.Add(inst);
        return inst;
    }
}
