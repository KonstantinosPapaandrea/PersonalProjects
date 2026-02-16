// Auto-added by cleanup pass
using UnityEngine;

namespace SlimeBusters.Internal
{
    public static class SLB_Debug
    {
#if UNITY_EDITOR
        public static void Log(object message) => Debug.Log(message);
        public static void Log(object message, Object context) => Debug.Log(message, context);
        public static void LogWarning(object message) => Debug.LogWarning(message);
        public static void LogWarning(object message, Object context) => Debug.LogWarning(message, context);
#else
        [System.Diagnostics.Conditional("UNITY_EDITOR")]
        public static void Log(object message) { }
        [System.Diagnostics.Conditional("UNITY_EDITOR")]
        public static void Log(object message, Object context) { }
        [System.Diagnostics.Conditional("UNITY_EDITOR")]
        public static void LogWarning(object message) { }
        [System.Diagnostics.Conditional("UNITY_EDITOR")]
        public static void LogWarning(object message, Object context) { }
#endif
        public static void LogError(object message) => Debug.LogError(message);
        public static void LogError(object message, Object context) => Debug.LogError(message, context);
    }
}
