-- Property Management enums (Postgres types)

do $$ begin
  create type managed_property_status as enum ('draft', 'active', 'archived');
exception
  when duplicate_object then null;
end $$;

do $$ begin
  create type tenant_status as enum ('applicant', 'approved', 'active', 'notice_period', 'vacated', 'rejected');
exception
  when duplicate_object then null;
end $$;

do $$ begin
  create type lease_status as enum ('draft', 'pending_signature', 'active', 'expiring_soon', 'expired', 'terminated', 'renewed');
exception
  when duplicate_object then null;
end $$;

do $$ begin
  create type rent_charge_status as enum ('pending', 'partial', 'paid', 'overdue', 'waived');
exception
  when duplicate_object then null;
end $$;

do $$ begin
  create type expense_category as enum ('maintenance', 'repairs', 'insurance', 'property_tax', 'hoa', 'utilities', 'marketing', 'legal', 'other');
exception
  when duplicate_object then null;
end $$;

do $$ begin
  create type maintenance_urgency as enum ('emergency', 'high', 'medium', 'low');
exception
  when duplicate_object then null;
end $$;

do $$ begin
  create type maintenance_category as enum ('plumbing', 'electrical', 'hvac', 'appliance', 'structural', 'pest_control', 'cleaning', 'other');
exception
  when duplicate_object then null;
end $$;

do $$ begin
  create type maintenance_request_status as enum ('open', 'in_review', 'work_order_created', 'resolved', 'closed');
exception
  when duplicate_object then null;
end $$;

do $$ begin
  create type work_order_status as enum ('created', 'assigned', 'in_progress', 'completed', 'closed', 'cancelled');
exception
  when duplicate_object then null;
end $$;

do $$ begin
  create type document_type as enum ('lease_agreement', 'id_proof', 'address_proof', 'income_proof', 'inspection_report', 'receipt', 'invoice', 'property_deed', 'insurance_policy', 'other');
exception
  when duplicate_object then null;
end $$;

do $$ begin
  create type inspection_type as enum ('move_in', 'move_out', 'routine');
exception
  when duplicate_object then null;
end $$;

do $$ begin
  create type message_thread_type as enum ('lease', 'maintenance', 'general');
exception
  when duplicate_object then null;
end $$;

