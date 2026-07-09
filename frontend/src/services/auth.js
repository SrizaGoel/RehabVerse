import { supabase } from "../lib/supabase";

// Sign Up
export async function signUp(email, password) {
  return await supabase.auth.signUp({
    email,
    password,
  });
}

// Login
export async function signIn(email, password) {
  return await supabase.auth.signInWithPassword({
    email,
    password,
  });
}

// Logout
export async function signOut() {
  return await supabase.auth.signOut();
}

// Current User
export async function getCurrentUser() {
  const {
    data: { user },
  } = await supabase.auth.getUser();

  return user;
}