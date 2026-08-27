-- Drop and recreate user_profiles with correct RLS
DROP TABLE IF EXISTS user_profiles;

CREATE TABLE user_profiles (
  id UUID PRIMARY KEY DEFAULT auth.uid(),
  github_id INTEGER UNIQUE NOT NULL,
  github_username TEXT NOT NULL,
  email TEXT,
  notify_ssl_renewal BOOLEAN DEFAULT TRUE,
  notify_domain_expiry BOOLEAN DEFAULT TRUE,
  notify_updates BOOLEAN DEFAULT TRUE,
  created_at TIMESTAMPTZ DEFAULT NOW(),
  updated_at TIMESTAMPTZ DEFAULT NOW()
);

ALTER TABLE user_profiles ENABLE ROW LEVEL SECURITY;

CREATE POLICY "Users can view own profile" ON user_profiles
  FOR SELECT USING (auth.uid() = id);

CREATE POLICY "Users can insert own profile" ON user_profiles
  FOR INSERT WITH CHECK (auth.uid() = id);

CREATE POLICY "Users can update own profile" ON user_profiles
  FOR UPDATE USING (auth.uid() = id);

CREATE INDEX IF NOT EXISTS idx_user_profiles_github_id ON user_profiles(github_id);
