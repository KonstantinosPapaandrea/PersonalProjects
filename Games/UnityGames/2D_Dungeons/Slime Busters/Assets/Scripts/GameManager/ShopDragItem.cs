using UnityEngine;
using UnityEngine.EventSystems;

public class ShopDragItem : MonoBehaviour, IBeginDragHandler, IDragHandler, IEndDragHandler
{
    [HideInInspector] public GameObject towerPrefab;
    [HideInInspector] public int cost;

    public CanvasGroup canvasGroup;
    public float dragAlpha = 0.6f;
    bool dragging;

    void Awake()
    {
        if (!canvasGroup) canvasGroup = GetComponent<CanvasGroup>();
    }

    public void OnBeginDrag(PointerEventData e)
    {
        // Close (hide) the shop, but keep GameObjects active
        ShopToggleButton.Instance?.Close();

        if (!towerPrefab) return;
        if (!GameManager.Instance.CanAfford(cost)) return;

        dragging = true;
        BuildManager.I.BeginDragPlacement(towerPrefab, cost);

        if (canvasGroup) { canvasGroup.alpha = dragAlpha; canvasGroup.blocksRaycasts = false; }
        BuildManager.I.UpdateGhostPositionFromScreen(e.position);
    }

    public void OnDrag(PointerEventData e)
    {
        if (!dragging) return;
        BuildManager.I.UpdateGhostPositionFromScreen(e.position);
    }

    public void OnEndDrag(PointerEventData e)
    {
        if (!dragging) return;
        dragging = false;

        bool placed = BuildManager.I.TryPlaceAtGhost();
        if (!placed) BuildManager.I.CancelDragPlacement();

        if (canvasGroup) { canvasGroup.alpha = 1f; canvasGroup.blocksRaycasts = true; }

        // Re-open after drag finishes
        ShopToggleButton.Instance?.Open();
    }
}
