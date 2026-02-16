using UnityEngine;
using UnityEngine.UI;
using TMPro;

public class ShopItemButton : MonoBehaviour
{
    [Header("UI Refs")]
    public Image iconImage;
    public TMP_Text nameText;
    public TMP_Text costText;

    [Header("Behaviours")]
    public Button clickButton;               // optional (tap-to-place path)
    public ShopDragItem dragItem;            // for drag & drop

    DragonDef def;

    public void Setup(DragonDef d)
    {
        def = d;
        if (iconImage) iconImage.sprite = d.icon;
        if (nameText) nameText.text = d.displayName;
        if (costText) costText.text = d.cost.ToString();

        // wire data into the drag script
        if (dragItem)
        {
            dragItem.towerPrefab = d.prefab;
            dragItem.cost = d.cost;
        }

        // optional: also support tap-to-place
        if (clickButton)
        {
            clickButton.onClick.RemoveAllListeners();
            clickButton.onClick.AddListener(() =>
            {
                if (GameManager.Instance.CanAfford(d.cost))
                    BuildManager.I.BeginPlacing(d.prefab, d.cost);
                else
                {
                    // TODO: feedback "not enough coins"
                }
            });
        }
    }
}
