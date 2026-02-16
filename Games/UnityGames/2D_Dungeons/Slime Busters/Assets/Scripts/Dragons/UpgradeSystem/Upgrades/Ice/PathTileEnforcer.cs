using UnityEngine;
using UnityEngine.Tilemaps;using SlimeBusters.Internal;

namespace SlimeBusters
{

public class PathTileEnforcer : MonoBehaviour
{
    [Header("Will be injected by spawner if available")]
    public Tilemap roadMap;

    [Header("Auto-find fallback (used if roadMap is null)")]
    public bool tryFindByTag = true;
    public string roadTag = "Path";
    public bool tryFindByName = true;
    public string roadObjectName = "Road"; // set to your Road tilemap GO name

    [Tooltip("Search radius in cells if spawn isn't on road.")]
    public int maxSearchRadiusCells = 2;

    [Tooltip("If no road cell found, destroy this patch.")]
    public bool destroyIfNoRoad = true;

    [Tooltip("Snap to exact cell center for clean alignment.")]
    public bool snapToCellCenter = true;

    void Awake()
    {
        // Fallback discovery if not injected
        if (!roadMap)
        {
            if (tryFindByTag)
            {
                var go = GameObject.FindWithTag(roadTag);
                if (go) roadMap = SLB_ComponentCache.Get<Tilemap>(go);
            }
            if (!roadMap && tryFindByName)
            {
                var go = GameObject.Find(roadObjectName);
                if (go) roadMap = SLB_ComponentCache.Get<Tilemap>(go);
            }
            if (!roadMap && RoadMapProvider.Instance) // Option 3 support
            {
                roadMap = RoadMapProvider.Instance.tilemap;
            }
        }

        if (!roadMap)
        {
            SLB_Debug.LogWarning("[PathTileEnforcer] No roadMap available. Destroying patch.");
            if (destroyIfNoRoad) Destroy(gameObject);
            return;
        }

        // Snap to nearest road cell
        var cell = roadMap.WorldToCell(transform.position);
        if (roadMap.HasTile(cell))
        {
            if (snapToCellCenter) transform.position = roadMap.GetCellCenterWorld(cell);
            return;
        }

        bool found = false;
        Vector3Int bestCell = cell;
        float bestDist = float.MaxValue;
        Vector3 worldPos = transform.position;

        for (int r = 1; r <= Mathf.Max(1, maxSearchRadiusCells); r++)
        {
            for (int dx = -r; dx <= r; dx++)
                for (int dy = -r; dy <= r; dy++)
                {
                    var c = new Vector3Int(cell.x + dx, cell.y + dy, cell.z);
                    if (!roadMap.HasTile(c)) continue;

                    var center = roadMap.GetCellCenterWorld(c);
                    float d = (center - worldPos).sqrMagnitude;
                    if (d < bestDist)
                    {
                        bestDist = d;
                        bestCell = c;
                        found = true;
                    }
                }
            if (found) break;
        }

        if (found)
        {
            if (snapToCellCenter) transform.position = roadMap.GetCellCenterWorld(bestCell);
        }
        else if (destroyIfNoRoad)
        {
            Destroy(gameObject);
        }
    }
}

}
