using System;
using System.Collections.Generic;
using UnityEngine;

public class ProgressService : MonoBehaviour
{
    public static ProgressService Instance { get; private set; }

    [Serializable]
    private class SaveModel
    {
        public List<string> unlocked = new();
        public List<string> regionIds = new();
        public List<int> stars = new();
        public int totalStars = 0;
    }

    private const string KEY = "TD_Progress_v1";
    private HashSet<string> _unlocked = new();
    private Dictionary<string, int> _stars = new();
    public int TotalStars { get; private set; }

    void Awake()
    {
        if (Instance != null && Instance != this) { Destroy(gameObject); return; }
        Instance = this;
        DontDestroyOnLoad(gameObject);
        Load();
        // Make sure the first region is always unlocked by default
        if (_unlocked.Count == 0) Unlock("grasslands");
    }

    public bool IsUnlocked(string regionId) => _unlocked.Contains(regionId);
    public int GetStars(string regionId) => _stars.TryGetValue(regionId, out var s) ? s : 0;

    public void Unlock(string regionId)
    {
        if (_unlocked.Add(regionId)) Save();
    }

    public void CompleteRegion(string regionId, int starsEarned)
    {
        starsEarned = Mathf.Clamp(starsEarned, 0, 3);
        int prev = GetStars(regionId);
        if (starsEarned > prev)
        {
            _stars[regionId] = starsEarned;
            RecalcTotalStars();
            Save();
        }
    }

    private void RecalcTotalStars()
    {
        int sum = 0;
        foreach (var kvp in _stars) sum += kvp.Value;
        TotalStars = sum;
    }

    public void ResetAll()
    {
        _unlocked.Clear(); _stars.Clear(); TotalStars = 0;
        Save();
    }

    private void Save()
    {
        var model = new SaveModel
        {
            unlocked = new List<string>(_unlocked),
            regionIds = new List<string>(_stars.Keys),
            stars = new List<int>(_stars.Values),
            totalStars = TotalStars
        };
        PlayerPrefs.SetString(KEY, JsonUtility.ToJson(model));
        PlayerPrefs.Save();
    }

    private void Load()
    {
        if (!PlayerPrefs.HasKey(KEY)) { TotalStars = 0; return; }
        var json = PlayerPrefs.GetString(KEY);
        var model = JsonUtility.FromJson<SaveModel>(json);
        _unlocked = new HashSet<string>(model.unlocked ?? new List<string>());
        _stars = new Dictionary<string, int>();
        if (model.regionIds != null && model.stars != null)
        {
            for (int i = 0; i < Mathf.Min(model.regionIds.Count, model.stars.Count); i++)
                _stars[model.regionIds[i]] = model.stars[i];
        }
        TotalStars = model.totalStars;
    }
}
