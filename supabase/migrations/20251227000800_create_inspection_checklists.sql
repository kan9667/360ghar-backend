-- Property Management: inspection checklists (move-in/move-out)

create table if not exists public.inspection_checklists (
    id bigserial primary key,

    property_id bigint not null references public.properties(id) on delete cascade,
    lease_id bigint not null references public.leases(id) on delete cascade,
    owner_id bigint not null references public.users(id) on delete cascade,

    inspection_type inspection_type not null,

    conducted_by_user_id bigint not null references public.users(id) on delete cascade,
    conducted_at timestamptz not null,

    rooms_data jsonb,
    overall_notes text,

    tenant_signature_document_id bigint references public.documents(id) on delete set null,
    owner_signature_document_id bigint references public.documents(id) on delete set null,
    signed_by_tenant_at timestamptz,
    signed_by_owner_at timestamptz,

    created_at timestamptz default now(),
    updated_at timestamptz
);

create index if not exists idx_inspection_checklists_owner_id on public.inspection_checklists (owner_id);
create index if not exists idx_inspection_checklists_property_id on public.inspection_checklists (property_id);
create index if not exists idx_inspection_checklists_lease_id on public.inspection_checklists (lease_id);
create index if not exists idx_inspection_checklists_conducted_at on public.inspection_checklists (conducted_at desc);

