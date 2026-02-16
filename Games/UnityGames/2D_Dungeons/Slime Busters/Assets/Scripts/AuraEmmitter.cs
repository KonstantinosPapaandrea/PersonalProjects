using System.Collections.Generic;
using UnityEngine;using SlimeBusters.Internal;

namespace SlimeBusters
{

[RequireComponent(typeof(Enemy))]
[ExecuteAlways] // so ring updates in Editor when values change
public class AuraEmitter : MonoBehaviour
{
    Enemy owner;
    SlimeDef def;

    float radius;
    float healPerSecond;
    float maxHpBonusPercent;

    // Resistance aura bonus (percent points 0..100 per type)
    SlimeDef.Resistances resistBonus;
    bool hasResistAura;

    // Track everyone currently inside our aura (used for (un)registering buffs)
    readonly HashSet<Enemy> recipients = new HashSet<Enemy>();
    int sourceId;

    // Scan cadence (runtime)
    [SerializeField] float scanInterval = 0.2f;
    float scanCd;

    // -------- Visual ring (LineRenderer) --------
    [Header("Ring Visual")]
    [SerializeField] bool showRing = true;
    [SerializeField] int ringSegments = 64;
    [SerializeField] float ringWidth = 0.06f;
    [SerializeField] Color ringColor = new Color(0.2f, 1f, 0.6f, 0.6f);
    [SerializeField] int ringSortingOrderOffset = +1; // draw above slime
    [SerializeField] float ringZOffset = -0.01f;

    LineRenderer lr;
    float lastBuiltRadius = -1f;
    int lastBuiltSegments = -1;

    // Which objects are allies? (Set to your Enemy layer in the Inspector for best perf)
    [SerializeField] LayerMask allyMask = ~0;

    // Debug aid
    [Header("Debug")]
    [SerializeField] bool verboseLogs = false;

    public void Bind(Enemy enemy, SlimeDef slimeDef)
    {
        owner = enemy;
        def = slimeDef;

        radius = Mathf.Max(0f, def?.auraRadius ?? 0f);
        healPerSecond = Mathf.Max(0f, def?.healingAuraPerSecond ?? 0f);
        maxHpBonusPercent = Mathf.Max(0f, def?.maxHpAuraPercent ?? 0f);

        resistBonus = def?.resistanceAuraBonus ?? default;
        hasResistAura =
            resistBonus.physical > 0 ||
            resistBonus.fire > 0 ||
            resistBonus.ice > 0 ||
            resistBonus.lightning > 0 ||
            resistBonus.egg > 0 ||
            resistBonus.crystal > 0;

        sourceId = GetInstanceID();
        scanCd = 0f;

        // Clean slate: drop any stale registrations
        UnregisterFromAll();

        // Self should immediately benefit from our auras
        if (owner)
        {
            if (maxHpBonusPercent > 0f) owner.RegisterMaxHpAura(sourceId, maxHpBonusPercent);
            if (hasResistAura) owner.RegisterResistanceAura(sourceId, resistBonus);
        }

        SetupRing();
        RefreshRing(true);
        ReportIfHidden("Bind()");
    }

    void OnDisable()
    {
        UnregisterFromAll();
        if (owner)
        {
            if (maxHpBonusPercent > 0f) owner.UnregisterMaxHpAura(sourceId);
            if (hasResistAura) owner.UnregisterResistanceAura(sourceId);
        }
        if (lr) lr.enabled = false;
    }

    void OnDestroy()
    {
        UnregisterFromAll();
        if (owner)
        {
            if (maxHpBonusPercent > 0f) owner.UnregisterMaxHpAura(sourceId);
            if (hasResistAura) owner.UnregisterResistanceAura(sourceId);
        }
    }

