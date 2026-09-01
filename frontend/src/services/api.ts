const API_URL = "http://127.0.0.1:8000";

// =========================
// INSCRIPTION
// =========================

export async function register(
  email: string,
  password: string
) {
  const response = await fetch(
    `${API_URL}/auth/register`,
    {
      method: "POST",

      headers: {
        "Content-Type": "application/json",
      },

      body: JSON.stringify({
        email,
        password,
      }),
    }
  );

  const data = await response.json();

  return {
    response,
    data,
  };
}

// =========================
// CONNEXION
// =========================

export async function login(
  email: string,
  password: string
) {
  const response = await fetch(
    `${API_URL}/auth/login`,
    {
      method: "POST",

      headers: {
        "Content-Type": "application/json",
      },

      body: JSON.stringify({
        email,
        password,
      }),
    }
  );

  const data = await response.json();

  return {
    response,
    data,
  };
}

// =========================
// PROFIL
// =========================

export async function getProfile() {
  const token = localStorage.getItem(
    "access_token"
  );

  const response = await fetch(
    `${API_URL}/profile`,
    {
      method: "GET",

      headers: {
        Authorization: `Bearer ${token}`,
      },
    }
  );

  const data = await response.json();

  return {
    response,
    data,
  };
}