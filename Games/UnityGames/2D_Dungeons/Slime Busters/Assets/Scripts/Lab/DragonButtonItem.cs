using UnityEngine;
using UnityEngine.UI;
using TMPro;
using System;

public class DragonButtonItem : MonoBehaviour
{
    public Image iconImage;
    public TMP_Text label;
    public Button button;

    public void Bind(string dragonClass, Sprite icon, Color tint, Action onClick)
    {
        if (label) label.text = dragonClass;
        if (iconImage)
        {
            iconImage.sprite = icon;
            iconImage.color = tint;
            iconImage.enabled = icon != null;
            iconImage.preserveAspect = true;
        }
        button.onClick.RemoveAllListeners();
        button.onClick.AddListener(() => onClick?.Invoke());
    }
}
