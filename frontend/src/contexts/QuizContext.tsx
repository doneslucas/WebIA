import {
  createContext,
  useContext,
  useState,
  type ReactNode,
} from "react";

import {
  generateQuiz,
  checkQuizAnswer,
  submitQuiz,
} from "../services/api";


export type QuizQuestion = {
  id: number;
  question: string;
  options: string[];
  difficulty: string;
};


type QuizContextType = {
  document: string;
  questionCount: string;
  difficulty: string;

  questions: QuizQuestion[];

  quizStarted: boolean;
  currentQuestion: number;

  answers: number[];

  showCorrection: boolean;
  finished: boolean;

  loading: boolean;
  message: string;

  currentAnswerCorrect: boolean | null;
  currentCorrectAnswer: number | null;
  currentExplanation: string;

  setDocument: (value: string) => void;
  setQuestionCount: (value: string) => void;
  setDifficulty: (value: string) => void;

  startQuiz: () => Promise<void>;

  selectAnswer: (answerIndex: number) => void;
  showQuestionCorrection: () => Promise<void>;
  nextQuestion: () => Promise<void>;

  returnToQuizHome: () => void;

  score: number;
};


const QuizContext =
  createContext<QuizContextType | undefined>(
    undefined
  );


type QuizProviderProps = {
  children: ReactNode;
};


