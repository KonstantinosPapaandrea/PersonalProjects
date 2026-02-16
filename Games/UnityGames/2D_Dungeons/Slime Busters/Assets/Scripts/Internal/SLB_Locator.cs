// Auto-added by cleanup pass
using System;
using System.Collections.Generic;
using UnityEngine;

namespace SlimeBusters.Internal
{
    /// <summary>
    /// Lightweight locator that caches results of FindObjectOfType<T>().
    /// Avoids repeated global scans at runtime.
    /// </summary>
    public static class SLB_Locator
    {
        static readonly Dictionary<Type, UnityEngine.Object> _cache = new();

        public static T Get<T>() where T : UnityEngine.Object
        {
            var key = typeof(T);
            if (!_cache.TryGetValue(key, out var obj) || obj == null)
            {
                obj = UnityEngine.Object.FindObjectOfType<T>();
                _cache[key] = obj;
            }
            return obj as T;
        }

        public static void Invalidate<T>() where T : UnityEngine.Object
        {
            _cache.Remove(typeof(T));
        }

        public static void Clear() => _cache.Clear();
    }
}
