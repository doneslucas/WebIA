import { useEffect, useState } from "react";

import { chat } from "../services/api";

import "./Chatbot.css";

type Source = {
  file: string;
  page: number | null;
};

type Message = {
  role: "user" | "assistant";
  content: string;
  sources?: Source[];
};

const CHAT_HISTORY_KEY = "webia_chatbot_messages";

const LOADING_STEPS = [
  {
    seconds: 1,
    message:
      "Compréhension de la question et identification des éléments clés",
  },
  {
    seconds: 10,
    message:
      "Recherche des informations pertinentes dans les documents",
  },
  {
    seconds: 20,
    message:
      "Analyse et mise en relation des informations trouvées",
  },
  {
    seconds: 30,
    message:
      "Élaboration d’une réponse claire et concise",
  },
];

function loadMessages(): Message[] {
  try {
    const savedMessages = localStorage.getItem(CHAT_HISTORY_KEY);

    if (!savedMessages) {
      return [];
    }

    const parsed: unknown = JSON.parse(savedMessages);

    if (!Array.isArray(parsed)) {
      return [];
    }

    return parsed.filter(
      (message): message is Message =>
        message !== null &&
        typeof message === "object" &&
        (message.role === "user" ||
          message.role === "assistant") &&
        typeof message.content === "string" &&
        (message.sources === undefined ||
          (Array.isArray(message.sources) &&
            message.sources.every(
              (source: unknown) =>
                source !== null &&
                typeof source === "object" &&
                "file" in source &&
                typeof source.file === "string" &&
                "page" in source &&
                (typeof source.page === "number" ||
                  source.page === null)
            )))
    );
  } catch (error) {
    console.error(
      "Impossible de récupérer la conversation du chatbot :",
      error
    );

    return [];
  }
}

function saveMessages(messages: Message[]) {
  try {
    localStorage.setItem(
      CHAT_HISTORY_KEY,
      JSON.stringify(messages)
    );
  } catch (error) {
    console.error(
      "Impossible de sauvegarder la conversation du chatbot :",
      error
    );
  }
}

