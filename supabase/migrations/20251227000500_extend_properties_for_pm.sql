-- Property Management: extend properties for managed rentals

alter table public.properties
  add column if not exists is_managed boolean default false;

alter table public.properties
  add column if not exists management_status managed_property_status default 'active';

alter table public.properties
  add column if not exists payment_due_day integer default 1;

alter table public.properties
  add column if not exists grace_period_days integer default 5;

alter table public.properties
  add column if not exists late_fee_policy jsonb;

alter table public.properties
  add column if not exists current_lease_id bigint references public.leases(id) on delete set null;

alter table public.properties
  add column if not exists current_tenant_id bigint references public.users(id) on delete set null;

-- Basic validation constraints
do $$ begin
  alter table public.properties
    add constraint chk_properties_payment_due_day
    check (payment_due_day between 1 and 28);
exception
  when duplicate_object then null;
end $$;

do $$ begin
  alter table public.properties
    add constraint chk_properties_grace_period_days
    check (grace_period_days >= 0);
exception
  when duplicate_object then null;
end $$;

create index if not exists idx_properties_owner_managed on public.properties (owner_id, is_managed);
create index if not exists idx_properties_current_lease_id on public.properties (current_lease_id);
create index if not exists idx_properties_current_tenant_id on public.properties (current_tenant_id);

