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

  if (response.ok) {
    localStorage.setItem(
      "access_token",
      data.access_token
    );
  }

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

// =========================
// CHATBOT
// =========================

export async function chat(question: string) {
  const token = localStorage.getItem(
    "access_token"
  );

  const response = await fetch(
    `${API_URL}/chat`,
    {
      method: "POST",

      headers: {
        "Content-Type": "application/json",
        Authorization: `Bearer ${token}`,
      },

      body: JSON.stringify({
        question,
      }),
    }
  );

  const data = await response.json();

  return {
    response,
    data,
  };
}

export async function uploadDocument(file: File) {
  const token = localStorage.getItem("access_token");

  const formData = new FormData();
  formData.append("file", file);

  const response = await fetch(
    `${API_URL}/documents/upload`,
    {
      method: "POST",
      headers: {
        Authorization: `Bearer ${token}`,
      },
      body: formData,
    }
  );

  const data = await response.json();

  return { response, data };
}