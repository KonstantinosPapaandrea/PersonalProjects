using UnityEngine;
using UnityEngine.UI;
using UnityEngine.SceneManagement;

[RequireComponent(typeof(Button))]
public class RegionButton : MonoBehaviour
{
    [Tooltip("Exact scene name as in Build Settings")]
    public string sceneName;

    void Awake()
    {
        // auto-wire the Button to load the target scene
        var btn = GetComponent<Button>();
        btn.onClick.RemoveAllListeners();
        btn.onClick.AddListener(LoadTarget);
    }

    public void LoadTarget()
    {
        if (string.IsNullOrEmpty(sceneName))
        {
            Debug.LogWarning($"RegionButton on {name} has no sceneName set.");
            return;
        }
        SceneManager.LoadScene(sceneName, LoadSceneMode.Single);
    }
}
