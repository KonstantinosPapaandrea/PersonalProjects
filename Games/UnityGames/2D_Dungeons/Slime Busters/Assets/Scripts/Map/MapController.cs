using System.Collections.Generic;
using UnityEngine;
using UnityEngine.SceneManagement;
using UnityEngine.UI;

public class MapController : MonoBehaviour
{
    [Header("Refs")]
    public RectTransform mapRect;         // the Image rect of the map artwork
    public RegionNode nodePrefab;
    public Transform nodesParent;         // under the same Canvas
    public List<RegionData> regions;

    [Header("Transition")]
    public GameObject loadingPanel;       // simple spinner UI

    void Start()
    {
        if (loadingPanel) loadingPanel.SetActive(false);
        SpawnNodes();
    }

    void SpawnNodes()
    {
        var W = mapRect.rect.width;
        var H = mapRect.rect.height;

        foreach (Transform child in nodesParent) Destroy(child.gameObject);

        foreach (var region in regions)
        {
            var node = Instantiate(nodePrefab, nodesParent);
            var rt = node.GetComponent<RectTransform>();
            // bottom-left (0,0) → top-right (W,H)
            Vector2 anchored = new Vector2(region.anchorX * W, region.anchorY * H);
            rt.anchoredPosition = anchored;

            bool unlocked = ProgressService.Instance.IsUnlocked(region.id)
                            || ProgressService.Instance.TotalStars >= region.requiredStars;
            int earned = ProgressService.Instance.GetStars(region.id);
            node.Bind(region, unlocked, earned, ProgressService.Instance.TotalStars, OnNodeClicked);
        }
    }

    void OnNodeClicked(RegionNode node)
    {
        // Optional: simple zoom/pulse here before load
        LoadRegion(node.data.sceneName);
    }

    async void LoadRegion(string sceneName)
    {
        if (loadingPanel) loadingPanel.SetActive(true);
        AsyncOperation op = SceneManager.LoadSceneAsync(sceneName, LoadSceneMode.Single);
        op.allowSceneActivation = true;
        // Optionally await while (op.progress < 0.9f) { await Task.Yield(); }
    }
}
