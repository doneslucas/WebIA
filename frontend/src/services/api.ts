
const API_URL = "http://127.0.0.1:8000";


async function refreshAccessToken(): Promise<string | null> {
  const refreshToken = localStorage.getItem("refresh_token");

  if (!refreshToken) {
    return null;
  }

  try {
    const response = await fetch(`${API_URL}/auth/refresh`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify({
        refresh_token: refreshToken,
      }),
    });

    if (!response.ok) {
      localStorage.removeItem("access_token");
      localStorage.removeItem("refresh_token");
      return null;
    }

    const data = await response.json();

    if (!data.access_token) {
      localStorage.removeItem("access_token");
      localStorage.removeItem("refresh_token");
      return null;
    }

    localStorage.setItem("access_token", data.access_token);

    return data.access_token;
  } catch (error) {
    console.error(
      "Erreur lors du renouvellement du token :",
      error,
    );

    return null;
  }
}


async function authenticatedFetch(
  url: string,
  options: RequestInit = {},
  retry = true,
): Promise<Response> {
  const token = localStorage.getItem("access_token");
  const headers = new Headers(options.headers);

  if (token) {
    headers.set("Authorization", `Bearer ${token}`);
  }

  const response = await fetch(url, {
    ...options,
    headers,
  });

  if (response.status !== 401 || !retry) {
    return response;
  }

  const newToken = await refreshAccessToken();

  if (!newToken) {
    return response;
  }

  const retryHeaders = new Headers(options.headers);
  retryHeaders.set("Authorization", `Bearer ${newToken}`);

  return fetch(url, {
    ...options,
    headers: retryHeaders,
  });
}


/**
 * Lit la progression via Server-Sent Events.
 * Le signal permet au composant React d'interrompre le flux.
 */
export async function streamDocumentProgress<T>(
  filename: string,
  onProgress: (progress: T) => void,
  signal: AbortSignal,
): Promise<void> {
  const response = await authenticatedFetch(
    `${API_URL}/documents/${encodeURIComponent(filename)}/progress/stream`,
    {
      method: "GET",
      headers: {
        Accept: "text/event-stream",
      },
      signal,
    },
  );

  if (!response.ok) {
    let message = "Impossible de suivre la progression du document.";

    try {
      const data = await response.json();
      message = data.detail || message;
    } catch {
      // Certaines erreurs ne sont pas renvoyées au format JSON.
    }

    throw new Error(message);
  }

  if (!response.body) {
    throw new Error("Le serveur n'a pas ouvert le flux SSE.");
  }

  const reader = response.body.getReader();
  const decoder = new TextDecoder();

  let buffer = "";
  let streamEnded = false;

  function processEvent(eventBlock: string): boolean {
    let eventName = "message";
    const dataLines: string[] = [];

    for (const line of eventBlock.split(/\r?\n/)) {
      if (line.startsWith(":")) {
        continue;
      }

      if (line.startsWith("event:")) {
        eventName = line.slice(6).trim();
      } else if (line.startsWith("data:")) {
        dataLines.push(line.slice(5).replace(/^ /, ""));
      }
    }

    if (eventName === "end") {
      streamEnded = true;
      return true;
    }

    if (eventName !== "progress" && eventName !== "message") {
      return false;
    }

    if (dataLines.length === 0) {
      return false;
    }

    const progress = JSON.parse(dataLines.join("\n")) as T;
    onProgress(progress);

    return false;
  }

  try {
    while (!streamEnded) {
      const { value, done } = await reader.read();

      if (value) {
        buffer += decoder.decode(value, { stream: !done });
      } else if (done) {
        buffer += decoder.decode();
      }

      const normalizedBuffer = buffer.replace(/\r\n/g, "\n");
      const events = normalizedBuffer.split("\n\n");

      buffer = events.pop() ?? "";

      for (const eventBlock of events) {
        if (processEvent(eventBlock)) {
          break;
        }
      }

      if (done) {
        if (!streamEnded && buffer.trim()) {
          processEvent(buffer);
        }

        break;
      }
    }
  } finally {
    try {
      await reader.cancel();
    } catch {
      // Le flux peut déjà être fermé ou annulé.
    }

    reader.releaseLock();
  }
}


export async function register(email: string, password: string) {
  const response = await fetch(`${API_URL}/auth/register`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify({
      email,
      password,
    }),
  });

  const data = await response.json();

  return { response, data };
}


export async function login(email: string, password: string) {
  const response = await fetch(`${API_URL}/auth/login`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify({
      email,
      password,
    }),
  });

  const data = await response.json();

  if (response.ok) {
    localStorage.setItem("access_token", data.access_token);
    localStorage.setItem("refresh_token", data.refresh_token);
  }

  return { response, data };
}


export async function getProfile() {
  const response = await authenticatedFetch(`${API_URL}/profile`, {
    method: "GET",
  });

  const data = await response.json();

  return { response, data };
}


export async function chat(question: string) {
  const response = await authenticatedFetch(`${API_URL}/chat`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify({ question }),
  });

  const data = await response.json();

  return { response, data };
}


