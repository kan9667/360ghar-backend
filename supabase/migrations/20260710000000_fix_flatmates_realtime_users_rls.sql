-- ============================================================
-- 360Ghar Schema — Fix Flatmates Realtime Authorization
-- ============================================================
-- Private Broadcast auth previously used a nested EXISTS on
-- public.users. That table has RLS enabled with zero policies,
-- so authenticated clients always saw zero rows and Realtime
-- returned Unauthorized for flatmates:user:{id}.
--
-- Use a SECURITY DEFINER helper that still binds to auth.uid()
-- from the subscriber JWT, without requiring public.users RLS
-- policies (which would open PostgREST surface on users).
-- ============================================================

CREATE OR REPLACE FUNCTION public.can_subscribe_flatmates_user_topic()
RETURNS boolean
LANGUAGE sql
STABLE
SECURITY DEFINER
SET search_path = public
AS $$
  SELECT
    (SELECT realtime.topic()) ~ '^flatmates:user:[0-9]+$'
    AND EXISTS (
      SELECT 1
      FROM public.users u
      WHERE u.id = split_part((SELECT realtime.topic()), ':', 3)::bigint
        AND u.supabase_user_id = (SELECT auth.uid())::text
        AND u.is_active IS TRUE
    );
$$;

REVOKE ALL ON FUNCTION public.can_subscribe_flatmates_user_topic() FROM PUBLIC;
GRANT EXECUTE ON FUNCTION public.can_subscribe_flatmates_user_topic() TO authenticated;

DROP POLICY IF EXISTS "flatmates users receive own broadcasts" ON realtime.messages;

CREATE POLICY "flatmates users receive own broadcasts"
ON realtime.messages
FOR SELECT
TO authenticated
USING (
  public.can_subscribe_flatmates_user_topic()
  AND realtime.messages.extension = 'broadcast'
);
