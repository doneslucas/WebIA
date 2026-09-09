import { useState } from "react";

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


function Chatbot() {
  const [question, setQuestion] = useState("");
  const [messages, setMessages] = useState<Message[]>([]);
  const [loading, setLoading] = useState(false);
  const [openSources, setOpenSources] = useState<number[]>([]);


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

                <div className="loading">
                  <span></span>
                  <span></span>
                  <span></span>
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