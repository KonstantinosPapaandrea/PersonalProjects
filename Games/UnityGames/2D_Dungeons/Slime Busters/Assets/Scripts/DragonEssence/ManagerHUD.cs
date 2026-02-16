using UnityEngine;
using UnityEngine.UI;
using TMPro;

public class ManagerHUD : MonoBehaviour
{
    [Header("Refs")]
    [SerializeField] TMP_Text balanceText;
    [SerializeField] TMP_Text statusText;
    [SerializeField] Button add100Button;
    [SerializeField] Button spend100Button;
    [SerializeField] Button refreshButton;

    void OnEnable()
    {
        if (DragonEssenceManager.Instance != null)
            DragonEssenceManager.Instance.OnEssenceAwarded += OnAwarded;
        WireButtons();
        RefreshUI();
    }

    void OnDisable()
    {
        if (DragonEssenceManager.Instance != null)
            DragonEssenceManager.Instance.OnEssenceAwarded -= OnAwarded;
    }

    void WireButtons()
    {
        add100Button.onClick.RemoveAllListeners();
        add100Button.onClick.AddListener(Add100);

        spend100Button.onClick.RemoveAllListeners();
        spend100Button.onClick.AddListener(Spend100);

        refreshButton.onClick.RemoveAllListeners();
        refreshButton.onClick.AddListener(RefreshUI);
    }

    void Add100()
    {
        // Simulate a win reward for testing
        var s = new MatchStats
        {
            wavesCleared = 10,
            won = true,
            livesStart = 20,
            livesEnd = 20,
            enemiesSpawned = 100,
            enemiesLeaked = 0,
            bossesKilled = 1,
            runSeconds = 240,
            difficultyTier = 0,
            streakWins = DragonEssenceManager.Instance.StreakWins
        };
        // Calculate whatever the formula gives, then top up to +100 if needed
        int before = DragonEssenceManager.Instance.Balance;
        DragonEssenceManager.Instance.Award(s);
        int gained = DragonEssenceManager.Instance.Balance - before;
        int pad = Mathf.Max(0, 100 - gained);
        if (pad > 0)
        {
            // Directly adjust via a private method would be cleaner; for debug we just call OnEssenceAwarded
            // but we also need to persist:
            var mgr = DragonEssenceManager.Instance;
            var ok = mgr.TrySpendDebug(-pad); // negative spend == add
            if (!ok) { /* ignore; just for debug */ }
        }
        statusText.text = $"+100 essence (debug).";
        RefreshUI();
    }

    void Spend100()
    {
        bool ok = DragonEssenceManager.Instance.TrySpendDebug(100);
        statusText.text = ok ? "Spent 100 essence (debug)." : "Not enough essence to spend 100.";
        RefreshUI();
    }

    void OnAwarded(int delta)
    {
        // Optional toast hook; we just refresh numbers
        RefreshUI();
    }

    void RefreshUI()
    {
        Debug.Log("test");
        if (DragonEssenceManager.Instance == null)
        {
            balanceText.text = "Essence: —";
            return;
        }
        balanceText.text = $"Essence: {DragonEssenceManager.Instance.Balance}";
    }
}
