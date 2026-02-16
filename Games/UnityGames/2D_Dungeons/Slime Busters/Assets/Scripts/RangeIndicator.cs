using UnityEngine;

public class RangeIndicator : MonoBehaviour
{
    [Header("Renderer")]
    public Material rangeMat;     // optional: if null or incompatible, we fallback
    public string sortingLayer = "Default";
    public int sortingOrder = 500;
    public float zOffset = -0.05f; // bring slightly toward camera in 2D

    [Header("Geometry")]
    [Min(0.01f)] public float radius = 3f;
    [Min(12)] public int segments = 64;
    [Min(0.001f)] public float lineWidth = 0.12f;
    public Color lineColor = new Color(1f, 0.92f, 0.16f, 1f); // nice yellow

    LineRenderer lr;

    // ---------- Creation ----------

    // Preferred: pass a material you know works in your pipeline (URP/Built-in)
    public static RangeIndicator Create(Transform parent, float radius, Material mat, Color color,
                                        float lineWidth = 0.12f, int segments = 64,
                                        int sortingOrder = 500, string sortingLayer = "Default",
                                        float zOffset = -0.05f)
    {
        var go = new GameObject("RangeIndicator");
        go.transform.SetParent(parent, false);
        go.transform.localPosition = new Vector3(0, 0, zOffset);

        var ri = go.AddComponent<RangeIndicator>();
        ri.rangeMat = mat;                     // ← set BEFORE Init/Build
        ri.radius = radius;
        ri.lineColor = color;
        ri.lineWidth = lineWidth;
        ri.segments = segments;
        ri.sortingOrder = sortingOrder;
        ri.sortingLayer = sortingLayer;

        ri.BuildRenderer();
        ri.RebuildCircle();
        go.SetActive(false);
        return ri;
    }


    // Convenience: no material passed -> uses a safe fallback (Sprites/Default)
    public static RangeIndicator Create(
        Transform parent,
        float radius,
        Color color,
        float lineWidth = 0.12f,
        int segments = 64,
        int sortingOrder = 500,
        string sortingLayer = "Default",
        float zOffset = -0.05f)
    {
        return Create(parent, radius, null, color, lineWidth, segments, sortingOrder, sortingLayer, zOffset);
    }

    // ---------- Public API ----------

    public void Show(bool on) => gameObject.SetActive(on);

    public void SetRadius(float r)
    {
        if (r <= 0f || Mathf.Approximately(r, radius)) { radius = Mathf.Max(0.01f, r); return; }
        radius = r;
        RebuildCircle();
    }

    public void SetColor(Color c)
    {
        lineColor = c.a <= 0f ? new Color(c.r, c.g, c.b, 1f) : c;
        if (lr) { lr.startColor = lr.endColor = lineColor; }
    }

    public void SetWidth(float w)
    {
        lineWidth = Mathf.Max(0.001f, w);
        if (lr) { lr.startWidth = lr.endWidth = lineWidth; }
    }

    // ---------- Internals ----------

    void BuildRenderer()
    {
        lr = gameObject.GetComponent<LineRenderer>();
        if (!lr) lr = gameObject.AddComponent<LineRenderer>();

        lr.useWorldSpace = false;
        lr.loop = true;
        lr.textureMode = LineTextureMode.Stretch;

        // Material: use provided if valid; otherwise build a safe fallback
        Material matToUse = null;

        if (rangeMat != null)
        {
            // make an instance so we don't mutate shared material
            matToUse = new Material(rangeMat);
            // If shader missing/incompatible it can render pink — the fallback below will replace it.
        }

        if (matToUse == null || matToUse.shader == null || matToUse.shader.name.Contains("Hidden"))
        {
            // Fallbacks that work in both Built-in & URP for simple lines:
            // Try Sprites/Default first (URP provides a compatible version)
            var spriteShader = Shader.Find("Sprites/Default");
            if (spriteShader != null) matToUse = new Material(spriteShader);
            else
            {
                // Last resort: Unlit/Color (Built-in); URP may still provide a compatible unlit
                var unlit = Shader.Find("Unlit/Color");
                matToUse = new Material(unlit);
            }
        }

        lr.material = matToUse;

        // Visual params
        lr.startColor = lr.endColor = lineColor;
        lr.startWidth = lr.endWidth = lineWidth;

        // Sorting on top of map/tiles
        lr.sortingLayerName = sortingLayer;
        lr.sortingOrder = sortingOrder;

        // Geometry
        lr.positionCount = Mathf.Max(12, segments);
    }

    void RebuildCircle()
    {
        if (!lr) return;

        int count = Mathf.Max(12, segments);
        if (lr.positionCount != count) lr.positionCount = count;

        // Draw a circle around local (0,0)
        for (int i = 0; i < count; i++)
        {
            float t = (i / (float)count) * Mathf.PI * 2f;
            lr.SetPosition(i, new Vector3(Mathf.Cos(t) * radius, Mathf.Sin(t) * radius, 0f));
        }
    }

    // If someone tweaks values in Inspector at runtime
    void OnValidate()
    {
        segments = Mathf.Max(12, segments);
        radius = Mathf.Max(0.01f, radius);
        lineWidth = Mathf.Max(0.001f, lineWidth);

        if (lr)
        {
            lr.startWidth = lr.endWidth = lineWidth;
            lr.startColor = lr.endColor = lineColor;
            lr.sortingLayerName = sortingLayer;
            lr.sortingOrder = sortingOrder;
            RebuildCircle();
        }
    }

    void Reset()
    {
        // If added in editor
        BuildRenderer();
        RebuildCircle();
    }
}
