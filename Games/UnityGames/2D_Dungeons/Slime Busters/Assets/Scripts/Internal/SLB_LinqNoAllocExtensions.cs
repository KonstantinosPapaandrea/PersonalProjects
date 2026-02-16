// Auto-added by cleanup pass
using System;
using System.Collections.Generic;

namespace SlimeBusters.Internal
{
    /// <summary>
    /// No-sort "min/max by" helpers that replace OrderBy(...).First() style patterns
    /// with a single pass. Reduces allocations compared to full sorting.
    /// </summary>
    public static class SLB_LinqNoAllocExtensions
    {
        public static T FirstByAscending<T, TKey>(this IEnumerable<T> source, Func<T, TKey> keySelector)
            where TKey : IComparable<TKey>
        {
            if (source == null) throw new ArgumentNullException(nameof(source));
            if (keySelector == null) throw new ArgumentNullException(nameof(keySelector));

            bool hasAny = false;
            T bestItem = default;
            TKey bestKey = default;

            foreach (var item in source)
            {
                var k = keySelector(item);
                if (!hasAny)
                {
                    hasAny = true;
                    bestItem = item;
                    bestKey = k;
                }
                else if (k.CompareTo(bestKey) < 0)
                {
                    bestKey = k;
                    bestItem = item;
                }
            }
            if (!hasAny) throw new InvalidOperationException("Sequence contains no elements");
            return bestItem;
        }

        public static T FirstByDescending<T, TKey>(this IEnumerable<T> source, Func<T, TKey> keySelector)
            where TKey : IComparable<TKey>
        {
            if (source == null) throw new ArgumentNullException(nameof(source));
            if (keySelector == null) throw new ArgumentNullException(nameof(keySelector));

            bool hasAny = false;
            T bestItem = default;
            TKey bestKey = default;

            foreach (var item in source)
            {
                var k = keySelector(item);
                if (!hasAny)
                {
                    hasAny = true;
                    bestItem = item;
                    bestKey = k;
                }
                else if (k.CompareTo(bestKey) > 0)
                {
                    bestKey = k;
                    bestItem = item;
                }
            }
            if (!hasAny) throw new InvalidOperationException("Sequence contains no elements");
            return bestItem;
        }
    }
}
