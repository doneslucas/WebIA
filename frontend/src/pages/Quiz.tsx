// frontend/src/pages/Quiz.tsx

import "./Quiz.css";

import {
  useQuiz,
  type QuizQuestion,
} from "../contexts/QuizContext";


function Quiz() {

  const {
    document,
    questionCount,
    difficulty,

    questions,

    quizStarted,
    currentQuestion,

    answers,

    showCorrection,
    finished,

    loading,
    message,

    currentAnswerCorrect,
    currentCorrectAnswer,
    currentExplanation,

    setDocument,
    setQuestionCount,
    setDifficulty,

    startQuiz,

    selectAnswer,
    showQuestionCorrection,
    nextQuestion,

    returnToQuizHome,

    score,
  } = useQuiz();


  function getResultInfo(
    percentage: number
  ) {

    if (percentage === 100) {

      return {
        emoji: "🏆",
        level: "Cyber Master",
        message:
          "PARFAIT ! Aucun piège ne t’a résisté !",
      };

    }


    if (percentage >= 90) {

      return {
        emoji: "🔥",
        level: "Cyber Hunter",
        message:
          "Impressionnant ! Tes réflexes sont affûtés !",
      };

    }


    if (percentage >= 75) {

      return {
        emoji: "😎",
        level: "Expert",
        message:
          "Très bon score, tu maîtrises le sujet !",
      };

    }


    if (percentage >= 60) {

      return {
        emoji: "🛡️",
        level: "Confirmé",
        message:
          "Bonne maîtrise, encore quelques efforts !",
      };

    }


    if (percentage >= 40) {

      return {
        emoji: "🧐",
        level: "Apprenti",
        message:
          "Tu progresses, continue comme ça !",
      };

    }


    if (percentage >= 20) {

      return {
        emoji: "🐣",
        level: "Débutant",
        message:
          "Les bases commencent à rentrer !",
      };

    }


    return {
      emoji: "😵‍💫",
      level: "À revoir",
      message:
        "Oups… il va falloir réviser !",
    };
  }


  if (!quizStarted) {

    return (
      <div className="quiz-page">

        <main className="quiz-container">

          <header className="quiz-header">

            <h1>
              Quiz & Exercices
            </h1>

            <p>
              Testez vos connaissances en
              cybersécurité grâce aux documents
              disponibles.
            </p>

          </header>


          <section className="quiz-modes">

            <div className="quiz-mode-card active">

              <div className="quiz-mode-icon">
                📝
              </div>

              <div>

                <h2>
                  Quiz QCM
                </h2>

                <p>
                  Répondez à une série de questions
                  générées à partir des documents.
                </p>

                <span className="quiz-mode-status">
                  V1 — Disponible
                </span>

              </div>

            </div>


            <div className="quiz-mode-card disabled">

              <div className="quiz-mode-icon">
                🎯
              </div>

              <div>

                <h2>
                  Exercices pratiques
                </h2>

                <p>
                  Analysez des situations concrètes
                  de cybersécurité.
                </p>

                <span className="quiz-mode-status">
                  V2 — À venir
                </span>

              </div>

            </div>


            <div className="quiz-mode-card disabled">

              <div className="quiz-mode-icon">
                🧠
              </div>

              <div>

                <h2>
                  Quiz adaptatif
                </h2>

                <p>
                  La difficulté évoluera selon
                  vos résultats.
                </p>

                <span className="quiz-mode-status">
                  V3 — À venir
                </span>

              </div>

            </div>

          </section>


          <section className="quiz-configuration">

            <div className="quiz-section-header">

              <h2>
                Configuration du quiz
              </h2>

              <p>
                Choisissez les paramètres de votre
                quiz.
              </p>

            </div>


            <div className="quiz-form">

              <div className="quiz-field">

                <label htmlFor="document">
                  Document
                </label>

                <select
                  id="document"
                  value={document}
                  onChange={(event) =>
                    setDocument(
                      event.target.value
                    )
                  }
                  disabled={loading}
                >

                  <option value="all">
                    Tous les documents
                  </option>

                  <option value="Cybermenaces.pdf">
                    Cybermenaces.pdf
                  </option>

                  <option value="Le_Phishing.pdf">
                    Le_Phishing.pdf
                  </option>

                  <option value="test.pdf">
                    test.pdf
                  </option>

                </select>

              </div>


              <div className="quiz-field">

                <label htmlFor="question-count">
                  Nombre de questions
                </label>

                <select
                  id="question-count"
                  value={questionCount}
                  onChange={(event) =>
                    setQuestionCount(
                      event.target.value
                    )
                  }
                  disabled={loading}
                >

                  <option value="5">
                    5 questions
                  </option>

                  <option value="10">
                    10 questions
                  </option>

                  <option value="15">
                    15 questions
                  </option>

                  <option value="20">
                    20 questions
                  </option>

                </select>

              </div>


              <div className="quiz-field">

                <label htmlFor="difficulty">
                  Difficulté
                </label>

                <select
                  id="difficulty"
                  value={difficulty}
                  onChange={(event) =>
                    setDifficulty(
                      event.target.value
                    )
                  }
                  disabled={loading}
                >

                  <option value="easy">
                    Facile
                  </option>

                  <option value="medium">
                    Intermédiaire
                  </option>

                  <option value="hard">
                    Difficile
                  </option>

                </select>

              </div>

            </div>


            <div className="quiz-information">

              <span>
                💡
              </span>

              <p>
                Les questions sont générées par
                l'intelligence artificielle à partir
                des documents de cybersécurité.
              </p>

            </div>


            {message && (
              <p className="quiz-message">
                {message}
              </p>
            )}


            <button
              type="button"
              className="quiz-start-button"
              onClick={startQuiz}
              disabled={loading}
            >

              {loading
                ? "Génération du quiz..."
                : "Générer le quiz"}

            </button>

          </section>

        </main>

      </div>
    );
  }


  if (finished) {

    const percentage =
      questions.length > 0
        ? Math.round(
            (score / questions.length) *
              100
          )
        : 0;


    const resultInfo =
      getResultInfo(percentage);


    return (
      <div className="quiz-page">

        <main className="quiz-container">

          <section className="quiz-result-card">

            <div className="quiz-result-icon">
              {resultInfo.emoji}
            </div>


            <h1>
              {resultInfo.level}
            </h1>


            <p className="quiz-result-score">
              {score} / {questions.length}
            </p>


            <p className="quiz-result-percentage">
              {percentage}%
            </p>


            <p className="quiz-result-message">
              {resultInfo.message}
            </p>


            <div className="quiz-result-actions">

              <button
                type="button"
                className="quiz-start-button"
                onClick={
                  returnToQuizHome
                }
              >
                Retour aux Quiz & Exercices
              </button>

            </div>

          </section>

        </main>

      </div>
    );
  }


  if (questions.length === 0) {

    return (
      <div className="quiz-page">

        <main className="quiz-container">

          <section className="quiz-configuration">

            <p className="quiz-message">
              Aucune question n'a été générée.
            </p>


            <button
              type="button"
              className="quiz-start-button"
              onClick={
                returnToQuizHome
              }
            >
              Retour aux Quiz & Exercices
            </button>

          </section>

        </main>

      </div>
    );
  }


  const current: QuizQuestion =
    questions[currentQuestion];


  const selectedAnswer =
    answers[currentQuestion];


  return (
    <div className="quiz-page">

      <main className="quiz-container">

        <header className="quiz-header">

          <h1>
            Quiz & Exercices
          </h1>

          <p>
            Question{" "}
            {currentQuestion + 1}{" "}
            sur{" "}
            {questions.length}
          </p>

        </header>


        <div className="quiz-progress">

          <div
            className="quiz-progress-bar"
            style={{
              width: `${
                (
                  (currentQuestion + 1) /
                  questions.length
                ) * 100
              }%`,
            }}
          />

        </div>


        <section className="quiz-question-card">

          <div className="quiz-question-number">
            Question{" "}
            {currentQuestion + 1}
          </div>


          <h2>
            {current.question}
          </h2>


          <div className="quiz-options">

            {current.options.map(
              (
                option,
                index
              ) => (

                <button
                  type="button"
                  key={option}
                  className={
                    selectedAnswer ===
                    index
                      ? "quiz-option selected"
                      : "quiz-option"
                  }
                  onClick={() =>
                    selectAnswer(index)
                  }
                  disabled={showCorrection}
                >

                  <span className="quiz-option-letter">
                    {String.fromCharCode(
                      65 + index
                    )}
                  </span>

                  <span>
                    {option}
                  </span>

                </button>

              )
            )}

          </div>


          {showCorrection && (

            <div className="quiz-correction">

              <h3>
                {currentAnswerCorrect
                  ? "🟢 Bonne réponse !"
                  : "🔴 Mauvaise réponse"}
              </h3>


              {!currentAnswerCorrect &&
                currentCorrectAnswer !== null && (

                  <p>

                    <strong>
                      La bonne réponse était :
                    </strong>{" "}

                    {
                      current.options[
                        currentCorrectAnswer
                      ]
                    }

                  </p>

                )}


              {currentExplanation && (

                <p>
                  {currentExplanation}
                </p>

              )}

            </div>

          )}


          {message && (

            <p className="quiz-message">
              {message}
            </p>

          )}


          <div className="quiz-navigation">

            {!showCorrection ? (

              <button
                type="button"
                className="quiz-start-button"
                onClick={
                  showQuestionCorrection
                }
                disabled={loading}
              >
                {loading
                  ? "Vérification..."
                  : "Vérifier ma réponse"}
              </button>

            ) : (

              <button
                type="button"
                className="quiz-start-button"
                onClick={
                  nextQuestion
                }
                disabled={loading}
              >

                {loading
                  ? "Enregistrement..."
                  : currentQuestion ===
                    questions.length - 1
                    ? "Voir mon résultat"
                    : "Question suivante"}

              </button>

            )}

          </div>

        </section>

      </main>

    </div>
  );
}


export default Quiz;