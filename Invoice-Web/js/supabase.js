import { createClient } from 'https://cdn.jsdelivr.net/npm/@supabase/supabase-js/+esm';

export const supabase = createClient(
    'https://mqvwyqytkpfqnbaosjwk.supabase.co',
    'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6Im1xdnd5cXl0a3BmcW5iYW9zandrIiwicm9sZSI6ImFub24iLCJpYXQiOjE3NTIxNTE0MTksImV4cCI6MjA2NzcyNzQxOX0.4bk05Jrd-JXhhbojYH0Wb2rvY_7T4CaR-KeXaX6cZmc'
  );