    void Update()
    {
#if UNITY_EDITOR
        // In edit mode, just keep the ring preview up-to-date.
        if (!Application.isPlaying)
        {
            PullDefValuesIfMissing();
            SetupRing();
            RefreshRing();
            return;
        }
#endif
        if (!owner) { if (lr) lr.enabled = false; return; }

        bool hasAnyAura = (healPerSecond > 0f) || (maxHpBonusPercent > 0f) || hasResistAura;
        if (!hasAnyAura || radius <= 0f)
        {
            if (lr) lr.enabled = false;
            return;
        }

        if (lr) lr.enabled = showRing;

        // Continuous healing for SELF (smooth)
        if (healPerSecond > 0f)
            owner.ReceiveHeal(healPerSecond * Time.deltaTime);

        // Periodic scan to (un)register auras on ALLIES and give them a small heal pulse
        scanCd -= Time.deltaTime;
        if (scanCd <= 0f)
        {
            scanCd = scanInterval;
            RefreshRecipientsAndPulseHeal();
        }

        RefreshRing();
    }

    // ---------- Allies scan ----------
    void RefreshRecipientsAndPulseHeal()
    {
        var pos = transform.position;
        var hits = Physics2D.OverlapCircleAll(pos, radius, allyMask);

        var current = new HashSet<Enemy>();
        if (hits != null)
        {
            foreach (var h in hits)
            {
                var e = SLB_ComponentCache.Get<Enemy>(h);
                if (!e) continue;

                current.Add(e);

                // Heal pulse for allies (optional: complements self continuous heal)
                if (healPerSecond > 0f)
                {
                    float pulse = healPerSecond * scanInterval * 0.5f;
                    e.ReceiveHeal(pulse);
                }

                // Register Max HP aura for allies entering
                if (maxHpBonusPercent > 0f && !recipients.Contains(e))
                    e.RegisterMaxHpAura(sourceId, maxHpBonusPercent);

                // Register Resistance aura for allies entering
                if (hasResistAura && !recipients.Contains(e))
                    e.RegisterResistanceAura(sourceId, resistBonus);

                // Track as a recipient if not already
                recipients.Add(e);
            }
        }

        // Remove auras from allies that left radius
        if (recipients.Count > 0)
        {
            s_tmp.Clear();
            foreach (var r in recipients) if (!current.Contains(r)) s_tmp.Add(r);

            foreach (var r in s_tmp)
            {
                if (r)
                {
                    if (maxHpBonusPercent > 0f) r.UnregisterMaxHpAura(sourceId);
                    if (hasResistAura) r.UnregisterResistanceAura(sourceId);
                }
                recipients.Remove(r);
            }
        }
    }

    void UnregisterFromAll()
    {
        if (recipients.Count == 0) return;
        foreach (var r in recipients)
        {
            if (!r) continue;
            if (maxHpBonusPercent > 0f) r.UnregisterMaxHpAura(sourceId);
            if (hasResistAura) r.UnregisterResistanceAura(sourceId);
        }
        recipients.Clear();
    }

    // ---------- Ring ----------
    void SetupRing()
    {
        if (!showRing) return;

        if (!lr)
        {
            // Only search under THIS transform; never scene-wide.
            Transform child = transform.Find("AuraRing");
            GameObject go = child ? child.gameObject : new GameObject("AuraRing");
            if (!child) go.transform.SetParent(transform, false);

            go.transform.localPosition = new Vector3(0f, 0f, ringZOffset);

            lr = SLB_ComponentCache.Get<LineRenderer>(go);
            if (!lr) lr = go.AddComponent<LineRenderer>();

            lr.loop = true;
            lr.useWorldSpace = false;
            lr.textureMode = LineTextureMode.Stretch;
            lr.numCornerVertices = 2;
            lr.numCapVertices = 2;

            lr.material = ResolveLineMaterial();
        }

        // Match host SpriteRenderer’s sorting so it renders with the slime
        var hostSR = owner ? owner.GetComponentInChildren<SpriteRenderer>() : null;
        if (hostSR)
        {
            lr.sortingLayerID = hostSR.sortingLayerID;
            lr.sortingOrder = hostSR.sortingOrder + ringSortingOrderOffset;
        }

        lr.startWidth = ringWidth;
        lr.endWidth = ringWidth;
        lr.startColor = ringColor;
        lr.endColor = ringColor;
    }

