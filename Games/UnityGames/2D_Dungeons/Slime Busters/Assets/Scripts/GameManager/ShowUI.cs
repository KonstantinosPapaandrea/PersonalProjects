using UnityEngine;

public class ShowUI : MonoBehaviour
{
    public Transform gridParent;
    public GameObject buttonPrefab;
    public System.Collections.Generic.List<DragonDef> dragons;

    [Header("Panel Root")]
    public GameObject panelRoot;         // keep active
    public CanvasGroup panelGroup;       // assign in Inspector

    void Start() { BuildButtons(); OpenShop(); }

    public void BuildButtons()
    {
        foreach (Transform c in gridParent) Destroy(c.gameObject);
        foreach (var def in dragons)
        {
            var go = Instantiate(buttonPrefab, gridParent);
            var item = go.GetComponent<ShopItemButton>();
            if (item) item.Setup(def);
        }
    }

    public void OpenShop()
    {
        if (!panelRoot) return;
        if (panelGroup)
        {
            panelGroup.alpha = 1f;
            panelGroup.interactable = true;
            panelGroup.blocksRaycasts = true;
        }
        else
        {
            panelRoot.SetActive(true); // fallback
        }
    }

    public void CloseShop()
    {
        if (!panelRoot) return;
        if (panelGroup)
        {
            panelGroup.alpha = 0f;
            panelGroup.interactable = false;
            panelGroup.blocksRaycasts = false;
        }
        else
        {
            // DO NOT SetActive(false) during drag or you'll miss OnEndDrag.
            // If no CanvasGroup, delay until after drag ends.
        }
    }

    public void ToggleShop()
    {
        if (!panelGroup) { return; } // encourage explicit open/close
        if (panelGroup.alpha > 0.5f) CloseShop(); else OpenShop();
    }
}
