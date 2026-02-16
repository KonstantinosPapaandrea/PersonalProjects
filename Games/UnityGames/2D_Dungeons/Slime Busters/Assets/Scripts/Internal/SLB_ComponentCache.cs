// Auto-added by cleanup pass
using System;
using System.Collections.Generic;
using UnityEngine;

namespace SlimeBusters.Internal
{
    /// <summary>
    /// Caches GetComponent<T>() lookups in a global dictionary keyed by (instanceId, type).
    /// This avoids repeated GetComponent in hot paths.
    /// </summary>
    public static class SLB_ComponentCache
    {
        static readonly Dictionary<(int, Type), Component> _cache = new(1024);

        public static T Get<T>(Component c) where T : Component
        {
            if (c == null) return null;
            var key = (c.GetInstanceID(), typeof(T));
            if (_cache.TryGetValue(key, out var comp) && comp)
                return (T)comp;

            if (c.TryGetComponent<T>(out var t))
            {
                _cache[key] = t;
                return t;
            }

            // fallback to GetComponent once
            t = c.GetComponent<T>();
            _cache[key] = t;
            return t;
        }
        public static T Get<T>(GameObject go) where T : Component
        {
            if (!go) return null;
            // Reuse Transform (a Component) to keep the cache keyed consistently
            return Get<T>(go.transform);
        }

        // NEW: allow passing a Transform directly
        public static T Get<T>(Transform t) where T : Component
        {
            if (!t) return null;
            return Get<T>((Component)t);
        }
    }
}
