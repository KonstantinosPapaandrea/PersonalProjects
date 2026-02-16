using UnityEngine;

public class ShopToggleButton : MonoBehaviour
{
    public static ShopToggleButton Instance { get; private set; }
    public ShowUI shop;

    void Awake()
    {
        if (Instance != null && Instance != this) { Destroy(gameObject); return; }
        Instance = this;
    }

    public void Open() => shop?.OpenShop();
    public void Close() => shop?.CloseShop();
    public void Toggle() => shop?.ToggleShop();
}
