const API_URL = "http://127.0.0.1:8000";


async function refreshAccessToken(): Promise<string | null> {

  const refreshToken =
    localStorage.getItem("refresh_token");

  if (!refreshToken) {
    return null;
  }

  try {

    const response = await fetch(
      `${API_URL}/auth/refresh`,
      {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          refresh_token: refreshToken,
        }),
      }
    );

    if (!response.ok) {

      localStorage.removeItem("access_token");
      localStorage.removeItem("refresh_token");

      return null;
    }

    const data =
      await response.json();

    if (!data.access_token) {

      localStorage.removeItem("access_token");
      localStorage.removeItem("refresh_token");

      return null;
    }

    localStorage.setItem(
      "access_token",
      data.access_token
    );

    return data.access_token;

  } catch (error) {

    console.error(
      "Erreur lors du renouvellement du token :",
      error
    );

    return null;
  }
}


async function authenticatedFetch(
  url: string,
  options: RequestInit = {},
  retry = true
): Promise<Response> {

  const token =
    localStorage.getItem("access_token");

  const headers =
    new Headers(options.headers);

  if (token) {

    headers.set(
      "Authorization",
      `Bearer ${token}`
    );
  }

  const response =
    await fetch(
      url,
      {
        ...options,
        headers,
      }
    );

  if (
    response.status !== 401 ||
    !retry
  ) {

    return response;
  }

  const newToken =
    await refreshAccessToken();

  if (!newToken) {
    return response;
  }

  const retryHeaders =
    new Headers(options.headers);

  retryHeaders.set(
    "Authorization",
    `Bearer ${newToken}`
  );

  return fetch(
    url,
    {
      ...options,
      headers: retryHeaders,
    }
  );
}


export async function register(
  email: string,
  password: string
) {

  const response =
    await fetch(
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

  const data =
    await response.json();

  return {
    response,
    data,
  };
}


export async function login(
  email: string,
  password: string
) {

  const response =
    await fetch(
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

  const data =
    await response.json();

  if (response.ok) {

    localStorage.setItem(
      "access_token",
      data.access_token
    );

    localStorage.setItem(
      "refresh_token",
      data.refresh_token
    );
  }

  return {
    response,
    data,
  };
}


export async function getProfile() {

  const response =
    await authenticatedFetch(
      `${API_URL}/profile`,
      {
        method: "GET",
      }
    );

  const data =
    await response.json();

  return {
    response,
    data,
  };
}


export async function chat(
  question: string
) {

  const response =
    await authenticatedFetch(
      `${API_URL}/chat`,
      {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          question,
        }),
      }
    );

  const data =
    await response.json();

  return {
    response,
    data,
  };
}


export async function uploadDocument(
  file: File
) {

  const formData =
    new FormData();

  formData.append(
    "file",
    file
  );

  const response =
    await authenticatedFetch(
      `${API_URL}/documents/upload`,
      {
        method: "POST",
        body: formData,
      }
    );

  const data =
    await response.json();

  return {
    response,
    data,
  };
}


export async function getDocuments() {

  const response =
    await authenticatedFetch(
      `${API_URL}/documents`,
      {
        method: "GET",
      }
    );

  const data =
    await response.json();

  return {
    response,
    data,
  };
}


export async function deleteDocument(
  filename: string
) {

  const response =
    await authenticatedFetch(
      `${API_URL}/documents/${encodeURIComponent(filename)}`,
      {
        method: "DELETE",
      }
    );

  const data =
    await response.json();

  return {
    response,
    data,
  };
}


export async function getProgress() {

  const response =
    await authenticatedFetch(
      `${API_URL}/progress`,
      {
        method: "GET",
      }
    );

  const data =
    await response.json();

  return {
    response,
    data,
  };
}


export async function changePassword(
  currentPassword: string,
  newPassword: string
) {

  const response =
    await authenticatedFetch(
      `${API_URL}/profile/password`,
      {
        method: "PUT",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          current_password:
            currentPassword,

          new_password:
            newPassword,
        }),
      }
    );

  const data =
    await response.json();

  return {
    response,
    data,
  };
}


export async function generateQuiz(
  document: string,
  questionCount: number,
  difficulty: string
) {

  const response =
    await authenticatedFetch(
      `${API_URL}/quiz/generate`,
      {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          document,
          question_count:
            questionCount,
          difficulty,
        }),
      }
    );

  const data =
    await response.json();

  return {
    response,
    data,
  };
}


export async function checkQuizAnswer(
  questionId: number,
  answer: number
) {

  const response =
    await authenticatedFetch(
      `${API_URL}/quiz/answer`,
      {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          question_id:
            questionId,

          answer,
        }),
      }
    );

  const data =
    await response.json();

  return {
    response,
    data,
  };
}


export async function submitQuiz(
  answers: Array<{
    question_id: number;
    answer: number;
  }>
) {

  const response =
    await authenticatedFetch(
      `${API_URL}/quiz/submit`,
      {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          answers,
        }),
      }
    );

  const data =
    await response.json();

  return {
    response,
    data,
  };
}