    void RefreshRing(bool force = false)
    {
        if (!lr || !showRing) return;

        // Keep style in sync
        lr.startWidth = ringWidth;
        lr.endWidth = ringWidth;
        lr.startColor = ringColor;
        lr.endColor = ringColor;

        int segs = Mathf.Max(8, ringSegments);
        if (force || !Mathf.Approximately(radius, lastBuiltRadius) || segs != lastBuiltSegments)
        {
            lastBuiltRadius = radius;
            lastBuiltSegments = segs;

            lr.positionCount = segs;
            float step = Mathf.PI * 2f / segs;
            for (int i = 0; i < segs; i++)
            {
                float a = i * step;
                lr.SetPosition(i, new Vector3(Mathf.Cos(a) * radius, Mathf.Sin(a) * radius, 0f));
            }
        }
    }

    Material ResolveLineMaterial()
    {
        // Try Sprite shader first (best with sorting layers in 2D)
        var mat = TryMakeMat("Sprites/Default");
        if (mat) return mat;

        // URP Unlit (common in URP projects)
        mat = TryMakeMat("Universal Render Pipeline/Unlit");
        if (mat) return mat;

        // Legacy fallback
        mat = TryMakeMat("Unlit/Color");
        if (mat) return mat;

        if (verboseLogs) SLB_Debug.LogWarning("[AuraEmitter] No suitable shader found for LineRenderer. Ring may be invisible.");
        return new Material(Shader.Find(null)); // still assign something
    }

    static Material TryMakeMat(string shaderName)
    {
        var sh = Shader.Find(shaderName);
        if (!sh) return null;
        var m = new Material(sh) { hideFlags = HideFlags.HideAndDontSave };
        return m;
    }

    // Editor-time preview updates when you tweak SlimeDef or fields
    void OnValidate()
    {
        PullDefValuesIfMissing();
        SetupRing();
        RefreshRing(true);
    }

    void PullDefValuesIfMissing()
    {
        if (!owner) owner = SLB_ComponentCache.Get<Enemy>(this);
        if (!def && owner)
        {
            // Access Enemy.def (serialized private) via reflection
            var f = typeof(Enemy).GetField("def", System.Reflection.BindingFlags.Instance | System.Reflection.BindingFlags.NonPublic | System.Reflection.BindingFlags.Public);
            if (f != null) def = (SlimeDef)f.GetValue(owner);
        }

        if (def)
        {
            radius = Mathf.Max(0f, def.auraRadius);
            healPerSecond = Mathf.Max(0f, def.healingAuraPerSecond);
            maxHpBonusPercent = Mathf.Max(0f, def.maxHpAuraPercent);
            resistBonus = def.resistanceAuraBonus;

            hasResistAura =
                resistBonus.physical > 0 ||
                resistBonus.fire > 0 ||
                resistBonus.ice > 0 ||
                resistBonus.lightning > 0 ||
                resistBonus.egg > 0 ||
                resistBonus.crystal > 0;
        }
    }

    void ReportIfHidden(string where)
    {
        if (!verboseLogs) return;

        if (!owner) SLB_Debug.Log($"[AuraEmitter] ({where}) owner is null");
        if (!def) SLB_Debug.Log($"[AuraEmitter] ({where}) def is null");
        if (def && def.auraRadius <= 0f) SLB_Debug.Log($"[AuraEmitter] ({where}) auraRadius <= 0");
        if (def && def.auraRadius > 0f &&
            def.healingAuraPerSecond <= 0f &&
            def.maxHpAuraPercent <= 0f &&
            !hasResistAura)
        {
            SLB_Debug.Log($"[AuraEmitter] ({where}) radius set but no aura values > 0 → hidden");
        }
    }

    static readonly List<Enemy> s_tmp = new List<Enemy>();

    void OnDrawGizmosSelected()
    {
        PullDefValuesIfMissing();
        if (def == null || def.auraRadius <= 0f) return;

        Gizmos.color = new Color(0.2f, 1f, 0.6f, 0.25f);
        Gizmos.DrawWireSphere(transform.position, def.auraRadius);
    }
}

}
