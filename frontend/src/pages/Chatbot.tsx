import { useState } from "react";
import { chat } from "../services/api";

type Source = {
  file: string;
  page: number | null;
};

type Message = {
  role: "user" | "assistant";
  content: string;
  sources?: Source[];
};

function Chatbot() {
  const [question, setQuestion] = useState("");
  const [messages, setMessages] = useState<Message[]>([]);
  const [loading, setLoading] = useState(false);

  async function sendMessage() {
    if (!question.trim() || loading) {
      return;
    }

    const userQuestion = question;

    setMessages((previous) => [
      ...previous,
      {
        role: "user",
        content: userQuestion,
      },
    ]);

    setQuestion("");
    setLoading(true);

    try {
      const result = await chat(userQuestion);

      if (!result.response.ok) {
        throw new Error("Erreur lors de la requête");
      }

      setMessages((previous) => [
        ...previous,
        {
          role: "assistant",
          content: result.data.answer,
          sources: result.data.sources,
        },
      ]);
    } catch (error) {
      console.error(error);

      setMessages((previous) => [
        ...previous,
        {
          role: "assistant",
          content:
            "Une erreur est survenue lors de la communication avec le serveur.",
        },
      ]);
    } finally {
      setLoading(false);
    }
  }

  return (
    <div>
      <h1>Assistant Cyber</h1>

      <div>
        {messages.map((message, index) => (
          <div key={index}>
            <strong>
              {message.role === "user" ? "Vous" : "Assistant"}
            </strong>

            <p>{message.content}</p>

            {message.sources && message.sources.length > 0 && (
              <div>
                <strong>Sources :</strong>

                <ul>
                  {message.sources.map((source, sourceIndex) => (
                    <li key={sourceIndex}>
                      {source.file} — page{" "}
                      {source.page !== null
                        ? source.page + 1
                        : "inconnue"}
                    </li>
                  ))}
                </ul>
              </div>
            )}
          </div>
        ))}
      </div>

      {loading && <p>Assistant en train de réfléchir...</p>}

      <div>
        <input
          type="text"
          value={question}
          onChange={(event) => setQuestion(event.target.value)}
          onKeyDown={(event) => {
            if (event.key === "Enter") {
              sendMessage();
            }
          }}
          placeholder="Posez votre question..."
        />

        <button onClick={sendMessage} disabled={loading}>
          Envoyer
        </button>
      </div>
    </div>
  );
}

export default Chatbot;