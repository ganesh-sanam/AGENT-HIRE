-- =====================================================================
-- AgentHire AI — Supabase Database & Storage Schema
-- =====================================================================

-- 1. Create sessions table for workflow state persistence
CREATE TABLE IF NOT EXISTS public.sessions (
    session_id TEXT PRIMARY KEY,
    status TEXT NOT NULL,
    state_json JSONB NOT NULL,
    score INTEGER DEFAULT 0,
    initial_score INTEGER DEFAULT 0,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT timezone('utc'::text, now()) NOT NULL,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT timezone('utc'::text, now()) NOT NULL
);

-- Enable Row Level Security (RLS)
ALTER TABLE public.sessions ENABLE ROW LEVEL SECURITY;

-- Allow backend service role full access
CREATE POLICY "Service role full access on sessions"
    ON public.sessions
    FOR ALL
    TO service_role
    USING (true)
    WITH CHECK (true);

-- 2. Create Storage Buckets for private resumes and generated PDFs
-- Note: Run these or create via Supabase Studio > Storage
INSERT INTO storage.buckets (id, name, public)
VALUES 
    ('resumes-private', 'resumes-private', false),
    ('resumes-generated', 'resumes-generated', false)
ON CONFLICT (id) DO NOTHING;

-- Storage RLS: Restrict access to authenticated backend
CREATE POLICY "Service role access on resumes storage"
    ON storage.objects
    FOR ALL
    TO service_role
    USING (bucket_id IN ('resumes-private', 'resumes-generated'))
    WITH CHECK (bucket_id IN ('resumes-private', 'resumes-generated'));
