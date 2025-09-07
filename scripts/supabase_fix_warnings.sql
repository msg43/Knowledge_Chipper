-- Supabase Security Advisor fixes
-- - Move `vector` extension out of `public`
-- - Set a fixed search_path for `public.get_subgraph`

-- 1) Ensure a dedicated schema for extensions exists
create schema if not exists extensions;

-- 2) Move the `vector` extension out of `public` if it is there
do $$
begin
  if exists (
    select 1
    from pg_extension e
    join pg_namespace n on n.oid = e.extnamespace
    where e.extname = 'vector' and n.nspname = 'public'
  ) then
    execute 'alter extension vector set schema extensions';
  end if;
end $$;

-- 3) Set a fixed search_path for all overloads of public.get_subgraph
--    This uses the safer default path used by Supabase projects.
do $$
declare
  rec record;
begin
  for rec in
    select n.nspname as schema_name,
           p.proname  as function_name,
           pg_get_function_identity_arguments(p.oid) as args
    from pg_proc p
    join pg_namespace n on n.oid = p.pronamespace
    where n.nspname = 'public' and p.proname = 'get_subgraph'
  loop
    execute format(
      'alter function %I.%I(%s) set search_path to public, extensions',
      rec.schema_name, rec.function_name, rec.args
    );
  end loop;
end $$;

-- Optional: If you want strict isolation, set to an empty search_path instead.
-- Make sure all object references inside the function are schema-qualified.
-- do $$
-- declare
--   rec record;
-- begin
--   for rec in
--     select n.nspname as schema_name,
--            p.proname  as function_name,
--            pg_get_function_identity_arguments(p.oid) as args
--     from pg_proc p
--     join pg_namespace n on n.oid = p.pronamespace
--     where n.nspname = 'public' and p.proname = 'get_subgraph'
--   loop
--     execute format(
--       'alter function %I.%I(%s) set search_path to ''',
--       rec.schema_name, rec.function_name, rec.args
--     );
--   end loop;
-- end $$;

-- Optional: keep extension schema discoverable for consumers
grant usage on schema extensions to public;
