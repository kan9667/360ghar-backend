-- Property Management: maintenance requests (work-order fields inline; no vendors)

create table if not exists public.maintenance_requests (
    id bigserial primary key,

    property_id bigint not null references public.properties(id) on delete cascade,
    lease_id bigint references public.leases(id) on delete set null,
    owner_id bigint not null references public.users(id) on delete cascade,
    tenant_user_id bigint references public.users(id) on delete set null,

    category maintenance_category not null,
    urgency maintenance_urgency not null,

    title text not null,
    description text,
    preferred_contact_method text,
    availability_notes text,

    request_status maintenance_request_status not null default 'open',

    assigned_agent_id bigint references public.agents(id) on delete set null,
    work_order_status work_order_status,
    priority text,
    estimated_cost real,
    actual_cost real,
    scheduled_for timestamptz,
    completed_at timestamptz,
    closed_at timestamptz,
    completion_notes text,

    created_at timestamptz default now(),
    updated_at timestamptz
);

create index if not exists idx_maintenance_requests_owner_id on public.maintenance_requests (owner_id);
create index if not exists idx_maintenance_requests_property_id on public.maintenance_requests (property_id);
create index if not exists idx_maintenance_requests_lease_id on public.maintenance_requests (lease_id);
create index if not exists idx_maintenance_requests_tenant_user_id on public.maintenance_requests (tenant_user_id);
create index if not exists idx_maintenance_requests_request_status on public.maintenance_requests (request_status);
create index if not exists idx_maintenance_requests_work_order_status on public.maintenance_requests (work_order_status);
create index if not exists idx_maintenance_requests_created_at on public.maintenance_requests (created_at desc);

-- Link documents.maintenance_request_id -> maintenance_requests.id
do $$ begin
  alter table public.documents
    add constraint fk_documents_maintenance_request_id
    foreign key (maintenance_request_id) references public.maintenance_requests(id) on delete set null;
exception
  when duplicate_object then null;
end $$;

create index if not exists idx_documents_maintenance_request_id on public.documents (maintenance_request_id);

