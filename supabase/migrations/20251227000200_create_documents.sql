-- Property Management: documents table (vault)

create table if not exists public.documents (
    id bigserial primary key,

    -- Portfolio owner / landlord context
    owner_id bigint not null references public.users(id),
    -- Optional subject user for KYC etc.
    user_id bigint references public.users(id) on delete set null,

    property_id bigint references public.properties(id) on delete set null,
    -- Link columns; FKs added after dependent tables exist
    lease_id bigint,
    maintenance_request_id bigint,
    rental_application_id bigint,

    document_type document_type not null,
    title text not null,

    file_url text not null,
    file_path text,
    mime_type text,
    file_size integer,

    shared_with_tenant boolean default false,
    shared_with_agent boolean default false,

    version integer default 1,
    replaces_document_id bigint references public.documents(id) on delete set null,
    created_by_user_id bigint references public.users(id) on delete set null,

    created_at timestamptz default now(),
    updated_at timestamptz
);

create index if not exists idx_documents_owner_id on public.documents (owner_id);
create index if not exists idx_documents_user_id on public.documents (user_id);
create index if not exists idx_documents_property_id on public.documents (property_id);
create index if not exists idx_documents_created_at on public.documents (created_at desc);

