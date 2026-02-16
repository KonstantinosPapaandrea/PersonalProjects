using UnityEngine;
using SlimeBusters;

public class BuildManager : MonoBehaviour
{
    public static BuildManager I;

    [Header("Layers")]
    [Tooltip("Tiles/objects you must NOT build on (e.g., Path).")]
    public LayerMask blockedMask;        // e.g., Path layer
    [Tooltip("Existing towers to avoid overlap.")]
    public LayerMask towersMask;         // e.g., Tower layer

    [Header("Placement")]
    public float checkRadius = 0.3f;     // overlap check around mouse
    public bool snapToGrid = true;
    public float gridSize = 0.5f;

    GameObject ghost;                    // preview object
    GameObject towerPrefab;              // what well place
    int towerCost;

    SpriteRenderer ghostSR;
    Color okColor = new Color(1, 1, 1, 0.6f);
    Color badColor = new Color(1, 0.4f, 0.4f, 0.6f);
    public bool IsPlacing => ghost != null;

    public void BeginDragPlacement(GameObject prefab, int cost)
    {
        BeginPlacing(prefab, cost); // reuse your existing method
    }
    public void UpdateGhostPositionFromScreen(Vector2 screenPos)
    {
        if (!ghost) return;
        Vector3 m = Camera.main.ScreenToWorldPoint(new Vector3(screenPos.x, screenPos.y, 10f));
        m.z = -1;

        if (snapToGrid)
        {
            m.x = Mathf.Round(m.x / gridSize) * gridSize;
            m.y = Mathf.Round(m.y / gridSize) * gridSize;
        }

        ghost.transform.position = m;

        // tint based on validity
        bool valid = IsValidSpot(m);
        if (ghostSR) ghostSR.color = valid ? okColor : badColor;
    }

    public bool TryPlaceAtGhost()
    {
        if (!ghost) return false;

        Vector3 pos = ghost.transform.position;
        pos.z = -1;
        bool valid = IsValidSpot(pos);

        if (!valid) return false;
        if (!GameManager.Instance.SpendCoins(towerCost)) return false;

        PlaceNow(pos);
        return true;
    }

    public void CancelDragPlacement()
    {
        CancelPlacing();
    }
    void Awake() { I = this; }

    void Update()
    {
        if (!ghost) return;

        // Follow mouse
        Vector3 m = Camera.main.ScreenToWorldPoint(Input.mousePosition);
        m.z = -1;
        if (snapToGrid)
        {
            m.x = Mathf.Round(m.x / gridSize) * gridSize;
            m.y = Mathf.Round(m.y / gridSize) * gridSize;
        }
        ghost.transform.position = m;

        // Valid spot?
        bool valid = IsValidSpot(m);

        // Tint ghost
        if (ghostSR) ghostSR.color = valid ? okColor : badColor;

        // Place / Cancel
        if (Input.GetMouseButtonDown(0) && valid)
        {
            if (GameManager.Instance.SpendCoins(towerCost))
            {
                PlaceNow(m);
            }
            else
            {
                // Optional: play "not enough coins" feedback
            }
        }

        if (Input.GetMouseButtonDown(1) || Input.GetKeyDown(KeyCode.Escape))
        {
            CancelPlacing();
        }
    }

    public void BeginPlacing(GameObject prefab, int cost)
    {
        CancelPlacing(); // clear any previous
        towerPrefab = prefab;
        towerCost = cost;

        ghost = Instantiate(towerPrefab);
        // ensure it's only a visual preview (disable Tower script while previewing)
        var tower = ghost.GetComponent<Dragon>();
        if (tower) tower.enabled = false;

        ghostSR = ghost.GetComponent<SpriteRenderer>();
        if (!ghostSR)
        {
            // fallback: find any SR in children
            ghostSR = ghost.GetComponentInChildren<SpriteRenderer>();
        }
        if (ghostSR) ghostSR.color = okColor;

        // put ghost on a harmless layer if needed so it doesn't block itself
        // e.g., Layer "IgnoreRaycast"
        ghost.layer = LayerMask.NameToLayer("Ignore Raycast");
    }

    void PlaceNow(Vector3 pos)
    {
        // create real tower
        var placed = Instantiate(towerPrefab, pos, Quaternion.identity);
        // put it on Tower layer (so future checks avoid overlap)
        int towerLayer = LayerMask.NameToLayer("Tower");
        if (towerLayer >= 0) placed.layer = towerLayer;

        CancelPlacing();
    }

    void CancelPlacing()
    {
        if (ghost) Destroy(ghost);
        ghost = null;
        ghostSR = null;
        towerPrefab = null;
        towerCost = 0;
    }

    bool IsValidSpot(Vector3 pos)
    {
        // Blocked by path or unbuildable?
        bool hitBlocked = Physics2D.OverlapCircle(pos, checkRadius, blockedMask);
        if (hitBlocked) return false;

        // Overlapping another tower?
        bool hitTower = Physics2D.OverlapCircle(pos, checkRadius, towersMask);
        if (hitTower) return false;

        return true;
    }

    // Optional gizmo to visualize check radius
    void OnDrawGizmosSelected()
    {
        if (!ghost) return;
        Gizmos.color = Color.yellow;
        Gizmos.DrawWireSphere(ghost.transform.position, checkRadius);
    }
}
