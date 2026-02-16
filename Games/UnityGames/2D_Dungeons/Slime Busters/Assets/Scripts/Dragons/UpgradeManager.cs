using TMPro;
using UnityEngine;
using UnityEngine.UI;
using SlimeBusters;

public class UpgradeManager : MonoBehaviour
{
    public static UpgradeManager Instance { get; private set; }
    // UpgradeManager.cs
    // fields
    [SerializeField] private GameObject upgradePanel;
    [SerializeField] private DragonUpgradePanel genericPanel;  // ← replace firePanel


    [Header("Debug/Legacy Stat Labels (optional)")]
    public TMP_Text Damage;
    public TMP_Text FireRate;
    public TMP_Text Range;

    [Header("Legacy Buttons (safe to remove later)")]
    public Button Damage_Button;
    public Button FireRate_Button;
    public Button Range_Button;

    public Dragon currentTarget;

    void Awake()
    {
        if (Instance != null && Instance != this) { Destroy(gameObject); return; }
        Instance = this;
        if (upgradePanel) upgradePanel.SetActive(false);
    }

    public bool ToggleFor(Dragon target)
    {
        if (!target) return false;

        // 1) Same target: toggle visibility
        if (currentTarget == target)
        {
            bool newState = !upgradePanel.activeSelf;
            upgradePanel.SetActive(newState);

            if (!newState)
            {
                // closing
                currentTarget.SetRangeVisible(false);
                currentTarget = null;
            }
            else
            {
                // reopening for same target
                NotifyPanelsTargetChanged();
                Refresh(target);
                currentTarget.SetRangeVisible(true);
            }
            return newState;
        }

        // 2) Different target: switch selection, keep panel open
        if (currentTarget != null) currentTarget.SetRangeVisible(false);
        currentTarget = target;

        if (!upgradePanel.activeSelf) upgradePanel.SetActive(true);

        NotifyPanelsTargetChanged();   // rebuild menu for the new dragon type
        Refresh(target);               // update stat labels, button states
        currentTarget.SetRangeVisible(true);

        return true; // panel is open for the new target
    }

    void NotifyPanelsTargetChanged()
    {
        if (!upgradePanel) return;
        if (genericPanel)  // your DragonUpgradePanel
        {
            if (currentTarget)
            {
                genericPanel.gameObject.SetActive(true);
                genericPanel.ShowFor(currentTarget);  // force rebuild for the new type
            }
            else
            {
                genericPanel.gameObject.SetActive(false);
            }
        }
    }


    public void Refresh(Dragon d)
    {
        if (!d) return;
        if (Damage) Damage.SetText(d.damage.ToString());
        if (FireRate) FireRate.SetText(d.fireRate.ToString("0.##"));
        if (Range) Range.SetText(d.range.ToString("0.##"));

        if (genericPanel && genericPanel.gameObject.activeInHierarchy)
            genericPanel.RefreshAll();
    }

    public void Close()
    {
        if (upgradePanel) upgradePanel.SetActive(false);
        if (currentTarget != null)
        {
            currentTarget.SetRangeVisible(false);
            currentTarget = null;
        }
    }

    public bool IsOpenFor(Dragon target)
    {
        return upgradePanel && upgradePanel.activeSelf && currentTarget == target;
    }

 


    // Legacy handlers (keep for now; remove when you swap to the 3-path UI)
    public void UpgradeDamage() => currentTarget?.UpgradeDamage();
    public void UpgradeRange() => currentTarget?.UpgradeRange();
    public void UpgradeFireRate() => currentTarget?.UpgradeFireRate();

    public void SellCurrent()
    {
        if (!currentTarget) return;
        var toSell = currentTarget;
        Close();
        toSell.Sell();
    }

   

}
