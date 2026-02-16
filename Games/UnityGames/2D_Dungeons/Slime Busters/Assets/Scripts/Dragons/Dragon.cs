namespace SlimeBusters
{
﻿using UnityEngine;

public class Dragon : MonoBehaviour
{
    // ───────────── Inspector ─────────────
    [Header("Targeting")]
    public bool canDetectCamo = false;
    public float range = 3f;
    public LayerMask enemyMask = 0;

    [Header("Firing")]
    [Tooltip("Global rate multiplier that AttackBehaviour uses to speed up cooldowns.")]
    public float fireRate = 1f;     // multiplier, not cadence gate
    public float damage = 1;
    public Transform firePoint;
    public AttackBehaviour attack;

    [Header("Aiming")]
    public Transform rotateRoot;

    [Header("Performance")]
    public float targetRefreshInterval = 0.15f;

    [Header("Range Viz")]
    [SerializeField] private Material rangeMaterial;
    RangeIndicator rangeInd;
    bool rangeVisible;
    [Header("Identity")]
    public DragonType dragonType;   // ← assign this in prefab (Fire / Ice / etc.)

    // ───────────── Runtime ─────────────
    Enemy _target;
    float _scanCd;

    // Costs (keep for now if you still need the old buttons; safe to remove later)
    int UpgradeDamageCost = 100;
    int UpgradeRangeCost = 100;
    int UpgradeFireRateCost = 100;

    // Convenience
    Transform AimTransform => rotateRoot ? rotateRoot : transform;
    Vector3 Origin => firePoint ? firePoint.position : transform.position;
    bool NeedsTarget => attack == null || attack.RequiresTarget;

    [HideInInspector] public DragonUpgrades upgrades;
    void Awake()
    {
        if (!upgrades) upgrades = gameObject.AddComponent<DragonUpgrades>();
        upgrades.Bind(this);
        attack?.Bind(this);
    }
    void Reset()
    {
        range = 3f; fireRate = 1f; damage = 1; targetRefreshInterval = 0.15f;
    }

    void Update()
    {
        _scanCd -= Time.deltaTime;

        TickTargeting();
        TickFiring(); // behaviour handles its own cooldowns internally
    }

    // ───────────── Targeting ─────────────

    void TickTargeting()
    {
        if (!NeedsTarget) { _target = null; return; }

        if (_scanCd <= 0f)
        {
            _scanCd = targetRefreshInterval;
            if (!IsValidTarget(_target)) _target = FindTarget();
        }

        if (IsValidTarget(_target))
        {
            Vector3 dir = _target.transform.position - AimTransform.position;
            float ang = Mathf.Atan2(dir.y, dir.x) * Mathf.Rad2Deg;
            AimTransform.rotation = Quaternion.Euler(0f, 0f, ang);
        }
    }

    bool IsValidTarget(Enemy e)
    {
        if (e == null) return false;
        if (!e.IsTargetableBy(this)) return false;
        if ((e.transform.position - transform.position).sqrMagnitude > range * range) return false;
        return true;
    }

    Enemy FindTarget()
    {
        Enemy best = null; float bestDsq = float.MaxValue;

        if (enemyMask.value != 0)
        {
            var hits = Physics2D.OverlapCircleAll(transform.position, range, enemyMask);
            foreach (var h in hits)
            {
                var e = h.GetComponent<Enemy>();
                if (!IsValidTarget(e)) continue;
                float dsq = (e.transform.position - transform.position).sqrMagnitude;
                if (dsq < bestDsq) { bestDsq = dsq; best = e; }
            }
            return best;
        }

        foreach (var e in GameObject.FindObjectsOfType<Enemy>())
        {
            if (!IsValidTarget(e)) continue;
            float dsq = (e.transform.position - transform.position).sqrMagnitude;
            if (dsq < bestDsq) { bestDsq = dsq; best = e; }
        }
        return best;
    }

    // ───────────── Firing ─────────────

    void TickFiring()
    {
        if (!attack) return;

        // If the behaviour needs a target, don't fire without one
        if (attack.RequiresTarget && !IsValidTarget(_target)) return;

        // Let behaviour run its own timers
        attack.Tick(Time.deltaTime);

        // Behaviour decides cadence
        if (attack.CanFireNow())
        {
            attack.Fire(Origin, _target, this);
        }
    }

    // ───────────── Range UI ─────────────

    void OnMouseDown()
    {
        UpgradeManager.Instance.ToggleFor(this);
    }

    public void SetRangeVisible(bool on)
    {
        rangeVisible = on;

        if (rangeInd == null && on)
        {
            rangeInd = RangeIndicator.Create(
                parent: transform,
                radius: range,
                mat: rangeMaterial,
                color: new Color(1f, 0.92f, 0.16f, 0.95f),
                lineWidth: 0.14f,
                segments: 72,
                sortingOrder: 500,
                sortingLayer: "Default",
                zOffset: -0.05f
            );
        }

        if (rangeInd)
        {
            if (on) rangeInd.SetRadius(range);
            rangeInd.Show(on);
        }
    }

    void OnDrawGizmosSelected()
    {
        Gizmos.color = new Color(1f, 0.92f, 0.16f, 0.8f);
        Gizmos.DrawWireSphere(transform.position, range);
    }

    // ───────────── Legacy stat upgrades (optional to keep/remove) ─────────────
    public void UpgradeDamage()
    {
        if (GameManager.Instance.CanAfford(UpgradeDamageCost))
        {
            GameManager.Instance.SpendCoins(UpgradeDamageCost);
            damage++;
            UpgradeManager.Instance.Refresh(this);
        }
    }

    public void UpgradeRange()
    {
        if (GameManager.Instance.CanAfford(UpgradeRangeCost))
        {
            GameManager.Instance.SpendCoins(UpgradeRangeCost);
            range++;
            if (rangeInd && rangeVisible) rangeInd.SetRadius(range);
            UpgradeManager.Instance.Refresh(this);
        }
    }

    public void UpgradeFireRate()
    {
        if (GameManager.Instance.CanAfford(UpgradeFireRateCost))
        {
            GameManager.Instance.SpendCoins(UpgradeFireRateCost);
            fireRate++;
            UpgradeManager.Instance.Refresh(this);
        }
    }

    // ───────────── Sell ─────────────

    public void Sell()
    {
        int refund = 50; // TODO: replace with your economy calc
        GameManager.Instance.AddCoins(refund);
        SetRangeVisible(false);
        if (UpgradeManager.Instance && UpgradeManager.Instance.currentTarget == this)
            UpgradeManager.Instance.Close();
        Destroy(gameObject);
    }
}

}
