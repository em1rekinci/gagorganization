-- BRA Quiz - Supabase Tabloları
-- Supabase Dashboard > SQL Editor'da çalıştır

-- Katılımcılar tablosu
CREATE TABLE IF NOT EXISTS participants (
  id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
  email TEXT UNIQUE NOT NULL,
  name TEXT NOT NULL,
  started_at TIMESTAMPTZ DEFAULT NOW()
);

-- Sonuçlar tablosu
CREATE TABLE IF NOT EXISTS results (
  id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
  email TEXT UNIQUE NOT NULL,
  name TEXT NOT NULL,
  score INTEGER NOT NULL DEFAULT 0,
  correct INTEGER NOT NULL DEFAULT 0,
  wrong INTEGER NOT NULL DEFAULT 0,
  submitted_at TIMESTAMPTZ DEFAULT NOW()
);

-- Index (sıralama için)
CREATE INDEX IF NOT EXISTS idx_results_score ON results(score DESC);

-- Row Level Security (RLS) - API key ile erişim için kapat
ALTER TABLE participants DISABLE ROW LEVEL SECURITY;
ALTER TABLE results DISABLE ROW LEVEL SECURITY;
