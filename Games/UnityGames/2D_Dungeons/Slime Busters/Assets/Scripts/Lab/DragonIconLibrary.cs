using UnityEngine;
using System.Collections.Generic;
using SlimeBusters;

[CreateAssetMenu(menuName = "TD/Lab/Dragon Icon Library")]
public class DragonIconLibrary : ScriptableObject
{
    [System.Serializable]
    public class Entry
    {
        public string dragonClass; // e.g. "Fire", "Ice"
        public Sprite icon;
        public Color tint = Color.white; // optional accent
    }

    public List<Entry> entries = new();

    public bool TryGet(string cls, out Sprite icon, out Color tint)
    {
        foreach (var e in entries)
        {
            if (!string.IsNullOrEmpty(e.dragonClass) && e.dragonClass == cls)
            {
                icon = e.icon; tint = e.tint; return true;
            }
        }
        icon = null; tint = Color.white; return false;
    }
}