/**
 * Importe un PDF.
 * Le backend réserve cette action aux administrateurs.
 */
export async function uploadDocument(file: File) {
  const formData = new FormData();
  formData.append("file", file);

  const response = await authenticatedFetch(
    `${API_URL}/documents/upload`,
    {
      method: "POST",
      body: formData,
    },
  );

  const data = await response.json();

  return { response, data };
}


/**
 * Récupère la liste des documents accessibles aux utilisateurs connectés.
 */
export async function getDocuments() {
  const response = await authenticatedFetch(`${API_URL}/documents`, {
    method: "GET",
  });

  const data = await response.json();

  return { response, data };
}


/**
 * Récupère le PDF original avec authentification.
 * Le composant peut ensuite l'afficher dans un nouvel onglet
 * à partir d'une URL Blob temporaire.
 *
 * Le backend autorise la consultation aux utilisateurs connectés,
 * sans leur accorder de droits de gestion du document.
 */
export async function getDocumentPdf(filename: string): Promise<Response> {
  return authenticatedFetch(
    `${API_URL}/documents/${encodeURIComponent(filename)}/view`,
    {
      method: "GET",
      headers: {
        Accept: "application/pdf",
      },
    },
  );
}


/**
 * Supprime un PDF.
 * Le backend réserve cette action aux administrateurs.
 */
export async function deleteDocument(filename: string) {
  const response = await authenticatedFetch(
    `${API_URL}/documents/${encodeURIComponent(filename)}`,
    {
      method: "DELETE",
    },
  );

  const data = await response.json();

  return { response, data };
}


/**
 * Lance la génération des questions.
 * Le backend réserve cette action aux administrateurs.
 */
export async function generateDocumentQuestions(filename: string) {
  const response = await authenticatedFetch(
    `${API_URL}/documents/${encodeURIComponent(filename)}/generate-questions`,
    {
      method: "POST",
    },
  );

  const data = await response.json();

  return { response, data };
}


export async function getGenerationProgress(filename: string) {
  const response = await authenticatedFetch(
    `${API_URL}/documents/${encodeURIComponent(filename)}/progress`,
    {
      method: "GET",
    },
  );

  const data = await response.json();

  return { response, data };
}


export async function getProgress() {
  const response = await authenticatedFetch(`${API_URL}/progress`, {
    method: "GET",
  });

  const data = await response.json();

  return { response, data };
}


export async function changePassword(
  currentPassword: string,
  newPassword: string,
) {
  const response = await authenticatedFetch(
    `${API_URL}/profile/password`,
    {
      method: "PUT",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify({
        current_password: currentPassword,
        new_password: newPassword,
      }),
    },
  );

  const data = await response.json();

  return { response, data };
}


// -------------------------------------------------
// Catégories
// -------------------------------------------------

export async function getQuizCategories() {
  const response = await authenticatedFetch(
    `${API_URL}/quiz/categories`,
    {
      method: "GET",
    },
  );

  const data = await response.json();

  return { response, data };
}


// -------------------------------------------------
// Quiz
// -------------------------------------------------

export async function generateQuiz(
  categoryIds: number[],
  questionCount: number,
  difficulty: string,
) {
  const response = await authenticatedFetch(
    `${API_URL}/quiz/generate`,
    {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify({
        category_ids: categoryIds,
        question_count: questionCount,
        difficulty,
      }),
    },
  );

  const data = await response.json();

  return { response, data };
}


export async function generateMixedQuiz(
  categoryIds: number[],
  questionCount: number,
  primaryDifficulty: string,
  secondaryDifficulty: string,
) {
  const response = await authenticatedFetch(
    `${API_URL}/quiz/generate-mixed`,
    {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify({
        category_ids: categoryIds,
        question_count: questionCount,
        primary_difficulty: primaryDifficulty,
        secondary_difficulty: secondaryDifficulty,
      }),
    },
  );

  const data = await response.json();

  return { response, data };
}


export async function getQuizGenerationStatus(
  categoryIds: number[],
  questionCount: number,
  difficulty: string,
) {
  const params = new URLSearchParams();

  params.set("requested_count", String(questionCount));
  params.set("difficulty", difficulty);

  categoryIds.forEach((categoryId) => {
    params.append("category_ids", String(categoryId));
  });

  const response = await authenticatedFetch(
    `${API_URL}/quiz/generation-status?${params.toString()}`,
    {
      method: "GET",
    },
  );

  const data = await response.json();

  return { response, data };
}


export async function checkQuizAnswer(
  questionId: number,
  answer: number,
) {
  const response = await authenticatedFetch(
    `${API_URL}/quiz/answer`,
    {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify({
        question_id: questionId,
        answer,
      }),
    },
  );

  const data = await response.json();

  return { response, data };
}


export async function submitQuiz(
  answers: Array<{
    question_id: number;
    answer: number;
  }>,
) {
  const response = await authenticatedFetch(
    `${API_URL}/quiz/submit`,
    {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify({ answers }),
    },
  );

  const data = await response.json();

  return { response, data };
}
