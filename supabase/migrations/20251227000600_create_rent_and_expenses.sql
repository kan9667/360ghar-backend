-- Property Management: rent ledger + expenses

create table if not exists public.rent_charges (
    id bigserial primary key,

    lease_id bigint not null references public.leases(id) on delete cascade,
    property_id bigint not null references public.properties(id) on delete cascade,
    owner_id bigint not null references public.users(id) on delete cascade,
    tenant_user_id bigint references public.users(id) on delete set null,

    billing_month date not null,
    period_start date not null,
    period_end date not null,
    due_date date not null,

    amount_due real not null,
    late_fee_assessed real default 0,
    status rent_charge_status not null default 'pending',

    created_at timestamptz default now(),
    updated_at timestamptz,

    constraint uq_rent_charges_lease_month unique (lease_id, billing_month)
);

create index if not exists idx_rent_charges_owner_id on public.rent_charges (owner_id);
create index if not exists idx_rent_charges_property_id on public.rent_charges (property_id);
create index if not exists idx_rent_charges_tenant_user_id on public.rent_charges (tenant_user_id);
create index if not exists idx_rent_charges_due_date on public.rent_charges (due_date);
create index if not exists idx_rent_charges_status on public.rent_charges (status);

create table if not exists public.rent_payments (
    id bigserial primary key,

    charge_id bigint not null references public.rent_charges(id) on delete cascade,
    lease_id bigint not null references public.leases(id) on delete cascade,
    property_id bigint not null references public.properties(id) on delete cascade,
    owner_id bigint not null references public.users(id) on delete cascade,
    tenant_user_id bigint references public.users(id) on delete set null,

    paid_at timestamptz not null,
    amount_paid real not null,
    payment_method text,
    reference text,
    notes text,

    receipt_document_id bigint references public.documents(id) on delete set null,

    created_at timestamptz default now(),
    updated_at timestamptz
);

create index if not exists idx_rent_payments_charge_id on public.rent_payments (charge_id);
create index if not exists idx_rent_payments_owner_id on public.rent_payments (owner_id);
create index if not exists idx_rent_payments_property_id on public.rent_payments (property_id);
create index if not exists idx_rent_payments_lease_id on public.rent_payments (lease_id);
create index if not exists idx_rent_payments_paid_at on public.rent_payments (paid_at desc);

create table if not exists public.expenses (
    id bigserial primary key,

    property_id bigint not null references public.properties(id) on delete cascade,
    owner_id bigint not null references public.users(id) on delete cascade,

    category expense_category not null,
    amount real not null,
    expense_date date not null,

    description text,
    notes text,
    receipt_document_id bigint references public.documents(id) on delete set null,

    is_recurring boolean default false,
    recurrence_rule jsonb,
    next_due_date date,

    created_at timestamptz default now(),
    updated_at timestamptz
);

create index if not exists idx_expenses_owner_id on public.expenses (owner_id);
create index if not exists idx_expenses_property_id on public.expenses (property_id);
create index if not exists idx_expenses_expense_date on public.expenses (expense_date desc);
create index if not exists idx_expenses_category on public.expenses (category);

