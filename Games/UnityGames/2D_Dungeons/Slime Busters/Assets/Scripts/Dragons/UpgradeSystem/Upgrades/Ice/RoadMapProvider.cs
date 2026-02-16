using UnityEngine;
using UnityEngine.Tilemaps;

public class RoadMapProvider : MonoBehaviour
{
    public static RoadMapProvider Instance { get; private set; }
    public Tilemap tilemap;

    void Awake()
    {
        if (Instance && Instance != this) { Destroy(gameObject); return; }
        Instance = this;
        if (!tilemap) tilemap = GetComponent<Tilemap>();
    }
}
