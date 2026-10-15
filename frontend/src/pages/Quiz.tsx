import "./Quiz.css";

import {
  useEffect,
  useMemo,
  useState,
} from "react";

import {
  useQuiz,
  type QuizQuestion,
} from "../contexts/QuizContext";

import {
  getQuizCategories,
} from "../services/api";


type CategoryQuestionCounts = {
  easy: number;
  medium: number;
  hard: number;
};


type CategoryItem = {
  id: number;
  name: string;
  family: string;
  question_counts: CategoryQuestionCounts;
};


function Quiz() {

  const {
    categoryIds,
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

    generationChoice,
    waitingForGeneration,

    setCategoryIds,
    setQuestionCount,
    setDifficulty,

    startQuiz,

    startWithAvailableQuestions,
    startMixedQuiz,
    waitForQuestions,
    cancelGenerationChoice,

    selectAnswer,
    showQuestionCorrection,
    nextQuestion,

    returnToQuizHome,

    score,

  } = useQuiz();


  const [
    categories,
    setCategories
  ] = useState<CategoryItem[]>([]);


  const [
    categoriesLoading,
    setCategoriesLoading
  ] = useState(true);


  const [
    categoriesError,
    setCategoriesError
  ] = useState("");


  const [
    openFamilies,
    setOpenFamilies
  ] = useState<Set<string>>(
    new Set()
  );


  useEffect(() => {

    async function loadCategories() {

      setCategoriesLoading(true);
      setCategoriesError("");

      try {

        const result =
          await getQuizCategories();

        if (!result.response.ok) {

          throw new Error(
            result.data.detail ||
            "Impossible de récupérer les catégories."
          );
        }

        if (
          !result.data.categories ||
          !Array.isArray(
            result.data.categories
          )
        ) {

          throw new Error(
            "Le serveur n'a pas retourné une liste de catégories valide."
          );
        }

        const validCategories: CategoryItem[] =
          result.data.categories.filter(
            (item: CategoryItem) =>
              typeof item.id === "number" &&
              typeof item.name === "string" &&
              typeof item.family === "string" &&
              item.question_counts &&
              typeof item.question_counts.easy === "number" &&
              typeof item.question_counts.medium === "number" &&
              typeof item.question_counts.hard === "number"
          );

        if (
          validCategories.length === 0
        ) {

          throw new Error(
            "Aucune catégorie valide n'a été retournée."
          );
        }

        setCategories(
          validCategories
        );

        setOpenFamilies(
          new Set(
            validCategories.map(
              (category) =>
                category.family
            )
          )
        );

      } catch (error) {

        console.error(
          "Erreur lors du chargement des catégories :",
          error
        );

        if (
          error instanceof Error
        ) {

          setCategoriesError(
            error.message
          );

        } else {

          setCategoriesError(
            "Impossible de charger les catégories."
          );
        }

      } finally {

        setCategoriesLoading(false);
      }
    }


    loadCategories();

  }, []);


  const categoriesByFamily =
    useMemo(() => {

      const grouped =
        new Map<string, CategoryItem[]>();

      categories.forEach(
        (category) => {

          const existing =
            grouped.get(
              category.family
            ) || [];

          existing.push(
            category
          );

          grouped.set(
            category.family,
            existing
          );
        }
      );

      return Array.from(
        grouped.entries()
      );

    }, [categories]);


  function toggleCategory(
    categoryId: number
  ) {

    setCategoryIds(
      categoryIds.includes(categoryId)
        ? categoryIds.filter(
            (id) =>
              id !== categoryId
          )
        : [
            ...categoryIds,
            categoryId
          ]
    );
  }


  function selectAllCategories() {

    setCategoryIds(
      categories.map(
        (category) =>
          category.id
      )
    );
  }


  function clearCategories() {

    setCategoryIds([]);
  }


  function toggleFamily(
    family: string
  ) {

    setOpenFamilies(
      (previous) => {

        const next =
          new Set(previous);

        if (
          next.has(family)
        ) {

          next.delete(family);

        } else {

          next.add(family);
        }

        return next;
      }
    );
  }


  function selectFamily(
    familyCategories: CategoryItem[]
  ) {

    const familyIds =
      familyCategories.map(
        (category) =>
          category.id
      );

    setCategoryIds(
      Array.from(
        new Set([
          ...categoryIds,
          ...familyIds
        ])
      )
    );
  }


  function clearFamily(
    familyCategories: CategoryItem[]
  ) {

    const familyIds =
      new Set(
        familyCategories.map(
          (category) =>
            category.id
        )
      );

    setCategoryIds(
      categoryIds.filter(
        (id) =>
          !familyIds.has(id)
      )
    );
  }


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
              cybersécurité grâce aux questions
              disponibles dans la banque.
            </p>

          </header>


          <section className="quiz-configuration">

            <div className="quiz-section-header">

              <h2>
                Configuration du quiz
              </h2>

              <p>
                Choisissez les thèmes et les
                paramètres de votre quiz.
              </p>

            </div>


            <div className="quiz-field">

              <label>
                Catégories
              </label>


              <div
                style={{
                  display: "flex",
                  justifyContent: "space-between",
                  alignItems: "center",
                  gap: "12px",
                  flexWrap: "wrap",
                  marginBottom: "15px",
                }}
              >

                <div>

                  <strong>
                    {categoryIds.length}
                  </strong>{" "}
                  / {categories.length} catégorie
                  {categories.length !== 1
                    ? "s"
                    : ""}{" "}
                  sélectionnée
                  {categoryIds.length !== 1
                    ? "s"
                    : ""}

                </div>


                <div
                  style={{
                    display: "flex",
                    gap: "8px",
                    flexWrap: "wrap",
                  }}
                >

                  <button
                    type="button"
                    className="quiz-start-button"
                    onClick={
                      selectAllCategories
                    }
                    disabled={
                      loading ||
                      categoriesLoading ||
                      categories.length === 0 ||
                      categoryIds.length ===
                        categories.length
                    }
                    style={{
                      width: "auto",
                      padding: "9px 14px",
                    }}
                  >
                    Tout sélectionner
                  </button>


                  <button
                    type="button"
                    className="quiz-start-button"
                    onClick={
                      clearCategories
                    }
                    disabled={
                      loading ||
                      categoryIds.length === 0
                    }
                    style={{
                      width: "auto",
                      padding: "9px 14px",
                    }}
                  >
                    Tout désélectionner
                  </button>

                </div>

              </div>


              {categoriesLoading && (

                <p className="quiz-message">
                  Chargement des catégories...
                </p>

              )}


              {categoriesError && (

                <p className="quiz-message">
                  {categoriesError}
                </p>

              )}


              {!categoriesLoading &&
                !categoriesError && (

                <div
                  style={{
                    display: "flex",
                    flexDirection: "column",
                    gap: "10px",
                  }}
                >

                  {categoriesByFamily.map(
                    (
                      [
                        family,
                        familyCategories
                      ]
                    ) => {

                      const selectedCount =
                        familyCategories.filter(
                          (category) =>
                            categoryIds.includes(
                              category.id
                            )
                        ).length;


                      const allSelected =
                        selectedCount ===
                        familyCategories.length;


                      const isOpen =
                        openFamilies.has(
                          family
                        );


                      const familyQuestionCounts =
                        familyCategories.reduce(
                          (totals, category) => ({
                            easy:
                              totals.easy +
                              category.question_counts.easy,

                            medium:
                              totals.medium +
                              category.question_counts.medium,

                            hard:
                              totals.hard +
                              category.question_counts.hard,
                          }),
                          {
                            easy: 0,
                            medium: 0,
                            hard: 0,
                          }
                        );


                      const familyQuestionTarget =
                        familyCategories.length * 50;


                      return (

                        <div
                          key={family}
                          style={{
                            border:
                              "1px solid #ddd",
                            borderRadius:
                              "10px",
                            overflow:
                              "hidden",
                          }}
                        >

                          <div
                            style={{
                              display: "flex",
                              alignItems:
                                "center",
                              justifyContent:
                                "space-between",
                              gap: "12px",
                              padding:
                                "13px 15px",
                              background:
                                "#f7f7f7",
                            }}
                          >

                            <button
                              type="button"
                              onClick={() =>
                                toggleFamily(
                                  family
                                )
                              }
                              disabled={
                                loading
                              }
                              style={{
                                flex: 1,
                                border: "none",
                                background:
                                  "transparent",
                                textAlign:
                                  "left",
                                cursor:
                                  loading
                                    ? "default"
                                    : "pointer",
                                fontSize:
                                  "16px",
                                fontWeight:
                                  600,
                                padding: 0,
                              }}
                            >

                              <span
                                style={{
                                  display:
                                    "inline-block",
                                  width:
                                    "22px",
                                }}
                              >
                                {isOpen
                                  ? "▼"
                                  : "▶"}
                              </span>

                              {family}

                              <span
                                style={{
                                  marginLeft:
                                    "10px",
                                  fontSize:
                                    "13px",
                                  fontWeight:
                                    500,
                                  opacity:
                                    0.7,
                                }}
                              >
                                {selectedCount} /{" "}
                                {
                                  familyCategories.length
                                }
                              </span>


                              <div
                                style={{
                                  display:
                                    "flex",
                                  gap:
                                    "10px",
                                  flexWrap:
                                    "wrap",
                                  marginTop:
                                    "5px",
                                  marginLeft:
                                    "22px",
                                  fontSize:
                                    "12px",
                                  fontWeight:
                                    400,
                                  opacity:
                                    0.65,
                                }}
                              >

                                <span>
                                  Facile{" "}
                                  {
                                    familyQuestionCounts.easy
                                  }
                                  /
                                  {
                                    familyQuestionTarget
                                  }
                                </span>


                                <span>
                                  Intermédiaire{" "}
                                  {
                                    familyQuestionCounts.medium
                                  }
                                  /
                                  {
                                    familyQuestionTarget
                                  }
                                </span>


                                <span>
                                  Difficile{" "}
                                  {
                                    familyQuestionCounts.hard
                                  }
                                  /
                                  {
                                    familyQuestionTarget
                                  }
                                </span>

                              </div>

                            </button>


                            <div
                              style={{
                                display:
                                  "flex",
                                gap:
                                  "6px",
                              }}
                            >

                              <button
                                type="button"
                                onClick={() =>
                                  selectFamily(
                                    familyCategories
                                  )
                                }
                                disabled={
                                  loading ||
                                  allSelected
                                }
                                style={{
                                  border:
                                    "1px solid #ccc",
                                  borderRadius:
                                    "6px",
                                  background:
                                    "white",
                                  padding:
                                    "5px 9px",
                                  cursor:
                                    "pointer",
                                  fontSize:
                                    "12px",
                                }}
                              >
                                Tout
                              </button>


                              <button
                                type="button"
                                onClick={() =>
                                  clearFamily(
                                    familyCategories
                                  )
                                }
                                disabled={
                                  loading ||
                                  selectedCount ===
                                    0
                                }
                                style={{
                                  border:
                                    "1px solid #ccc",
                                  borderRadius:
                                    "6px",
                                  background:
                                    "white",
                                  padding:
                                    "5px 9px",
                                  cursor:
                                    "pointer",
                                  fontSize:
                                    "12px",
                                }}
                              >
                                Aucun
                              </button>

                            </div>

                          </div>


                          {isOpen && (

                            <div
                              style={{
                                display:
                                  "grid",
                                gridTemplateColumns:
                                  "repeat(auto-fit, minmax(260px, 1fr))",
                                gap: "8px",
                                padding:
                                  "12px",
                              }}
                            >

                              {familyCategories.map(
                                (category) => {

                                  const selected =
                                    categoryIds.includes(
                                      category.id
                                    );


                                  return (

                                    <label
                                      key={
                                        category.id
                                      }
                                      style={{
                                        display:
                                          "flex",
                                        alignItems:
                                          "flex-start",
                                        gap:
                                          "10px",
                                        cursor:
                                          loading
                                            ? "default"
                                            : "pointer",
                                        padding:
                                          "10px 11px",
                                        borderRadius:
                                          "7px",
                                        border:
                                          selected
                                            ? "2px solid #333"
                                            : "1px solid #ddd",
                                        background:
                                          selected
                                            ? "#f2f2f2"
                                            : "white",
                                        opacity:
                                          loading
                                            ? 0.7
                                            : 1,
                                      }}
                                    >

                                      <input
                                        type="checkbox"
                                        checked={
                                          selected
                                        }
                                        onChange={() =>
                                          toggleCategory(
                                            category.id
                                          )
                                        }
                                        disabled={
                                          loading
                                        }
                                        style={{
                                          marginTop:
                                            "3px",
                                        }}
                                      />


                                      <span
                                        style={{
                                          display:
                                            "flex",
                                          flexDirection:
                                            "column",
                                          gap:
                                            "3px",
                                          minWidth:
                                            0,
                                        }}
                                      >

                                        <span>
                                          {
                                            category.name
                                          }
                                        </span>


                                        <span
                                          style={{
                                            display:
                                              "flex",
                                            gap:
                                              "8px",
                                            flexWrap:
                                              "wrap",
                                            fontSize:
                                              "12px",
                                            opacity:
                                              0.65,
                                            fontWeight:
                                              400,
                                          }}
                                        >

                                          <span>
                                            Facile{" "}
                                            {
                                              category
                                                .question_counts
                                                .easy
                                            }
                                            /50
                                          </span>


                                          <span>
                                            Intermédiaire{" "}
                                            {
                                              category
                                                .question_counts
                                                .medium
                                            }
                                            /50
                                          </span>


                                          <span>
                                            Difficile{" "}
                                            {
                                              category
                                                .question_counts
                                                .hard
                                            }
                                            /50
                                          </span>

                                        </span>

                                      </span>

                                    </label>

                                  );
                                }
                              )}

                            </div>

                          )}

                        </div>

                      );

                    }
                  )}

                </div>

              )}

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


            <div className="quiz-information">

              <span>
                💡
              </span>

              <p>
                Les questions sont sélectionnées
                aléatoirement dans la banque selon
                les catégories et la difficulté
                choisies.
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
              disabled={
                loading ||
                categoriesLoading ||
                categoryIds.length === 0
              }
            >

              {loading
                ? "Préparation du quiz..."
                : "Générer le quiz"}

            </button>

          </section>


          {generationChoice && (

            <section
              className="quiz-configuration"
              style={{
                marginTop: "20px",
              }}
            >

              <div className="quiz-section-header">

                <h2>
                  Pas assez de questions disponibles
                </h2>

                <p>
                  Tu demandes{" "}
                  <strong>
                    {generationChoice.requested_count}
                  </strong>{" "}
                  questions en difficulté{" "}
                  <strong>
                    {generationChoice.difficulty}
                  </strong>
                  , mais seulement{" "}
                  <strong>
                    {generationChoice.available_count}
                  </strong>{" "}
                  questions sont actuellement
                  disponibles dans les catégories
                  sélectionnées.
                </p>

              </div>


              <div
                style={{
                  display: "flex",
                  flexDirection: "column",
                  gap: "12px",
                }}
              >

                {generationChoice.options.available.enabled && (

                  <button
                    type="button"
                    className="quiz-start-button"
                    onClick={
                      startWithAvailableQuestions
                    }
                    disabled={
                      loading ||
                      waitingForGeneration
                    }
                  >

                    ▶️ Jouer maintenant avec{" "}
                    {
                      generationChoice.options
                        .available.question_count
                    }{" "}
                    questions

                  </button>

                )}


                {generationChoice.options.mixed.enabled && (

                  <>

                    <p
                      style={{
                        marginBottom: "0",
                        marginTop: "8px",
                      }}
                    >

                      <strong>
                        Compléter avec une autre difficulté :
                      </strong>

                    </p>


                    {generationChoice.options.mixed.difficulties.map(
                      (option) => (

                        <button
                          type="button"
                          key={
                            option.difficulty
                          }
                          className="quiz-start-button"
                          onClick={() =>
                            startMixedQuiz(
                              option.difficulty
                            )
                          }
                          disabled={
                            loading ||
                            waitingForGeneration
                          }
                        >

                          🔀 Compléter avec{" "}
                          {option.difficulty}{" "}
                          (
                          {option.questions_needed}{" "}
                          questions)

                        </button>

                      )
                    )}

                  </>

                )}


                {generationChoice.options.wait.enabled && (

                  <button
                    type="button"
                    className="quiz-start-button"
                    onClick={
                      waitForQuestions
                    }
                    disabled={
                      loading ||
                      waitingForGeneration
                    }
                  >

                    {waitingForGeneration
                      ? "⏳ Génération en cours..."
                      : `⏳ Attendre la génération des ${generationChoice.missing_count} questions restantes`}

                  </button>

                )}


                <button
                  type="button"
                  className="quiz-start-button"
                  onClick={
                    cancelGenerationChoice
                  }
                  disabled={
                    loading
                  }
                >

                  Annuler

                </button>

              </div>


              {waitingForGeneration && (

                <p
                  className="quiz-message"
                  style={{
                    marginTop: "15px",
                  }}
                >

                  {message ||
                    "La banque de questions est en cours de génération. Cette page vérifie régulièrement la progression."}

                </p>

              )}

            </section>

          )}

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