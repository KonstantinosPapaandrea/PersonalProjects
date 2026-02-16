using System;
using System.IO;
using System.Text;
using System.Security.Cryptography;
using UnityEngine;
using System.Collections.Generic;

[Serializable]
public class EssenceSave
{
    public int essenceBalance;
    public int todayEarned;
    public long lastEarnedUnix;
    public int streakWins;
    public List<Upgrade> upgradeLevels = new();  // Store upgrades as a list of Upgrade objects
    public int dragonSouls;
    public List<string> ownedCosmetics = new();
    public List<string> ownedInfusionIds = new();

    // --- Meta
    public int version = 1;
    public long lastSaveUnix;
    public string checksum;

    [Serializable]
    public class Upgrade
    {
        public string key;
        public int level;

        public Upgrade(string key, int level)
        {
            this.key = key;
            this.level = level;
        }
    }
}

public class DragonEssenceManager : MonoBehaviour
{
    public static DragonEssenceManager Instance { get; private set; }
    EssenceSave save = new();

    // Expose upgradeLevels as a property (List<Upgrade>) for access
    public List<EssenceSave.Upgrade> UpgradeLevels => save.upgradeLevels;

    public int LastAwardDelta { get; private set; }
    public event Action<int> OnEssenceAwarded;

    static string SavePath => Path.Combine(Application.persistentDataPath, "dragon_essence.json");
    static string TempPath => SavePath + ".tmp";
    static string BackupPath => SavePath + ".bak";

    const string SALT = "dOpAline~Ess3nce~S@lt#1";

    void Awake()
    { //ResetUpgrades();
        if (Instance == null)
        {
            Instance = this;
            transform.SetParent(null);
            DontDestroyOnLoad(gameObject);
            Load();
            Application.quitting += OnAppQuitting;
        }
        else if (Instance != this)
        {
            Destroy(gameObject);
        }
    }

    void OnAppQuitting() => SaveSafe();

    public int Balance => save.essenceBalance;
    public int TodayEarned { get { ResetIfNewDay(); return save.todayEarned; } }
    public int StreakWins => save.streakWins;

    public int Award(MatchStats stats)
    {
        ResetIfNewDay();
        bool firstWinToday = !HasEarnedToday() || (stats.won && save.streakWins == 0);

        int reward = RewardCalculator.Calculate(stats, save.todayEarned, firstWinToday);
        LastAwardDelta = reward;

        save.essenceBalance += reward;
        save.todayEarned += reward;
        save.lastEarnedUnix = Now();
        if (stats.won) save.streakWins++; else save.streakWins = 0;

        SaveSafe();
        OnEssenceAwarded?.Invoke(reward);
        return reward;
    }
    public void ResetUpgrades()
    {
        // Clear all the upgrades and reset essence balance
        save.upgradeLevels.Clear();
        save.essenceBalance = 100;

        // You can also reset other values like streaks, dragon souls, etc., if needed
        save.streakWins = 0;
        save.dragonSouls = 0;
        save.ownedCosmetics.Clear();
        save.ownedInfusionIds.Clear();

        // Call SaveSafe to persist changes
        SaveSafe();

        Debug.Log("[DragonEssenceManager] Upgrades and essence reset.");
    }

    public bool TryPurchase(string nodeId, int cost)
    {
        if (save.essenceBalance < cost) return false;
        save.essenceBalance -= cost;

        // Check if the upgrade exists in the list, or add it
        var existingUpgrade = save.upgradeLevels.Find(u => u.key == nodeId);
        if (existingUpgrade != null)
        {
            existingUpgrade.level++;
        }
        else
        {
            save.upgradeLevels.Add(new EssenceSave.Upgrade(nodeId, 1));
        }

        SaveSafe();
        return true;
    }

    // New method to spend essence for testing purposes
    public bool TrySpendDebug(int amount)
    {
        if (amount <= 0) return false;
        if (save.essenceBalance < amount) return false;
        save.essenceBalance -= amount;
        SaveSafe();
        OnEssenceAwarded?.Invoke(-amount); // Fire an event to show deduction on the UI
        return true;
    }

