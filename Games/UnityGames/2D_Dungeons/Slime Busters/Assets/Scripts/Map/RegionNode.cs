using UnityEngine;
using UnityEngine.UI;
using TMPro;
using UnityEngine.EventSystems;

public class RegionNode : MonoBehaviour, IPointerEnterHandler, IPointerExitHandler
{
    public Button button;
    public Image icon;
    public GameObject lockOverlay;
    public TextMeshProUGUI lockText;
    public TextMeshProUGUI label;
    public Image[] starImages; // size 3, fillAmount or sprite swap

    [HideInInspector] public RegionData data;

    public void Bind(RegionData d, bool unlocked, int earnedStars, int totalStars, System.Action<RegionNode> onClick)
    {
        data = d;
        label.text = d.displayName;
        if (icon) icon.sprite = d.icon;

        // Lock state
        bool isLocked = !unlocked && totalStars < d.requiredStars;
        lockOverlay.SetActive(isLocked);
        lockText.text = isLocked ? $"{d.requiredStars}★ required" : "";

        // Stars
        for (int i = 0; i < starImages.Length; i++)
        {
            var img = starImages[i];
            img.gameObject.SetActive(true);
            img.fillAmount = (i < earnedStars) ? 1f : 0f; // if using filled sprite
        }

        button.onClick.RemoveAllListeners();
        button.onClick.AddListener(() => onClick?.Invoke(this));

        // Visual tinting
        var colors = button.colors;
        colors.normalColor = isLocked ? new Color(1, 1, 1, 0.6f) : Color.white;
        colors.highlightedColor = isLocked ? new Color(1, 1, 1, 0.7f) : new Color(1, 1, 1, 0.95f);
        button.colors = colors;

        button.interactable = !isLocked; // optional: allow click to shake even if locked
    }

    public void OnPointerEnter(PointerEventData eventData) { /* hover FX if you want */ }
    public void OnPointerExit(PointerEventData eventData) { }
}
