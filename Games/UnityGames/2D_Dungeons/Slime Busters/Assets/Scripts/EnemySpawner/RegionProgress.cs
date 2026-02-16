using UnityEngine;

/// <summary>
/// Tiny helper to persist the player's level per region via PlayerPrefs.
/// </summary>
public static class RegionProgress
{
    static string Key(string regionId) => $"endlesslevel.progress.{regionId}";

    /// <summary>Load saved level for a region; default = 1.</summary>
    public static int LoadLevel(string regionId, int defaultLevel = 1)
        => PlayerPrefs.GetInt(Key(regionId), defaultLevel);

    /// <summary>Save current level for a region (clamped to >=1).</summary>
    public static void SaveLevel(string regionId, int level)
        => PlayerPrefs.SetInt(Key(regionId), Mathf.Max(1, level));
}