    void ResetIfNewDay()
    {
        if (save.lastEarnedUnix == 0) return;
        var last = DateTimeOffset.FromUnixTimeSeconds(save.lastEarnedUnix).ToLocalTime().Date;
        var now = DateTime.Now.Date;
        if (now > last) save.todayEarned = 0;
    }

    bool HasEarnedToday()
    {
        if (save.lastEarnedUnix == 0) return false;
        return DateTimeOffset.FromUnixTimeSeconds(save.lastEarnedUnix).ToLocalTime().Date == DateTime.Now.Date;
    }

    long Now() => DateTimeOffset.UtcNow.ToUnixTimeSeconds();

    // === Robust save/load ===
    public void SaveSafe()
    {
        try
        {
            save.version = 1;
            save.lastSaveUnix = Now();

            string json = JsonUtility.ToJson(save);
            string sig = ComputeChecksum(json);
            // re-pack to include checksum
            save.checksum = sig;
            json = JsonUtility.ToJson(save);

            // Atomic write: write temp, then replace
            File.WriteAllText(TempPath, json, Encoding.UTF8);
            if (File.Exists(SavePath)) File.Copy(SavePath, BackupPath, overwrite: true);
#if UNITY_EDITOR_WIN || UNITY_STANDALONE
            if (File.Exists(SavePath)) File.Replace(TempPath, SavePath, BackupPath, ignoreMetadataErrors: true);
            else File.Move(TempPath, SavePath);
#else
            File.Move(TempPath, SavePath);
#endif
        }
        catch (Exception ex)
        {
            Debug.LogError("[Essence] Save failed: " + ex);
        }
    }

    void Load()
    {
        try
        {
            if (File.Exists(SavePath))
            {
                string json = File.ReadAllText(SavePath, Encoding.UTF8);
                var loaded = JsonUtility.FromJson<EssenceSave>(json);
                if (loaded != null && ValidateChecksum(loaded, json))
                {
                    save = loaded;
                    return;
                }
                else
                {
                    Debug.LogWarning("[Essence] Save checksum invalid—trying backup.");
                }
            }
            if (File.Exists(BackupPath))
            {
                string json = File.ReadAllText(BackupPath, Encoding.UTF8);
                var loaded = JsonUtility.FromJson<EssenceSave>(json);
                if (loaded != null && ValidateChecksum(loaded, json))
                {
                    save = loaded;
                    SaveSafe();
                    return;
                }
            }

            // Fallback to PlayerPrefs for legacy data
            if (PlayerPrefs.HasKey("dragon_essence_v1"))
            {
                string old = PlayerPrefs.GetString("dragon_essence_v1");
                var legacy = JsonUtility.FromJson<EssenceSave>(old);
                if (legacy != null) { save = legacy; SaveSafe(); return; }
            }
            save = new EssenceSave(); // fresh start
            SaveSafe();
        }
        catch (Exception ex)
        {
            Debug.LogError("[Essence] Load failed: " + ex);
            save = new EssenceSave();
        }
    }

    // === Integrity ===
    string ComputeChecksum(string json)
    {
        var copy = JsonUtility.FromJson<EssenceSave>(json);
        if (copy != null) copy.checksum = string.Empty;
        string stripped = JsonUtility.ToJson(copy);

        using var sha = SHA256.Create();
        var bytes = sha.ComputeHash(Encoding.UTF8.GetBytes(stripped + SALT));
        return BitConverter.ToString(bytes).Replace("-", "").ToLowerInvariant();
    }

    bool ValidateChecksum(EssenceSave candidate, string originalJson)
    {
        try
        {
            var copy = JsonUtility.FromJson<EssenceSave>(originalJson);
            if (copy == null) return false;
            string sig = copy.checksum;
            copy.checksum = string.Empty;
            string stripped = JsonUtility.ToJson(copy);
            using var sha = SHA256.Create();
            var bytes = sha.ComputeHash(Encoding.UTF8.GetBytes(stripped + SALT));
            string shouldBe = BitConverter.ToString(bytes).Replace("-", "").ToLowerInvariant();
            return !string.IsNullOrEmpty(sig) && sig == shouldBe;
        }
        catch { return false; }
    }
}