export function QuizProvider({
  children,
}: QuizProviderProps) {

  const [document, setDocument] =
    useState("all");

  const [questionCount, setQuestionCount] =
    useState("10");

  const [difficulty, setDifficulty] =
    useState("medium");


  const [questions, setQuestions] =
    useState<QuizQuestion[]>([]);


  const [quizStarted, setQuizStarted] =
    useState(false);

  const [currentQuestion, setCurrentQuestion] =
    useState(0);


  const [answers, setAnswers] =
    useState<number[]>([]);


  const [showCorrection, setShowCorrection] =
    useState(false);

  const [finished, setFinished] =
    useState(false);


  const [loading, setLoading] =
    useState(false);

  const [message, setMessage] =
    useState("");


  const [
    currentAnswerCorrect,
    setCurrentAnswerCorrect
  ] = useState<boolean | null>(null);

  const [
    currentCorrectAnswer,
    setCurrentCorrectAnswer
  ] = useState<number | null>(null);

  const [
    currentExplanation,
    setCurrentExplanation
  ] = useState("");


  const [score, setScore] =
    useState(0);


  async function startQuiz() {

    setMessage("");
    setLoading(true);

    try {

      const result = await generateQuiz(
        document,
        Number(questionCount),
        difficulty
      );


      if (!result.response.ok) {

        throw new Error(
          result.data.detail ||
          "Erreur lors de la génération du quiz."
        );
      }


      if (
        !result.data.questions ||
        !Array.isArray(result.data.questions)
      ) {

        throw new Error(
          "Le serveur n'a pas retourné de questions valides."
        );
      }


      const validQuestions =
        result.data.questions.filter(
          (
            question: QuizQuestion
          ) =>
            typeof question.id === "number" &&
            typeof question.question === "string" &&
            Array.isArray(question.options) &&
            question.options.length === 4 &&
            typeof question.difficulty === "string"
        );


      if (
        validQuestions.length !==
        result.data.questions.length
      ) {

        throw new Error(
          "Certaines questions reçues du serveur sont invalides."
        );
      }


      setQuestions(
        validQuestions
      );

      setCurrentQuestion(0);

      setAnswers([]);

      setScore(0);

      setShowCorrection(false);

      setFinished(false);

      setCurrentAnswerCorrect(null);

      setCurrentCorrectAnswer(null);

      setCurrentExplanation("");

      setQuizStarted(true);

    } catch (error) {

      console.error(error);


      if (error instanceof Error) {

        setMessage(
          error.message
        );

      } else {

        setMessage(
          "Une erreur est survenue lors de la génération du quiz."
        );
      }

    } finally {

      setLoading(false);
    }
  }


  function selectAnswer(
    answerIndex: number
  ) {

    if (
      showCorrection ||
      finished
    ) {
      return;
    }


    if (
      answerIndex < 0 ||
      answerIndex > 3
    ) {
      return;
    }


    setAnswers((previous) => {

      const updated = [
        ...previous
      ];

      updated[currentQuestion] =
        answerIndex;

      return updated;
    });


    setMessage("");
  }


  async function showQuestionCorrection() {

    const selectedAnswer =
      answers[currentQuestion];


    if (
      selectedAnswer === undefined
    ) {

      setMessage(
        "Veuillez sélectionner une réponse avant de continuer."
      );

      return;
    }


    const question =
      questions[currentQuestion];


    if (!question) {

      setMessage(
        "Question introuvable."
      );

      return;
    }


    setLoading(true);

    setMessage("");


    try {

      const result =
        await checkQuizAnswer(
          question.id,
          selectedAnswer
        );


      if (!result.response.ok) {

        throw new Error(
          result.data.detail ||
          "Impossible de vérifier la réponse."
        );
      }


      setCurrentAnswerCorrect(
        result.data.is_correct
      );

      setCurrentCorrectAnswer(
        result.data.correct_answer
      );

      setCurrentExplanation(
        result.data.explanation ||
        ""
      );

      setShowCorrection(true);

    } catch (error) {

      console.error(
        "Erreur lors de la vérification de la réponse :",
        error
      );


      if (
        error instanceof Error
      ) {

        setMessage(
          error.message
        );

      } else {

        setMessage(
          "Erreur lors de la vérification de la réponse."
        );
      }

    } finally {

      setLoading(false);
    }
  }


  async function nextQuestion() {

    if (
      currentQuestion ===
      questions.length - 1
    ) {

      setLoading(true);

      setMessage("");

      try {

        const formattedAnswers =
          questions.map(
            (
              question,
              index
            ) => {

              const answer =
                answers[index];

              if (
                answer === undefined
              ) {
                throw new Error(
                  "Toutes les questions doivent avoir une réponse."
                );
              }

              return {
                question_id:
                  question.id,
                answer,
              };
            }
          );


        const result =
          await submitQuiz(
            formattedAnswers
          );


        if (!result.response.ok) {

          throw new Error(
            result.data.detail ||
            "Impossible d'enregistrer le quiz."
          );
        }


        if (
          typeof result.data.score !==
          "number"
        ) {

          throw new Error(
            "Le serveur n'a pas retourné de score valide."
          );
        }


        setScore(
          result.data.score
        );

        setFinished(true);

        setShowCorrection(false);

        setMessage("");

      } catch (error) {

        console.error(
          "Erreur lors de l'enregistrement du quiz :",
          error
        );


        if (
          error instanceof Error
        ) {

          setMessage(
            error.message
          );

        } else {

          setMessage(
            "Erreur lors de l'enregistrement du quiz."
          );
        }

      } finally {

        setLoading(false);
      }

      return;
    }


    setCurrentQuestion(
      (previous) =>
        previous + 1
    );

    setShowCorrection(false);

    setCurrentAnswerCorrect(null);

    setCurrentCorrectAnswer(null);

    setCurrentExplanation("");

    setMessage("");
  }


  function returnToQuizHome() {

    setQuizStarted(false);

    setCurrentQuestion(0);

    setAnswers([]);

    setScore(0);

    setShowCorrection(false);

    setFinished(false);

    setQuestions([]);

    setCurrentAnswerCorrect(null);

    setCurrentCorrectAnswer(null);

    setCurrentExplanation("");

    setMessage("");
  }


  return (
    <QuizContext.Provider
      value={{
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
      }}
    >
      {children}
    </QuizContext.Provider>
  );
}


export function useQuiz() {

  const context =
    useContext(
      QuizContext
    );


  if (!context) {

    throw new Error(
      "useQuiz doit être utilisé à l'intérieur de QuizProvider."
    );
  }


  return context;
}