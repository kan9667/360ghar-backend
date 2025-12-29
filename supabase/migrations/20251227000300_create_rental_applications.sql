-- Property Management: rental applications (forms + submissions)

create table if not exists public.rental_application_forms (
    id bigserial primary key,
    owner_id bigint not null references public.users(id),
    property_id bigint references public.properties(id) on delete set null,

    title text not null,
    description text,
    slug text not null unique,
    is_active boolean default true,

    application_fee_amount real,
    required_document_types jsonb,
    questions jsonb,
    config jsonb,

    created_at timestamptz default now(),
    updated_at timestamptz
);

create index if not exists idx_rental_application_forms_owner_id on public.rental_application_forms (owner_id);
create index if not exists idx_rental_application_forms_property_id on public.rental_application_forms (property_id);

create table if not exists public.rental_applications (
    id bigserial primary key,
    form_id bigint not null references public.rental_application_forms(id) on delete cascade,
    property_id bigint not null references public.properties(id) on delete cascade,
    owner_id bigint not null references public.users(id) on delete cascade,

    status tenant_status default 'applicant',

    applicant_user_id bigint references public.users(id) on delete set null,
    applicant_full_name text,
    applicant_phone text,
    applicant_email text,

    answers jsonb,
    application_data jsonb,
    emergency_contacts jsonb,

    submitted_at timestamptz,
    decision_at timestamptz,
    decided_by_user_id bigint references public.users(id) on delete set null,

    created_at timestamptz default now(),
    updated_at timestamptz
);

create index if not exists idx_rental_applications_owner_id on public.rental_applications (owner_id);
create index if not exists idx_rental_applications_property_id on public.rental_applications (property_id);
create index if not exists idx_rental_applications_form_id on public.rental_applications (form_id);
create index if not exists idx_rental_applications_status on public.rental_applications (status);
create index if not exists idx_rental_applications_submitted_at on public.rental_applications (submitted_at desc);

-- Link documents.rental_application_id -> rental_applications.id (added after dependent table exists)
do $$ begin
  alter table public.documents
    add constraint fk_documents_rental_application_id
    foreign key (rental_application_id) references public.rental_applications(id) on delete set null;
exception
  when duplicate_object then null;
end $$;

create index if not exists idx_documents_rental_application_id on public.documents (rental_application_id);

