using System.Collections.Generic;
using UnityEngine;

/// <summary>
/// Lightweight data models for a wave and its groups.
/// Keep these POCO-style so other systems can use them without dependencies.
/// </summary>
[System.Serializable]
public class WaveGroup
{
    public SlimeDef slime;
    public int count = 5;
    public float interval = 0.6f; // seconds between spawns in this group
    public float startTime = 0f;  // offset (sec) from wave start
}

[System.Serializable]
public class Wave
{
    public string name = "Wave";
    public bool useTimeline = true;         // if true, groups run in parallel respecting startTime
    public List<WaveGroup> groups = new();  // composition
}