function Chatbot() {
  const [question, setQuestion] = useState("");
  const [messages, setMessages] = useState<Message[]>(loadMessages);
  const [loading, setLoading] = useState(false);
  const [openSources, setOpenSources] = useState<number[]>([]);
  const [loadingSeconds, setLoadingSeconds] = useState(0);

  // Synchronise la conversation si elle est modifiée
  // dans un autre onglet, notamment lors d'une déconnexion.
  useEffect(() => {
    function handleStorageChange(event: StorageEvent) {
      if (event.key === CHAT_HISTORY_KEY) {
        setMessages(loadMessages());
        setOpenSources([]);
      }
    }

    window.addEventListener("storage", handleStorageChange);

    return () => {
      window.removeEventListener(
        "storage",
        handleStorageChange
      );
    };
  }, []);

  useEffect(() => {
    if (!loading) {
      setLoadingSeconds(0);
      return;
    }

    const startTime = Date.now();

    setLoadingSeconds(1);

    const intervalId = window.setInterval(() => {
      const elapsedSeconds = Math.floor(
        (Date.now() - startTime) / 1000
      );

      setLoadingSeconds(Math.max(1, elapsedSeconds));
    }, 1000);

    return () => {
      window.clearInterval(intervalId);
    };
  }, [loading]);

  const currentLoadingStep =
    [...LOADING_STEPS]
      .reverse()
      .find((step) => loadingSeconds >= step.seconds) ??
    LOADING_STEPS[0];

  async function sendMessage() {
    if (!question.trim() || loading) {
      return;
    }

    // Empêche une requête sans session authentifiée.
    const tokenAtStart = localStorage.getItem("access_token");

    if (!tokenAtStart) {
      return;
    }

    const userQuestion = question.trim();

    const userMessage: Message = {
      role: "user",
      content: userQuestion,
    };

    const updatedMessages = [
      ...loadMessages(),
      userMessage,
    ];

    setMessages(updatedMessages);
    saveMessages(updatedMessages);

    setQuestion("");
    setLoading(true);

    try {
      const result = await chat(userQuestion);

      // Si le compte a changé ou s'est déconnecté
      // pendant la requête, ne sauvegarde pas sa réponse.
      if (
        localStorage.getItem("access_token") !== tokenAtStart
      ) {
        return;
      }

      if (!result.response.ok) {
        throw new Error("Erreur lors de la requête");
      }

      const assistantMessage: Message = {
        role: "assistant",
        content: result.data.answer,
        sources: result.data.sources,
      };

      const finalMessages = [
        ...loadMessages(),
        assistantMessage,
      ];

      saveMessages(finalMessages);
      setMessages(finalMessages);
    } catch (error) {
      console.error(error);

      // Ne pas réintroduire de messages après une déconnexion.
      if (
        localStorage.getItem("access_token") !== tokenAtStart
      ) {
        return;
      }

      const errorMessage: Message = {
        role: "assistant",
        content:
          "Une erreur est survenue lors de la communication avec le serveur.",
      };

      const finalMessages = [
        ...loadMessages(),
        errorMessage,
      ];

      saveMessages(finalMessages);
      setMessages(finalMessages);
    } finally {
      setLoading(false);
    }
  }

  function toggleSources(index: number) {
    setOpenSources((previous) => {
      if (previous.includes(index)) {
        return previous.filter(
          (sourceIndex) => sourceIndex !== index
        );
      }

      return [...previous, index];
    });
  }

  return (
    <div className="chatbot-page">
      <div className="chatbot-container">
        <header className="chatbot-header">
          <div>
            <h1>Assistant Cyber</h1>

            <p>
              Assistant spécialisé en cybersécurité
            </p>
          </div>
        </header>

        <main className="chatbot-messages">
          {messages.length === 0 && (
            <div className="chatbot-welcome">
              <h2>Bonjour 👋</h2>

              <p>
                Pose une question concernant les documents de
                cybersécurité disponibles dans la base.
              </p>
            </div>
          )}

          {messages.map((message, index) => (
            <div
              key={index}
              className={`message ${
                message.role === "user"
                  ? "message-user"
                  : "message-assistant"
              }`}
            >
              <div className="message-content">
                <div className="message-role">
                  {message.role === "user"
                    ? "Vous"
                    : "Assistant"}
                </div>

                <p>{message.content}</p>

                {message.role === "assistant" &&
                  message.sources &&
                  message.sources.length > 0 && (
                    <div className="sources-container">
                      <button
                        type="button"
                        className="sources-button"
                        onClick={() => toggleSources(index)}
                      >
                        📚 Sources{" "}
                        {openSources.includes(index)
                          ? "▲"
                          : "▼"}
                      </button>

                      {openSources.includes(index) && (
                        <div className="sources">
                          {message.sources.map(
                            (source, sourceIndex) => (
                              <div
                                key={sourceIndex}
                                className="source"
                              >
                                📄{" "}
                                {source.file
                                  .split(/[\\/]/)
                                  .pop()}{" "}
                                — page{" "}
                                {source.page !== null
                                  ? source.page + 1
                                  : "inconnue"}
                              </div>
                            )
                          )}
                        </div>
                      )}
                    </div>
                  )}
              </div>
            </div>
          ))}

          {loading && (
            <div className="message message-assistant">
              <div className="message-content">
                <div className="message-role">
                  Assistant
                </div>

                <div className="loading-status">
                  <p className="loading-status-text">
                    {currentLoadingStep.message}
                  </p>

                  <div className="loading">
                    <span></span>
                    <span></span>
                    <span></span>
                  </div>
                </div>
              </div>
            </div>
          )}
        </main>

        <div className="chatbot-input-container">
          <input
            type="text"
            value={question}
            onChange={(event) =>
              setQuestion(event.target.value)
            }
            onKeyDown={(event) => {
              if (event.key === "Enter") {
                sendMessage();
              }
            }}
            placeholder="Posez votre question..."
            disabled={loading}
          />

          <button
            onClick={sendMessage}
            disabled={loading || !question.trim()}
          >
            Envoyer
          </button>
        </div>
      </div>
    </div>
  );
}

export default Chatbot;