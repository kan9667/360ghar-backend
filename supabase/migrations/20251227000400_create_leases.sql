-- Property Management: leases

create table if not exists public.leases (
    id bigserial primary key,

    property_id bigint not null references public.properties(id) on delete cascade,
    owner_id bigint not null references public.users(id) on delete cascade,

    tenant_user_id bigint references public.users(id) on delete set null,
    tenant_name text,
    tenant_phone text,
    tenant_email text,

    status lease_status not null default 'draft',

    start_date date not null,
    end_date date not null,

    monthly_rent real not null,
    security_deposit real not null,

    late_fee_amount real,
    late_fee_percentage real,
    grace_period_days integer default 5,
    payment_due_day integer default 1,

    lease_terms jsonb,
    special_clauses text,

    signed_by_tenant_at timestamptz,
    signed_by_owner_at timestamptz,

    lease_document_id bigint references public.documents(id) on delete set null,

    created_at timestamptz default now(),
    updated_at timestamptz
);

create index if not exists idx_leases_owner_id on public.leases (owner_id);
create index if not exists idx_leases_property_id on public.leases (property_id);
create index if not exists idx_leases_tenant_user_id on public.leases (tenant_user_id);
create index if not exists idx_leases_status on public.leases (status);
create index if not exists idx_leases_end_date on public.leases (end_date);

-- At most one active lease per property
create unique index if not exists uq_leases_property_active
  on public.leases (property_id)
  where status = 'active';

-- Link documents.lease_id -> leases.id
do $$ begin
  alter table public.documents
    add constraint fk_documents_lease_id
    foreign key (lease_id) references public.leases(id) on delete set null;
exception
  when duplicate_object then null;
end $$;

create index if not exists idx_documents_lease_id on public.documents (lease_id);

